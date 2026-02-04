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
    /** 点击数据点时的回调，参数为对应日期 (YYYY-MM-DD) */
    onDataPointClick?: (date: string) => void;
}

/** 自定义 Tooltip */
const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
        const total = payload.reduce((sum: number, entry: any) => sum + (Number(entry.value) || 0), 0).toFixed(1);

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
                        <span className="font-mono font-bold text-slate-700">{entry.value}h</span>
                    </div>
                ))}
                <div className="mt-2 pt-2 border-t border-gray-100 flex justify-between">
                    <span className="text-slate-500 font-medium">合计</span>
                    <span className="font-mono font-bold text-slate-800">{total}h</span>
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
    height = 280,
    onDataPointClick
}) => {
    // 将分钟转换为小时
    const processedData = React.useMemo(() => {
        return data.map(item => {
            const newItem = { ...item };
            categories.forEach(cat => {
                const val = newItem[cat.key];
                if (val !== undefined && val !== null) {
                    // 保留一位小数
                    newItem[cat.key] = Number((Number(val) / 60).toFixed(1));
                }
            });
            return newItem;
        });
    }, [data, categories]);

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
            <div style={{ height }} className={onDataPointClick ? 'cursor-pointer' : ''}>
                <ResponsiveContainer width="100%" height="100%">
                    <LineChart
                        data={processedData}
                        margin={{ top: 10, right: 10, left: -15, bottom: 0 }}
                        onClick={(e) => {
                            console.log('[TimeDistributionChart] onClick triggered', e);
                            if (onDataPointClick && e && e.activeTooltipIndex !== undefined) {
                                const index = parseInt(String(e.activeTooltipIndex), 10);
                                const clickedData = processedData[index];
                                console.log('[TimeDistributionChart] clickedData:', clickedData);
                                const date = clickedData?.date as string;
                                console.log('[TimeDistributionChart] date:', date);
                                if (date) {
                                    console.log('[TimeDistributionChart] Navigating to date:', date);
                                    onDataPointClick(date);
                                } else {
                                    console.warn('[TimeDistributionChart] No date found in data point:', clickedData);
                                }
                            }
                        }}
                    >
                        <CartesianGrid vertical={false} stroke="#E2E8F0" strokeDasharray="3 3" />
                        <XAxis
                            dataKey="label"
                            axisLine={false}
                            tickLine={false}
                            tick={({ x, y, payload }) => {
                                const item = processedData[payload.index];
                                const dateStr = item?.['date'] as string;
                                // Format date: MM-DD
                                const formattedDate = dateStr ? dateStr.split('-').slice(1).join('-') : '';

                                return (
                                    <g transform={`translate(${x},${y})`}>
                                        <text x={0} y={0} dy={16} textAnchor="middle" fill="#94A3B8" fontSize={11} fontWeight={500}>
                                            {payload.value}
                                        </text>
                                        {formattedDate && (
                                            <text x={0} y={0} dy={32} textAnchor="middle" fill="#CBD5E1" fontSize={10}>
                                                {formattedDate}
                                            </text>
                                        )}
                                    </g>
                                );
                            }}
                            height={50}
                        />
                        <YAxis
                            axisLine={false}
                            tickLine={false}
                            tick={{ fill: '#94A3B8', fontSize: 11 }}
                            tickCount={5}
                            unit="h"
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
                                    activeDot={{
                                        r: onDataPointClick ? 7 : 5,
                                        strokeWidth: onDataPointClick ? 2 : 0,
                                        stroke: onDataPointClick ? '#fff' : undefined,
                                        style: onDataPointClick ? { cursor: 'pointer', filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.2))' } : undefined
                                    }}
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
