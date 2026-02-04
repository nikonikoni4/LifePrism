/**
 * TodoListWidget - 首页待办事项组件
 * 
 * 只读展示今日一级任务，带跳转按钮至 Goals 页面
 */

import React, { useState, useEffect } from 'react';
import { Check, ChevronRight, Target, Loader2 } from 'lucide-react';
import { TodoItem } from '../../../../../apps/goals/types/todo';
import { taskPoolApi } from '../../../../../apps/goals/apis/taskPool';

interface TodoListWidgetProps {
    selectedDate: string;
    todolist?: any[];  // 从首页 API 传入的数据（暂未使用）
    onNavigateToGoals?: () => void;  // 跳转到 goals 页面的回调
}

const TodoListWidget: React.FC<TodoListWidgetProps> = ({
    selectedDate,
    todolist,
    onNavigateToGoals
}) => {
    const [items, setItems] = useState<TodoItem[]>([]);
    const [dailyFocusContent, setDailyFocusContent] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);

    // 加载今日任务
    useEffect(() => {
        const loadTodos = async () => {
            setLoading(true);
            try {
                const allTodos = await taskPoolApi.fetchTaskPool(null, null, 'scheduled');
                const todosForDate = allTodos.filter(todo => todo.scheduledDate === selectedDate);
                setItems(todosForDate);
                // Note: dailyFocusContent not available in V2 - set to null for now
                setDailyFocusContent(null);
            } catch (error) {
                console.error('Failed to load todos:', error);
            } finally {
                setLoading(false);
            }
        };

        loadTodos();
    }, [selectedDate]);

    return (
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 h-full flex flex-col overflow-hidden">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-slate-100">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-blue-50 rounded-xl flex items-center justify-center">
                        <Target className="w-5 h-5 text-blue-500" />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-slate-800">Today's Focus</h3>
                        {dailyFocusContent ? (
                            <p className="text-xs text-blue-600 font-medium">{dailyFocusContent}</p>
                        ) : (
                            <p className="text-xs text-slate-400">未设置今日重点</p>
                        )}
                    </div>
                </div>

                {/* 跳转按钮 */}
                <button
                    onClick={onNavigateToGoals}
                    className="w-10 h-10 bg-slate-50 hover:bg-slate-100 rounded-xl flex items-center justify-center transition-colors group"
                    title="前往 Goal 页面"
                >
                    <ChevronRight className="w-5 h-5 text-slate-400 group-hover:text-slate-600 transition-colors" />
                </button>
            </div>

            {/* Content */}
            <div className="flex-1 overflow-y-auto px-4 py-4">
                {loading ? (
                    <div className="flex items-center justify-center h-full">
                        <Loader2 className="w-6 h-6 animate-spin text-blue-500" />
                    </div>
                ) : items.length > 0 ? (
                    <div className="space-y-2">
                        {items.map((item) => (
                            <div
                                key={item.id}
                                className="group flex items-center gap-3 px-4 py-3 rounded-xl transition-colors"
                                style={{ backgroundColor: item.color || '#FFFFFF' }}
                            >
                                {/* 完成状态指示器（只读） */}
                                <div
                                    className={`w-5 h-5 rounded-lg border-[1.5px] flex items-center justify-center flex-shrink-0 ${item.state === 'completed'
                                        ? 'bg-slate-800 border-slate-800'
                                        : 'border-slate-300 bg-white/50'
                                        }`}
                                >
                                    {item.state === 'completed' && (
                                        <Check size={12} className="text-white" strokeWidth={3} />
                                    )}
                                </div>

                                {/* 任务内容 */}
                                <span
                                    className={`flex-1 text-sm font-medium ${item.state === 'completed'
                                        ? 'text-slate-400 line-through decoration-slate-300'
                                        : 'text-slate-700'
                                        }`}
                                >
                                    {item.content}
                                </span>

                                {/* 跨日标记 */}
                                {item.expectedFinishAt && item.scheduledDate !== item.expectedFinishAt && (
                                    <span className="text-xs font-semibold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">
                                        跨日
                                    </span>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="flex flex-col items-center justify-center h-full text-slate-300">
                        <div className="w-16 h-16 bg-slate-50 rounded-2xl flex items-center justify-center mb-4">
                            <Target size={28} className="text-slate-200" />
                        </div>
                        <p className="text-sm font-bold uppercase tracking-widest">No tasks today</p>
                        <p className="text-xs text-slate-400 mt-1">点击右上角按钮添加任务</p>
                    </div>
                )}
            </div>

            {/* Footer - 任务统计 */}
            {items.length > 0 && (
                <div className="px-6 py-4 border-t border-slate-100 bg-slate-50/50">
                    <div className="flex items-center justify-between text-sm">
                        <span className="text-slate-500 font-medium">
                            已完成 {items.filter(i => i.state === 'completed').length} / {items.length} 项
                        </span>
                        <button
                            onClick={onNavigateToGoals}
                            className="text-blue-500 hover:text-blue-600 font-semibold transition-colors flex items-center gap-1"
                        >
                            管理任务
                            <ChevronRight size={16} />
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default TodoListWidget;
