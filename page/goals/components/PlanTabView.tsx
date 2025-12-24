
import React, { useState, useMemo } from 'react';
import {
    Calendar,
    Target,
    Plus,
    Trash2,
    ChevronDown,
    ChevronRight,
    ChevronUp,
    LayoutGrid,
    List,
    Check,
    CheckCircle2,
    FileText,
    Sparkles,
    ClipboardList,
    BookOpen,
    X
} from 'lucide-react';
import { MOCK_TODOS, MOCK_PLANS } from '../api';
import { GoalItem } from '../types';

// --- Types ---
interface WeekData {
    id: string;
    weekNum: number;
    label: string;
    startDate: string;
    endDate: string;
    isCompleted: boolean;
    summary: string;
}

// --- Helper Functions ---
const getWeeksInMonth = (year: number, month: number): WeekData[] => {
    const weeks: WeekData[] = [];
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    // Start from the first day of the month
    let currentDate = new Date(firstDay);
    // Adjust to Monday of that week
    const dayOfWeek = currentDate.getDay();
    const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    currentDate.setDate(currentDate.getDate() + diff);

    let weekNum = 1;
    while (currentDate <= lastDay || weekNum <= 4) {
        const weekStart = new Date(currentDate);
        const weekEnd = new Date(currentDate);
        weekEnd.setDate(weekEnd.getDate() + 6);

        const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const startStr = `${monthNames[weekStart.getMonth()]} ${String(weekStart.getDate()).padStart(2, '0')}`;
        const endStr = `${monthNames[weekEnd.getMonth()]} ${String(weekEnd.getDate()).padStart(2, '0')}`;

        weeks.push({
            id: `w${weekNum}`,
            weekNum,
            label: `${startStr} - ${endStr}`,
            startDate: weekStart.toISOString().split('T')[0],
            endDate: weekEnd.toISOString().split('T')[0],
            isCompleted: weekNum <= 2, // Mock: first 2 weeks completed
            summary: weekNum === 1
                ? 'Launch the MVP beta and gather initial user feedback.'
                : weekNum === 2
                    ? 'Focus on optimizing database queries and API response times.'
                    : `What is the main objective for Week ${weekNum}?`
        });

        currentDate.setDate(currentDate.getDate() + 7);
        weekNum++;
        if (weekNum > 4) break;
    }

    return weeks;
};

const getMonthsAround = (): { value: string; label: string; year: number; month: number }[] => {
    const today = new Date();
    const months = [];
    const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];

    for (let i = -2; i <= 2; i++) {
        const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
        months.push({
            value: `${monthNames[d.getMonth()]} ${d.getFullYear()}`,
            label: `${monthNames[d.getMonth()]} ${d.getFullYear()}`,
            year: d.getFullYear(),
            month: d.getMonth()
        });
    }
    return months;
};

const PlanTabView: React.FC = () => {
    // View type: 'week' (detailed) or 'month' (card grid)
    const [viewType, setViewType] = useState<'week' | 'month'>('month');

    const today = new Date();
    const currentMonthLabel = `${['January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'][today.getMonth()]} ${today.getFullYear()}`;

    const [selectedMonth, setSelectedMonth] = useState(currentMonthLabel);
    const [isMonthOpen, setIsMonthOpen] = useState(false);
    const [viewMode, setViewMode] = useState<'detail' | 'compact'>('detail');

    const availableMonths = useMemo(() => getMonthsAround(), []);

    const selectedMonthData = useMemo(() => {
        const found = availableMonths.find(m => m.value === selectedMonth);
        return found || { year: today.getFullYear(), month: today.getMonth() };
    }, [selectedMonth, availableMonths, today]);

    const weeksInMonth = useMemo(() =>
        getWeeksInMonth(selectedMonthData.year, selectedMonthData.month),
        [selectedMonthData]
    );

    const [selectedWeek, setSelectedWeek] = useState(weeksInMonth[0]?.id || 'w1');

    // Week summaries state for editing (plan content)
    const [weekSummaries, setWeekSummaries] = useState<Record<string, string>>({});

    // Summary view state
    const [showSummaryView, setShowSummaryView] = useState(false);

    // Weekly summary reflection content (actual summary written after the week)
    const [weeklySummaryContent, setWeeklySummaryContent] = useState<Record<string, string>>({});

    // Monthly summary content
    const [monthlySummaryContent, setMonthlySummaryContent] = useState<Record<string, string>>({});

    // Collapsed state for daily sections in summary view
    const [collapsedDays, setCollapsedDays] = useState<Record<string, boolean>>({});

    const getWeekSummary = (weekId: string, defaultSummary: string) => {
        return weekSummaries[weekId] ?? defaultSummary;
    };

    const updateWeekSummary = (weekId: string, content: string) => {
        setWeekSummaries(prev => ({ ...prev, [weekId]: content }));
    };

    const getWeeklySummaryContent = (weekId: string) => {
        return weeklySummaryContent[weekId] ?? '';
    };

    const updateWeeklySummaryContent = (weekId: string, content: string) => {
        setWeeklySummaryContent(prev => ({ ...prev, [weekId]: content }));
    };

    const getMonthlySummaryContent = (monthKey: string) => {
        return monthlySummaryContent[monthKey] ?? '';
    };

    const updateMonthlySummaryContent = (monthKey: string, content: string) => {
        setMonthlySummaryContent(prev => ({ ...prev, [monthKey]: content }));
    };

    const toggleDayCollapse = (dayDate: string) => {
        setCollapsedDays(prev => ({ ...prev, [dayDate]: !prev[dayDate] }));
    };

    // Days for the selected week
    const days = useMemo(() => {
        const week = weeksInMonth.find(w => w.id === selectedWeek);
        if (!week) return [];

        const dayNames = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
        const result = [];
        const start = new Date(week.startDate);

        for (let i = 0; i < 7; i++) {
            const d = new Date(start);
            d.setDate(start.getDate() + i);
            result.push({
                name: dayNames[i],
                date: d.toISOString().split('T')[0]
            });
        }
        return result;
    }, [selectedWeek, weeksInMonth]);

    // Local state for todos
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

    const handleSummaryClick = () => {
        setShowSummaryView(!showSummaryView);
    };

    return (
        <div className="flex flex-1 h-full overflow-hidden bg-transparent">
            {/* Left: Sidebar */}
            <div className="w-56 border-r border-slate-200 bg-white pt-6 px-4 flex flex-col flex-shrink-0 transition-all duration-300">

                {/* Week/Month Toggle */}
                <div className="mb-6">
                    <div className="bg-slate-100 p-1 rounded-xl flex items-center">
                        <button
                            onClick={() => setViewType('week')}
                            className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-all ${viewType === 'week'
                                ? 'bg-white text-slate-800 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                                }`}
                        >
                            Week
                        </button>
                        <button
                            onClick={() => setViewType('month')}
                            className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-all ${viewType === 'month'
                                ? 'bg-white text-slate-800 shadow-sm'
                                : 'text-slate-500 hover:text-slate-700'
                                }`}
                        >
                            Month
                        </button>
                    </div>
                </div>

                <span className="text-[10px] font-black text-slate-300 uppercase tracking-[0.2em] mb-2 block px-1">Focus on strategy</span>

                {/* Month Selector */}
                <div className="mb-6 relative">
                    <button
                        onClick={() => setIsMonthOpen(!isMonthOpen)}
                        className={`flex items-center justify-between w-full p-3 border rounded-xl font-bold text-sm transition-all group ${isMonthOpen
                            ? 'bg-white border-blue-200 ring-2 ring-blue-50'
                            : 'bg-slate-50 border-slate-200 hover:bg-white text-slate-700'
                            }`}
                    >
                        <span className="flex items-center gap-2">
                            <span className={isMonthOpen ? 'text-slate-800' : ''}>{selectedMonth.split(' ')[0]} {selectedMonth.split(' ')[1]}</span>
                        </span>
                        <div className="flex items-center gap-1">
                            <div className="w-2 h-2 rounded-full bg-blue-500" />
                            <ChevronDown size={14} className={`text-slate-400 transition-transform duration-200 ${isMonthOpen ? 'rotate-180' : ''}`} />
                        </div>
                    </button>

                    {/* Dropdown Menu */}
                    {isMonthOpen && (
                        <>
                            <div className="fixed inset-0 z-20 cursor-default" onClick={() => setIsMonthOpen(false)}></div>
                            <div className="absolute top-full left-0 mt-2 w-full bg-white rounded-xl shadow-xl border border-slate-100 z-30 overflow-hidden animate-in fade-in zoom-in-95 duration-200 p-1">
                                {availableMonths.map(month => (
                                    <button
                                        key={month.value}
                                        onClick={() => {
                                            setSelectedMonth(month.value);
                                            setIsMonthOpen(false);
                                        }}
                                        className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold transition-colors flex items-center justify-between ${selectedMonth === month.value
                                            ? 'bg-blue-50 text-blue-600'
                                            : 'text-slate-600 hover:bg-slate-50'
                                            }`}
                                    >
                                        {month.label}
                                        {selectedMonth === month.value && <Check size={14} />}
                                    </button>
                                ))}
                            </div>
                        </>
                    )}
                </div>

                {/* Week List */}
                <div
                    className="flex-1 space-y-1 overflow-y-auto scrollbar-light"
                    onWheel={(e) => e.stopPropagation()}
                >
                    {weeksInMonth.map(week => (
                        <button
                            key={week.id}
                            onClick={() => setSelectedWeek(week.id)}
                            className={`w-full text-left px-3 py-2.5 rounded-xl transition-all ${selectedWeek === week.id
                                ? 'bg-blue-50 text-blue-600 border border-blue-200'
                                : 'text-slate-600 hover:bg-slate-50 border border-transparent'
                                }`}
                        >
                            <div className="flex items-center justify-between">
                                <span className="text-sm font-bold">Week {week.weekNum}</span>
                                {selectedWeek === week.id && <div className="w-1.5 h-1.5 rounded-full bg-blue-500" />}
                            </div>
                            <span className="text-[10px] text-slate-400">{week.label}</span>
                        </button>
                    ))}
                </div>

                {/* Summary Button */}
                <div className="mt-4 mb-4">
                    <button
                        onClick={handleSummaryClick}
                        className={`w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-bold transition-all group ${showSummaryView
                            ? 'bg-blue-500 text-white border-2 border-blue-500 shadow-lg'
                            : 'bg-white border-2 border-slate-200 text-slate-700 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600'
                            }`}
                    >
                        <ClipboardList size={16} className={showSummaryView ? 'text-white' : 'text-slate-400 group-hover:text-blue-500 transition-colors'} />
                        <span>{viewType === 'week' ? '周总结' : '月总结'}</span>
                    </button>
                </div>
            </div>

            {/* Right: Main Content Area */}
            <div className="flex-1 overflow-y-auto p-6 scrollbar-light transition-all">
                {showSummaryView ? (
                    /* ========== SUMMARY VIEW ========== */
                    viewType === 'week' ? (
                        /* ----- WEEKLY SUMMARY VIEW ----- */
                        (() => {
                            const currentWeek = weeksInMonth.find(w => w.id === selectedWeek);
                            const weekPlan = currentWeek ? getWeekSummary(currentWeek.id, currentWeek.summary) : '';
                            const isPlaceholder = weekPlan.startsWith('What is the main objective');

                            return (
                                <div className="max-w-4xl mx-auto">
                                    {/* Header */}
                                    <div className="flex items-center justify-between mb-6">
                                        <div className="flex items-center gap-4">
                                            <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Weekly Summary</h2>
                                            <span className="text-sm font-bold text-slate-400 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                                                {currentWeek?.label}
                                            </span>
                                        </div>
                                        <button
                                            onClick={() => setShowSummaryView(false)}
                                            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                                        >
                                            <X size={20} />
                                        </button>
                                    </div>

                                    {/* Original Plan Section */}
                                    <div className="bg-gradient-to-r from-amber-50 to-orange-50 rounded-2xl border border-amber-100 p-5 mb-6">
                                        <div className="flex items-center gap-3 mb-3">
                                            <div className="p-2 bg-amber-100 rounded-lg">
                                                <BookOpen size={18} className="text-amber-600" />
                                            </div>
                                            <span className="text-sm font-bold text-amber-700">原计划（月计划内写的内容）</span>
                                        </div>
                                        <p className={`text-sm leading-relaxed ${isPlaceholder || !weekPlan ? 'text-slate-400 italic' : 'text-slate-700'}`}>
                                            {isPlaceholder || !weekPlan ? '本周还没有设置计划目标' : weekPlan}
                                        </p>
                                    </div>

                                    {/* Daily Breakdown - Collapsible */}
                                    <div className="bg-white rounded-2xl border border-slate-200 mb-6 overflow-hidden">
                                        <div className="bg-slate-50 border-b border-slate-200 px-5 py-3">
                                            <span className="text-xs font-black text-slate-500 uppercase tracking-widest">每日完成情况</span>
                                        </div>
                                        <div className="divide-y divide-slate-100">
                                            {days.map(day => {
                                                const dayTodos = localTodos.filter(t => t.date === day.date);
                                                const completedCount = dayTodos.filter(t => t.completed).length;
                                                const totalCount = dayTodos.length;
                                                const isCollapsed = collapsedDays[day.date] ?? true;
                                                const completionRate = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0;

                                                return (
                                                    <div key={day.date}>
                                                        <button
                                                            onClick={() => toggleDayCollapse(day.date)}
                                                            className="w-full px-5 py-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                                                        >
                                                            <div className="flex items-center gap-4">
                                                                <span className="text-sm font-bold text-slate-700 w-24">{day.name}</span>
                                                                <div className="flex items-center gap-2">
                                                                    <div className="w-24 h-2 bg-slate-100 rounded-full overflow-hidden">
                                                                        <div
                                                                            className={`h-full rounded-full transition-all ${completionRate === 100 ? 'bg-green-500' : completionRate > 50 ? 'bg-blue-500' : 'bg-slate-300'}`}
                                                                            style={{ width: `${completionRate}%` }}
                                                                        />
                                                                    </div>
                                                                    <span className={`text-xs font-bold ${completionRate === 100 ? 'text-green-600' : 'text-slate-400'}`}>
                                                                        {completedCount}/{totalCount}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                            {isCollapsed ? <ChevronRight size={16} className="text-slate-400" /> : <ChevronUp size={16} className="text-slate-400" />}
                                                        </button>

                                                        {/* Expanded Todo List */}
                                                        {!isCollapsed && (
                                                            <div className="px-5 pb-4 bg-slate-50/50">
                                                                {dayTodos.length > 0 ? (
                                                                    <div className="space-y-2 pl-4 border-l-2 border-slate-200">
                                                                        {dayTodos.map(todo => (
                                                                            <div key={todo.id} className="flex items-center gap-2 py-1">
                                                                                <div className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 ${todo.completed ? 'bg-green-500' : 'bg-slate-200'}`}>
                                                                                    {todo.completed && <Check size={10} className="text-white" strokeWidth={3} />}
                                                                                </div>
                                                                                <span className={`text-sm ${todo.completed ? 'text-slate-400 line-through' : 'text-slate-600'}`}>
                                                                                    {todo.text}
                                                                                </span>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                ) : (
                                                                    <p className="text-xs text-slate-400 italic pl-4">当天没有任务</p>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>

                                    {/* Summary Content - Editable */}
                                    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                                        <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center gap-2">
                                            <Sparkles size={14} className="text-blue-500" />
                                            <span className="text-xs font-black text-slate-500 uppercase tracking-widest">周总结内容</span>
                                        </div>
                                        <textarea
                                            className="w-full p-5 min-h-[200px] resize-none outline-none text-slate-700 leading-relaxed placeholder-slate-300"
                                            placeholder="写下这周的总结、反思和收获..."
                                            value={getWeeklySummaryContent(selectedWeek)}
                                            onChange={(e) => updateWeeklySummaryContent(selectedWeek, e.target.value)}
                                        />
                                    </div>
                                </div>
                            );
                        })()
                    ) : (
                        /* ----- MONTHLY SUMMARY VIEW ----- */
                        <div className="max-w-4xl mx-auto">
                            {/* Header */}
                            <div className="flex items-center justify-between mb-6">
                                <div className="flex items-center gap-4">
                                    <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Monthly Summary</h2>
                                    <span className="text-sm font-bold text-slate-400 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm">
                                        {selectedMonth}
                                    </span>
                                </div>
                                <button
                                    onClick={() => setShowSummaryView(false)}
                                    className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-all"
                                >
                                    <X size={20} />
                                </button>
                            </div>

                            {/* Weeks Overview */}
                            <div className="bg-white rounded-2xl border border-slate-200 mb-6 overflow-hidden">
                                <div className="bg-slate-50 border-b border-slate-200 px-5 py-3">
                                    <span className="text-xs font-black text-slate-500 uppercase tracking-widest">各周完成情况</span>
                                </div>
                                <div className="grid grid-cols-4 divide-x divide-slate-100">
                                    {weeksInMonth.map(week => (
                                        <div key={week.id} className="p-4 text-center">
                                            <div className={`w-10 h-10 mx-auto mb-2 rounded-full flex items-center justify-center ${week.isCompleted ? 'bg-green-100 text-green-600' : 'bg-slate-100 text-slate-400'}`}>
                                                {week.isCompleted ? <CheckCircle2 size={20} /> : <span className="text-sm font-bold">{week.weekNum}</span>}
                                            </div>
                                            <span className="text-xs font-bold text-slate-600">Week {week.weekNum}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Monthly Summary Content - Editable */}
                            <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden">
                                <div className="bg-slate-50 border-b border-slate-200 px-5 py-3 flex items-center gap-2">
                                    <Sparkles size={14} className="text-blue-500" />
                                    <span className="text-xs font-black text-slate-500 uppercase tracking-widest">月总结内容</span>
                                </div>
                                <textarea
                                    className="w-full p-5 min-h-[300px] resize-none outline-none text-slate-700 leading-relaxed placeholder-slate-300"
                                    placeholder="写下这个月的总结、反思和收获..."
                                    value={getMonthlySummaryContent(selectedMonth)}
                                    onChange={(e) => updateMonthlySummaryContent(selectedMonth, e.target.value)}
                                />
                            </div>
                        </div>
                    )
                ) : viewType === 'month' ? (
                    /* ========== MONTH VIEW - Card Grid ========== */
                    <div className="max-w-5xl mx-auto">
                        {/* Header */}
                        <div className="flex items-center gap-4 mb-8">
                            <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Monthly Plan</h2>
                            <span className="text-lg font-medium text-slate-400">|</span>
                            <span className="text-lg font-medium text-slate-500">{selectedMonth}</span>
                        </div>

                        {/* Week Cards Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
                            {weeksInMonth.map(week => (
                                <div
                                    key={week.id}
                                    className={`bg-white rounded-2xl border border-slate-200 p-6 hover:shadow-lg transition-all cursor-pointer group ${selectedWeek === week.id ? 'ring-2 ring-blue-200' : ''
                                        }`}
                                    onClick={() => {
                                        setSelectedWeek(week.id);
                                        setViewType('week');
                                    }}
                                >
                                    {/* Card Header */}
                                    <div className="flex items-start justify-between mb-4">
                                        <div>
                                            <h3 className="text-xl font-bold text-slate-800">Week {week.weekNum}</h3>
                                            <span className="text-xs text-slate-400">{week.label}</span>
                                        </div>
                                        <div className={`p-2 rounded-lg ${week.isCompleted
                                            ? 'bg-green-50 text-green-500'
                                            : 'bg-slate-50 text-slate-400'
                                            }`}>
                                            {week.isCompleted
                                                ? <CheckCircle2 size={20} />
                                                : <FileText size={20} />
                                            }
                                        </div>
                                    </div>

                                    {/* Weekly Summary Section */}
                                    <div className="mb-2">
                                        <span className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                                            WEEKLY SUMMARY & FOCUS
                                        </span>
                                    </div>
                                    <div className="bg-slate-50 rounded-xl p-4 min-h-[80px]">
                                        <textarea
                                            className="w-full bg-transparent resize-none outline-none text-sm text-slate-600 placeholder-slate-300 leading-relaxed"
                                            placeholder={`What is the main objective for Week ${week.weekNum}?`}
                                            value={getWeekSummary(week.id, week.summary === `What is the main objective for Week ${week.weekNum}?` ? '' : week.summary)}
                                            onChange={(e) => {
                                                e.stopPropagation();
                                                updateWeekSummary(week.id, e.target.value);
                                            }}
                                            onClick={(e) => e.stopPropagation()}
                                            rows={3}
                                        />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                ) : (
                    /* ========== WEEK VIEW - Detailed Day by Day ========== */
                    <div className={`mx-auto space-y-6 pb-20 ${viewMode === 'compact' ? 'max-w-[1920px]' : 'max-w-4xl'}`}>
                        <div className="flex justify-between items-end">
                            <div className="flex items-center gap-4">
                                <h2 className="text-3xl font-bold text-slate-800 tracking-tight">Weekly Plan</h2>
                                <span className="text-sm font-bold text-slate-400 bg-white px-3 py-1 rounded-full border border-slate-200 shadow-sm mt-1">
                                    {weeksInMonth.find(w => w.id === selectedWeek)?.label}
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

                        {/* Weekly Focus Banner - Shows summary from Month View */}
                        {(() => {
                            const currentWeek = weeksInMonth.find(w => w.id === selectedWeek);
                            const weekFocus = currentWeek ? getWeekSummary(currentWeek.id, currentWeek.summary) : '';
                            const isPlaceholder = weekFocus.startsWith('What is the main objective');

                            return (
                                <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-2xl border border-blue-100 p-5 mb-6 flex items-start gap-4">
                                    <div className="p-2.5 bg-blue-100 rounded-xl flex-shrink-0">
                                        <Target size={20} className="text-blue-600" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <span className="text-[10px] font-black text-blue-500 uppercase tracking-widest block mb-1">
                                            WEEKLY FOCUS (FROM MONTH VIEW)
                                        </span>
                                        {isPlaceholder || !weekFocus ? (
                                            <p className="text-sm text-slate-400 italic">
                                                No focus set for this week. Edit in Month view.
                                            </p>
                                        ) : (
                                            <p className="text-sm font-medium text-slate-700 leading-relaxed">
                                                {weekFocus}
                                            </p>
                                        )}
                                    </div>
                                </div>
                            );
                        })()}

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
                )}
            </div>
        </div>
    );
};

export default PlanTabView;
