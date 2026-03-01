import React, { useState, useRef, useEffect } from 'react';
import { Flame, Anchor, Check, MoreHorizontal } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { Habit } from '../../../types/entities';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { useToast } from '../../shared/Toast';
import { HabitFormDialog } from '../../dialogs/HabitFormDialog';
import { HabitHistoryDialog } from '../../dialogs/HabitHistoryDialog';
import { useMindspaceStore } from '../../../hooks/useMindspaceStore';
import { Gem, Shield } from 'lucide-react';

interface HabitCardProps {
    habit: Habit;
}

export const HabitCard: React.FC<HabitCardProps> = ({ habit }) => {
    const { checkIn, undoCheckIn, pauseHabit, deleteHabit } = useHabitStore();
    const { showToast } = useToast();

    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);

    const { values, commitments } = useMindspaceStore();
    const valueKeyword = habit.valueId ? values.find(v => v.id === habit.valueId)?.keyword : null;
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

    // Fallback values for progress if no challenge active
    const progressCurrent = habit.currentChallenge?.completedCount || 0;
    const progressTotal = habit.currentChallenge?.requiredCompletions || 1;
    const progressPercent = Math.min((progressCurrent / progressTotal) * 100, 100);

    // Use todayCompleted from optimistic state, fallback to false if undefined
    const isDoneToday = habit.todayCompleted || false;

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
        if (window.confirm('删除后不可恢复，确认删除？')) {
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

    return (
        <>
            <div className="min-w-[220px] bg-slate-50 rounded-[20px] p-4 border border-neutral-100 flex flex-col justify-between transition-transform hover:-translate-y-0.5 hover:bg-slate-100 duration-300 relative group min-h-[140px]">

                {/* Menu Action */}
                <div className="absolute top-3 right-3 z-10" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1 rounded-md transition-colors ${isMenuOpen ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-200 opacity-0 group-hover:opacity-100'}`}
                    >
                        <MoreHorizontal size={16} />
                    </button>
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-xl shadow-lg border border-slate-100 py-1 overflow-hidden">
                            <button
                                onClick={() => { setIsFormOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                            >
                                编辑
                            </button>
                            <button
                                onClick={handlePause}
                                className="w-full text-left px-3 py-2 text-xs text-amber-600 hover:bg-amber-50 font-medium"
                            >
                                暂停
                            </button>
                            <button
                                onClick={() => { setIsHistoryOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                            >
                                历史记录
                            </button>
                            <div className="h-px bg-slate-100 my-1"></div>
                            <button
                                onClick={handleDelete}
                                className="w-full text-left px-3 py-2 text-xs text-red-600 hover:bg-red-50 font-medium"
                            >
                                删除
                            </button>
                        </div>
                    )}
                </div>

                <div>
                    {/* Top Header of Card */}
                    <div className="flex justify-between items-start mb-2.5">
                        <h3 className="text-[15px] font-bold text-neutral-900 tracking-tight leading-tight truncate pr-6">{habit.name}</h3>
                        <div className="flex flex-col items-end flex-shrink-0">
                            <span className="text-[10px] font-black text-neutral-800">Lv.{habit.currentLevel}</span>
                        </div>
                    </div>

                    {/* Pill Tags inline */}
                    <div className="flex flex-col gap-1.5 mb-1 h-auto overflow-hidden">
                        <div className="flex flex-wrap gap-1.5">
                            <span className="flex items-center bg-[#F4F5F7] px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wide text-neutral-500 uppercase">
                                {freqText}
                            </span>
                            {habit.streak > 0 && (
                                <span className="flex items-center gap-1 text-[9px] font-bold text-amber-600 bg-amber-50 px-2 py-0.5 rounded-md tracking-wide">
                                    <Flame size={10} className="fill-amber-500" strokeWidth={2} /> {habit.streak}
                                </span>
                            )}
                            {habit.anchorInfo && (
                                <span className="flex items-center gap-1 text-blue-600 bg-blue-50/60 px-2 py-0.5 rounded-full text-[9px] font-bold truncate max-w-[120px]">
                                    <Anchor size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                    <span className="truncate">{habit.anchorInfo.triggerTime || ''} {habit.anchorInfo.nodeName}</span>
                                </span>
                            )}
                        </div>
                        {(valueKeyword || commitmentContent) && (
                            <div className="flex flex-wrap gap-1.5">
                                {valueKeyword && (
                                    <span className="flex items-center gap-1 text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded-full text-[9px] font-bold truncate max-w-[100px]" title={valueKeyword}>
                                        <Gem size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                        <span className="truncate">{valueKeyword}</span>
                                    </span>
                                )}
                                {commitmentContent && (
                                    <span className="flex items-center gap-1 text-teal-600 bg-teal-50 px-2 py-0.5 rounded-full text-[9px] font-bold truncate max-w-[140px]" title={commitmentContent}>
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
                        <div className="flex justify-between items-center mb-1">
                            <span className="text-[9px] font-bold text-neutral-400 tracking-wider">PROGRESS</span>
                            <span className="text-[9px] font-bold text-neutral-500 tracking-wider">
                                {progressCurrent}/{progressTotal}
                            </span>
                        </div>
                        <div className="h-[4px] w-full bg-[#F4F5F7] rounded-full overflow-hidden">
                            <div className="h-full bg-neutral-900 rounded-full transition-all duration-500" style={{ width: `${progressPercent}%` }} />
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
                                className={`flex items-center justify-center bg-emerald-50 text-emerald-600 px-3 py-1.5 rounded-md text-[10px] font-bold transition-colors hover:bg-emerald-100 border border-emerald-100/50 ${habit.isCheckingIn ? 'opacity-50 cursor-not-allowed' : ''}`}>
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
                                className={`flex items-center justify-center bg-neutral-900 text-white px-4 py-1.5 rounded-md text-[10px] font-bold transition-all hover:bg-neutral-800 hover:scale-105 active:scale-95 shadow-md shadow-neutral-900/20 ${habit.isCheckingIn ? 'opacity-50 cursor-not-allowed' : ''}`}>
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
