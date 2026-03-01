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
        <div className="bg-white rounded-[24px] p-6 shadow-sm border border-neutral-100 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 relative overflow-hidden">
            {/* Background Decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-50/50 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none" />

            {/* Title & Stats */}
            <div className="flex flex-col relative z-10 w-full sm:w-auto">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest mb-2">Today Dashboard</h2>
                <div className="flex items-baseline gap-1.5">
                    {isRestDay ? (
                        <span className="text-[20px] font-bold text-neutral-600">休息日</span>
                    ) : (
                        <>
                            <span className="text-[44px] font-black tracking-tighter text-neutral-900 leading-none">{completed}</span>
                            <span className="text-[18px] font-bold text-neutral-300">/{total}</span>
                        </>
                    )}
                </div>
            </div>

            {/* Progress Layout */}
            <div className="flex-1 w-full max-w-lg relative z-10 mt-4 sm:mt-0">
                <div className="flex items-center justify-between mb-3">
                    <span className="text-[13px] font-bold text-neutral-600">今日进度</span>
                    <span className="text-emerald-600 font-extrabold text-[14px] px-3.5 py-1 bg-[#F0FDF4] rounded-full border border-emerald-100 shadow-sm">
                        {percentage}%
                    </span>
                </div>
                <div className="h-[8px] w-full bg-slate-100 rounded-full overflow-hidden">
                    <div className="h-full bg-emerald-500 rounded-full transition-all duration-500" style={{ width: `${percentage}%` }} />
                </div>
            </div>

            {/* Detail Arrow */}
            <div className="hidden sm:flex w-10 h-10 shrink-0 rounded-full bg-white items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer border border-neutral-100 shadow-sm relative z-10 ml-4">
                <ArrowRight size={16} className="text-neutral-400 -rotate-45" />
            </div>
        </div>
    );
};
