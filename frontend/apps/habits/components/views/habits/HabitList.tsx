import React, { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Plus, Sparkles } from 'lucide-react';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { HabitCard } from './HabitCard';
import { PausedHabitCard } from './PausedHabitCard';
import { HabitFormDialog } from '../../dialogs/HabitFormDialog';

type HabitFilter = 'all' | 'active' | 'paused';

const FILTER_OPTIONS: Array<{ key: HabitFilter; label: string }> = [
    { key: 'all', label: '全部' },
    { key: 'active', label: '激活' },
    { key: 'paused', label: '暂定' }
];

export const HabitList: React.FC = () => {
    const { activeHabits, pausedHabits } = useHabitStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [isFilterOpen, setIsFilterOpen] = useState(false);
    const [filter, setFilter] = useState<HabitFilter>('all');
    const filterMenuRef = useRef<HTMLDivElement>(null);

    const totalHabits = activeHabits.length + pausedHabits.length;
    const showActiveSection = filter === 'all' || filter === 'active';
    const showPausedSection = filter === 'all' || filter === 'paused';
    const selectedFilterLabel = FILTER_OPTIONS.find(option => option.key === filter)?.label ?? '全部';

    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (filterMenuRef.current && !filterMenuRef.current.contains(event.target as Node)) {
                setIsFilterOpen(false);
            }
        };
        if (isFilterOpen) {
            document.addEventListener('mousedown', handleClickOutside);
        }
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isFilterOpen]);

    return (
        <div className="col-span-12 lg:col-span-6 bg-[linear-gradient(180deg,#FFFFFF_0%,#F8FFFC_100%)] rounded-[24px] p-6 h-full flex flex-col overflow-hidden shadow-[0_10px_28px_rgba(15,23,42,0.08)] border border-emerald-100/70">
            <div className="flex items-center justify-between mb-6 shrink-0 pr-2">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em] flex items-center gap-2">
                    习惯列表 <span className="inline-flex items-center justify-center h-7 min-w-7 px-2.5 rounded-full bg-slate-100 text-slate-700 text-[11px] font-semibold shadow-sm">{totalHabits}</span>
                </h2>
                <div className="flex items-center gap-2">
                    <div className="relative" ref={filterMenuRef}>
                        <button
                            onClick={() => setIsFilterOpen(prev => !prev)}
                            className="min-h-10 text-xs font-semibold text-slate-600 flex items-center gap-1 hover:text-slate-900 hover:bg-slate-200 active:bg-slate-300 bg-slate-100 px-3 py-1.5 rounded-full transition-colors border border-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40 focus-visible:ring-offset-2"
                        >
                            筛选：{selectedFilterLabel}
                            <ChevronDown size={14} className={`transition-transform ${isFilterOpen ? 'rotate-180' : ''}`} />
                        </button>
                        {isFilterOpen && (
                            <div className="absolute right-0 top-full mt-1.5 w-28 bg-white rounded-xl shadow-lg border border-slate-100 py-1 overflow-hidden z-20">
                                {FILTER_OPTIONS.map(option => (
                                    <button
                                        key={option.key}
                                        onClick={() => {
                                            setFilter(option.key);
                                            setIsFilterOpen(false);
                                        }}
                                        className={`w-full text-left px-3 py-2 text-xs hover:bg-slate-50 active:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40 font-medium flex items-center justify-between ${filter === option.key ? 'text-emerald-700' : 'text-slate-700'}`}
                                    >
                                        <span>{option.label}</span>
                                        {filter === option.key && <Check size={12} />}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                    <button
                        onClick={() => setIsCreateOpen(true)}
                        className="min-h-10 text-xs font-semibold text-white flex items-center gap-1 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 px-3 py-1.5 rounded-full transition-all shadow-md shadow-emerald-700/20 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Plus size={14} /> 新建习惯
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar pr-2">
                {totalHabits === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-16">
                        <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mb-3">
                            <Sparkles size={20} className="text-emerald-300" />
                        </div>
                        <p className="text-sm text-slate-600 font-semibold">还没有习惯</p>
                        <p className="text-xs text-slate-500 mt-1">点击「新建习惯」开始你的第一个挑战</p>
                    </div>
                ) : (
                    <div className="flex flex-col gap-5 pb-4">
                        {showActiveSection && (
                            <section className="space-y-3">
                                <div className="flex items-center gap-2 px-1">
                                    <span className="h-2 w-2 rounded-full bg-emerald-500" />
                                    <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-[0.03em]">激活习惯</h3>
                                    <span className="text-[11px] text-slate-500">{activeHabits.length}</span>
                                </div>
                                {activeHabits.length === 0 ? (
                                    <p className="text-xs text-slate-500 px-1">暂无激活习惯</p>
                                ) : (
                                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                                        {activeHabits.map(habit => (
                                            <HabitCard key={habit.id} habit={habit} />
                                        ))}
                                    </div>
                                )}
                            </section>
                        )}

                        {showPausedSection && (
                            <section className="space-y-3">
                                <div className="flex items-center gap-2 px-1">
                                    <span className="h-2 w-2 rounded-full bg-slate-400" />
                                    <h3 className="text-xs font-semibold text-slate-700 uppercase tracking-[0.03em]">暂定习惯</h3>
                                    <span className="text-[11px] text-slate-500">{pausedHabits.length}</span>
                                </div>
                                {pausedHabits.length === 0 ? (
                                    <p className="text-xs text-slate-500 px-1">暂无暂定习惯</p>
                                ) : (
                                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
                                        {pausedHabits.map(habit => (
                                            <PausedHabitCard key={habit.id} habit={habit} />
                                        ))}
                                    </div>
                                )}
                            </section>
                        )}
                    </div>
                )}
            </div>

            <HabitFormDialog
                isOpen={isCreateOpen}
                onClose={() => setIsCreateOpen(false)}
            />
        </div>
    );
};
