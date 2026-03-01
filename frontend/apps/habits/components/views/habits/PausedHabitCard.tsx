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
    const valueKeyword = habit.valueId ? values.find(v => v.id === habit.valueId)?.keyword : null;
    const commitmentContent = habit.commitmentId ? commitments.find(c => c.id === habit.commitmentId)?.content : null;

    const menuRef = useRef<HTMLDivElement>(null);

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
        if (window.confirm('删除后不可恢复，确认删除？')) {
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
            <div className="bg-[#F4F5F7]/50 border border-dashed border-neutral-300 rounded-[20px] p-4 flex flex-col justify-center min-h-[140px] group relative hover:bg-[#F4F5F7] hover:border-neutral-400 transition-colors">

                {/* Menu Action */}
                <div className="absolute top-3 right-3 z-10" ref={menuRef}>
                    <button
                        onClick={() => setIsMenuOpen(!isMenuOpen)}
                        className={`p-1 rounded-md transition-colors ${isMenuOpen ? 'bg-slate-200 text-slate-800' : 'text-slate-400 hover:text-slate-600 hover:bg-slate-200 opacity-0 group-hover:opacity-100'}`}
                    >
                        <MoreHorizontal size={16} />
                    </button>
                    {isMenuOpen && (
                        <div className="absolute right-0 top-full mt-1 w-32 bg-white rounded-xl shadow-lg border border-slate-100 py-1 overflow-hidden z-20">
                            <button
                                onClick={() => { setIsFormOpen(true); setIsMenuOpen(false); }}
                                className="w-full text-left px-3 py-2 text-xs text-slate-700 hover:bg-slate-50 font-medium"
                            >
                                编辑
                            </button>
                            <button
                                onClick={handleResume}
                                className="w-full text-left px-3 py-2 text-xs text-emerald-600 hover:bg-emerald-50 font-medium"
                            >
                                恢复
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

                <div className="flex justify-between items-center mb-3 pr-6">
                    <h3 className="text-[14px] font-bold text-neutral-400 line-through decoration-neutral-300 truncate">{habit.name}</h3>
                </div>
                <div className="flex flex-col gap-1.5 mt-auto w-full">
                    {(valueKeyword || commitmentContent) && (
                        <div className="flex flex-wrap gap-1.5 overflow-hidden">
                            {valueKeyword && (
                                <span className="flex items-center gap-1 text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded-full text-[9px] font-bold truncate max-w-[80px]" title={valueKeyword}>
                                    <Gem size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                    <span className="truncate">{valueKeyword}</span>
                                </span>
                            )}
                            {commitmentContent && (
                                <span className="flex items-center gap-1 text-neutral-400 bg-neutral-100 px-2 py-0.5 rounded-full text-[9px] font-bold truncate max-w-[100px]" title={commitmentContent}>
                                    <Shield size={10} strokeWidth={2.5} className="flex-shrink-0" />
                                    <span className="truncate">{commitmentContent}</span>
                                </span>
                            )}
                        </div>
                    )}
                    <div className="flex items-center gap-2">
                        <span className="bg-white text-neutral-400 px-2 py-0.5 rounded-full text-[9px] font-bold tracking-wide uppercase border border-neutral-200 flex-shrink-0">Paused</span>
                        <button
                            onClick={handleResume}
                            className="text-[10px] font-bold text-neutral-400 ml-auto flex items-center gap-1 hover:text-emerald-600 opacity-0 group-hover:opacity-100 transition-opacity">
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
