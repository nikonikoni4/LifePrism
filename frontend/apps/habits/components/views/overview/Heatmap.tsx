import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { format, subDays } from 'date-fns';
import { useStatsStore } from '../../../hooks/useStatsStore';
import { HeatmapDayItem } from '../../../types/backend';

const rateToLevel = (item: HeatmapDayItem): number => {
    if (item.isRestDay) return 0;
    const rate = item.completionRate ?? 0;
    if (rate === 0) return 0;
    if (rate < 0.35) return 1;
    if (rate < 0.6) return 2;
    if (rate < 0.85) return 3;
    return 4;
};

const levelColors: Record<number, string> = {
    0: 'bg-slate-200',
    1: 'bg-emerald-100',
    2: 'bg-emerald-200',
    3: 'bg-emerald-300',
    4: 'bg-emerald-500',
};

export const Heatmap: React.FC = () => {
    const { heatmapData } = useStatsStore();
    const hasHeatmapData = heatmapData.length > 0;

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
        <div className="flex flex-col justify-between bg-[linear-gradient(180deg,#FFFFFF_0%,#F8FAFC_100%)] rounded-[24px] p-5 shadow-[0_10px_28px_rgba(15,23,42,0.08)] border border-slate-100/80 relative h-full">
            <div className="flex items-center justify-between mb-2">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em]">12-Week Flow</h2>
                <div className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer">
                    <ArrowRight size={14} className="text-neutral-400 -rotate-45" />
                </div>
            </div>
            {!hasHeatmapData ? (
                <div className="flex-1 flex items-center justify-center">
                    <p className="text-[13px] text-slate-500 font-medium">暂无记录</p>
                </div>
            ) : (
                <div className="flex flex-col gap-3">
                    <div className="grid grid-flow-col grid-rows-7 gap-[4px] inline-grid self-start md:mx-auto">
                        {grid.map((level, i) => (
                            <div
                                key={i}
                                className={`w-[11px] h-[11px] rounded-[3px] border border-black/[0.03] ${levelColors[level] || 'bg-slate-200'}`}
                            />
                        ))}
                    </div>
                    <div className="flex items-center justify-end gap-1.5 text-[10px] text-slate-500 font-medium">
                        <span>低</span>
                        {[0, 1, 2, 3, 4].map(level => (
                            <span key={level} className={`w-2.5 h-2.5 rounded-[2px] ${levelColors[level]}`} />
                        ))}
                        <span>高</span>
                    </div>
                </div>
            )}
        </div>
    );
};
