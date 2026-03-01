import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { useStatsStore } from '../../../hooks/useStatsStore';

export const TrendsChart: React.FC = () => {
    const { weeklyData } = useStatsStore();

    const last4 = useMemo(() => {
        const data = weeklyData.slice(-4);
        while (data.length < 4) {
            data.unshift({ weekStartDate: '', weekEndDate: '', rate: 0, habitCount: 0 });
        }
        return data;
    }, [weeklyData]);

    return (
        <div className="flex flex-col justify-between bg-white rounded-[24px] p-5 shadow-sm border border-neutral-100 relative h-full">
            <div className="flex items-center justify-between mb-2">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest">4-Week Trend</h2>
                <div className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer">
                    <ArrowRight size={14} className="text-neutral-400 -rotate-45" />
                </div>
            </div>
            <div className="flex items-end justify-between gap-3 h-[60px] w-full mt-auto px-2">
                {last4.map((week, i) => {
                    const isCurrentWeek = i === last4.length - 1;
                    const heightPct = Math.max(5, Math.round(week.rate * 100));
                    return (
                        <div
                            key={i}
                            className={`flex-1 rounded-[6px] transition-colors ${isCurrentWeek
                                    ? 'bg-emerald-500 shadow-lg shadow-emerald-500/30'
                                    : 'bg-slate-100 hover:bg-slate-200'
                                }`}
                            style={{ height: `${heightPct}%` }}
                            title={week.weekStartDate ? `${week.weekStartDate} ~ ${week.weekEndDate}: ${Math.round(week.rate * 100)}%` : ''}
                        />
                    );
                })}
            </div>
        </div>
    );
};
