/**
 * Todo Stats Card Component
 * 
 * Todo 统计卡片组件 - 统一展示任务完成情况
 */

import React from 'react';
import { TrendingUp, CheckSquare, ListTodo, Square, Clock, AlertTriangle } from 'lucide-react';
import { TodoStatsData } from '../types';

interface TodoStatsCardProps {
    stats: TodoStatsData;
    title?: string;
    subTitle?: string;
    className?: string;
}

const TodoStatsCard: React.FC<TodoStatsCardProps> = ({
    stats,
    title = '任务完成度',
    subTitle = 'Todo 整体达成率',
    className = ''
}) => {
    const completionRate = stats.total > 0
        ? ((stats.completed / stats.total) * 100).toFixed(1)
        : '0.0';

    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 flex flex-col ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-6">
                <div className="p-2 bg-emerald-50 text-emerald-500 rounded-xl">
                    <TrendingUp size={18} />
                </div>
                <h3 className="text-base font-bold text-slate-800">{title}</h3>
            </div>

            {/* Center Content Component */}
            <div className="flex-1 flex flex-col justify-center">
                {/* Main Completion Rate */}
                <div className="text-center mb-8">
                    <div className="inline-flex items-baseline gap-1 mb-2">
                        <span className="text-5xl font-bold font-mono text-emerald-500">
                            {completionRate}
                        </span>
                        <span className="text-2xl font-bold text-slate-400">%</span>
                    </div>
                    <p className="text-sm text-slate-400">{subTitle}</p>
                </div>

                {/* Progress Bar */}
                <div className="h-3 bg-gray-100 rounded-full overflow-hidden mb-8">
                    <div
                        className="h-full bg-gradient-to-r from-emerald-400 to-emerald-500 rounded-full transition-all duration-700"
                        style={{ width: `${completionRate}%` }}
                    />
                </div>
            </div>

            {/* 4 Stats Grid */}
            <div className="grid grid-cols-4 gap-2 border-t border-gray-100 pt-6">
                {/* Total */}
                <div className="text-center">
                    <div className="flex justify-center mb-1">
                        <ListTodo size={14} className="text-slate-400/70" />
                    </div>
                    <p className="text-lg font-bold text-slate-700 font-mono leading-tight">
                        {stats.total}
                    </p>
                    <p className="text-[10px] text-slate-400 font-medium scale-90">总计</p>
                </div>

                {/* Completed */}
                <div className="text-center relative after:absolute after:left-0 after:top-2 after:bottom-2 after:w-px after:bg-gray-100 after:content-['']">
                    <div className="flex justify-center mb-1">
                        <CheckSquare size={14} className="text-emerald-500/70" />
                    </div>
                    <p className="text-lg font-bold text-emerald-600 font-mono leading-tight">
                        {stats.completed}
                    </p>
                    <p className="text-[10px] text-slate-400 font-medium scale-90">已完成</p>
                </div>

                {/* Pending */}
                <div className="text-center relative after:absolute after:left-0 after:top-2 after:bottom-2 after:w-px after:bg-gray-100 after:content-['']">
                    <div className="flex justify-center mb-1">
                        <Square size={14} className="text-amber-500/70" />
                    </div>
                    <p className="text-lg font-bold text-amber-600 font-mono leading-tight">
                        {stats.pending}
                    </p>
                    <p className="text-[10px] text-slate-400 font-medium scale-90">待完成</p>
                </div>

                {/* Procrastination Rate */}
                <div className="text-center relative after:absolute after:left-0 after:top-2 after:bottom-2 after:w-px after:bg-gray-100 after:content-['']">
                    <div className="flex justify-center mb-1">
                        <Clock size={14} className="text-rose-500/70" />
                    </div>
                    <p className="text-lg font-bold text-rose-500 font-mono leading-tight">
                        {stats.procrastinationRate}%
                    </p>
                    <p className="text-[10px] text-slate-400 font-medium scale-90">拖延率</p>
                </div>
            </div>
        </div>
    );
};

export default TodoStatsCard;
