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
        <div className="col-span-12 lg:col-span-6 bg-white rounded-[24px] p-6 h-full flex flex-col overflow-hidden shadow-[0_8px_30px_rgb(0,0,0,0.08)] border-none">
            <div className="flex items-center justify-between mb-6 shrink-0 pr-2">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest flex items-center gap-2">
                    Active Habits <span className="bg-[#F4F5F7] text-neutral-600 text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm">{activeHabits.length}</span>
                </h2>
                <div className="flex items-center gap-2">
                    <button className="text-xs font-bold text-neutral-400 flex items-center gap-1 hover:text-neutral-900 bg-[#F4F5F7] px-3 py-1.5 rounded-full transition-colors border border-neutral-100">
                        Filters
                    </button>
                    <button
                        onClick={() => setIsCreateOpen(true)}
                        className="text-xs font-bold text-white flex items-center gap-1 bg-neutral-900 hover:bg-neutral-800 px-3 py-1.5 rounded-full transition-all shadow-md active:scale-95"
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
                        <p className="text-sm text-slate-400 font-medium">还没有习惯</p>
                        <p className="text-xs text-slate-300 mt-1">点击「新建习惯」开始你的第一个挑战</p>
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
