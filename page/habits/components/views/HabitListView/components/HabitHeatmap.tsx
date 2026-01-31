import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Calendar } from 'lucide-react';
import { HeatmapData } from '../../../../types';

interface HabitHeatmapProps {
  data: HeatmapData[];
  className?: string;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

// Get color based on completion rate
const getHeatColor = (rate: number): string => {
  if (rate === 0) return '#f1f5f9';  // slate-100
  if (rate < 0.25) return '#bbf7d0'; // green-200
  if (rate < 0.5) return '#86efac';  // green-300
  if (rate < 0.75) return '#4ade80'; // green-400
  if (rate < 1) return '#22c55e';    // green-500
  return '#16a34a';                   // green-600
};

const HabitHeatmap: React.FC<HabitHeatmapProps> = ({ data, className = '' }) => {
  const { weeks, monthLabels } = useMemo(() => {
    // Group data into weeks (last 12 weeks)
    const weeks: (HeatmapData | null)[][] = [];
    let currentWeek: (HeatmapData | null)[] = [];
    const monthLabels: { week: number; label: string }[] = [];

    // Sort data by date
    const sortedData = [...data].sort((a, b) =>
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );

    if (sortedData.length === 0) {
      return { weeks: [], monthLabels: [] };
    }

    // Find the first day and pad to start of week
    const firstDate = new Date(sortedData[0].date);
    const firstDayOfWeek = firstDate.getDay();

    // Pad the first week
    for (let i = 0; i < firstDayOfWeek; i++) {
      currentWeek.push(null);
    }

    let lastMonth = -1;

    sortedData.forEach((day, index) => {
      const date = new Date(day.date);
      const dayOfWeek = date.getDay();

      // If we're starting a new week (Sunday)
      if (dayOfWeek === 0 && currentWeek.length > 0) {
        weeks.push(currentWeek);
        currentWeek = [];
      }

      currentWeek.push(day);

      // Track month labels
      const month = date.getMonth();
      if (month !== lastMonth) {
        monthLabels.push({
          week: weeks.length,
          label: date.toLocaleDateString('zh-CN', { month: 'short' })
        });
        lastMonth = month;
      }
    });

    // Push the last week
    if (currentWeek.length > 0) {
      // Pad the last week
      while (currentWeek.length < 7) {
        currentWeek.push(null);
      }
      weeks.push(currentWeek);
    }

    return { weeks, monthLabels };
  }, [data]);

  const formatTooltip = (day: HeatmapData) => {
    const date = new Date(day.date);
    const dateStr = date.toLocaleDateString('zh-CN', {
      month: 'long',
      day: 'numeric',
      weekday: 'short'
    });
    return `${dateStr}\n完成 ${day.completedHabits}/${day.totalHabits} 个习惯`;
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className={`bg-white/80 backdrop-blur-sm rounded-[1.5rem] border border-slate-100 shadow-sm p-6 ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-50 text-green-500 rounded-xl">
            <Calendar size={18} />
          </div>
          <div>
            <h3 className="text-base font-bold text-slate-800">习惯热力图</h3>
            <p className="text-xs text-slate-400 mt-0.5">最近 12 周的完成情况</p>
          </div>
        </div>

        {/* Legend */}
        <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
          <span>少</span>
          <div className="flex gap-0.5">
            {[0, 0.25, 0.5, 0.75, 1].map((rate, i) => (
              <div
                key={i}
                className="w-3 h-3 rounded-sm"
                style={{ backgroundColor: getHeatColor(rate) }}
              />
            ))}
          </div>
          <span>多</span>
        </div>
      </div>

      {/* Heatmap Grid */}
      <div className="overflow-x-auto">
        <div className="min-w-[600px]">
          {/* Month labels */}
          <div className="flex mb-1 ml-8">
            {monthLabels.map((label, i) => (
              <div
                key={i}
                className="text-[10px] text-slate-400 font-medium"
                style={{
                  marginLeft: i === 0 ? `${label.week * 14}px` : undefined,
                  width: i < monthLabels.length - 1
                    ? `${(monthLabels[i + 1].week - label.week) * 14}px`
                    : 'auto'
                }}
              >
                {label.label}
              </div>
            ))}
          </div>

          {/* Grid */}
          <div className="flex">
            {/* Weekday labels */}
            <div className="flex flex-col gap-0.5 mr-2 pt-0.5">
              {WEEKDAYS.map((day, i) => (
                <div
                  key={i}
                  className="h-3 text-[9px] text-slate-400 font-medium flex items-center"
                  style={{ visibility: i % 2 === 1 ? 'visible' : 'hidden' }}
                >
                  {day}
                </div>
              ))}
            </div>

            {/* Weeks */}
            <div className="flex gap-0.5">
              {weeks.map((week, weekIndex) => (
                <div key={weekIndex} className="flex flex-col gap-0.5">
                  {week.map((day, dayIndex) => (
                    <motion.div
                      key={dayIndex}
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      transition={{ delay: weekIndex * 0.01 + dayIndex * 0.005 }}
                      className="w-3 h-3 rounded-sm cursor-pointer transition-transform hover:scale-125 relative group"
                      style={{
                        backgroundColor: day ? getHeatColor(day.completionRate) : 'transparent'
                      }}
                    >
                      {day && (
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-20">
                          <div className="bg-slate-800 text-white px-2.5 py-1.5 rounded-lg text-[10px] whitespace-pre shadow-lg">
                            {formatTooltip(day)}
                          </div>
                          <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-slate-800" />
                        </div>
                      )}
                    </motion.div>
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Legend */}
      <div className="flex sm:hidden items-center justify-center gap-1.5 text-xs text-slate-400 mt-4 pt-4 border-t border-slate-100">
        <span>少</span>
        <div className="flex gap-0.5">
          {[0, 0.25, 0.5, 0.75, 1].map((rate, i) => (
            <div
              key={i}
              className="w-3 h-3 rounded-sm"
              style={{ backgroundColor: getHeatColor(rate) }}
            />
          ))}
        </div>
        <span>多</span>
      </div>
    </motion.div>
  );
};

export default HabitHeatmap;
