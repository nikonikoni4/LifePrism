import React, { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Calendar } from 'lucide-react';
import { HeatmapData } from '../../../../types';

interface HabitHeatmapProps {
  data: HeatmapData[];
  className?: string;
}

const WEEKDAYS = ['日', '一', '二', '三', '四', '五', '六'];

// Warm amber color palette
const getHeatColor = (rate: number): string => {
  if (rate === 0) return '#F5F5F4';  // stone-100
  if (rate < 0.25) return '#FEF3C7'; // amber-100
  if (rate < 0.5) return '#FDE68A';  // amber-200
  if (rate < 0.75) return '#FCD34D'; // amber-300
  if (rate < 1) return '#FBBF24';    // amber-400
  return '#F59E0B';                   // amber-500
};

const HabitHeatmap: React.FC<HabitHeatmapProps> = ({ data, className = '' }) => {
  const { weeks, monthLabels } = useMemo(() => {
    const weeks: (HeatmapData | null)[][] = [];
    let currentWeek: (HeatmapData | null)[] = [];
    const monthLabels: { week: number; label: string }[] = [];

    const sortedData = [...data].sort((a, b) =>
      new Date(a.date).getTime() - new Date(b.date).getTime()
    );

    if (sortedData.length === 0) {
      return { weeks: [], monthLabels: [] };
    }

    const firstDate = new Date(sortedData[0].date);
    const firstDayOfWeek = firstDate.getDay();

    for (let i = 0; i < firstDayOfWeek; i++) {
      currentWeek.push(null);
    }

    let lastMonth = -1;

    sortedData.forEach((day) => {
      const date = new Date(day.date);
      const dayOfWeek = date.getDay();

      if (dayOfWeek === 0 && currentWeek.length > 0) {
        weeks.push(currentWeek);
        currentWeek = [];
      }

      currentWeek.push(day);

      const month = date.getMonth();
      if (month !== lastMonth) {
        monthLabels.push({
          week: weeks.length,
          label: date.toLocaleDateString('zh-CN', { month: 'short' })
        });
        lastMonth = month;
      }
    });

    if (currentWeek.length > 0) {
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
      transition={{ delay: 0.2 }}
      className={`bg-white rounded-2xl border border-stone-100 p-5 ${className}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-50 text-amber-500 rounded-xl">
            <Calendar size={16} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-stone-800">习惯热力图</h3>
            <p className="text-[10px] text-stone-400 mt-0.5">最近 12 周</p>
          </div>
        </div>

        {/* Legend */}
        <div className="hidden sm:flex items-center gap-1.5 text-[10px] text-stone-400">
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
      <div className="overflow-x-auto overflow-y-visible pb-2">
        <div className="flex justify-center">
          <div className="inline-block">
            {/* Month labels */}
            <div className="flex mb-1.5 ml-8">
              {monthLabels.map((label, i) => (
                <div
                  key={i}
                  className="text-[10px] text-stone-400 font-medium"
                  style={{
                    marginLeft: i === 0 ? `${label.week * 18}px` : undefined,
                    width: i < monthLabels.length - 1
                      ? `${(monthLabels[i + 1].week - label.week) * 18}px`
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
              <div className="flex flex-col gap-[3px] mr-1.5 pt-0.5">
                {WEEKDAYS.map((day, i) => (
                  <div
                    key={i}
                    className="h-[14px] text-[9px] text-stone-400 font-medium flex items-center justify-end w-5"
                    style={{ visibility: i % 2 === 1 ? 'visible' : 'hidden' }}
                  >
                    {day}
                  </div>
                ))}
              </div>

              {/* Weeks */}
              <div className="flex gap-[3px]">
                {weeks.map((week, weekIndex) => (
                  <div key={weekIndex} className="flex flex-col gap-[3px]">
                    {week.map((day, dayIndex) => (
                      <motion.div
                        key={dayIndex}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: weekIndex * 0.008 + dayIndex * 0.003 }}
                        className="w-[14px] h-[14px] rounded-[3px] cursor-pointer transition-transform hover:scale-125 relative group/cell"
                        style={{
                          backgroundColor: day ? getHeatColor(day.completionRate) : 'transparent'
                        }}
                      >
                        {day && (
                          <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover/cell:opacity-100 transition-opacity pointer-events-none z-[100]">
                            <div className="bg-stone-800 text-white px-2.5 py-1.5 rounded-lg text-[10px] whitespace-pre shadow-xl">
                              {formatTooltip(day)}
                            </div>
                            <div className="absolute top-full left-1/2 -translate-x-1/2 border-4 border-transparent border-t-stone-800" />
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
      </div>

      {/* Mobile Legend */}
      <div className="flex sm:hidden items-center justify-center gap-1.5 text-[10px] text-stone-400 mt-3 pt-3 border-t border-stone-50">
        <span>少</span>
        <div className="flex gap-1">
          {[0, 0.25, 0.5, 0.75, 1].map((rate, i) => (
            <div
              key={i}
              className="w-3.5 h-3.5 rounded-sm"
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
