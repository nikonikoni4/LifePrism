import React from 'react';
import { ArrowRight } from 'lucide-react';

interface HeatmapProps {
    // In Phase 2+, we can pass actual week data
}

export const Heatmap: React.FC<HeatmapProps> = () => {
    return (
        <div className="flex flex-col justify-between bg-white rounded-[24px] p-6 shadow-sm border border-neutral-100">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest">12-Week Flow</h2>
                <div className="w-8 h-8 rounded-full bg-white flex items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer shadow-sm">
                    <ArrowRight size={14} className="text-neutral-400 -rotate-45" />
                </div>
            </div>
            <div className="grid grid-flow-col grid-rows-5 gap-[5px] inline-grid self-start mt-auto">
                {Array.from({ length: 12 * 5 }).map((_, i) => (
                    <div key={i} className={`w-[12px] h-[12px] rounded-[3px] border border-black/[0.03] ${Math.random() > 0.7 ? 'bg-emerald-500' :
                        Math.random() > 0.4 ? 'bg-emerald-300' :
                            Math.random() > 0.2 ? 'bg-emerald-100' : 'bg-white'
                        }`} />
                ))}
            </div>
        </div>
    );
};
