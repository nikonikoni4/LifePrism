import React, { useState, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Calendar, Check, FolderOpen, Folder } from 'lucide-react';

// --- Types ---
interface WeekData {
    id: string;
    weekNum: number;
    label: string;
    startDate: string;
    endDate: string;
}

interface MonthNode {
    key: string;
    label: string;
    year: number;
    month: number;
    weeks: WeekData[];
}

interface DateTreeSelectorProps {
    viewType: 'week' | 'month';
    selectedMonth: string;
    selectedWeek: string;
    onViewTypeChange: (type: 'week' | 'month') => void;
    onMonthChange: (month: string) => void;
    onWeekChange: (weekId: string, monthKey: string) => void;
}

// --- Helper Functions ---
const getWeeksInMonth = (year: number, month: number): WeekData[] => {
    const weeks: WeekData[] = [];
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);

    let currentDate = new Date(firstDay);
    const dayOfWeek = currentDate.getDay();
    const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    currentDate.setDate(currentDate.getDate() + diff);

    let weekNum = 1;
    while (currentDate <= lastDay || weekNum <= 4) {
        const weekStart = new Date(currentDate);
        const weekEnd = new Date(currentDate);
        weekEnd.setDate(weekEnd.getDate() + 6);

        weeks.push({
            id: `${year}-${month}-w${weekNum}`,
            weekNum,
            label: `${month + 1}-${weekStart.getDate()} ~ ${month + 1}-${weekEnd.getDate()}`,
            startDate: weekStart.toISOString().split('T')[0],
            endDate: weekEnd.toISOString().split('T')[0],
        });

        currentDate.setDate(currentDate.getDate() + 7);
        weekNum++;
        if (weekNum > 5) break;
    }

    return weeks;
};

const getMonthsRange = (): MonthNode[] => {
    const today = new Date();
    const months: MonthNode[] = [];

    // Range: current month ± 1 month (total 3 months)
    for (let i = -1; i <= 1; i++) {
        const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
        const year = d.getFullYear();
        const month = d.getMonth();
        const key = `${year}-${String(month + 1).padStart(2, '0')}`;

        months.push({
            key,
            label: `${year}-${String(month + 1).padStart(2, '0')}`,
            year,
            month,
            weeks: getWeeksInMonth(year, month),
        });
    }
    return months;
};

// Animation variants
const weekListVariants = {
    open: {
        height: 'auto',
        opacity: 1,
        transition: {
            height: { duration: 0.3, ease: [0.4, 0, 0.2, 1] },
            opacity: { duration: 0.2, delay: 0.1 }
        }
    },
    closed: {
        height: 0,
        opacity: 0,
        transition: {
            height: { duration: 0.25, ease: [0.4, 0, 0.2, 1] },
            opacity: { duration: 0.15 }
        }
    }
};

const chevronVariants = {
    open: { rotate: 90 },
    closed: { rotate: 0 }
};

const DateTreeSelector: React.FC<DateTreeSelectorProps> = ({
    viewType,
    selectedMonth,
    selectedWeek,
    onViewTypeChange,
    onMonthChange,
    onWeekChange,
}) => {
    const [expandedMonths, setExpandedMonths] = useState<Set<string>>(new Set([selectedMonth]));
    const [isYearMonthPickerOpen, setIsYearMonthPickerOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    const months = useMemo(() => getMonthsRange(), []);

    // Sync expanded state with viewType
    useEffect(() => {
        if (viewType === 'week') {
            // Expand current month in week view
            setExpandedMonths(new Set([selectedMonth]));
        } else {
            // Collapse all in month view
            setExpandedMonths(new Set());
        }
    }, [viewType, selectedMonth]);

    const toggleMonth = (monthKey: string) => {
        setExpandedMonths(prev => {
            const next = new Set(prev);
            if (next.has(monthKey)) {
                next.delete(monthKey);
            } else {
                next.add(monthKey);
            }
            return next;
        });
    };

    const handleMonthSelect = (monthKey: string) => {
        onMonthChange(monthKey);
        setIsYearMonthPickerOpen(false);
        // Auto expand selected month
        setExpandedMonths(prev => new Set([...prev, monthKey]));
    };

    return (
        <div className="flex flex-col h-full">
            {/* View Type Toggle */}
            <div className="mb-4">
                <div className="bg-slate-100 p-1 rounded-xl flex items-center">
                    <button
                        onClick={() => onViewTypeChange('week')}
                        className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-all ${viewType === 'week'
                            ? 'bg-white text-slate-800 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                            }`}
                    >
                        Week
                    </button>
                    <button
                        onClick={() => onViewTypeChange('month')}
                        className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold transition-all ${viewType === 'month'
                            ? 'bg-white text-slate-800 shadow-sm'
                            : 'text-slate-500 hover:text-slate-700'
                            }`}
                    >
                        Month
                    </button>
                </div>
            </div>

            <span className="text-[10px] font-black text-slate-300 uppercase tracking-[0.2em] mb-2 block px-1">
                Focus on strategy
            </span>

            {/* Year-Month Picker */}
            <div className="mb-4 relative">
                <button
                    onClick={() => setIsYearMonthPickerOpen(!isYearMonthPickerOpen)}
                    className={`flex items-center justify-between w-full p-3 border rounded-xl font-bold text-sm transition-all group ${isYearMonthPickerOpen
                        ? 'bg-white border-blue-200 ring-2 ring-blue-50'
                        : 'bg-slate-50 border-slate-200 hover:bg-white text-slate-700'
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <Calendar size={14} className="text-slate-400" />
                        <span>{selectedMonth}</span>
                    </span>
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        <ChevronDown
                            size={14}
                            className={`text-slate-400 transition-transform duration-200 ${isYearMonthPickerOpen ? 'rotate-180' : ''
                                }`}
                        />
                    </div>
                </button>

                <AnimatePresence>
                    {isYearMonthPickerOpen && (
                        <>
                            <div
                                className="fixed inset-0 z-20"
                                onClick={() => setIsYearMonthPickerOpen(false)}
                            />
                            <motion.div
                                initial={{ opacity: 0, scale: 0.95, y: -10 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95, y: -10 }}
                                transition={{ duration: 0.15 }}
                                className="absolute top-full left-0 mt-2 w-full bg-white rounded-xl shadow-xl border border-slate-100 z-30 overflow-hidden p-1"
                            >
                                {months.map(month => (
                                    <button
                                        key={month.key}
                                        onClick={() => handleMonthSelect(month.key)}
                                        className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold transition-colors flex items-center justify-between ${selectedMonth === month.key
                                            ? 'bg-blue-50 text-blue-600'
                                            : 'text-slate-600 hover:bg-slate-50'
                                            }`}
                                    >
                                        {month.label}
                                        {selectedMonth === month.key && <Check size={14} />}
                                    </button>
                                ))}
                            </motion.div>
                        </>
                    )}
                </AnimatePresence>
            </div>

            {/* Tree View */}
            <div
                ref={containerRef}
                className="flex-1 overflow-y-auto scrollbar-light"
            >
                <div className="space-y-1">
                    {months.map(month => {
                        const isExpanded = expandedMonths.has(month.key);
                        const isSelected = selectedMonth === month.key;

                        return (
                            <div key={month.key} className="select-none">
                                {/* Month Node */}
                                <button
                                    onClick={() => {
                                        toggleMonth(month.key);
                                        onMonthChange(month.key);
                                    }}
                                    className={`w-full flex items-center gap-2 px-2 py-2 rounded-lg transition-all text-left ${isSelected
                                        ? 'bg-emerald-50 text-emerald-700'
                                        : 'text-slate-600 hover:bg-slate-50'
                                        }`}
                                >
                                    <motion.div
                                        variants={chevronVariants}
                                        animate={isExpanded ? 'open' : 'closed'}
                                        transition={{ duration: 0.2 }}
                                    >
                                        <ChevronRight size={14} className="text-slate-400" />
                                    </motion.div>
                                    {isExpanded ? (
                                        <FolderOpen size={16} className="text-emerald-500" />
                                    ) : (
                                        <Folder size={16} className="text-emerald-400" />
                                    )}
                                    <span className="text-sm font-bold">{month.label}</span>
                                </button>

                                {/* Week List (Animated) */}
                                <AnimatePresence initial={false}>
                                    {isExpanded && (
                                        <motion.div
                                            key={`weeks-${month.key}`}
                                            variants={weekListVariants}
                                            initial="closed"
                                            animate="open"
                                            exit="closed"
                                            className="overflow-hidden"
                                        >
                                            <div className="pl-6 space-y-0.5 py-1">
                                                {month.weeks.map(week => {
                                                    const isWeekSelected = selectedWeek === week.id;

                                                    return (
                                                        <button
                                                            key={week.id}
                                                            onClick={() => onWeekChange(week.id, month.key)}
                                                            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all text-left ${isWeekSelected
                                                                ? 'bg-blue-50 text-blue-600 border border-blue-200'
                                                                : 'text-slate-500 hover:bg-slate-50 border border-transparent'
                                                                }`}
                                                        >
                                                            <Calendar size={14} className={isWeekSelected ? 'text-blue-500' : 'text-slate-400'} />
                                                            <div className="flex flex-col">
                                                                <span className="text-xs font-bold">
                                                                    第{week.weekNum}周
                                                                </span>
                                                                <span className="text-[10px] text-slate-400">
                                                                    ({week.label})
                                                                </span>
                                                            </div>
                                                            {isWeekSelected && (
                                                                <div className="ml-auto w-1.5 h-1.5 rounded-full bg-blue-500" />
                                                            )}
                                                        </button>
                                                    );
                                                })}
                                            </div>
                                        </motion.div>
                                    )}
                                </AnimatePresence>
                            </div>
                        );
                    })}
                </div>
            </div>
        </div>
    );
};

export default DateTreeSelector;
