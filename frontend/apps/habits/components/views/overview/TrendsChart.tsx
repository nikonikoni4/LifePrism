import React, { useMemo } from 'react';
import { ArrowRight } from 'lucide-react';
import { useStatsStore } from '../../../hooks/useStatsStore';

export const TrendsChart: React.FC = () => {
    const { weeklyData } = useStatsStore();
    const hasTrendData = weeklyData.length > 0 && weeklyData.some(item =>
        item.rate > 0 || item.habitCount > 0 || Boolean(item.weekStartDate || item.weekEndDate)
    );

    const last4 = useMemo(() => {
        const data = weeklyData.slice(-4);
        while (data.length < 4) {
            data.unshift({ weekStartDate: '', weekEndDate: '', rate: 0, habitCount: 0 });
        }
        return data;
    }, [weeklyData]);

    const chart = useMemo(() => {
        const width = 300;
        const height = 120;
        const paddingX = 16;
        const paddingY = 14;
        const usableHeight = height - paddingY * 2;
        const usableWidth = width - paddingX * 2;

        const points = last4.map((week, index) => {
            const x = paddingX + (index / (last4.length - 1)) * usableWidth;
            const rate = Math.max(0, Math.min(1, week.rate));
            const y = height - paddingY - rate * usableHeight;
            return { x, y, rate };
        });

        const linePath = points.map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x} ${p.y}`).join(' ');
        const areaPath = points.length > 0
            ? `${linePath} L ${points[points.length - 1].x} ${height - paddingY} L ${points[0].x} ${height - paddingY} Z`
            : '';

        return { width, height, paddingY, points, linePath, areaPath };
    }, [last4]);

    return (
        <div className="flex flex-col justify-between bg-white rounded-[24px] p-5 shadow-[0_10px_28px_rgba(15,23,42,0.08)] border-none relative h-full">
            <div className="flex items-center justify-between mb-4">
                <h2 className="text-[14px] font-semibold text-slate-700 uppercase tracking-[0.02em]">4-Week Trend</h2>
                <div className="w-7 h-7 rounded-full flex items-center justify-center hover:bg-neutral-50 transition-colors cursor-pointer">
                    <ArrowRight size={14} className="text-neutral-400 -rotate-45" />
                </div>
            </div>
            {!hasTrendData ? (
                <div className="flex-1 flex items-center justify-center">
                    <p className="text-[13px] text-slate-500 font-medium">暂无趋势数据</p>
                </div>
            ) : (
                <div className="w-full mt-auto">
                    <div className="relative w-full h-[132px]">
                        <svg viewBox={`0 0 ${chart.width} ${chart.height}`} className="w-full h-full" preserveAspectRatio="none">
                            <defs>
                                <linearGradient id="trend-area-fill" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="0%" stopColor="#10B981" stopOpacity="0.16" />
                                    <stop offset="100%" stopColor="#10B981" stopOpacity="0.04" />
                                </linearGradient>
                            </defs>

                            {[0, 1, 2].map(i => {
                                const y = chart.paddingY + ((chart.height - chart.paddingY * 2) / 2) * i;
                                return (
                                    <line
                                        key={i}
                                        x1={12}
                                        x2={chart.width - 12}
                                        y1={y}
                                        y2={y}
                                        stroke="#E2E8F0"
                                        strokeWidth="1"
                                        strokeDasharray="2 3"
                                    />
                                );
                            })}

                            <path d={chart.areaPath} fill="url(#trend-area-fill)" />
                            <path d={chart.linePath} fill="none" stroke="#10B981" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" />

                            {chart.points.map((point, index) => {
                                const week = last4[index];
                                const isCurrentWeek = index === last4.length - 1;
                                return (
                                    <g key={index}>
                                        <circle
                                            cx={point.x}
                                            cy={point.y}
                                            r={isCurrentWeek ? 4 : 3}
                                            fill={isCurrentWeek ? '#059669' : '#10B981'}
                                            stroke="#FFFFFF"
                                            strokeWidth="1.5"
                                        >
                                            <title>
                                                {week.weekStartDate ? `${week.weekStartDate} ~ ${week.weekEndDate}: ${Math.round(point.rate * 100)}%` : `${Math.round(point.rate * 100)}%`}
                                            </title>
                                        </circle>
                                    </g>
                                );
                            })}
                        </svg>
                    </div>

                    <div className="mt-2 grid grid-cols-4 gap-1 text-[10px] font-semibold text-slate-500">
                        {last4.map((week, index) => {
                            const label = week.weekStartDate ? `W${index + 1}` : `W${index + 1}`;
                            return (
                                <div key={index} className="text-center">
                                    <div>{label}</div>
                                    <div className="text-slate-600">{Math.round(Math.max(0, Math.min(1, week.rate)) * 100)}%</div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};
