/**
 * Goal Progress Card Component
 * 
 * 目标进度卡片组件
 */

import React, { useState } from 'react';
import { Target, ChevronDown, ChevronUp, Clock, CheckCircle2, Circle } from 'lucide-react';
import { GoalProgressData } from '../types';

interface GoalProgressCardProps {
    goals: GoalProgressData[];
    title?: string;
    className?: string;
}

const GoalProgressCard: React.FC<GoalProgressCardProps> = ({
    goals,
    title = 'Goal 进度',
    className = ''
}) => {
    const [expandedGoal, setExpandedGoal] = useState<string | null>(null);

    const formatTime = (minutes: number) => {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        if (hours > 0) {
            return `${hours}h ${mins}m`;
        }
        return `${mins}m`;
    };

    const getProgressColor = (completed: number, total: number) => {
        const rate = total > 0 ? completed / total : 0;
        if (rate >= 0.8) return 'bg-emerald-500';
        if (rate >= 0.5) return 'bg-amber-500';
        return 'bg-slate-300';
    };

    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 ${className}`}>
            {/* Header */}
            <div className="flex items-center gap-3 mb-4">
                <div className="p-2 bg-blue-50 text-blue-500 rounded-xl">
                    <Target size={18} />
                </div>
                <h3 className="text-base font-bold text-slate-800">{title}</h3>
            </div>

            {/* Goals List */}
            <div className="space-y-4">
                {goals.map((goal) => {
                    const isExpanded = expandedGoal === goal.goalId;
                    const progressRate = goal.todoTotal > 0
                        ? Math.round((goal.todoCompleted / goal.todoTotal) * 100)
                        : 0;

                    return (
                        <div
                            key={goal.goalId}
                            className="border border-gray-100 rounded-xl overflow-hidden"
                        >
                            {/* Goal Header */}
                            <button
                                onClick={() => setExpandedGoal(isExpanded ? null : goal.goalId)}
                                className="w-full p-4 flex items-center gap-3 hover:bg-gray-50 transition-colors"
                            >
                                {/* Color Indicator */}
                                <div
                                    className="w-3 h-3 rounded-full flex-shrink-0"
                                    style={{ backgroundColor: goal.goalColor }}
                                />

                                {/* Goal Info */}
                                <div className="flex-1 text-left">
                                    <div className="flex items-center justify-between mb-1">
                                        <span className="font-medium text-slate-800 text-sm">
                                            {goal.goalName}
                                        </span>
                                        <span className="text-xs text-slate-400 font-mono">
                                            {progressRate}%
                                        </span>
                                    </div>

                                    {/* Progress Bar */}
                                    <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full rounded-full transition-all duration-500 ${getProgressColor(goal.todoCompleted, goal.todoTotal)}`}
                                            style={{ width: `${progressRate}%` }}
                                        />
                                    </div>
                                </div>

                                {/* Expand Icon */}
                                {isExpanded ? (
                                    <ChevronUp size={16} className="text-slate-400" />
                                ) : (
                                    <ChevronDown size={16} className="text-slate-400" />
                                )}
                            </button>

                            {/* Expanded Content */}
                            {isExpanded && (
                                <div className="px-4 pb-4 border-t border-gray-50 bg-gray-50/50">
                                    {/* Stats */}
                                    <div className="flex gap-4 py-3 border-b border-gray-100">
                                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                            <Clock size={12} />
                                            <span>投入 {formatTime(goal.timeInvested)}</span>
                                        </div>
                                        <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                            <CheckCircle2 size={12} className="text-emerald-500" />
                                            <span>{goal.todoCompleted}/{goal.todoTotal} 完成</span>
                                        </div>
                                    </div>

                                    {/* Todo List */}
                                    <div className="mt-3 space-y-2 max-h-48 overflow-y-auto">
                                        {goal.todoList.map((todo) => (
                                            <div
                                                key={todo.id}
                                                className="flex items-center gap-2 text-xs"
                                            >
                                                {todo.completed ? (
                                                    <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" />
                                                ) : (
                                                    <Circle size={14} className="text-slate-300 flex-shrink-0" />
                                                )}
                                                <span className={`${todo.completed ? 'text-slate-400 line-through' : 'text-slate-600'}`}>
                                                    {todo.content}
                                                </span>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
};

export default GoalProgressCard;
