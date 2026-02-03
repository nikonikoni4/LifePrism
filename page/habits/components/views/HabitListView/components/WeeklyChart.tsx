import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { ArrowUpRight } from 'lucide-react';
import { HeatmapData } from '../../../../types';

interface WeeklyChartProps {
  data: HeatmapData[];
  className?: string;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

export const WeeklyChart: React.FC<WeeklyChartProps> = ({ data, className = '' }) => {
  const weekData = useMemo(() => {
    // Get last 7 days of data
    const today = new Date();
    const last7Days: { date: string; rate: number; isToday: boolean; dayLabel: string }[] = [];

    for (let i = 6; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];
      const dayOfWeek = date.getDay();

      const dayData = data.find(d => d.date === dateStr);

      last7Days.push({
        date: dateStr,
        rate: dayData?.completionRate ?? 0,
        isToday: i === 0,
        dayLabel: WEEKDAYS[dayOfWeek],
      });
    }

    return last7Days;
  }, [data]);

  const avgRate = useMemo(() => {
    const validDays = weekData.filter(d => d.rate > 0);
    if (validDays.length === 0) return 0;
    return validDays.reduce((sum, d) => sum + d.rate, 0) / validDays.length;
  }, [weekData]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className={`bg-white rounded-2xl border border-stone-100 p-5 ${className}`}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-sm font-semibold text-stone-800">周度完成分析</h3>
          <p className="text-xs text-stone-400 mt-0.5">最近 7 天完成率</p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-stone-900">{Math.round(avgRate * 100)}%</span>
          <ArrowUpRight size={16} className="text-stone-400" />
        </div>
      </div>

      {/* Bar Chart */}
      <div className="flex items-end justify-between gap-2 h-32">
        {weekData.map((day, index) => (
          <div key={day.date} className="flex-1 flex flex-col items-center gap-2">
            {/* Bar */}
            <div className="relative w-full flex justify-center">
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: `${Math.max(day.rate * 100, 4)}%` }}
                transition={{ delay: index * 0.05, duration: 0.5, ease: 'easeOut' }}
                className={`w-full max-w-[32px] rounded-t-lg ${
                  day.isToday
                    ? 'bg-emerald-500'
                    : day.rate > 0
                    ? 'bg-emerald-400'
                    : 'bg-stone-100'
                }`}
                style={{
                  minHeight: '4px',
                  height: `${Math.max(day.rate * 100, 4)}px`,
                  maxHeight: '100px',
                }}
              />
              {/* Today indicator dot */}
              {day.isToday && day.rate > 0 && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.5 }}
                  className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-emerald-600 rounded-full"
                />
              )}
            </div>

            {/* Day label */}
            <span className={`text-xs font-medium ${
              day.isToday ? 'text-emerald-600' : 'text-stone-400'
            }`}>
              {day.dayLabel}
            </span>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 mt-4 pt-4 border-t border-stone-50">
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-emerald-500" />
          <span className="text-[10px] text-stone-400">今天</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-emerald-400" />
          <span className="text-[10px] text-stone-400">已完成</span>
        </div>
        <div className="flex items-center gap-1.5">
          <div className="w-3 h-3 rounded bg-stone-100" />
          <span className="text-[10px] text-stone-400">未完成</span>
        </div>
      </div>
    </motion.div>
  );
};

export default WeeklyChart;
