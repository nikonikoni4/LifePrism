import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Calendar, ChevronUp, ChevronDown } from 'lucide-react';
import { HeatmapData } from '../../../../types';

interface HabitHeatmapProps {
  data: HeatmapData[];
  className?: string;
  defaultExpanded?: boolean;
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

const HabitHeatmap: React.FC<HabitHeatmapProps> = ({ data, className = '', defaultExpanded = true }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

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
      className={`bg-white/80 backdrop-blur-sm rounded-[1.5rem] border border-slate-100 shadow-sm p-6 overflow-visible ${className}`}
    >
      {/* Header - Clickable */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between mb-4 group"
      >
        <div className="flex items-center gap-3">
          <div className="p-2 bg-green-50 text-green-500 rounded-xl">
            <Calendar size={18} />
          </div>
          <div className="text-left">
            <h3 className="text-base font-bold text-slate-800">习惯热力图</h3>
            <p className="text-xs text-slate-400 mt-0.5">最近 12 周的完成情况</p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Legend - only show when expanded */}
          {isExpanded && (
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
          )}

          {/* Collapse toggle */}
          <div className="p-1.5 rounded-lg text-slate-400 group-hover:text-slate-600 group-hover:bg-slate-100 transition-colors">
            {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </div>
        </div>
      </button>

      {/* Collapsible Content */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-visible"
          >
            {/* Heatmap Grid - centered */}
            <div className="overflow-x-auto overflow-y-visible pt-2 pb-4 px-2">
              <div className="flex justify-center">
                <div className="inline-block pr-4">
                  {/* Month labels */}
                  <div className="flex mb-2 ml-10">
                    {monthLabels.map((label, i) => (
                      <div
                        key={i}
                        className="text-xs text-slate-400 font-medium"
                        style={{
                          marginLeft: i === 0 ? `${label.week * 20}px` : undefined,
                          width: i < monthLabels.length - 1
                            ? `${(monthLabels[i + 1].week - label.week) * 20}px`
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
                    <div className="flex flex-col gap-1 mr-2 pt-0.5">
                      {WEEKDAYS.map((day, i) => (
                        <div
                          key={i}
                          className="h-4 text-[10px] text-slate-400 font-medium flex items-center justify-end w-6"
                          style={{ visibility: i % 2 === 1 ? 'visible' : 'hidden' }}
                        >
                          {day}
                        </div>
                      ))}
                    </div>

                    {/* Weeks */}
                    <div className="flex gap-1">
                      {weeks.map((week, weekIndex) => (
                        <div key={weekIndex} className="flex flex-col gap-1">
                          {week.map((day, dayIndex) => (
                            <motion.div
                              key={dayIndex}
                              initial={{ scale: 0 }}
                              animate={{ scale: 1 }}
                              transition={{ delay: weekIndex * 0.01 + dayIndex * 0.005 }}
                              className="w-4 h-4 rounded-[3px] cursor-pointer transition-transform hover:scale-125 relative group/cell"
                              style={{
                                backgroundColor: day ? getHeatColor(day.completionRate) : 'transparent'
                              }}
                            >
                              {day && (
                                <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-3 opacity-0 group-hover/cell:opacity-100 transition-opacity pointer-events-none z-[100]">
                                  <div className="bg-slate-800 text-white px-3 py-2 rounded-lg text-xs whitespace-pre shadow-xl">
                                    {formatTooltip(day)}
                                  </div>
                                  <div className="absolute top-full left-1/2 -translate-x-1/2 border-[6px] border-transparent border-t-slate-800" />
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
            <div className="flex sm:hidden items-center justify-center gap-1.5 text-xs text-slate-400 mt-4 pt-4 border-t border-slate-100">
              <span>少</span>
              <div className="flex gap-1">
                {[0, 0.25, 0.5, 0.75, 1].map((rate, i) => (
                  <div
                    key={i}
                    className="w-4 h-4 rounded-[3px]"
                    style={{ backgroundColor: getHeatColor(rate) }}
                  />
                ))}
              </div>
              <span>多</span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default HabitHeatmap;
