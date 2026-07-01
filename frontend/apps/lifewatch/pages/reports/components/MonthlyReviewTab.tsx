/**
 * Monthly Review Tab Component
 * 
 * 每月总结 Tab 组件
 */

import React, { useState, useEffect, useCallback } from 'react';
import { CalendarRange, RefreshCw } from 'lucide-react';
import TimeOverviewWidget from './TimeOverviewWidget';
import CalendarHeatmap from './CalendarHeatmap';
import GoalProgressCard from './GoalProgressCard';
import TodoStatsCard from './TodoStatsCard';
import TimeDistributionChart from './TimeDistributionChart';
import TrendComparisonCard from './TrendComparisonCard';
import { ReportsAPI } from '../api';
import { MonthlyReportData } from '../types';
import { getMockMonthlyReport, getMockComparisonData } from '../mockData';

/** 获取月份的结束日期 */
const getMonthEndDate = (month: string): string => {
    const [year, mon] = month.split('-').map(Number);
    const lastDay = new Date(year, mon, 0).getDate();
    return `${year}-${String(mon).padStart(2, '0')}-${String(lastDay).padStart(2, '0')}`;
};

interface MonthlyReviewTabProps {
    className?: string;
    /** 点击图表数据点时跳转到日报告的回调 */
    onNavigateToDaily?: (date: string) => void;
}

const MonthlyReviewTab: React.FC<MonthlyReviewTabProps> = ({ className = '', onNavigateToDaily }) => {
    // 默认使用本月
    const [selectedMonth, setSelectedMonth] = useState<string>(() => {
        const today = new Date();
        return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
    });

    // 数据状态
    const [reportData, setReportData] = useState<MonthlyReportData | null>(null);
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
            const data = await ReportsAPI.getMonthlyReport(selectedMonth, forceRefresh);
            setReportData(data);
        } catch (err) {
            console.error('获取月报告失败:', err);
            setError(err instanceof Error ? err.message : '获取数据失败');
            // 出错时使用 mock 数据
            setReportData(getMockMonthlyReport(selectedMonth));
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    }, [selectedMonth]);

    // 月份变化时重新加载
    useEffect(() => {
        fetchReport(false);
    }, [fetchReport]);

    // 强制刷新处理
    const handleForceRefresh = () => {
        fetchReport(true);
    };



    const formatMonthDisplay = (month: string) => {
        const [year, mon] = month.split('-');
        return `${year}年${parseInt(mon)}月`;
    };

    const handlePrevMonth = () => {
        const [year, mon] = selectedMonth.split('-').map(Number);
        const prevDate = new Date(year, mon - 2, 1);
        setSelectedMonth(`${prevDate.getFullYear()}-${String(prevDate.getMonth() + 1).padStart(2, '0')}`);
    };

    const handleNextMonth = () => {
        const [year, mon] = selectedMonth.split('-').map(Number);
        const nextDate = new Date(year, mon, 1);
        const now = new Date();
        // 不允许选择未来月份
        if (nextDate <= now) {
            setSelectedMonth(`${nextDate.getFullYear()}-${String(nextDate.getMonth() + 1).padStart(2, '0')}`);
        }
    };

    const handleToCurrentMonth = () => {
        const today = new Date();
        setSelectedMonth(`${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`);
    };

    const isCurrentMonth = () => {
        const today = new Date();
        const currentMonth = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
        return selectedMonth === currentMonth;
    };

    // Loading 状态
    if (loading && !reportData) {
        return (
            <div className={`flex items-center justify-center h-96 ${className}`}>
                <div className="flex flex-col items-center gap-3">
                    <RefreshCw className="w-8 h-8 text-purple-500 animate-spin" />
                    <p className="text-slate-500">加载中...</p>
                </div>
            </div>
        );
    }

    // 使用 mock 数据作为后备
    const displayData = reportData || getMockMonthlyReport(selectedMonth);

    // 使用后端返回的趋势数据（如果没有则从热力图生成 fallback）
    const displayTrendData = displayData.monthlyTrend && displayData.monthlyTrend.length > 0
        ? displayData.monthlyTrend
        : displayData.heatmapData.map(day => ({
            label: day.date.split('-')[2],
            ...(day.categoryBreakdown || {})
        }));

    // 使用后端返回的 comparisonData，如果没有则 fallback 到 mock 数据
    const comparisonData = displayData.comparisonData || (() => {
        // 计算对比日期 (上月)
        const currentStart = `${selectedMonth}-01`;
        const currentEnd = getMonthEndDate(selectedMonth);

        const [currYear, currMonth] = selectedMonth.split('-').map(Number);
        const prevDate = new Date(currYear, currMonth - 2, 1);
        const prevYear = prevDate.getFullYear();
        const prevMonthVal = prevDate.getMonth() + 1;
        const prevMonthStr = `${prevYear}-${String(prevMonthVal).padStart(2, '0')}`;
        const prevStart = `${prevMonthStr}-01`;
        const prevEnd = getMonthEndDate(prevMonthStr);

        return getMockComparisonData(currentStart, currentEnd, prevStart, prevEnd);
    })();

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Month Selector & Refresh Button */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-50 text-purple-500 rounded-xl">
                        <CalendarRange size={18} />
                    </div>
                    <div>
                        <p className="text-sm font-bold text-slate-800">
                            {formatMonthDisplay(selectedMonth)}
                        </p>
                        <p className="text-xs text-slate-400">每月总结</p>
                    </div>
                </div>
                <div className="flex items-center gap-2">
                    {/* 强制刷新按钮 */}
                    <button
                        onClick={handleForceRefresh}
                        disabled={refreshing}
                        className={`
                            flex items-center gap-2 px-4 py-2 
                            bg-gradient-to-r from-purple-500 to-pink-500 
                            text-white text-sm font-medium rounded-xl
                            hover:from-purple-600 hover:to-pink-600
                            focus:ring-2 focus:ring-purple-300 focus:outline-none
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
                        onClick={handlePrevMonth}
                        className="px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium hover:bg-gray-100 transition-colors"
                    >
                        上月
                    </button>
                    <button
                        onClick={handleToCurrentMonth}
                        disabled={isCurrentMonth()}
                        className={`px-3 py-2 rounded-xl text-sm font-medium transition-colors ${isCurrentMonth()
                            ? 'bg-purple-500 text-white'
                            : 'bg-gray-50 border border-gray-200 hover:bg-gray-100'
                            }`}
                    >
                        本月
                    </button>
                    <button
                        onClick={handleNextMonth}
                        disabled={isCurrentMonth()}
                        className={`px-3 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium transition-colors ${isCurrentMonth() ? 'opacity-50 cursor-not-allowed' : 'hover:bg-gray-100'
                            }`}
                    >
                        下月
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

                {/* Monthly Trend Chart */}
                <div className="lg:col-span-12">
                    <TimeDistributionChart
                        data={displayTrendData}
                        categories={displayData.categories}
                        title="月度时间分布趋势"
                        subtitle="点击数据点可查看当日详情"
                        height={300}
                        onDataPointClick={onNavigateToDaily}
                    />
                </div>

                {/* Left Column - Charts */}
                <div className="lg:col-span-8">
                    {/* Calendar Heatmap */}
                    <CalendarHeatmap
                        data={displayData.heatmapData}
                        categories={displayData.categories}
                        month={selectedMonth}
                        title="月度活跃热力图"
                        className="h-full"
                    />
                </div>

                <div className="lg:col-span-4">
                    {/* Monthly Todo Stats */}
                    <TodoStatsCard
                        stats={displayData.todoStats}
                        title="月度 Todo 追踪"
                        subTitle="本月任务整体达成率"
                        className="h-full"
                    />
                </div>
                {/* 环比对比组件 (新增) */}
                <div className="lg:col-span-12">
                    <TrendComparisonCard
                        data={comparisonData}
                        title="本月环比趋势"
                    />
                </div>
                <div className="lg:col-span-8">
                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={displayData.timeOverview}
                        chartHeight="h-[500px]"
                        className="h-[600px]"
                    />
                </div>



                <div className="lg:col-span-4">
                    {/* Monthly Goal Investment */}
                    <GoalProgressCard
                        goals={displayData.goalProgress}
                        title="月度 Goal 投入"
                        height="h-[600px]"
                    />
                </div>

                {/* TODO: 月报 AI 总结已废弃，仅日报支持 AI 总结（每天 10:00 自动更新） */}
            </div>
        </div>
    );
};

export default MonthlyReviewTab;
