import React, { useState, useMemo, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, ChevronRight, Calendar, Check, FolderOpen, Folder } from 'lucide-react';

// --- Types ---
interface DayData {
    date: string;      // YYYY-MM-DD
    dayOfWeek: string; // 周一, 周二, etc.
    dayNum: number;    // 1-31
    isToday: boolean;
}

interface WeekNode {
    key: string;        // YYYY-WXX format
    weekNum: number;
    label: string;      // e.g., "12-23 ~ 12-29"
    startDate: string;
    endDate: string;
    days: DayData[];
}

interface WeekDayTreeSelectorProps {
    selectedDate: string;
    onDateChange: (date: string) => void;
}

// --- Helper Functions ---
const DAY_NAMES = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

const getWeekNumber = (date: Date): number => {
    const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d.getTime() - yearStart.getTime()) / 86400000) + 1) / 7);
};

const getWeeksRange = (centerDate: string): WeekNode[] => {
    const today = new Date().toISOString().split('T')[0];
    const center = new Date(centerDate);
    const weeks: WeekNode[] = [];

    // Get Monday of current week
    const currentMonday = new Date(center);
    const dayOfWeek = currentMonday.getDay();
    const diff = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
    currentMonday.setDate(currentMonday.getDate() + diff);

    // Generate 3 weeks: current week ± 1 week
    for (let weekOffset = -1; weekOffset <= 1; weekOffset++) {
        const weekStart = new Date(currentMonday);
        weekStart.setDate(currentMonday.getDate() + weekOffset * 7);

        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);

        const weekNum = getWeekNumber(weekStart);
        const year = weekStart.getFullYear();

        const days: DayData[] = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(weekStart);
            d.setDate(weekStart.getDate() + i);
            const dateStr = d.toISOString().split('T')[0];
            days.push({
                date: dateStr,
                dayOfWeek: DAY_NAMES[d.getDay()],
                dayNum: d.getDate(),
                isToday: dateStr === today
            });
        }

        const startLabel = `${weekStart.getMonth() + 1}-${weekStart.getDate()}`;
        const endLabel = `${weekEnd.getMonth() + 1}-${weekEnd.getDate()}`;

        weeks.push({
            key: `${year}-W${String(weekNum).padStart(2, '0')}`,
            weekNum,
            label: `${startLabel} ~ ${endLabel}`,
            startDate: weekStart.toISOString().split('T')[0],
            endDate: weekEnd.toISOString().split('T')[0],
            days
        });
    }

    return weeks;
};

const getMonthsRange = (): { key: string; label: string }[] => {
    const today = new Date();
    const months = [];

    for (let i = -1; i <= 1; i++) {
        const d = new Date(today.getFullYear(), today.getMonth() + i, 1);
        const year = d.getFullYear();
        const month = d.getMonth() + 1;
        months.push({
            key: `${year}-${String(month).padStart(2, '0')}`,
            label: `${year}-${String(month).padStart(2, '0')}`
        });
    }

    return months;
};

// Animation variants
const dayListVariants = {
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

const WeekDayTreeSelector: React.FC<WeekDayTreeSelectorProps> = ({
    selectedDate,
    onDateChange,
}) => {
    const [centerDate, setCenterDate] = useState(selectedDate);
    const [expandedWeeks, setExpandedWeeks] = useState<Set<string>>(() => {
        // Find which week contains the selected date and expand it
        const weeks = getWeeksRange(selectedDate);
        const containingWeek = weeks.find(w =>
            w.days.some(d => d.date === selectedDate)
        );
        return new Set(containingWeek ? [containingWeek.key] : []);
    });
    const [isMonthPickerOpen, setIsMonthPickerOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    const weeks = useMemo(() => getWeeksRange(centerDate), [centerDate]);
    const months = useMemo(() => getMonthsRange(), []);

    // Get current month label from centerDate
    const currentMonthLabel = useMemo(() => {
        const d = new Date(centerDate);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
    }, [centerDate]);

    // Update expanded state when selected date changes
    useEffect(() => {
        const containingWeek = weeks.find(w =>
            w.days.some(d => d.date === selectedDate)
        );
        if (containingWeek && !expandedWeeks.has(containingWeek.key)) {
            setExpandedWeeks(prev => new Set([...prev, containingWeek.key]));
        }
    }, [selectedDate, weeks]);

    const toggleWeek = (weekKey: string) => {
        setExpandedWeeks(prev => {
            const next = new Set(prev);
            if (next.has(weekKey)) {
                next.delete(weekKey);
            } else {
                next.add(weekKey);
            }
            return next;
        });
    };

    const handleMonthSelect = (monthKey: string) => {
        // Parse month key and set center date to first day of that month
        const [year, month] = monthKey.split('-').map(Number);
        const newCenterDate = new Date(year, month - 1, 15).toISOString().split('T')[0];
        setCenterDate(newCenterDate);
        setIsMonthPickerOpen(false);
    };

    return (
        <div className="flex flex-col h-full">
            {/* Month Picker Header */}
            <div className="mb-4 relative">
                <button
                    onClick={() => setIsMonthPickerOpen(!isMonthPickerOpen)}
                    className={`flex items-center justify-between w-full p-3 border rounded-xl font-bold text-sm transition-all group ${isMonthPickerOpen
                        ? 'bg-white border-blue-200 ring-2 ring-blue-50'
                        : 'bg-slate-50 border-slate-200 hover:bg-white text-slate-700'
                        }`}
                >
                    <span className="flex items-center gap-2">
                        <Calendar size={14} className="text-slate-400" />
                        <span>{currentMonthLabel}</span>
                    </span>
                    <div className="flex items-center gap-1">
                        <div className="w-2 h-2 rounded-full bg-blue-500" />
                        <ChevronDown
                            size={14}
                            className={`text-slate-400 transition-transform duration-200 ${isMonthPickerOpen ? 'rotate-180' : ''
                                }`}
                        />
                    </div>
                </button>

                <AnimatePresence>
                    {isMonthPickerOpen && (
                        <>
                            <div
                                className="fixed inset-0 z-20"
                                onClick={() => setIsMonthPickerOpen(false)}
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
                                        className={`w-full text-left px-3 py-2.5 rounded-lg text-xs font-bold transition-colors flex items-center justify-between ${currentMonthLabel === month.key
                                            ? 'bg-blue-50 text-blue-600'
                                            : 'text-slate-600 hover:bg-slate-50'
                                            }`}
                                    >
                                        {month.label}
                                        {currentMonthLabel === month.key && <Check size={14} />}
                                    </button>
                                ))}
                            </motion.div>
                        </>
                    )}
                </AnimatePresence>
            </div>

            <span className="text-[10px] font-black text-slate-300 uppercase tracking-[0.2em] mb-2 block px-1">
                Calendar
            </span>

            {/* Tree View */}
            <div
                ref={containerRef}
                className="flex-1 overflow-y-auto scrollbar-light"
            >
                <div className="space-y-1">
                    {weeks.map(week => {
                        const isExpanded = expandedWeeks.has(week.key);
                        const hasSelectedDate = week.days.some(d => d.date === selectedDate);

                        return (
                            <div key={week.key} className="select-none">
                                {/* Week Node */}
                                <button
                                    onClick={() => toggleWeek(week.key)}
                                    className={`w-full flex items-center gap-2 px-2 py-2 rounded-lg transition-all text-left ${hasSelectedDate
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
                                    <div className="flex flex-col">
                                        <span className="text-sm font-bold">第{week.weekNum}周</span>
                                        <span className="text-[10px] text-slate-400">({week.label})</span>
                                    </div>
                                </button>

                                {/* Day List (Animated) */}
                                <AnimatePresence initial={false}>
                                    {isExpanded && (
                                        <motion.div
                                            key={`days-${week.key}`}
                                            variants={dayListVariants}
                                            initial="closed"
                                            animate="open"
                                            exit="closed"
                                            className="overflow-hidden"
                                        >
                                            <div className="pl-6 space-y-0.5 py-1">
                                                {week.days.map(day => {
                                                    const isDaySelected = selectedDate === day.date;

                                                    return (
                                                        <button
                                                            key={day.date}
                                                            onClick={() => onDateChange(day.date)}
                                                            className={`w-full flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all text-left ${isDaySelected
                                                                ? 'bg-blue-50 text-blue-600 border border-blue-200'
                                                                : day.isToday
                                                                    ? 'bg-blue-50/30 border border-blue-100 hover:bg-blue-50'
                                                                    : 'text-slate-500 hover:bg-slate-50 border border-transparent'
                                                                }`}
                                                        >
                                                            <Calendar size={14} className={isDaySelected ? 'text-blue-500' : day.isToday ? 'text-blue-400' : 'text-slate-400'} />
                                                            <div className="flex items-center gap-2">
                                                                <span className="text-xs font-bold">
                                                                    {day.dayOfWeek}
                                                                </span>
                                                                <span className={`text-[10px] ${isDaySelected || day.isToday ? 'text-blue-400' : 'text-slate-400'}`}>
                                                                    {day.date.slice(5)}
                                                                </span>
                                                                {day.isToday && (
                                                                    <span className="text-[8px] bg-blue-500 text-white px-1.5 py-0.5 rounded-full font-bold">
                                                                        TODAY
                                                                    </span>
                                                                )}
                                                            </div>
                                                            {isDaySelected && (
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

export default WeekDayTreeSelector;
