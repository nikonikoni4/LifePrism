import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { useHabitStore } from '../../../hooks/useHabitStore';
import { Habit } from '../../../types/entities';

export const TodayDashboard: React.FC = () => {
    const { activeHabits } = useHabitStore();

    const { completed, total, percentage } = useMemo(() => {
        const today = new Date().getDay(); // 0 is Sunday, 1 is Monday...
        // Map JS getDay (0-6, 0=Sun) to our backend specificDays (1-7, 1=Mon, 7=Sun)
        const currentDayStr = today === 0 ? 7 : today;

        const scheduledHabits = activeHabits.filter(h => {
            const type = h.frequency.type;
            if (type === 'daily') return true;
            if (type === 'weekdays') return currentDayStr >= 1 && currentDayStr <= 5;
            if (type === 'weekend') return currentDayStr === 6 || currentDayStr === 7;
            if (type === 'custom' && h.frequency.specificDays) {
                return h.frequency.specificDays.includes(currentDayStr);
            }
            return false;
        });

        const total = scheduledHabits.length;
        const completed = scheduledHabits.filter(h => h.todayCompleted).length;
        const percentage = total === 0 ? 0 : Math.round((completed / total) * 100);

        return { completed, total, percentage };
    }, [activeHabits]);
    return (
        <div className="flex flex-col justify-between bg-emerald-900 rounded-[24px] p-6 shadow-md border border-emerald-800 relative overflow-hidden">
            <div className="relative z-10 flex items-center justify-between mb-4">
                <h1 className="text-[12px] font-bold text-white/50 uppercase tracking-widest">Today Dashboard</h1>
                <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center border border-white/10 hover:bg-white/10 transition-colors cursor-pointer">
                    <ArrowRight size={14} className="text-white -rotate-45" />
                </div>
            </div>

            <div className="relative z-10 flex items-center justify-between mt-auto">
                <div className="flex items-baseline gap-1.5">
                    <span className="text-[54px] font-black tracking-tighter text-white leading-none">{completed}</span>
                    <span className="text-[20px] font-bold text-white/40">/{total}</span>
                </div>
                <span className="text-emerald-400 font-extrabold text-[15px] px-3.5 py-1 bg-emerald-500/10 rounded-full border border-emerald-500/20">
                    {percentage}%
                </span>
            </div>
            {/* A subtle progress bar at the bottom */}
            <div className="relative z-10 w-full h-[4px] bg-white/10 rounded-full mt-5 overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${percentage}%` }} />
            </div>

            {/* Decorative background element, optional */}
            <div className="absolute top-[-50%] right-[-10%] w-[150px] h-[150px] bg-emerald-500/20 blur-[60px] rounded-full z-0 pointer-events-none" />
        </div>
    );
};
