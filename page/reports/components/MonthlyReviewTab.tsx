/**
 * Monthly Review Tab Component
 * 
 * 每月总结 Tab 组件
 */

import React, { useState, useMemo } from 'react';
import { CalendarRange, ArrowRight, AlertCircle } from 'lucide-react';
import TimeOverviewWidget from './TimeOverviewWidget';
import CalendarHeatmap from './CalendarHeatmap';
import GoalProgressCard from './GoalProgressCard';
import TodoStatsCard from './TodoStatsCard';
import AISummaryCard from './AISummaryCard';
import { getMockMonthlyReport } from '../mockData';

interface MonthlyReviewTabProps {
    className?: string;
}

const MonthlyReviewTab: React.FC<MonthlyReviewTabProps> = ({ className = '' }) => {
    // 默认使用本月
    const [selectedMonth, setSelectedMonth] = useState<string>(() => {
        const today = new Date();
        return `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}`;
    });

    // 获取 Mock 数据
    const reportData = useMemo(() => {
        return getMockMonthlyReport(selectedMonth);
    }, [selectedMonth]);

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

    const formatTime = (minutes: number) => {
        const hours = Math.floor(minutes / 60);
        return `${hours}h`;
    };

    return (
        <div className={`space-y-6 ${className}`}>
            {/* Month Selector */}
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

            {/* Main Content Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Left Column - Charts */}
                <div className="lg:col-span-8">
                    {/* Calendar Heatmap */}
                    <CalendarHeatmap
                        data={reportData.heatmapData}
                        categories={reportData.categories}
                        month={selectedMonth}
                        title="月度活跃热力图"
                        className="h-full"
                    />
                </div>

                <div className="lg:col-span-4">
                    {/* Monthly Todo Stats */}
                    <TodoStatsCard
                        stats={reportData.todoStats}
                        title="月度 Todo 追踪"
                        subTitle="本月任务整体达成率"
                        className="h-full"
                    />
                </div>

                <div className="lg:col-span-8">
                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={reportData.timeOverview}
                        chartHeight="h-[500px]"
                        className="h-[600px]"
                    />
                </div>

                <div className="lg:col-span-4">
                    {/* Monthly Goal Investment */}
                    <GoalProgressCard
                        goals={reportData.goalProgress}
                        title="月度 Goal 投入"
                        height="h-[600px]"
                    />
                </div>

                <div className="lg:col-span-12 space-y-6">
                    {/* AI Summary */}
                    <AISummaryCard
                        title="AI 全局总结"
                        content={reportData.aiSummary}
                    />
                </div>
            </div>
        </div>
    );
};

export default MonthlyReviewTab;
