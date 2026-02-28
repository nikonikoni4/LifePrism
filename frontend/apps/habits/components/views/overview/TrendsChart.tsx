import React from 'react';
import { ArrowRight } from 'lucide-react';

interface TrendsChartProps {
    // In Phase 2+, we can pass actual trend percentages
}

export const TrendsChart: React.FC<TrendsChartProps> = () => {
    return (
        <div className="flex flex-col justify-between bg-white rounded-[24px] p-6 shadow-sm border border-neutral-100">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest">4-Week Trend</h2>
                <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer shadow-sm">
                    <ArrowRight size={14} className="text-neutral-400 -rotate-45" />
                </div>
            </div>
            <div className="flex items-end justify-between gap-3 h-[80px] w-full mt-auto">
                <div className="flex-1 bg-slate-100 hover:bg-slate-200 transition-colors rounded-[8px] h-[50%]" />
                <div className="flex-1 bg-slate-100 hover:bg-slate-200 transition-colors rounded-[8px] h-[70%]" />
                <div className="flex-1 bg-slate-100 hover:bg-slate-200 transition-colors rounded-[8px] h-[40%]" />
                <div className="flex-1 bg-emerald-500 rounded-[8px] h-[90%] shadow-lg shadow-emerald-500/30" />
            </div>
        </div>
    );
};
