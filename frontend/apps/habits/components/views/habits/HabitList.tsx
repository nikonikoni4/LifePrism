import React, { useState } from 'react';
import { Plus, Sparkles } from 'lucide-react';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { HabitCard } from './HabitCard';
import { PausedHabitCard } from './PausedHabitCard';
import { HabitFormDialog } from '../../dialogs/HabitFormDialog';

export const HabitList: React.FC = () => {
    const { activeHabits, pausedHabits } = useHabitStore();
    const [isCreateOpen, setIsCreateOpen] = useState(false);

    return (
        <div className="col-span-12 lg:col-span-6 bg-[linear-gradient(180deg,#FFFFFF_0%,#F8FFFC_100%)] rounded-[24px] p-6 h-full flex flex-col overflow-hidden shadow-[0_10px_28px_rgba(15,23,42,0.08)] border border-emerald-100/70">
            <div className="flex items-center justify-between mb-6 shrink-0 pr-2">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em] flex items-center gap-2">
                    习惯列表 <span className="inline-flex items-center justify-center h-7 min-w-7 px-2.5 rounded-full bg-slate-100 text-slate-700 text-[11px] font-semibold shadow-sm">{activeHabits.length}</span>
                </h2>
                <div className="flex items-center gap-2">
                    <button className="min-h-10 text-xs font-semibold text-slate-600 flex items-center gap-1 hover:text-slate-900 hover:bg-slate-200 active:bg-slate-300 bg-slate-100 px-3 py-1.5 rounded-full transition-colors border border-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-400/40 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed">
                        筛选
                    </button>
                    <button
                        onClick={() => setIsCreateOpen(true)}
                        className="min-h-10 text-xs font-semibold text-white flex items-center gap-1 bg-emerald-600 hover:bg-emerald-500 active:bg-emerald-700 px-3 py-1.5 rounded-full transition-all shadow-md shadow-emerald-700/20 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Plus size={14} /> 新建习惯
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto no-scrollbar pr-2">
                {activeHabits.length === 0 && pausedHabits.length === 0 ? (
                    <div className="flex flex-col items-center justify-center h-full text-center py-16">
                        <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mb-3">
                            <Sparkles size={20} className="text-emerald-300" />
                        </div>
                        <p className="text-sm text-slate-600 font-semibold">还没有习惯</p>
                        <p className="text-xs text-slate-500 mt-1">点击「新建习惯」开始你的第一个挑战</p>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 pb-4">
                        {activeHabits.map(habit => (
                            <HabitCard key={habit.id} habit={habit} />
                        ))}
                        {pausedHabits.map(habit => (
                            <PausedHabitCard key={habit.id} habit={habit} />
                        ))}
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
