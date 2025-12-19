/**
 * TodoList Widget V2
 * 
 * 待办事项组件，使用 V2 API
 */
import React, { useState, useEffect } from 'react';
import { Check, Plus, Trophy, Link } from 'lucide-react';
import { TodoListDataV2 } from '../types';
import { ActivityAPIV2 } from '../api';

interface TodoListWidgetV2Props {
    selectedDate: string;
    todolist?: TodoListDataV2[];  // Optional: if provided, use this data instead of fetching
}

const TodoListWidgetV2: React.FC<TodoListWidgetV2Props> = ({ selectedDate, todolist: propsTodolist }) => {
    const [todos, setTodos] = useState<TodoListDataV2[]>([]);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        // If props data is provided, use it directly
        if (propsTodolist) {
            setTodos(propsTodolist);
            return;
        }

        // Otherwise, fetch data from V2 API
        const fetchData = async () => {
            setLoading(true);
            try {
                const response = await ActivityAPIV2.getStats({
                    date: selectedDate,
                    include: 'todolist',
                });
                setTodos(response.todolist || []);
            } catch (error) {
                console.error('Failed to load todolist:', error);
                setTodos([]);
            } finally {
                setLoading(false);
            }
        };

        if (selectedDate) {
            fetchData();
        }
    }, [selectedDate, propsTodolist]);

    const toggleTodo = (id: number) => {
        setTodos(prev => prev.map(t =>
            t.id === id ? { ...t, isCompleted: !t.isCompleted } : t
        ));
        // TODO: 调用 API 更新状态
    };

    const completedCount = todos.filter(t => t.isCompleted).length;
    const totalCount = todos.length;
    const progress = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

    // 根据 linkToGoal 获取样式
    const getLinkToGoalStyle = (linkToGoal: number) => {
        switch (linkToGoal) {
            case 1: return 'bg-indigo-100 text-indigo-700 border-indigo-200';
            case 2: return 'bg-blue-100 text-blue-700 border-blue-200';
            case 3: return 'bg-green-100 text-green-700 border-green-200';
            case 4: return 'bg-amber-100 text-amber-700 border-amber-200';
            default: return 'bg-gray-100 text-gray-700 border-gray-200';
        }
    };

    if (loading) {
        return (
            <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col h-full animate-pulse">
                <div className="h-8 bg-gray-200 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-200 rounded w-full mb-8"></div>
                <div className="space-y-3">
                    <div className="h-12 bg-gray-100 rounded-2xl"></div>
                    <div className="h-12 bg-gray-100 rounded-2xl"></div>
                    <div className="h-12 bg-gray-100 rounded-2xl"></div>
                </div>
            </div>
        );
    }

    return (
        <div className="bg-white rounded-3xl shadow-sm border border-gray-100 p-8 flex flex-col h-full relative overflow-hidden">
            {/* Decorative Elements */}
            <div className="absolute -top-12 -right-12 w-48 h-48 bg-gradient-to-br from-blue-50 to-purple-50 rounded-full blur-3xl pointer-events-none opacity-60"></div>

            {/* Header */}
            <div className="flex justify-between items-start mb-8 z-10">
                <div>
                    <div className="inline-flex items-center px-3 py-1 rounded-full bg-slate-100 border border-slate-200 text-slate-600 text-xs font-bold uppercase tracking-wide mb-3">
                        Daily Tasks
                    </div>
                    <h2 className="text-2xl font-bold text-slate-900 tracking-tight">Today's Focus</h2>
                    <p className="text-slate-500 text-sm mt-1 font-medium">Your daily mission control.</p>
                </div>
                <div className="w-14 h-14 rounded-2xl bg-orange-50 border border-orange-100 flex items-center justify-center text-orange-500 shadow-sm">
                    <Trophy size={24} strokeWidth={2.5} />
                </div>
            </div>

            {/* Progress Bar */}
            <div className="mb-8 z-10">
                <div className="flex justify-between items-end mb-2">
                    <span className="text-sm font-semibold text-slate-700">Daily Progress</span>
                    <span className="text-2xl font-bold text-slate-900">{progress}%</span>
                </div>
                <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden shadow-inner">
                    <div
                        className="h-full bg-morandi-blue rounded-full transition-all duration-1000 ease-out shadow-sm"
                        style={{ width: `${progress}%` }}
                    ></div>
                </div>
            </div>

            {/* Tasks List */}
            <div className="flex-1 overflow-y-auto no-scrollbar space-y-3 z-10 pr-2">
                {todos.length > 0 ? (
                    todos.map((todo) => (
                        <div
                            key={todo.id}
                            onClick={() => toggleTodo(todo.id)}
                            className={`group flex items-center p-3.5 rounded-2xl border transition-all duration-200 cursor-pointer ${todo.isCompleted
                                ? 'bg-gray-50 border-transparent opacity-60'
                                : 'bg-white border-gray-100 hover:border-blue-200 hover:shadow-md hover:shadow-blue-500/5'
                                }`}
                        >
                            <div className={`w-6 h-6 rounded-lg border-2 mr-4 flex-shrink-0 flex items-center justify-center transition-all duration-300 ${todo.isCompleted
                                ? 'bg-morandi-blue border-morandi-blue scale-100'
                                : 'border-gray-300 bg-white group-hover:border-morandi-blue'
                                }`}>
                                {todo.isCompleted && <Check size={14} className="text-white" strokeWidth={3} />}
                            </div>

                            <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between mb-0.5">
                                    <p className={`text-sm font-semibold truncate transition-all ${todo.isCompleted ? 'text-gray-400 line-through decoration-2' : 'text-slate-700'
                                        }`}>
                                        {todo.name}
                                    </p>
                                </div>
                                <div className="flex items-center gap-2">
                                    {todo.linkToGoal > 0 && (
                                        <span className={`text-[10px] px-2 py-0.5 rounded-full border font-bold flex items-center gap-1 ${getLinkToGoalStyle(todo.linkToGoal)}`}>
                                            <Link size={10} />
                                            Goal #{todo.linkToGoal}
                                        </span>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="text-center text-slate-400 py-8">No tasks for today</div>
                )}

                {/* Add Button */}
                <button className="w-full py-3.5 mt-2 rounded-2xl border-2 border-dashed border-gray-200 text-gray-400 hover:text-morandi-blue hover:border-morandi-blue/40 hover:bg-blue-50/30 transition-all flex items-center justify-center gap-2 text-sm font-bold">
                    <Plus size={18} />
                    Add Task
                </button>
            </div>
        </div>
    );
};

export default TodoListWidgetV2;
