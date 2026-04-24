import React, { useState, useRef, useEffect } from 'react';
import { Flame, Anchor, Check, MoreHorizontal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Habit } from '../../../types/entities';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { useToast } from '../../shared/Toast';
import { HabitFormDialog } from '../../dialogs/HabitFormDialog';
import { HabitHistoryDialog } from '../../dialogs/HabitHistoryDialog';
import { useMindspaceStore } from '../../../hooks/useMindspaceStore';
import { useSettlementStore } from '../../../hooks/useSettlementStore';
import { Gem, Shield } from 'lucide-react';

interface HabitCardProps {
    habit: Habit;
}

export const HabitCard: React.FC<HabitCardProps> = ({ habit }) => {
    const { checkIn, undoCheckIn, pauseHabit, deleteHabit } = useHabitStore();
    const { openBackfill } = useSettlementStore();
    const { showToast } = useToast();

    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);

    const { values, commitments } = useMindspaceStore();
    const valueKeyword = habit.valueId ? values.find(v => v.id === habit.valueId)?.keywords : null;
    const commitmentContent = habit.commitmentId ? commitments.find(c => c.id === habit.commitmentId)?.content : null;

    const menuRef = useRef<HTMLDivElement>(null);

    // Close menu when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        if (isMenuOpen) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isMenuOpen]);

    // Determine frequency text
    const freqText = habit.frequency.type === 'daily' ? '每天' :
        habit.frequency.type === 'weekdays' ? '工作日' :
            habit.frequency.type === 'weekend' ? '周末' : '自定义';

    const weeklyDays =
        habit.frequency.type === 'daily' ? 7 :
            habit.frequency.type === 'weekdays' ? 5 :
                habit.frequency.type === 'weekend' ? 2 :
                    (habit.frequency.specificDays?.length ?? 0);

    // Progress now uses total challenge days as denominator.
    const challengeWeeks = habit.currentChallenge?.challengeWeeks ?? 0;
    const progressCurrent = habit.currentChallenge?.completedCount ?? 0;
    const progressRequired = habit.currentChallenge?.requiredCompletions ?? 0;
    const remainingRestDays = habit.currentChallenge?.remainingRestDays ?? 0;
    const progressTotal = challengeWeeks > 0 && weeklyDays > 0 ? challengeWeeks * weeklyDays : 1;
    const progressPercent = Math.min((progressCurrent / progressTotal) * 100, 100);
    const thresholdPercent = Math.min((progressRequired / progressTotal) * 100, 100);
    const challengeRemainingRequiredDays = Math.max(progressRequired - progressCurrent, 0);

    // Use todayCompleted from optimistic state, fallback to false if undefined
    const isDoneToday = habit.todayCompleted || false;
    const challengeStatusHint = !habit.currentChallenge
        ? null
        : remainingRestDays > 0
            ? `☕ 休息余额 ${remainingRestDays} 天`
            : isDoneToday
                ? '✨ 休息额度已用完，继续保持'
                : '⏳ 今日待打卡 (无剩余休息日)';
    const challengeStatusTooltip = !habit.currentChallenge
        ? ''
        : `💡 挑战进度：剩余 ${challengeRemainingRequiredDays} 天 | 目标需打卡：${progressRequired} 天 | 休息余额：${remainingRestDays} 天`;

    const pillBaseClass = 'inline-flex items-center h-7 px-3 rounded-full text-[10px] font-semibold leading-none';
    const pillNeutralClass = `${pillBaseClass} text-slate-600 bg-slate-100`;
    const pillWarningClass = `${pillBaseClass} text-amber-700 bg-amber-100`;
    const pillInfoClass = `${pillBaseClass} text-sky-700 bg-sky-100`;
    const pillSuccessClass = `${pillBaseClass} text-emerald-700 bg-emerald-100`;

    const handleCheckIn = async () => {
        try {
            await checkIn(habit.id);
        } catch {
            showToast('error', '打卡失败，请重试');
        }
    };

    const handleUndoCheckIn = async () => {
        try {
            await undoCheckIn(habit.id);
        } catch {
            showToast('error', '取消打卡失败，请重试');
        }
    };

    const handleDelete = async () => {
        const confirmed = window.electronAPI?.showConfirm
            ? await window.electronAPI.showConfirm({ message: '删除后不可恢复，确认删除？' })
            : confirm('删除后不可恢复，确认删除？');

        if (confirmed) {
            try {
                await deleteHabit(habit.id);
            } catch {
                showToast('error', '删除失败，请重试');
            }
        }
        setIsMenuOpen(false);
    };

    const handlePause = async () => {
        try {
            await pauseHabit(habit.id);
        } catch {
            showToast('error', '暂停失败，请重试');
        }
        setIsMenuOpen(false);
    };

    const handleOpenBackfill = () => {
        if (habit.currentChallenge?.id) {
            void openBackfill(habit.id, habit.currentChallenge.id);
        } else {
            showToast('error', '当前无可补录挑战');
        }
        setIsMenuOpen(false);
    };

    return (
        <>
            <div className={`min-w-[220px] bg-white rounded-[20px] p-4 shadow-[0_8px_22px_rgba(15,23,42,0.08)] border border-slate-100/70 flex flex-col justify-between transition-all hover:shadow-[0_14px_30px_rgba(15,23,42,0.12)] hover:-translate-y-0.5 duration-300 relative group min-h-[140px] ${isMenuOpen ? 'z-30' : 'z-0'}`}>

                {/* Menu Action */}
                <div className="absolute top-3 right-3 z-30" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 active:scale-95 ${isMenuOpen ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-200 opacity-0 group-hover:opacity-100'}`}
                    >
                        <MoreHorizontal size={16} />
                    </button>
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-36 bg-white rounded-xl shadow-lg border border-slate-100 py-1 overflow-hidden z-40">
                            <button
                                onClick={() => { setIsFormOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 active:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40 font-medium"
                            >
                                编辑
                            </button>
                            <button
                                onClick={handlePause}
                                className="w-full text-left px-3 py-2 text-xs text-amber-700 hover:bg-amber-50 active:bg-amber-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-400/40 font-medium"
                            >
                                暂停
                            </button>
                            <button
                                onClick={handleOpenBackfill}
                                className="w-full text-left px-3 py-2 text-xs text-indigo-700 hover:bg-indigo-50 active:bg-indigo-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/40 font-medium"
                            >
                                补录近7天
                            </button>
                            <button
                                onClick={() => { setIsHistoryOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 active:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40 font-medium"
                            >
                                历史记录
                            </button>
                            <div className="h-px bg-slate-100 my-1"></div>
                            <button
                                onClick={handleDelete}
                                className="w-full text-left px-3 py-2 text-xs text-red-700 hover:bg-red-50 active:bg-red-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-400/40 font-medium"
                            >
                                删除
                            </button>
                        </div>
                    )}
                </div>

                <div>
                    {/* Top Header of Card */}
                    <div className="flex justify-between items-start mb-2.5 pr-10">
                        <h3 className="text-[16px] font-extrabold text-slate-900 tracking-[-0.01em] leading-tight truncate pr-2">{habit.name}</h3>
                        <div className="flex flex-col items-end flex-shrink-0">
                            <span className="text-[11px] font-semibold text-slate-700">Lv.{habit.currentLevel}</span>
                        </div>
                    </div>

                    {/* Pill Tags inline */}
                    <div className="flex flex-col gap-1.5 mb-1 h-auto overflow-hidden">
                        <div className="flex flex-wrap gap-1.5">
                            <span className={`${pillNeutralClass} uppercase tracking-[0.02em]`}>
                                {freqText}
                            </span>
                            {habit.streak > 0 && (
                                <span className={`${pillWarningClass} gap-1 tracking-[0.01em]`}>
                                    <Flame size={10} className="fill-amber-500" strokeWidth={2} /> {habit.streak}
                                </span>
                            )}
                            {habit.anchorInfo && (
                                <span className={`${pillInfoClass} gap-1 truncate max-w-[150px]`}>
                                    <Anchor size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                    <span className="truncate">{habit.anchorInfo.triggerTime || ''} {habit.anchorInfo.nodeName}</span>
                                </span>
                            )}
                        </div>
                        {(valueKeyword || commitmentContent) && (
                            <div className="flex flex-wrap gap-1.5">
                                {valueKeyword && (
                                    <span className={`${pillInfoClass} gap-1 truncate max-w-[120px]`} title={valueKeyword}>
                                        <Gem size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                        <span className="truncate">{valueKeyword}</span>
                                    </span>
                                )}
                                {commitmentContent && (
                                    <span className={`${pillSuccessClass} gap-1 truncate max-w-[160px]`} title={commitmentContent}>
                                        <Shield size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                        <span className="truncate">{commitmentContent}</span>
                                    </span>
                                )}
                            </div>
                        )}
                    </div>
                </div>

                {/* Bottom Actions of Card */}
                <div className="flex items-center justify-between mt-auto">
                    <div className="flex-1 mr-4">
                        {habit.currentChallenge && challengeStatusHint && (
                            <div className="mb-1 flex justify-start">
                                <span
                                    className="text-[10px] font-medium text-slate-600"
                                    title={challengeStatusTooltip}
                                >
                                    {challengeStatusHint}
                                </span>
                            </div>
                        )}
                        <div className="flex justify-between items-center mb-1">
                            <span className="text-[10px] font-semibold text-slate-500 tracking-[0.02em]">PROGRESS</span>
                            <span className="text-[10px] font-semibold text-slate-600 tracking-[0.01em]">
                                {progressCurrent}/{progressTotal}
                            </span>
                        </div>
                        <div className="relative h-[6px] w-full rounded-full bg-[#F4F5F7]">
                            <div className="absolute inset-0 overflow-hidden rounded-full">
                                <div className="h-full bg-neutral-900 rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }} />
                            </div>
                            {habit.currentChallenge && (
                                <div
                                    className="absolute top-1/2 z-20 h-[6px] w-[3px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-red-600 shadow-[0_0_0_1px_rgba(255,255,255,0.95),0_0_8px_rgba(220,38,38,0.55)]"
                                    style={{ left: `${thresholdPercent}%` }}
                                    title={`最低达标线: ${progressRequired}/${progressTotal}`}
                                />
                            )}
                        </div>
                    </div>
                    <AnimatePresence mode="wait">
                        {isDoneToday ? (
                            <motion.button
                                key="done"
                                initial={{ scale: 0.8, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                exit={{ scale: 0.8, opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                onClick={handleUndoCheckIn}
                                disabled={habit.isCheckingIn}
                                className={`min-h-10 min-w-[84px] flex items-center justify-center bg-emerald-50 text-emerald-700 px-2.5 py-1.5 rounded-full text-[9px] font-semibold tracking-[0.01em] transition-colors border border-emerald-200 hover:bg-emerald-100 active:bg-emerald-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${habit.isCheckingIn ? 'opacity-50 cursor-not-allowed' : ''}`}>
                                <Check size={12} strokeWidth={3} className="mr-1" /> DONE
                            </motion.button>
                        ) : (
                            <motion.button
                                key="checkin"
                                initial={{ scale: 0.8, opacity: 0 }}
                                animate={{ scale: 1, opacity: 1 }}
                                exit={{ scale: 0.8, opacity: 0 }}
                                transition={{ duration: 0.2 }}
                                onClick={handleCheckIn}
                                disabled={habit.isCheckingIn}
                                className={`min-h-10 min-w-[82px] flex items-center justify-center bg-emerald-600 text-white px-2.5 py-1 rounded-full text-[10px] font-semibold tracking-[0.01em] transition-all shadow-md shadow-emerald-700/20 hover:bg-emerald-500 active:bg-emerald-700 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${habit.isCheckingIn ? 'opacity-50 cursor-not-allowed' : ''}`}>
                                CHECK IN
                            </motion.button>
                        )}
                    </AnimatePresence>
                </div>
            </div>

            {/* Dialogs */}
            <HabitFormDialog
                isOpen={isFormOpen}
                onClose={() => setIsFormOpen(false)}
                habit={habit}
            />
            <HabitHistoryDialog
                isOpen={isHistoryOpen}
                onClose={() => setIsHistoryOpen(false)}
                habit={habit}
            />
        </>
    );
};
