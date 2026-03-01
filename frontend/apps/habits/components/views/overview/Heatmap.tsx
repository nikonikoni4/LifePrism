import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { format, subDays } from 'date-fns';
import { useStatsStore } from '../../../hooks/useStatsStore';
import { HeatmapDayItem } from '../../../types/backend';

const rateToLevel = (item: HeatmapDayItem): number => {
    if (item.isRestDay) return 0;
    const rate = item.completionRate ?? 0;
    if (rate === 0) return 0;
    if (rate < 0.25) return 1;
    if (rate < 0.5) return 2;
    if (rate < 0.75) return 3;
    if (rate < 1) return 4;
    return 5;
};

const levelColors: Record<number, string> = {
    0: 'bg-slate-100',
    1: 'bg-emerald-100',
    2: 'bg-emerald-200',
    3: 'bg-emerald-300',
    4: 'bg-emerald-400',
    5: 'bg-emerald-500',
};

export const Heatmap: React.FC = () => {
    const { heatmapData } = useStatsStore();

    // 构建 12 周 × 7 天的网格（按列优先：每列=一周，每行=周几）
    const grid = useMemo(() => {
        if (heatmapData.length === 0) {
            return Array.from({ length: 12 * 7 }, () => 0);
        }
        // 用 map 快速查找
        const dayMap = new Map<string, HeatmapDayItem>();
        heatmapData.forEach(d => dayMap.set(d.date, d));

        // 找到最后一天，往前推 12 周
        const sorted = [...heatmapData].sort((a, b) => a.date.localeCompare(b.date));
        const lastDate = sorted.length > 0 ? new Date(sorted[sorted.length - 1].date) : new Date();

        const cells: number[] = [];
        // 12 周 = 84 天
        for (let i = 83; i >= 0; i--) {
            const d = subDays(lastDate, i);
            const dateStr = format(d, 'yyyy-MM-dd');
            const item = dayMap.get(dateStr);
            cells.push(item ? rateToLevel(item) : 0);
        }
        return cells;
    }, [heatmapData]);

    return (
        <div className="flex flex-col justify-between bg-white rounded-[24px] p-5 shadow-sm border border-neutral-100 relative h-full">
            <div className="flex items-center justify-between mb-2">
                <h2 className="text-[12px] font-bold text-neutral-400 uppercase tracking-widest">12-Week Flow</h2>
                <div className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer">
                    <ArrowRight size={14} className="text-neutral-400 -rotate-45" />
                </div>
            </div>
            <div className="grid grid-flow-col grid-rows-7 gap-[4px] inline-grid self-start md:mx-auto">
                {grid.map((level, i) => (
                    <div
                        key={i}
                        className={`w-[11px] h-[11px] rounded-[3px] border border-black/[0.03] ${levelColors[level] || 'bg-slate-50'}`}
                    />
                ))}
            </div>
        </div>
    );
};
