import React from 'react';
import { ArrowRight } from 'lucide-react';
import { useStatsStore } from '../../../hooks/useStatsStore';

export const TodayDashboard: React.FC = () => {
    const { todayOverview } = useStatsStore();

    const completed = todayOverview?.completedCount ?? 0;
    const total = todayOverview?.scheduledCount ?? 0;
    const percentage = todayOverview?.completionRate != null
        ? Math.round(todayOverview.completionRate * 100)
        : (total === 0 ? 0 : Math.round((completed / total) * 100));
    const isRestDay = todayOverview?.isRestDay ?? false;

    return (
        <div className="flex flex-col justify-between bg-emerald-900 rounded-[24px] p-6 shadow-md border border-emerald-800 relative overflow-hidden">
            <div className="relative z-10 flex items-center justify-between mb-4">
                <h1 className="text-[12px] font-bold text-white/50 uppercase tracking-widest">Today Dashboard</h1>
                <div className="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center border border-white/10 hover:bg-white/10 transition-colors cursor-pointer">
                    <ArrowRight size={14} className="text-white -rotate-45" />
                </div>
            </div>

            <div className="relative z-10 flex items-center justify-between mt-auto">
                {isRestDay ? (
                    <span className="text-[20px] font-bold text-white/60">休息日</span>
                ) : (
                    <div className="flex items-baseline gap-1.5">
                        <span className="text-[54px] font-black tracking-tighter text-white leading-none">{completed}</span>
                        <span className="text-[20px] font-bold text-white/40">/{total}</span>
                    </div>
                )}
                <span className="text-emerald-400 font-extrabold text-[15px] px-3.5 py-1 bg-emerald-500/10 rounded-full border border-emerald-500/20">
                    {percentage}%
                </span>
            </div>
            <div className="relative z-10 w-full h-[4px] bg-white/10 rounded-full mt-5 overflow-hidden">
                <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${percentage}%` }} />
            </div>

            <div className="absolute top-[-50%] right-[-10%] w-[150px] h-[150px] bg-emerald-500/20 blur-[60px] rounded-full z-0 pointer-events-none" />
        </div>
    );
};
