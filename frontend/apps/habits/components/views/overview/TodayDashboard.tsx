import React from 'react';
import { ArrowRight } from 'lucide-react';
import { useStatsStore } from '../../../hooks/useStatsStore';

export const TodayDashboard: React.FC = () => {
    const { todayOverview } = useStatsStore();

    const completed = todayOverview?.completedCount ?? 0;
    const total = todayOverview?.scheduledCount ?? 0;
    const rawPercentage = todayOverview?.completionRate != null
        ? Math.round(todayOverview.completionRate * 100)
        : (total === 0 ? 0 : Math.round((completed / total) * 100));
    const percentage = Math.max(0, Math.min(100, rawPercentage));
    const isRestDay = todayOverview?.isRestDay ?? false;

    return (
        <div className="bg-[linear-gradient(180deg,#FFFFFF_0%,#F7FEFB_100%)] rounded-[24px] p-6 shadow-[0_10px_28px_rgba(15,23,42,0.08)] border border-emerald-100/70 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6 relative overflow-hidden">
            {/* Background Decoration */}
            <div className="absolute top-0 right-0 w-64 h-64 bg-emerald-50/50 rounded-full blur-3xl -translate-y-1/2 translate-x-1/3 pointer-events-none" />

            {/* Title & Stats */}
            <div className="flex flex-col relative z-10 w-full sm:w-auto">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em] mb-2">今日打卡</h2>
                <div className="flex items-baseline gap-1.5">
                    {isRestDay ? (
                        <span className="text-[28px] sm:text-[34px] font-extrabold text-slate-700">休息日</span>
                    ) : (
                        <>
                            <span className="text-[36px] sm:text-[52px] font-extrabold tracking-[-0.03em] text-slate-900 leading-none">{completed}</span>
                            <span className="text-[20px] font-semibold text-slate-300">/{total}</span>
                        </>
                    )}
                </div>
            </div>

            {/* Progress Layout */}
            <div className="flex-1 w-full max-w-lg relative z-10 mt-4 sm:mt-0">
                <div className="flex items-center justify-between mb-3">
                    <span className="text-[14px] font-semibold text-slate-700 tracking-[0.02em]">今日进度</span>
                    <span className="inline-flex items-center justify-center h-7 px-3 rounded-full text-emerald-700 font-semibold text-[12px] bg-emerald-100 border border-emerald-200 shadow-sm">
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
