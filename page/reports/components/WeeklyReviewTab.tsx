/**
 * Weekly Review Tab Component
 * 
 * 每周总结 Tab 组件
 */

import React, { useState, useMemo } from 'react';
import { CalendarDays, TrendingUp } from 'lucide-react';
import TimeOverviewWidget from '../../common/TimeOverviewWidget';
import TimeDistributionChart from './TimeDistributionChart';
import GoalProgressCard from './GoalProgressCard';
import AISummaryCard from './AISummaryCard';
import { getMockWeeklyReport } from '../mockData';

interface WeeklyReviewTabProps {
    className?: string;
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

const WeeklyReviewTab: React.FC<WeeklyReviewTabProps> = ({ className = '' }) => {
    // 默认使用本周
    const [weekOffset, setWeekOffset] = useState<number>(0);

    const { startDate, endDate } = useMemo(() => {
        const today = new Date();
        today.setDate(today.getDate() + weekOffset * 7);
        return getWeekRange(today);
    }, [weekOffset]);

    // 获取 Mock 数据
    const reportData = useMemo(() => {
        return getMockWeeklyReport(startDate, endDate);
    }, [startDate, endDate]);

    const formatWeekDisplay = (start: string, end: string) => {
        const startDate = new Date(start);
        const endDate = new Date(end);
        const startMonth = startDate.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
        const endMonth = endDate.toLocaleDateString('zh-CN', { month: 'long', day: 'numeric' });
        return `${startMonth} - ${endMonth}`;
    };

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Week Selector */}
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
                                ? 'bg-blue-500 text-white'
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

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column - Charts */}
                <div className="lg:col-span-8 space-y-6">
                    {/* Weekly Trend Line Chart */}
                    <TimeDistributionChart
                        data={reportData.weeklyTrend}
                        categories={reportData.categories}
                        title="周度趋势折线图"
                        subtitle="展示周一至周日各分类的每日时长波动"
                        height={280}
                    />

                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={reportData.timeOverview}
                        chartHeight="h-[350px]"
                    />
                </div>

                {/* Right Column - Stats & AI */}
                <div className="lg:col-span-4 space-y-6">
                    {/* Weekly Goal Progress */}
                    <GoalProgressCard
                        goals={reportData.goalProgress}
                        title="本周 Goal 复盘"
                    />

                    {/* Task Completion Rate */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-emerald-50 text-emerald-500 rounded-xl">
                                <TrendingUp size={18} />
                            </div>
                            <h3 className="text-base font-bold text-slate-800">任务完成度</h3>
                        </div>

                        <div className="text-center py-4">
                            <div className="inline-flex items-baseline gap-1">
                                <span className="text-5xl font-bold font-mono text-emerald-500">
                                    {reportData.taskCompletionRate.toFixed(1)}
                                </span>
                                <span className="text-2xl font-bold text-slate-400">%</span>
                            </div>
                            <p className="text-sm text-slate-400 mt-2">本周 Todo 整体达成率</p>
                        </div>

                        {/* Progress Bar */}
                        <div className="h-3 bg-gray-100 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full transition-all duration-700"
                                style={{ width: `${reportData.taskCompletionRate}%` }}
                            />
                        </div>
                    </div>

                    {/* AI Summary */}
                    <AISummaryCard
                        title="AI 规律总结"
                        content={reportData.aiSummary}
                    />
                </div>
            </div>
        </div>
    );
};

export default WeeklyReviewTab;
