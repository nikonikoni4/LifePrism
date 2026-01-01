/**
 * Todo Stats Card Component
 * 
 * Todo 统计卡片组件
 */

import React from 'react';
import { CheckSquare, Square, ListTodo } from 'lucide-react';
import { TodoStatsData } from '../types';

interface TodoStatsCardProps {
    stats: TodoStatsData;
    title?: string;
    className?: string;
}

const TodoStatsCard: React.FC<TodoStatsCardProps> = ({
    stats,
    title = 'Todo 统计',
    className = ''
}) => {
    const completionRate = stats.total > 0
        ? Math.round((stats.completed / stats.total) * 100)
        : 0;

    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-amber-50 text-amber-500 rounded-xl">
                    <ListTodo size={18} />
                </div>
                <h3 className="text-base font-bold text-slate-800">{title}</h3>
            </div>

            {/* Progress Ring */}
            <div className="flex items-center justify-center mb-6">
                <div className="relative w-28 h-28">
                    {/* Background Ring */}
                    <svg className="w-full h-full -rotate-90">
                        <circle
                            cx="56"
                            cy="56"
                            r="48"
                            strokeWidth="10"
                            stroke="#f1f5f9"
                            fill="none"
                        />
                        <circle
                            cx="56"
                            cy="56"
                            r="48"
                            strokeWidth="10"
                            stroke="#10b981"
                            fill="none"
                            strokeLinecap="round"
                            strokeDasharray={`${completionRate * 3.02} 302`}
                            className="transition-all duration-700"
                        />
                    </svg>

                    {/* Center Text */}
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold text-slate-800 font-mono">
                            {completionRate}%
                        </span>
                        <span className="text-[10px] text-slate-400 font-medium uppercase">
                            完成率
                        </span>
                    </div>
                </div>
            </div>

            {/* Stats Grid */}
            <div className="grid grid-cols-3 gap-3">
                <div className="text-center p-3 bg-gray-50 rounded-xl">
                    <div className="flex items-center justify-center gap-1 mb-1">
                        <ListTodo size={12} className="text-slate-400" />
                    </div>
                    <p className="text-xl font-bold font-mono text-slate-800">{stats.total}</p>
                    <p className="text-[10px] text-slate-400 font-medium uppercase">总计</p>
                </div>

                <div className="text-center p-3 bg-emerald-50 rounded-xl">
                    <div className="flex items-center justify-center gap-1 mb-1">
                        <CheckSquare size={12} className="text-emerald-500" />
                    </div>
                    <p className="text-xl font-bold font-mono text-emerald-600">{stats.completed}</p>
                    <p className="text-[10px] text-slate-400 font-medium uppercase">已完成</p>
                </div>

                <div className="text-center p-3 bg-orange-50 rounded-xl">
                    <div className="flex items-center justify-center gap-1 mb-1">
                        <Square size={12} className="text-orange-500" />
                    </div>
                    <p className="text-xl font-bold font-mono text-orange-600">{stats.pending}</p>
                    <p className="text-[10px] text-slate-400 font-medium uppercase">待完成</p>
                </div>
            </div>
        </div>
    );
};

export default TodoStatsCard;
