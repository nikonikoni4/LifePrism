/**
 * Calendar Heatmap Component
 * 
 * 月度热力图组件
 */

import React, { useState, useMemo } from 'react';
import { Calendar } from 'lucide-react';
import { HeatmapDay, CategoryConfig } from '../types';

interface CalendarHeatmapProps {
    data: HeatmapDay[];
    categories: CategoryConfig[];
    month: string;  // YYYY-MM
    title?: string;
    className?: string;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

/** 根据值获取热力颜色 */
const getHeatColor = (value: number, maxValue: number, color: string = '#5B8FF9'): string => {
    if (value === 0) return '#f1f5f9';

    const intensity = Math.min(value / maxValue, 1);

    // 解析颜色并调整透明度
    if (color.startsWith('#')) {
        const r = parseInt(color.slice(1, 3), 16);
        const g = parseInt(color.slice(3, 5), 16);
        const b = parseInt(color.slice(5, 7), 16);
        return `rgba(${r}, ${g}, ${b}, ${0.2 + intensity * 0.8})`;
    }

    return color;
};

const CalendarHeatmap: React.FC<CalendarHeatmapProps> = ({
    data,
    categories,
    month,
    title = '月度活跃热力图',
    className = ''
}) => {
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

    const { weeks, maxValue, selectedColor } = useMemo(() => {
        const [year, mon] = month.split('-').map(Number);
        const firstDay = new Date(year, mon - 1, 1);
        const firstDayOfWeek = firstDay.getDay();
        const daysInMonth = new Date(year, mon, 0).getDate();

        // 构建日历网格
        const weeks: (HeatmapDay | null)[][] = [];
        let currentWeek: (HeatmapDay | null)[] = [];

        // 填充第一周的空白
        for (let i = 0; i < firstDayOfWeek; i++) {
            currentWeek.push(null);
        }

        // 填充日期
        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = `${year}-${String(mon).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const dayData = data.find(item => item.date === dateStr);

            currentWeek.push(dayData || { date: dateStr, value: 0 });

            if (currentWeek.length === 7) {
                weeks.push(currentWeek);
                currentWeek = [];
            }
        }

        // 填充最后一周的空白
        if (currentWeek.length > 0) {
            while (currentWeek.length < 7) {
                currentWeek.push(null);
            }
            weeks.push(currentWeek);
        }

        // 计算最大值
        let max = 0;
        data.forEach(d => {
            if (selectedCategory && d.categoryBreakdown) {
                max = Math.max(max, d.categoryBreakdown[selectedCategory] || 0);
            } else {
                max = Math.max(max, d.value);
            }
        });

        // 获取选中分类的颜色
        const color = selectedCategory
            ? categories.find(c => c.key === selectedCategory)?.color || '#5B8FF9'
            : '#5B8FF9';

        return { weeks, maxValue: max || 1, selectedColor: color };
    }, [data, month, selectedCategory, categories]);

    const getValue = (day: HeatmapDay): number => {
        if (selectedCategory && day.categoryBreakdown) {
            return day.categoryBreakdown[selectedCategory] || 0;
        }
        return day.value;
    };

    const formatTime = (minutes: number) => {
        const hours = Math.floor(minutes / 60);
        const mins = minutes % 60;
        if (hours > 0) {
            return `${hours}h ${mins}m`;
        }
        return `${mins}m`;
    };

    return (
        <div className={`bg-white rounded-2xl shadow-sm border border-gray-100 p-6 ${className}`}>
            {/* Header */}
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-50 text-emerald-500 rounded-xl">
                        <Calendar size={18} />
                    </div>
                    <div>
                        <h3 className="text-base font-bold text-slate-800">{title}</h3>
                        <p className="text-xs text-slate-400 mt-0.5">
                            {month.replace('-', '年')}月
                        </p>
                    </div>
                </div>

                {/* Category Filter */}
                <div className="flex flex-wrap gap-2">
                    <button
                        onClick={() => setSelectedCategory(null)}
                        className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wide transition-all ${selectedCategory === null
                                ? 'bg-slate-800 text-white'
                                : 'bg-gray-50 text-slate-600 hover:bg-gray-100'
                            }`}
                    >
                        全部
                    </button>
                    {categories.map((cat) => (
                        <button
                            key={cat.key}
                            onClick={() => setSelectedCategory(cat.key)}
                            className={`px-3 py-1.5 rounded-lg text-[10px] font-bold uppercase tracking-wide transition-all flex items-center gap-1.5 ${selectedCategory === cat.key
                                    ? 'bg-white border-2 shadow-sm'
                                    : 'bg-gray-50 border border-transparent hover:bg-gray-100'
                                }`}
                            style={{
                                borderColor: selectedCategory === cat.key ? cat.color : undefined
                            }}
                        >
                            <div
                                className="w-2 h-2 rounded-full"
                                style={{ backgroundColor: cat.color }}
                            />
                            {cat.name}
                        </button>
                    ))}
                </div>
            </div>

            {/* Weekday Headers */}
            <div className="grid grid-cols-7 gap-1 mb-2">
                {WEEKDAYS.map((day, i) => (
                    <div
                        key={i}
                        className="text-center text-[10px] font-bold text-slate-400 uppercase py-1"
                    >
                        {day}
                    </div>
                ))}
            </div>

            {/* Calendar Grid */}
            <div className="space-y-1">
                {weeks.map((week, weekIndex) => (
                    <div key={weekIndex} className="grid grid-cols-7 gap-1">
                        {week.map((day, dayIndex) => {
                            if (!day) {
                                return (
                                    <div
                                        key={dayIndex}
                                        className="aspect-square rounded-lg"
                                    />
                                );
                            }

                            const value = getValue(day);
                            const dateNum = parseInt(day.date.split('-')[2]);

                            return (
                                <div
                                    key={dayIndex}
                                    className="aspect-square rounded-lg flex flex-col items-center justify-center relative group cursor-pointer transition-transform hover:scale-105"
                                    style={{
                                        backgroundColor: getHeatColor(value, maxValue, selectedColor)
                                    }}
                                >
                                    <span className="text-xs font-medium text-slate-600">
                                        {dateNum}
                                    </span>

                                    {/* Tooltip */}
                                    <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                                        <div className="bg-slate-800 text-white px-3 py-2 rounded-lg text-xs whitespace-nowrap shadow-lg">
                                            <div className="font-bold mb-1">{day.date}</div>
                                            <div>{formatTime(value)}</div>
                                            {day.categoryBreakdown && !selectedCategory && (
                                                <div className="mt-1 pt-1 border-t border-slate-600 space-y-0.5">
                                                    {categories.map(cat => {
                                                        const catValue = day.categoryBreakdown?.[cat.key] || 0;
                                                        if (catValue === 0) return null;
                                                        return (
                                                            <div key={cat.key} className="flex items-center gap-1.5">
                                                                <div
                                                                    className="w-1.5 h-1.5 rounded-full"
                                                                    style={{ backgroundColor: cat.color }}
                                                                />
                                                                <span>{cat.name}: {formatTime(catValue)}</span>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                        <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                ))}
            </div>

            {/* Legend */}
            <div className="flex items-center justify-end gap-2 mt-4 text-xs text-slate-400">
                <span>少</span>
                <div className="flex gap-0.5">
                    {[0.1, 0.3, 0.5, 0.7, 1].map((intensity, i) => (
                        <div
                            key={i}
                            className="w-3 h-3 rounded-sm"
                            style={{
                                backgroundColor: getHeatColor(intensity * maxValue, maxValue, selectedColor)
                            }}
                        />
                    ))}
                </div>
                <span>多</span>
            </div>
        </div>
    );
};

export default CalendarHeatmap;
