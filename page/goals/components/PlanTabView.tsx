
import React, { useState } from 'react';
import {
    Calendar,
    Target,
    Plus,
    Trash2,
    ChevronDown,
    LayoutGrid,
    List,
    Check
} from 'lucide-react';
import { MOCK_TODOS, MOCK_PLANS } from '../api';
import { GoalItem } from '../types';

const WEEK_DATA = [
    { id: 'w1', label: 'Dec 01 - Dec 07', isActive: true },
    { id: 'w2', label: 'Dec 08 - Dec 14', isActive: false },
    { id: 'w3', label: 'Dec 15 - Dec 21', isActive: false },
    { id: 'w4', label: 'Dec 22 - Dec 28', isActive: false },
];

const AVAILABLE_MONTHS = [
    'October 2025',
    'November 2025',
    'December 2025',
    'January 2026',
    'February 2026'
];

const PlanTabView: React.FC = () => {
    const [selectedWeek, setSelectedWeek] = useState(WEEK_DATA[0].id);
    const [selectedMonth, setSelectedMonth] = useState('December 2025');
    const [isMonthOpen, setIsMonthOpen] = useState(false);
    const [viewMode, setViewMode] = useState<'detail' | 'compact'>('detail');

    // In a real app, you would fetch tasks based on week range.
    // For demo, we are using the existing MOCK_TODOS and dynamically filtering.

    const days = [
        { name: 'Monday', date: '2025-12-01' },
        { name: 'Tuesday', date: '2025-12-02' },
        { name: 'Wednesday', date: '2025-12-03' },
        { name: 'Thursday', date: '2025-12-04' },
        { name: 'Friday', date: '2025-12-05' },
        { name: 'Saturday', date: '2025-12-06' },
        { name: 'Sunday', date: '2025-12-07' },
    ];

    // Local state for todos to allow simple add/check within this view
    const [localTodos, setLocalTodos] = useState<GoalItem[]>(MOCK_TODOS);
    const [newTodoInput, setNewTodoInput] = useState<{ [key: string]: string }>({});

    const toggleTodo = (id: string) => {
        setLocalTodos(prev => prev.map(t => t.id === id ? { ...t, completed: !t.completed } : t));
    };

    const deleteTodo = (id: string) => {
        setLocalTodos(prev => prev.filter(t => t.id !== id));
    };

    const addTodo = (date: string) => {
        const text = newTodoInput[date];
        if (!text?.trim()) return;

        const newId = `nt-${Date.now()}`;
        const newTask: GoalItem = {
            id: newId,
            text: text,
            completed: false,
            date: date,
            trackedTime: '0m',
            tag: 'New'
        };

        setLocalTodos([...localTodos, newTask]);
        setNewTodoInput(prev => ({ ...prev, [date]: '' }));
    };

    return (
        <div className="flex h-full overflow-hidden bg-transparent">
            {/* Left: Week Selector - Removed overflow-y-auto to disable scrolling */}
            <div className="w-64 border-r border-slate-200 bg-white pt-10 px-6 flex flex-col flex-shrink-0 transition-all duration-300">

                {/* Month Selector */}
                <div className="mb-8 relative">
                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-2 block">Month</span>
                    <button
                        onClick={() => setIsMonthOpen(!isMonthOpen)}
                        className={`flex items-center justify-between w-full p-3 border rounded-xl font-bold transition-all group shadow-sm hover:shadow-md ${isMonthOpen ? 'bg-white border-blue-200 ring-2 ring-blue-50' : 'bg-slate-50 border-slate-200 hover:bg-white text-slate-700'}`}
                    >
                        <span className="flex items-center gap-2">
                            <Calendar size={16} className={`transition-colors ${isMonthOpen ? 'text-blue-500' : 'text-slate-400 group-hover:text-blue-500'}`} />
                            <span className={isMonthOpen ? 'text-slate-800' : ''}>{selectedMonth}</span>
                        </span>
                        <ChevronDown size={16} className={`text-slate-400 transition-transform duration-200 ${isMonthOpen ? 'rotate-180' : ''}`} />
                    </button>

                    {/* Dropdown Menu */}
                    {isMonthOpen && (
                        <>
                            <div className="fixed inset-0 z-20 cursor-default" onClick={() => setIsMonthOpen(false)}></div>
                            <div className="absolute top-full left-0 mt-2 w-full bg-white rounded-xl shadow-xl border border-slate-100 z-30 overflow-hidden animate-in fade-in zoom-in-95 duration-200 p-1">
                                {AVAILABLE_MONTHS.map(month => (
                                    <button
                                        key={month}
                                        onClick={() => {
                                            setSelectedMonth(month);
                                            setIsMonthOpen(false);
                                        }}
                                        className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold transition-colors flex items-center justify-between ${selectedMonth === month
                                                ? 'bg-blue-50 text-blue-600'
                                                : 'text-slate-600 hover:bg-slate-50'
                                            }`}
                                    >
                                        {month}
                                        {selectedMonth === month && <Check size={14} />}
                                    </button>
                                ))}
                            </div>
                        </>
                    )}
                </div>

                <div className="h-px bg-slate-100 w-full mb-8"></div>

                <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-[0.2em] mb-6">Select Week</h4>
                <div className="space-y-2">
                    {WEEK_DATA.map(week => (
                        <button
                            key={week.id}
                            onClick={() => setSelectedWeek(week.id)}
                            className={`w-full text-left px-4 py-3 rounded-xl text-sm font-bold transition-all flex justify-between items-center ${selectedWeek === week.id
                                    ? 'bg-blue-50 text-blue-600 shadow-sm ring-1 ring-blue-100'
                                    : 'text-slate-500 hover:bg-slate-50'
                                }`}
                        >
                            <span>{week.label}</span>
                            {selectedWeek === week.id && <div className="w-2 h-2 rounded-full bg-blue-500"></div>}
                        </button>
                    ))}
                </div>

                <div className="mt-auto mb-10 p-6 bg-slate-50 rounded-2xl border border-slate-200 text-center">
                    <Target size={24} className="text-slate-400 mx-auto mb-3" />
                    <p className="text-xs font-semibold text-slate-500">Plan ahead to stay ahead.</p>
                </div>
            </div>

            {/* Right: Day Grid */}
            <div className="flex-1 overflow-y-auto p-6 no-scrollbar transition-all">
                <div className={`mx-auto space-y-6 pb-20 ${viewMode === 'compact' ? 'max-w-[1920px]' : 'max-w-4xl'}`}>
                    <div className="flex justify-between items-end">
                        <div className="flex items-center gap-4">
                            <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Weekly Plan</h2>
                            <span className="text-sm font-bold text-slate-400 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm mt-1">
                                {WEEK_DATA.find(w => w.id === selectedWeek)?.label}
                            </span>
                        </div>

                        {/* Layout Switcher */}
                        <div className="bg-white p-1 rounded-xl border border-slate-200 shadow-sm flex items-center gap-1">
                            <button
                                onClick={() => setViewMode('detail')}
                                className={`p-2 rounded-lg transition-all flex items-center gap-2 ${viewMode === 'detail' ? 'bg-slate-100 text-slate-800 shadow-inner' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'}`}
                                title="Detail View"
                            >
                                <List size={18} strokeWidth={2.5} />
                            </button>
                            <button
                                onClick={() => setViewMode('compact')}
                                className={`p-2 rounded-lg transition-all flex items-center gap-2 ${viewMode === 'compact' ? 'bg-slate-100 text-slate-800 shadow-inner' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-50'}`}
                                title="Compact Grid"
                            >
                                <LayoutGrid size={18} strokeWidth={2.5} />
                            </button>
                        </div>
                    </div>

                    <div className={viewMode === 'compact' ? 'grid grid-cols-1 md:grid-cols-2 xl:grid-cols-12 gap-4' : 'space-y-6'}>
                        {days.map((day, index) => {
                            const dayTodos = localTodos.filter(t => t.date === day.date);
                            const defaultFocus = MOCK_PLANS.find(p => p.date === day.date)?.content || '';

                            // 3 up (span 4), 4 down (span 3)
                            const compactColSpan = index < 3 ? 'xl:col-span-4' : 'xl:col-span-3';

                            return (
                                <div key={day.date} className={`bg-white rounded-[1.5rem] border border-slate-200 overflow-hidden shadow-sm hover:shadow-md transition-shadow ${viewMode === 'compact' ? `flex flex-col ${compactColSpan}` : ''}`}>
                                    {/* Row 0: Day Header */}
                                    <div className="bg-slate-50/80 border-b border-slate-200 px-4 py-3 flex items-center justify-between backdrop-blur-sm">
                                        <span className="text-sm font-bold text-slate-800">{day.name}</span>
                                        <span className="text-[10px] font-mono font-medium text-slate-400">{day.date}</span>
                                    </div>

                                    {viewMode === 'compact' ? (
                                        /* COMPACT LAYOUT - Stacked & Denser */
                                        <div className="flex flex-col p-4 gap-4 h-full">
                                            {/* Intent Area */}
                                            <div className="flex flex-col gap-1.5">
                                                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Focus</span>
                                                <textarea
                                                    className="w-full h-16 p-3 bg-slate-50 rounded-xl border border-slate-100 resize-none outline-none text-slate-700 font-medium leading-relaxed placeholder-slate-300 text-xs focus:bg-white focus:border-blue-200 transition-all no-scrollbar"
                                                    placeholder={`Focus for ${day.name}...`}
                                                    defaultValue={defaultFocus}
                                                />
                                            </div>

                                            {/* Tasks Area */}
                                            <div className="flex flex-col gap-2">
                                                <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest">Tasks</span>
                                                <div className="space-y-2">
                                                    {dayTodos.map(todo => (
                                                        <div key={todo.id} className="group flex items-start gap-2">
                                                            <button
                                                                onClick={() => toggleTodo(todo.id)}
                                                                className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center transition-colors flex-shrink-0 ${todo.completed ? 'bg-blue-600 border-blue-600' : 'bg-white border-slate-300 hover:border-blue-500'
                                                                    }`}
                                                            >
                                                                {todo.completed && <Check size={10} className="text-white" strokeWidth={4} />}
                                                            </button>
                                                            <span className={`text-xs font-medium truncate flex-1 leading-tight ${todo.completed ? 'text-slate-300 line-through' : 'text-slate-600'}`}>
                                                                {todo.text}
                                                            </span>
                                                            <button
                                                                onClick={() => deleteTodo(todo.id)}
                                                                className="opacity-0 group-hover:opacity-100 text-slate-300 hover:text-red-500 transition-all"
                                                            >
                                                                <Trash2 size={12} />
                                                            </button>
                                                        </div>
                                                    ))}
                                                </div>
                                                {/* Compact Add Input */}
                                                <div className="mt-3 pt-3 border-t border-dashed border-slate-100 flex items-center gap-2">
                                                    <Plus size={14} className="text-slate-400" />
                                                    <input
                                                        type="text"
                                                        value={newTodoInput[day.date] || ''}
                                                        onChange={(e) => setNewTodoInput({ ...newTodoInput, [day.date]: e.target.value })}
                                                        onKeyDown={(e) => e.key === 'Enter' && addTodo(day.date)}
                                                        placeholder="Add..."
                                                        className="flex-1 bg-transparent text-xs font-medium outline-none text-slate-700 placeholder-slate-300"
                                                    />
                                                </div>
                                            </div>
                                        </div>
                                    ) : (
                                        /* DETAIL LAYOUT */
                                        <div className="flex flex-col">
                                            <div className="flex border-b border-slate-100 min-h-[100px]">
                                                <div className="w-32 md:w-40 flex-shrink-0 bg-slate-50 border-r border-slate-100 flex items-center justify-center p-4">
                                                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest text-center leading-relaxed">
                                                        Focus<br />Intent
                                                    </span>
                                                </div>
                                                <div className="flex-1 p-0">
                                                    <textarea
                                                        className="w-full h-full p-5 resize-none outline-none text-slate-700 font-medium leading-relaxed bg-transparent placeholder-slate-300 text-sm no-scrollbar"
                                                        placeholder={`What is your main focus for ${day.name}?`}
                                                        defaultValue={defaultFocus}
                                                    />
                                                </div>
                                            </div>

                                            <div className="flex min-h-[120px]">
                                                <div className="w-32 md:w-40 flex-shrink-0 bg-slate-50 border-r border-slate-100 flex items-center justify-center p-4">
                                                    <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest text-center leading-relaxed">
                                                        Execution
                                                    </span>
                                                </div>
                                                <div className="flex-1 p-5 bg-white">
                                                    <div className="space-y-3">
                                                        {dayTodos.map(todo => (
                                                            <div key={todo.id} className="group flex items-center gap-3">
                                                                <button
                                                                    onClick={() => toggleTodo(todo.id)}
                                                                    className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors flex-shrink-0 ${todo.completed ? 'bg-blue-600 border-blue-600' : 'bg-white border-slate-300 hover:border-blue-500'
                                                                        }`}
                                                                >
                                                                    {todo.completed && <Check size={12} className="text-white" strokeWidth={3} />}
                                                                </button>
                                                                <span className={`text-sm font-medium truncate flex-1 ${todo.completed ? 'text-slate-300 line-through' : 'text-slate-600'}`}>
                                                                    {todo.text}
                                                                </span>
                                                                <button
                                                                    onClick={() => deleteTodo(todo.id)}
                                                                    className="opacity-0 group-hover:opacity-100 p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                                                                >
                                                                    <Trash2 size={14} />
                                                                </button>
                                                            </div>
                                                        ))}
                                                    </div>

                                                    <div className="mt-4 pt-3 border-t border-dashed border-slate-100 flex items-center gap-2">
                                                        <Plus size={16} className="text-slate-400" />
                                                        <input
                                                            type="text"
                                                            value={newTodoInput[day.date] || ''}
                                                            onChange={(e) => setNewTodoInput({ ...newTodoInput, [day.date]: e.target.value })}
                                                            onKeyDown={(e) => e.key === 'Enter' && addTodo(day.date)}
                                                            placeholder="Add a specific task..."
                                                            className="flex-1 bg-transparent text-sm font-medium outline-none text-slate-700 placeholder-slate-300"
                                                        />
                                                        {newTodoInput[day.date] && (
                                                            <button
                                                                onClick={() => addTodo(day.date)}
                                                                className="text-[10px] font-bold bg-slate-900 text-white px-2 py-1 rounded"
                                                            >
                                                                ADD
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PlanTabView;
