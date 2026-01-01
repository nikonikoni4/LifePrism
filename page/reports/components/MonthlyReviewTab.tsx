/**
 * Monthly Review Tab Component
 * 
 * 每月总结 Tab 组件
 */

import React, { useState, useMemo } from 'react';
import { CalendarRange, ArrowRight, AlertCircle } from 'lucide-react';
import TimeOverviewWidget from '../../common/TimeOverviewWidget';
import CalendarHeatmap from './CalendarHeatmap';
import GoalProgressCard from './GoalProgressCard';
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
                <div className="lg:col-span-8 space-y-6">
                    {/* Calendar Heatmap */}
                    <CalendarHeatmap
                        data={reportData.heatmapData}
                        categories={reportData.categories}
                        month={selectedMonth}
                        title="月度活跃热力图"
                    />

                    {/* Sunburst Chart */}
                    <TimeOverviewWidget
                        data={reportData.timeOverview}
                        chartHeight="h-[350px]"
                    />
                </div>

                {/* Right Column - Stats & AI */}
                <div className="lg:col-span-4 space-y-6">
                    {/* Monthly Goal Investment */}
                    <GoalProgressCard
                        goals={reportData.goalProgress}
                        title="月度 Goal 投入"
                    />

                    {/* Monthly Todo Tracking */}
                    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
                        <div className="flex items-center gap-3 mb-4">
                            <div className="p-2 bg-amber-50 text-amber-500 rounded-xl">
                                <CalendarRange size={18} />
                            </div>
                            <h3 className="text-base font-bold text-slate-800">月度 Todo 追踪</h3>
                        </div>

                        {/* Completion Stats */}
                        <div className="grid grid-cols-2 gap-3 mb-4">
                            <div className="p-3 bg-emerald-50 rounded-xl text-center">
                                <p className="text-2xl font-bold font-mono text-emerald-600">
                                    {reportData.todoTracking.completionRate.toFixed(1)}%
                                </p>
                                <p className="text-[10px] text-slate-500 font-medium uppercase mt-1">
                                    完成率
                                </p>
                            </div>
                            <div className="p-3 bg-gray-50 rounded-xl text-center">
                                <p className="text-2xl font-bold font-mono text-slate-700">
                                    {reportData.todoTracking.totalCompleted}
                                </p>
                                <p className="text-[10px] text-slate-500 font-medium uppercase mt-1">
                                    已完成
                                </p>
                            </div>
                        </div>

                        {/* Carry Over Items */}
                        {reportData.todoTracking.carryOverItems.length > 0 && (
                            <div className="border-t border-gray-100 pt-4">
                                <div className="flex items-center gap-2 mb-3">
                                    <AlertCircle size={14} className="text-amber-500" />
                                    <span className="text-xs font-bold text-slate-600 uppercase">
                                        需滚动至下月 ({reportData.todoTracking.carryOverItems.length})
                                    </span>
                                </div>
                                <div className="space-y-2">
                                    {reportData.todoTracking.carryOverItems.map((item, index) => (
                                        <div
                                            key={item.id}
                                            className="flex items-center gap-2 p-2 bg-amber-50 rounded-lg"
                                        >
                                            <ArrowRight size={12} className="text-amber-500 flex-shrink-0" />
                                            <div className="flex-1 min-w-0">
                                                <p className="text-xs text-slate-700 truncate">
                                                    {item.content}
                                                </p>
                                                {item.goalName && (
                                                    <p className="text-[10px] text-slate-400 truncate">
                                                        关联: {item.goalName}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>

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
