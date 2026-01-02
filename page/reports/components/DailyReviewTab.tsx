/**
 * Daily Review Tab Component
 * 
 * 每日总结 Tab 组件
 */

import React, { useState, useMemo } from 'react';
import { Calendar } from 'lucide-react';
import TimeOverviewWidget from './TimeOverviewWidget';
import TimeDistributionChart from './TimeDistributionChart';
import GoalProgressCard from './GoalProgressCard';
import TodoStatsCard from './TodoStatsCard';
import AISummaryCard from './AISummaryCard';
import { getMockDailyReport } from '../mockData';

interface DailyReviewTabProps {
    className?: string;
}

const DailyReviewTab: React.FC<DailyReviewTabProps> = ({ className = '' }) => {
    // 默认使用今天的日期
    const [selectedDate, setSelectedDate] = useState<string>(() => {
        const today = new Date();
        return today.toISOString().split('T')[0];
    });

    // 获取 Mock 数据
    const reportData = useMemo(() => {
        return getMockDailyReport(selectedDate);
    }, [selectedDate]);

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

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Date Selector */}
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
                <input
                    type="date"
                    value={selectedDate}
                    onChange={(e) => setSelectedDate(e.target.value)}
                    className="px-4 py-2 bg-gray-50 border border-gray-200 rounded-xl text-sm font-medium focus:ring-2 focus:ring-blue-100 focus:outline-none cursor-pointer"
                />
            </div>

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column - Charts */}
                <div className="lg:col-span-8 space-y-6">
                    {/* Time Distribution Line Chart */}
                    <TimeDistributionChart
                        data={reportData.timeDistribution}
                        categories={reportData.categories}
                        title="时间分布折线图"
                        subtitle="展示 0~24h 内不同类别的分段使用趋势"
                        height={260}
                    />
                </div>
                <div className="lg:col-span-4 space-y-6">

                    {/* Todo Stats */}
                    <TodoStatsCard
                        stats={reportData.todoStats}
                        title="Todo 统计"
                        className="h-[380px]"
                    />
                </div>
                <div className="lg:col-span-8 space-y-6">

                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={reportData.timeOverview}
                        chartHeight="h-[450px]"
                    />
                </div>
                {/* Right Column - Stats & AI */}
                <div className="lg:col-span-4 space-y-6">
                    {/* Goal Progress */}
                    <GoalProgressCard
                        goals={reportData.goalProgress}
                        title="Goal 进度跟踪"
                        height="600px"
                    />
                </div>

                <div className="lg:col-span-12 space-y-6">

                    {/* AI Summary */}
                    <AISummaryCard
                        title="AI 智能总结"
                        content={reportData.aiSummary}
                    />
                </div>
            </div>
        </div>
    );
};

export default DailyReviewTab;
