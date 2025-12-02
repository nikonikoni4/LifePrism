
import React, { useState } from 'react';
import { ChevronLeft, ChevronRight, Calendar, Filter, RefreshCw, Clock } from 'lucide-react';

// Generate 30 days of mock history data
// Generate 30 days of mock history data centered around the selected date
const generateMockHistory = (centerDateStr: string) => {
  const history = [];
  const centerDate = new Date(centerDateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0); // Normalize today to midnight

  // Window: 15 days before + center date + 14 days after = 30 days
  const startDate = new Date(centerDate);
  startDate.setDate(centerDate.getDate() - 15);

  for (let i = 0; i < 30; i++) {
    const d = new Date(startDate);
    d.setDate(startDate.getDate() + i);

    const month = d.getMonth() + 1;
    const day = d.getDate();
    const dateStr = `${month}/${day}`;
    const fullDate = d.toISOString().split('T')[0];

    // Random value between 10 and 100, with some "weekend" dips
    const dayOfWeek = d.getDay();
    let baseValue = Math.floor(Math.random() * 60) + 30;
    if (dayOfWeek === 0 || dayOfWeek === 6) baseValue -= 20;

    const isActualToday = d.getTime() === today.getTime();
    const isFuture = d.getTime() > today.getTime();
    const isSelected = fullDate === centerDateStr;

    history.push({
      day: dateStr,
      fullDate: fullDate,
      value: Math.max(10, baseValue),
      isActualToday,
      isFuture,
      isSelected
    });
  }
  return history;
};

interface ActivitySummaryHeaderProps {
  selectedDate: string;
  onDateChange: (date: string) => void;
}

const ActivitySummaryHeader: React.FC<ActivitySummaryHeaderProps> = ({ selectedDate, onDateChange }) => {
  const dateInputRef = React.useRef<HTMLInputElement>(null);

  // Memoize history generation to avoid unnecessary recalculations
  const history = React.useMemo(() => generateMockHistory(selectedDate), [selectedDate]);

  const handleDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onDateChange(e.target.value);
  };

  const formatDateDisplay = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', year: 'numeric' });
  };

  const handleCalendarClick = () => {
    if (dateInputRef.current) {
      if ('showPicker' in dateInputRef.current) {
        (dateInputRef.current as any).showPicker();
      } else {
        dateInputRef.current.click();
      }
    }
  };

  // Calculate start and end dates for labels based on the window
  const startDateLabel = history[0].day;
  const endDateLabel = history[history.length - 1].day;

  return (
    <div className="bg-white rounded-3xl p-6 lg:p-8 shadow-sm border border-gray-100 mb-8 animate-fade-in w-full">

      {/* Top Row: Title & Stats */}
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-3">
            Activity Summary
            <span className="text-slate-300 font-light hidden md:inline">|</span>
            <span className="text-slate-500 font-medium text-lg">{formatDateDisplay(selectedDate)}</span>
          </h2>
          <div className="flex items-center gap-2 mt-2 text-morandi-blue font-semibold">
            <Clock size={16} />
            <span>Total Active Time: <span className="font-mono text-lg font-bold">6h 35m</span></span>
          </div>
        </div>
      </div>

      {/* Middle Row: Controls */}
      <div className="flex flex-col md:flex-row justify-between items-center gap-4 mb-8">
        {/* Date Navigation */}
        <div className="flex items-center w-full md:w-auto bg-gray-50 p-1 rounded-xl border border-gray-200 relative group">
          <button className="p-2 hover:bg-white hover:shadow-sm rounded-lg text-slate-500 transition-all z-10">
            <ChevronLeft size={20} />
          </button>

          <div
            className="flex-1 md:flex-none px-4 flex items-center justify-center gap-2 border-l border-r border-gray-200/50 mx-1 relative cursor-pointer"
            onClick={handleCalendarClick}
          >
            {/* Invisible Date Picker Trigger */}
            <input
              ref={dateInputRef}
              type="date"
              value={selectedDate}
              onChange={handleDateChange}
              className="absolute inset-0 opacity-0 cursor-pointer z-20 w-full h-full pointer-events-none"
            />
            <Calendar size={18} className="text-morandi-blue pointer-events-none" />
            <span className="text-sm font-bold text-slate-700 whitespace-nowrap pointer-events-none">{selectedDate}</span>
          </div>

          <button className="p-2 hover:bg-white hover:shadow-sm rounded-lg text-slate-500 transition-all z-10">
            <ChevronRight size={20} />
          </button>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-3 w-full md:w-auto">
          <button className="flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-slate-600 text-sm font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm">
            <Filter size={16} />
            Filters
          </button>
          <button className="flex-1 md:flex-none flex items-center justify-center gap-2 px-4 py-2.5 bg-white border border-gray-200 rounded-xl text-slate-600 text-sm font-semibold hover:bg-gray-50 hover:border-gray-300 transition-all shadow-sm">
            <RefreshCw size={16} />
            Refresh
          </button>
        </div>
      </div>

      {/* Bottom Row: Mini Trend Chart (Sparkline) */}
      <div className="relative pt-6 border-t border-dashed border-gray-100">
        <div className="h-[80px] flex items-end justify-between gap-1 md:gap-2">
          {history.map((item, index) => (
            <div key={index} className="flex-1 flex flex-col justify-end group relative">

              {/* Tooltip on Hover */}
              <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-800 text-white text-[10px] py-1 px-2 rounded pointer-events-none whitespace-nowrap z-10 shadow-lg">
                {item.day}: {item.value}m
              </div>

              {/* The Bar */}
              <div
                onClick={() => !item.isFuture && onDateChange(item.fullDate)}
                className={`w-full rounded-t-sm transition-all duration-300 relative min-h-[4px] 
                  ${item.isFuture
                    ? 'bg-transparent border-2 border-dashed border-gray-300 cursor-default'
                    : 'cursor-pointer hover:opacity-80'
                  }
                  ${!item.isFuture && item.isSelected ? 'bg-morandi-orange' : ''}
                  ${!item.isFuture && !item.isSelected ? 'bg-gray-200' : ''}
                `}
                style={{ height: item.isFuture ? '40%' : `${item.value}%` }}
              >
                {/* "Today" Indicator Label - Always on actual today */}
                {item.isActualToday && (
                  <div className="absolute -top-8 left-1/2 -translate-x-1/2 flex flex-col items-center animate-bounce-slight z-20">
                    <span className="bg-morandi-orange text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm whitespace-nowrap">
                      Today
                    </span>
                    <div className="w-0 h-0 border-l-[4px] border-l-transparent border-r-[4px] border-r-transparent border-t-[4px] border-t-morandi-orange mt-0.5"></div>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* X-Axis Labels */}
        <div className="flex justify-between mt-2 px-1">
          <span className="text-[10px] font-bold text-gray-400">{startDateLabel}</span>
          <span className="text-[10px] font-bold text-gray-400">{endDateLabel}</span>
        </div>
      </div>

    </div>
  );
};

export default ActivitySummaryHeader;
