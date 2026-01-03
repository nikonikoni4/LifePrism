/**
 * Time Distribution Chart Component
 * 
 * 时间分布折线图
 */

import React, { useState } from 'react';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend
} from 'recharts';
import { TrendingUp } from 'lucide-react';
import { TimeDistributionPoint, CategoryConfig } from '../types';

interface TimeDistributionChartProps {
    data: TimeDistributionPoint[];
    categories: CategoryConfig[];
    title?: string;
    subtitle?: string;
    xAxisLabel?: string;
    className?: string;
    height?: number;
}

/** 自定义 Tooltip */
const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        const total = payload.reduce((sum: number, entry: any) => sum + (entry.value || 0), 0);

        return (
            <div className="bg-white p-4 border border-gray-100 shadow-xl rounded-2xl text-sm">
                <p className="font-bold text-slate-800 mb-2">{label}</p>
                {payload.map((entry: any, index: number) => (
                    <div key={index} className="flex items-center justify-between gap-4 mb-1 last:mb-0">
                        <div className="flex items-center gap-2">
                            <div
                                className="w-2.5 h-2.5 rounded-full"
                                style={{ backgroundColor: entry.color }}
                            />
                            <span className="text-slate-500 font-medium">{entry.name}</span>
                        </div>
                        <span className="font-mono font-bold text-slate-700">{entry.value}m</span>
                    </div>
                ))}
                <div className="mt-2 pt-2 border-t border-gray-100 flex justify-between">
                    <span className="text-slate-500 font-medium">合计</span>
                    <span className="font-mono font-bold text-slate-800">{total}m</span>
                </div>
            </div>
        );
    }
    return null;
};

const TimeDistributionChart: React.FC<TimeDistributionChartProps> = ({
    data,
    categories,
    title = '时间分布趋势',
    subtitle,
    xAxisLabel,
    className = '',
    height = 280
}) => {
    const [visibleCategories, setVisibleCategories] = useState<Set<string>>(
        new Set(categories.map(c => c.key))
    );

    const toggleCategory = (key: string) => {
        setVisibleCategories(prev => {
            const next = new Set(prev);
            if (next.has(key)) {
                // 至少保留一个分类可见
                if (next.size > 1) {
                    next.delete(key);
                }
            } else {
                next.add(key);
            }
            return next;
        });
    };

    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 ${className}`}>
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-50 text-blue-500 rounded-xl">
                        <TrendingUp size={18} />
                    </div>
                    <div>
                        <h3 className="text-base font-bold text-slate-800">{title}</h3>
                        {subtitle && (
                            <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>
                        )}
                    </div>
                </div>

                {/* Category Toggles */}
                <div className="flex flex-wrap gap-2">
                    {categories.map((cat) => {
                        const isActive = visibleCategories.has(cat.key);
                        return (
                            <button
                                key={cat.key}
                                onClick={() => toggleCategory(cat.key)}
                                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wide transition-all flex items-center gap-1.5 ${isActive
                                    ? 'bg-white border border-gray-200 shadow-sm'
                                    : 'bg-gray-50 border border-transparent opacity-50'
                                    }`}
                            >
                                <div
                                    className="w-2 h-2 rounded-full"
                                    style={{ backgroundColor: cat.color }}
                                />
                                {cat.name}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* Chart */}
            <div style={{ height }}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={data} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                        <CartesianGrid vertical={false} stroke="#E2E8F0" strokeDasharray="3 3" />
                        <XAxis
                            dataKey="label"
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#94A3B8', fontSize: 11, fontWeight: 500 }}
                            dy={10}
                        />
                        <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#94A3B8', fontSize: 11 }}
                            tickCount={5}
                            unit="m"
                        />
                        <Tooltip content={<CustomTooltip />} />

                        {categories.map((cat) => (
                            visibleCategories.has(cat.key) && (
                                <Line
                                    key={cat.key}
                                    type="monotone"
                                    dataKey={cat.key}
                                    name={cat.name}
                                    stroke={cat.color}
                                    strokeWidth={2}
                                    dot={{ fill: cat.color, strokeWidth: 0, r: 3 }}
                                    activeDot={{ r: 5, strokeWidth: 0 }}
                                    animationDuration={800}
                                />
                            )
                        ))}
                    </LineChart>
                </ResponsiveContainer>
            </div>
        </div>
    );
};

export default TimeDistributionChart;
