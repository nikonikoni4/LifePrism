/**
 * Daily Review Tab Component
 * 
 * 每日总结 Tab 组件
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Calendar, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react';
import TimeOverviewWidget from './TimeOverviewWidget';
import TimeDistributionChart from './TimeDistributionChart';
import GoalProgressCard from './GoalProgressCard';
import TodoStatsCard from './TodoStatsCard';
import AISummaryCard from './AISummaryCard';
import TrendComparisonCard from './TrendComparisonCard';
import { ReportsAPI } from '../api';
import { DailyReportData } from '../types';
import { getMockDailyReport, getMockComparisonData } from '../mockData';

interface DailyReviewTabProps {
    className?: string;
    /** 从外部导航传入的初始日期 (YYYY-MM-DD) */
    initialDate?: string;
    /** 当 initialDate 被使用后的回调 */
    onDateUsed?: () => void;
}

const DailyReviewTab: React.FC<DailyReviewTabProps> = ({
    className = '',
    initialDate,
    onDateUsed
}) => {
    // 默认使用今天的日期，如果有外部传入的日期则使用它
    const [selectedDate, setSelectedDate] = useState<string>(() => {
        if (initialDate) {
            return initialDate;
        }
        const today = new Date();
        return today.toISOString().split('T')[0];
    });

    // 当 initialDate 变化时更新日期并通知父组件
    React.useEffect(() => {
        if (initialDate && initialDate !== selectedDate) {
            setSelectedDate(initialDate);
            onDateUsed?.();
        }
    }, [initialDate, selectedDate, onDateUsed]);

    // 数据状态
    const [reportData, setReportData] = useState<DailyReportData | null>(null);
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 加载报告数据
    const fetchReport = useCallback(async (forceRefresh: boolean = false) => {
        if (forceRefresh) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }
        setError(null);

        try {
            const data = await ReportsAPI.getDailyReport(selectedDate, forceRefresh);
            setReportData(data);
        } catch (err) {
            console.error('获取日报告失败:', err);
            setError(err instanceof Error ? err.message : '获取数据失败');
            // 出错时使用 mock 数据
            setReportData(getMockDailyReport(selectedDate));
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [selectedDate]);

    // 日期变化时重新加载
    useEffect(() => {
        fetchReport(false);
    }, [fetchReport]);

    // 强制刷新处理
    const handleForceRefresh = () => {
        fetchReport(true);
    };

    const formatDisplayDate = (dateStr: string) => {
        const date = new Date(dateStr);
        const options: Intl.DateTimeFormatOptions = {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            weekday: 'long'
        };
        return date.toLocaleDateString('zh-CN', options);
    };

    // Loading 状态
    if (loading && !reportData) {
        return (
            <div className={`flex items-center justify-center h-96 ${className}`}>
                <div className="flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 text-blue-500 animate-spin" />
                    <p className="text-slate-500">加载中...</p>
                </div>
            </div>
        );
    }

    // 使用 mock 数据作为后备
    const displayData = reportData || getMockDailyReport(selectedDate);

    // 使用后端返回的 comparisonData，如果没有则 fallback 到 mock 数据
    const comparisonData = displayData.comparisonData || (() => {
        // 计算对比日期 (昨天)
        const prevDate = new Date(selectedDate);
        prevDate.setDate(prevDate.getDate() - 1);
        const prevDateStr = prevDate.toISOString().split('T')[0];
        return getMockComparisonData(selectedDate, selectedDate, prevDateStr, prevDateStr);
    })();

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Date Selector & Refresh Button */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-50 text-blue-500 rounded-xl">
                        <Calendar size={18} />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-800">
                            {formatDisplayDate(selectedDate)}
                        </p>
                        <p className="text-xs text-slate-400">每日总结</p>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    {/* 强制刷新按钮 */}
                    <button
                        onClick={handleForceRefresh}
                        disabled={refreshing}
                        className={`
                            flex items-center gap-2 px-4 py-2 
                            bg-gradient-to-r from-blue-500 to-indigo-500 
                            text-white text-sm font-medium rounded-xl
                            hover:from-blue-600 hover:to-indigo-600
                            focus:ring-2 focus:ring-blue-300 focus:outline-none
                            disabled:opacity-60 disabled:cursor-not-allowed
                            transition-all duration-200
                            shadow-sm hover:shadow-md
                        `}
                    >
                        <RefreshCw
                            size={16}
                            className={refreshing ? 'animate-spin' : ''}
                        />
                        {refreshing ? '刷新中...' : '重新计算'}
                    </button>

                    {/* 日期选择区域 */}
                    <div className="flex items-center bg-gray-50 border border-gray-200 rounded-xl p-1">
                        <button
                            onClick={() => {
                                const date = new Date(selectedDate);
                                date.setDate(date.getDate() - 1);
                                setSelectedDate(date.toISOString().split('T')[0]);
                            }}
                            className="p-2 hover:bg-white hover:shadow-sm rounded-lg text-slate-500 hover:text-blue-500 transition-all focus:outline-none focus:ring-2 focus:ring-blue-100"
                            title="前一天"
                        >
                            <ChevronLeft size={18} />
                        </button>

                        <input
                            type="date"
                            value={selectedDate}
                            onChange={(e) => setSelectedDate(e.target.value)}
                            className="px-2 py-1 bg-transparent border-none text-sm font-medium focus:ring-0 cursor-pointer text-slate-700 outline-none h-full"
                        />

                        <button
                            onClick={() => {
                                const date = new Date(selectedDate);
                                date.setDate(date.getDate() + 1);
                                setSelectedDate(date.toISOString().split('T')[0]);
                            }}
                            className="p-2 hover:bg-white hover:shadow-sm rounded-lg text-slate-500 hover:text-blue-500 transition-all focus:outline-none focus:ring-2 focus:ring-blue-100"
                            title="后一天"
                        >
                            <ChevronRight size={18} />
                        </button>
                    </div>
                </div>
            </div>

            {/* Error Message */}
            {error && (
                <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-center gap-3">
                    <div className="text-amber-500">⚠️</div>
                    <div>
                        <p className="text-sm font-medium text-amber-800">数据加载失败</p>
                        <p className="text-xs text-amber-600">{error}（已使用演示数据）</p>
                    </div>
                </div>
            )}

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">


                {/* Left Column - Charts */}
                <div className="lg:col-span-8 space-y-6">
                    {/* Time Distribution Line Chart */}
                    <TimeDistributionChart
                        data={displayData.timeDistribution}
                        categories={displayData.categories}
                        title="时间分布堆积图"
                        subtitle="展示 0~24h 内不同类别的分段使用趋势"
                        height={260}
                    />
                </div>
                <div className="lg:col-span-4 space-y-6">
                    {/* Todo Stats */}
                    <TodoStatsCard
                        stats={displayData.todoStats}
                        title="Todo 统计"
                        className="h-[380px]"
                    />
                </div>
                {/* 环比对比组件 (新增) */}
                <div className="lg:col-span-12">
                    <TrendComparisonCard
                        data={comparisonData}
                        title="今日环比趋势"
                    />
                </div>
                <div className="lg:col-span-8 space-y-6">
                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={displayData.timeOverview}
                        chartHeight="h-[450px]"
                    />
                </div>
                {/* Right Column - Stats & AI */}
                <div className="lg:col-span-4 space-y-6">
                    {/* Goal Progress */}
                    <GoalProgressCard
                        goals={displayData.goalProgress}
                        title="Goal 进度跟踪"
                        height="600px"
                    />
                </div>

                <div className="lg:col-span-12 space-y-6">
                    {/* AI Summary */}
                    <AISummaryCard
                        title="AI 总结"
                        reportType="daily"
                        date={selectedDate}
                        content={displayData.aiSummary}
                    />
                </div>
            </div>
        </div>
    );
};

export default DailyReviewTab;
