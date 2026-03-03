import React from 'react';
import { format, parseISO } from 'date-fns';
import { ChevronLeft, Calendar, AlertCircle } from 'lucide-react';
import { useSettlementStore } from '../../hooks/useSettlementStore';
import { useHabitStore } from '../../hooks/useHabitStore';

interface BackfillViewProps {
    onBack?: () => void;
}

export const SettlementBackfillView: React.FC<BackfillViewProps> = ({ onBack }) => {
    const { backfillState, backfill, closeBackfill } = useSettlementStore();
    const { activeHabits } = useHabitStore();
    const [selectedDate, setSelectedDate] = React.useState<string | null>(null);
    const [error, setError] = React.useState<string | null>(null);

    const activeHabitId = backfillState?.habitId ?? null;
    const challengeId = backfillState?.challengeId ?? null;
    const habit = activeHabitId ? activeHabits.find(h => h.id === activeHabitId) : undefined;
    const backfillDays = backfillState?.days ?? [];

    const handleConfirm = async () => {
        if (!activeHabitId || !challengeId || !selectedDate) return;
        setError(null);
        try {
            await backfill(activeHabitId, challengeId, selectedDate);
            setSelectedDate(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : '补录失败');
        }
    };

    const handleBack = () => {
        closeBackfill();
        onBack?.();
    };

    if (!activeHabitId || !challengeId || !backfillState) return null;

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
                {backfillState.isLoading && (
                    <div className="text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded-xl px-4 py-3">
                        正在加载可补录日期...
                    </div>
                )}
                {backfillDays.map(day => (
                    <label
                        key={day.date}
                        className={`flex items-center gap-3 px-4 py-3 rounded-xl border transition-colors cursor-pointer ${
                            !day.selectable
                                ? 'bg-slate-50 border-slate-100 opacity-50 cursor-not-allowed'
                                : selectedDate === day.date
                                    ? 'bg-indigo-50 border-indigo-300'
                                    : 'bg-white border-slate-200 hover:border-slate-300'
                        }`}
                    >
                        <input
                            type="radio"
                            name="backfill-date"
                            checked={selectedDate === day.date}
                            disabled={!day.selectable}
                            onChange={() => setSelectedDate(day.date)}
                            className="w-4 h-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        />
                        <span className="text-sm text-slate-700">
                            {format(parseISO(day.date), 'MM/dd (EEE)')}
                        </span>
                        {!day.selectable && day.reason === 'already_checked_in' && (
                            <span className="ml-auto text-xs text-slate-500 font-medium">已打卡</span>
                        )}
                        {!day.selectable && day.reason === 'before_challenge_start' && (
                            <span className="ml-auto text-xs text-slate-500 font-medium">挑战开始前</span>
                        )}
                        {!day.selectable && day.reason === 'after_challenge_end' && (
                            <span className="ml-auto text-xs text-slate-500 font-medium">挑战结束后</span>
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
                        disabled={!selectedDate || backfillState.isProcessing || backfillState.isLoading}
                        className="flex-1 px-4 py-2.5 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 disabled:bg-slate-300 disabled:cursor-not-allowed rounded-xl transition-colors"
                    >
                        {backfillState.isProcessing ? '补录中...' : '确认补录'}
                    </button>
                </div>
            </div>
        </div>
    );
};
