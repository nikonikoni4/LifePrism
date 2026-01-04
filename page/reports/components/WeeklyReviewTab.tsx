/**
 * Weekly Review Tab Component
 * 
 * 每周总结 Tab 组件
 */

import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { CalendarDays, RefreshCw } from 'lucide-react';
import TimeOverviewWidget from './TimeOverviewWidget';
import TimeDistributionChart from './TimeDistributionChart';
import GoalProgressCard from './GoalProgressCard';
import TodoStatsCard from './TodoStatsCard';
import AISummaryCard from './AISummaryCard';
import { ReportsAPI } from '../api';
import { WeeklyReportData } from '../types';
import { getMockWeeklyReport } from '../mockData';

interface WeeklyReviewTabProps {
    className?: string;
    /** 点击图表数据点时跳转到日报告的回调 */
    onNavigateToDaily?: (date: string) => void;
}

/** 获取指定日期所在周的起止日期 */
const getWeekRange = (date: Date): { start: string; end: string } => {
    const day = date.getDay();
    const diff = date.getDate() - day + (day === 0 ? -6 : 1); // 调整为周一开始

    const monday = new Date(date);
    monday.setDate(diff);

    const sunday = new Date(monday);
    sunday.setDate(monday.getDate() + 6);

    return {
        start: monday.toISOString().split('T')[0],
        end: sunday.toISOString().split('T')[0]
    };
};

const WeeklyReviewTab: React.FC<WeeklyReviewTabProps> = ({ className = '', onNavigateToDaily }) => {
    // 默认使用本周
    const [weekOffset, setWeekOffset] = useState<number>(0);

    // 数据状态
    const [reportData, setReportData] = useState<WeeklyReportData | null>(null);
    const [loading, setLoading] = useState(false);
    const [refreshing, setRefreshing] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const { start: startDate, end: endDate } = useMemo(() => {
        const today = new Date();
        today.setDate(today.getDate() + weekOffset * 7);
        return getWeekRange(today);
    }, [weekOffset]);

    // 加载报告数据
    const fetchReport = useCallback(async (forceRefresh: boolean = false) => {
        if (forceRefresh) {
            setRefreshing(true);
        } else {
            setLoading(true);
        }
        setError(null);

        try {
            const data = await ReportsAPI.getWeeklyReport(startDate, forceRefresh);
            setReportData(data);
        } catch (err) {
            console.error('获取周报告失败:', err);
            setError(err instanceof Error ? err.message : '获取数据失败');
            // 出错时使用 mock 数据
            setReportData(getMockWeeklyReport(startDate, endDate));
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [startDate, endDate]);

    // 周变化时重新加载
    useEffect(() => {
        fetchReport(false);
    }, [fetchReport]);

    // 强制刷新处理
    const handleForceRefresh = () => {
        fetchReport(true);
    };

    const formatWeekDisplay = (start: string, end: string) => {
        const startDate = new Date(start);
        const endDate = new Date(end);
        const startMonth = startDate.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
        const endMonth = endDate.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
        return `${startMonth} - ${endMonth}`;
    };

    // Loading 状态
    if (loading && !reportData) {
        return (
            <div className={`flex items-center justify-center h-96 ${className}`}>
                <div className="flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
                    <p className="text-slate-500">加载中...</p>
                </div>
            </div>
        );
    }

    // 使用 mock 数据作为后备
    const displayData = reportData || getMockWeeklyReport(startDate, endDate);

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Week Selector & Refresh Button */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-indigo-50 text-indigo-500 rounded-xl">
                        <CalendarDays size={18} />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-800">
                            {formatWeekDisplay(startDate, endDate)}
                        </p>
                        <p className="text-xs text-slate-400">每周总结</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {/* 强制刷新按钮 */}
                    <button
                        onClick={handleForceRefresh}
                        disabled={refreshing}
                        className={`
                            flex items-center gap-2 px-4 py-2 
                            bg-gradient-to-r from-indigo-500 to-purple-500 
                            text-white text-sm font-medium rounded-xl
                            hover:from-indigo-600 hover:to-purple-600
                            focus:ring-2 focus:ring-indigo-300 focus:outline-none
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

                    <button
                        onClick={() => setWeekOffset(prev => prev - 1)}
                        className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors"
                    >
                        上周
                    </button>
                    <button
                        onClick={() => setWeekOffset(0)}
                        disabled={weekOffset === 0}
                        className={`px-3 py-2 rounded-xl text-sm font-medium transition-colors ${weekOffset === 0
                            ? 'bg-indigo-500 text-white'
                            : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'
                            }`}
                    >
                        本周
                    </button>
                    <button
                        onClick={() => setWeekOffset(prev => prev + 1)}
                        disabled={weekOffset >= 0}
                        className={`px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium transition-colors ${weekOffset >= 0 ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100'
                            }`}
                    >
                        下周
                    </button>
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
                    {/* Weekly Trend Line Chart */}
                    <TimeDistributionChart
                        data={displayData.weeklyTrend}
                        categories={displayData.categories}
                        title="周度趋势折线图"
                        subtitle="展示周一至周日各分类的每日时长波动，点击数据点可查看当日详情"
                        height={260}
                        onDataPointClick={onNavigateToDaily}
                    />
                </div>
                <div className="lg:col-span-4 space-y-6">
                    {/* Weekly Todo Stats */}
                    <TodoStatsCard
                        stats={displayData.todoStats}
                        title="任务完成度"
                        subTitle="本周 Todo 整体达成率"
                        className="h-[380px]"
                    />
                </div>

                <div className="lg:col-span-8 space-y-6">
                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={displayData.timeOverview}
                        chartHeight="h-[450px]"
                    />
                </div>

                <div className="lg:col-span-4 space-y-6">
                    {/* Weekly Goal Progress */}
                    <GoalProgressCard
                        goals={displayData.goalProgress}
                        title="本周 Goal 复盘"
                        height="600px"
                    />
                </div>

                <div className="lg:col-span-12 space-y-6">
                    {/* AI Summary */}
                    <AISummaryCard
                        title="AI 规律总结"
                        reportType="weekly"
                        weekStartDate={startDate}
                        weekEndDate={endDate}
                        content={displayData.aiSummary}
                    />
                </div>
            </div>
        </div>
    );
};

export default WeeklyReviewTab;

