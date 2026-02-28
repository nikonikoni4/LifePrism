import React, { useMemo } from 'react';
import { format, subDays, isBefore, parseISO } from 'date-fns';
import { ChevronLeft, Calendar, AlertCircle } from 'lucide-react';
import { useSettlementStore } from '../../hooks/useSettlementStore';
import { useHabitStore } from '../../hooks/useHabitStore';

interface BackfillViewProps {
    onBack?: () => void;
}

export const SettlementBackfillView: React.FC<BackfillViewProps> = ({ onBack }) => {
    const { backfillState, backfill, closeBackfill } = useSettlementStore();
    const { activeHabits } = useHabitStore();
    const [selectedDates, setSelectedDates] = React.useState<Set<string>>(new Set());
    const [completedDates, setCompletedDates] = React.useState<Set<string>>(new Set());
    const [error, setError] = React.useState<string | null>(null);

    if (!backfillState) return null;

    const habit = activeHabits.find(h => h.id === backfillState.habitId);
    const challengeStartDate = habit?.currentChallenge?.startDate;

    // 生成近7天日期列表（today-6 到 today-1）
    const backfillDays = useMemo(() => {
        const today = new Date();
        const days: { date: string; label: string; disabled: boolean }[] = [];
        for (let i = 6; i >= 1; i--) {
            const d = subDays(today, i);
            const dateStr = format(d, 'yyyy-MM-dd');
            const disabled = challengeStartDate
                ? isBefore(d, parseISO(challengeStartDate))
                : false;
            days.push({
                date: dateStr,
                label: format(d, 'MM/dd (EEE)'),
                disabled: disabled || completedDates.has(dateStr),
            });
        }
        return days;
    }, [challengeStartDate, completedDates]);

    const toggleDate = (date: string) => {
        setSelectedDates(prev => {
            const next = new Set(prev);
            if (next.has(date)) next.delete(date);
            else next.add(date);
            return next;
        });
    };

    const handleConfirm = async () => {
        if (selectedDates.size === 0) return;
        setError(null);
        const sorted = Array.from(selectedDates).sort();
        for (const date of sorted) {
            try {
                await backfill(backfillState.habitId, date);
                setCompletedDates(prev => new Set(prev).add(date));
                setSelectedDates(prev => {
                    const next = new Set(prev);
                    next.delete(date);
                    return next;
                });
            } catch (err) {
                setError(err instanceof Error ? err.message : '补录失败');
                break;
            }
        }
    };

    const handleBack = () => {
        closeBackfill();
        onBack?.();
    };

    return (
        <div className="flex flex-col h-full">
            {/* Header */}
            <div className="flex items-center gap-2 px-6 py-4 border-b border-slate-100 shrink-0">
                <button
                    onClick={handleBack}
                    className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors"
                >
                    <ChevronLeft size={18} />
                </button>
                <div>
                    <h3 className="text-sm font-bold text-slate-800">补录打卡</h3>
                    <p className="text-xs text-slate-500">{habit?.name ?? '未知习惯'}</p>
                </div>
            </div>

            {/* Date List */}
            <div className="flex-1 overflow-y-auto px-6 py-4 space-y-2">
                <p className="text-xs text-slate-500 mb-3 flex items-center gap-1.5">
                    <Calendar size={12} />
                    选择需要补录的日期（近7天）
                </p>
                {backfillDays.map(day => (
                    <label
                        key={day.date}
                        className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors cursor-pointer ${
                            day.disabled
                                ? 'bg-slate-50 border-slate-100 opacity-50 cursor-not-allowed'
                                : completedDates.has(day.date)
                                    ? 'bg-emerald-50 border-emerald-200'
                                    : selectedDates.has(day.date)
                                        ? 'bg-indigo-50 border-indigo-300'
                                        : 'bg-white border-slate-200 hover:border-slate-300'
                        }`}
                    >
                        <input
                            type="checkbox"
                            checked={selectedDates.has(day.date) || completedDates.has(day.date)}
                            disabled={day.disabled || completedDates.has(day.date)}
                            onChange={() => toggleDate(day.date)}
                            className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className={`text-sm ${completedDates.has(day.date) ? 'text-emerald-700 font-medium' : 'text-slate-700'}`}>
                            {day.label}
                        </span>
                        {completedDates.has(day.date) && (
                            <span className="ml-auto text-xs text-emerald-600 font-medium">已补录</span>
                        )}
                    </label>
                ))}
            </div>

            {/* Footer */}
            <div className="px-6 py-4 border-t border-slate-100 shrink-0 space-y-2">
                {(error || backfillState.error) && (
                    <div className="flex items-center gap-2 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">
                        <AlertCircle size={14} />
                        {error || backfillState.error}
                    </div>
                )}
                <div className="flex gap-2">
                    <button
                        onClick={handleBack}
                        className="flex-1 px-4 py-2.5 text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-xl transition-colors"
                    >
                        返回
                    </button>
                    <button
                        onClick={handleConfirm}
                        disabled={selectedDates.size === 0 || backfillState.isProcessing}
                        className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed rounded-xl transition-colors"
                    >
                        {backfillState.isProcessing ? '补录中...' : `确认补录 (${selectedDates.size})`}
                    </button>
                </div>
            </div>
        </div>
    );
};
