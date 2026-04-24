import React, { useState, useRef, useEffect } from 'react';
import { Play, MoreHorizontal } from 'lucide-react';
import { Habit } from '../../../types/entities';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { useToast } from '../../shared/Toast';
import { HabitFormDialog } from '../../dialogs/HabitFormDialog';
import { HabitHistoryDialog } from '../../dialogs/HabitHistoryDialog';
import { useMindspaceStore } from '../../../hooks/useMindspaceStore';
import { Gem, Shield } from 'lucide-react';

interface PausedHabitCardProps {
    habit: Habit;
}

export const PausedHabitCard: React.FC<PausedHabitCardProps> = ({ habit }) => {
    const { resumeHabit, deleteHabit } = useHabitStore();
    const { showToast } = useToast();

    const [isMenuOpen, setIsMenuOpen] = useState(false);
    const [isFormOpen, setIsFormOpen] = useState(false);
    const [isHistoryOpen, setIsHistoryOpen] = useState(false);

    const { values, commitments } = useMindspaceStore();
    const valueKeyword = habit.valueId ? values.find(v => v.id === habit.valueId)?.keywords : null;
    const commitmentContent = habit.commitmentId ? commitments.find(c => c.id === habit.commitmentId)?.content : null;

    const menuRef = useRef<HTMLDivElement>(null);
    const pillBaseClass = 'inline-flex items-center h-7 px-3 rounded-full text-[10px] font-semibold leading-none';
    const pillNeutralClass = `${pillBaseClass} text-slate-600 bg-slate-100`;
    const pillInfoClass = `${pillBaseClass} text-sky-700 bg-sky-100`;
    const pillSuccessClass = `${pillBaseClass} text-emerald-700 bg-emerald-100`;

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
                setIsMenuOpen(false);
            }
        };
        if (isMenuOpen) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isMenuOpen]);

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

    const handleResume = async () => {
        try {
            await resumeHabit(habit.id);
        } catch {
            showToast('error', '恢复失败，请重试');
        }
        setIsMenuOpen(false);
    };

    return (
        <>
            <div className={`bg-white/70 border border-dashed border-slate-300 rounded-[20px] p-4 flex flex-col justify-center min-h-[140px] group relative hover:bg-slate-50/90 hover:border-slate-400 transition-colors shadow-[0_6px_18px_rgba(15,23,42,0.05)] ${isMenuOpen ? 'z-30' : 'z-0'}`}>

                {/* Menu Action */}
                <div className="absolute top-3 right-3 z-10" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 active:scale-95 ${isMenuOpen ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-200 opacity-0 group-hover:opacity-100'}`}
                    >
                        <MoreHorizontal size={16} />
                    </button>
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-xl shadow-lg border border-slate-100 py-1 overflow-hidden z-40">
                            <button
                                onClick={() => { setIsFormOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 active:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40 font-medium"
                            >
                                编辑
                            </button>
                            <button
                                onClick={handleResume}
                                className="w-full text-left px-3 py-2 text-xs text-emerald-700 hover:bg-emerald-50 active:bg-emerald-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/40 font-medium"
                            >
                                恢复
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

                <div className="flex justify-between items-center mb-3 pr-6">
                    <h3 className="text-[15px] font-semibold text-slate-500 line-through decoration-slate-300 truncate">{habit.name}</h3>
                </div>
                <div className="flex flex-col gap-1.5 mt-auto w-full">
                    {(valueKeyword || commitmentContent) && (
                        <div className="flex flex-wrap gap-1.5 overflow-hidden">
                            {valueKeyword && (
                                <span className={`${pillInfoClass} gap-1 truncate max-w-[100px]`} title={valueKeyword}>
                                    <Gem size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                    <span className="truncate">{valueKeyword}</span>
                                </span>
                            )}
                            {commitmentContent && (
                                <span className={`${pillSuccessClass} gap-1 truncate max-w-[130px]`} title={commitmentContent}>
                                    <Shield size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                    <span className="truncate">{commitmentContent}</span>
                                </span>
                            )}
                        </div>
                    )}
                    <div className="flex items-center gap-2">
                        <span className={`${pillNeutralClass} uppercase tracking-[0.02em] border border-slate-200`}>Paused</span>
                        <button
                            onClick={handleResume}
                            className="min-h-10 text-[10px] font-semibold text-slate-600 ml-auto flex items-center gap-1 hover:text-emerald-700 active:text-emerald-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed opacity-0 group-hover:opacity-100 transition-opacity">
                            <Play size={10} className="fill-current mr-1" /> Resume
                        </button>
                    </div>
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
