
import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Calendar, X, ChevronUp, ChevronDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { getMoodStyleByScore } from '../../utils/moodColor';

interface DateSelectProps {
  value: string;
  onChange: (date: string) => void;
  className?: string;
  entries?: any[];
}

const WEEKS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

export const DateSelect: React.FC<DateSelectProps> = ({ value, onChange, className, entries }) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const [viewDate, setViewDate] = useState(() => {
    if (value) {
      const [y, m, d] = value.split('-').map(Number);
      return new Date(y, m - 1, d);
    }
    return new Date();
  });

  useEffect(() => {
    if (isOpen && value) {
      const [y, m, d] = value.split('-').map(Number);
      setViewDate(new Date(y, m - 1, d));
    }
  }, [isOpen, value]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const formatDate = (date: Date) => {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  };

  const scoresMap = useMemo(() => {
    const map = new Map<string, number>();
    if (!entries) return map;
    entries.forEach(e => {
        const d = new Date(e.timestamp);
        const k = formatDate(d); 
        // If multiple entries exist for a day, we take the last one's score
        map.set(k, e.mood.score);
    });
    return map;
  }, [entries]);

  const year = viewDate.getFullYear();
  const month = viewDate.getMonth();

  const handlePrevMonth = () => setViewDate(new Date(year, month - 1, 1));
  const handleNextMonth = () => setViewDate(new Date(year, month + 1, 1));
  
  const handleToday = () => {
    const today = new Date();
    const dateStr = formatDate(today);
    onChange(dateStr);
    setViewDate(today);
    setIsOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange('');
    setIsOpen(false);
  };

  const generateDays = () => {
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    const firstDay = new Date(year, month, 1).getDay(); 
    
    const days = [];
    for (let i = 0; i < firstDay; i++) {
      days.push(null);
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(new Date(year, month, i));
    }
    return days;
  };

  const days = generateDays();
  const formattedValue = value ? value.substring(5).replace('-', '/') : 'Date';

  return (
    <div className={`relative ${className}`} ref={containerRef}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`
          flex items-center gap-2 px-4 py-2 rounded-full border transition-all duration-300 shadow-sm group hover:shadow-lg
          ${value 
            ? 'bg-gradient-to-r from-blue-50 to-rose-50 border-indigo-100 text-slate-700' 
            : 'bg-white/90 border-white/60 text-slate-500 hover:bg-white hover:border-white backdrop-blur-md'
          }
        `}
      >
        <Calendar size={14} className={value ? 'text-indigo-500' : 'text-slate-400 group-hover:text-indigo-400 transition-colors'} />
        <span className="text-xs font-bold tracking-wide min-w-[3rem] text-center">
          {formattedValue}
        </span>
        {value && (
          <div
            role="button"
            onClick={handleClear}
            className="ml-1 p-0.5 rounded-full bg-slate-200/50 hover:bg-rose-200/50 text-slate-500 hover:text-rose-500 transition-colors cursor-pointer"
          >
            <X size={10} strokeWidth={3} />
          </div>
        )}
      </button>

      {/* Dropdown Calendar */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.2, ease: "easeOut" }}
            className="absolute top-full right-0 mt-3 z-50 w-72 bg-white/95 backdrop-blur-3xl rounded-[2rem] shadow-[0_20px_60px_-10px_rgba(0,0,0,0.15)] border border-white/80 overflow-hidden ring-1 ring-white/60"
          >
            {/* Ambient Gradients for that "Pink-Blue" feel */}
            <div className="absolute top-[-20%] left-[-20%] w-[50%] h-[50%] bg-blue-200/30 blur-3xl rounded-full pointer-events-none" />
            <div className="absolute bottom-[-20%] right-[-20%] w-[50%] h-[50%] bg-rose-200/30 blur-3xl rounded-full pointer-events-none" />

            {/* Header */}
            <div className="relative flex items-center justify-between px-6 py-5 border-b border-slate-100/50">
              <span className="text-lg font-bold text-slate-800 tracking-tight font-serif">
                {year}年{String(month + 1).padStart(2, '0')}月
              </span>
              <div className="flex gap-1">
                 <button onClick={handlePrevMonth} className="p-1.5 hover:bg-white/50 rounded-full transition-colors text-slate-400 hover:text-slate-700">
                    <ChevronUp size={18} />
                 </button>
                 <button onClick={handleNextMonth} className="p-1.5 hover:bg-white/50 rounded-full transition-colors text-slate-400 hover:text-slate-700">
                    <ChevronDown size={18} />
                 </button>
              </div>
            </div>

            {/* Grid */}
            <div className="relative p-5">
              <div className="grid grid-cols-7 mb-3">
                {WEEKS.map(w => (
                  <div key={w} className="text-center text-[10px] text-slate-400 font-bold uppercase tracking-wider">
                    {w}
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-7 gap-y-3 gap-x-1">
                {days.map((d, i) => {
                  if (!d) return <div key={`empty-${i}`} />;
                  
                  const dStr = formatDate(d);
                  const isSelected = value === dStr;
                  const isToday = formatDate(new Date()) === dStr;
                  const score = scoresMap.get(dStr);
                  const moodStyle = score !== undefined ? getMoodStyleByScore(score) : null;

                  return (
                    <div key={i} className="flex justify-center">
                      <button
                        onClick={() => {
                          onChange(dStr);
                          setIsOpen(false);
                        }}
                        style={{
                            background: isSelected 
                                ? `linear-gradient(to top right, #60a5fa, #818cf8)` 
                                : moodStyle 
                                    ? moodStyle.bg 
                                    : undefined,
                            boxShadow: isSelected ? '0 4px 6px -1px rgba(147, 197, 253, 0.5)' : undefined
                        }}
                        className={`
                          w-8 h-8 rounded-full text-xs transition-all flex items-center justify-center relative font-medium
                          ${isSelected 
                            ? 'text-white' 
                            : 'text-slate-600 hover:bg-white/80 hover:shadow-md'
                          }
                          ${!isSelected && isToday ? 'text-rose-500 font-bold' : ''}
                        `}
                      >
                        {d.getDate()}
                        {!isSelected && isToday && (
                            <div className="absolute -bottom-1 w-1 h-1 bg-rose-400 rounded-full"></div>
                        )}
                        {/* Dot Indicator for selected state if needed */}
                        {isSelected && moodStyle && (
                            <div className="absolute bottom-1 w-1 h-1 rounded-full border border-white/50" style={{ backgroundColor: moodStyle.bg }}></div>
                        )}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Footer */}
            <div className="relative flex items-center justify-between px-6 py-4 border-t border-slate-100/50 bg-white/50">
               <button 
                onClick={handleClear}
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors font-medium hover:underline decoration-slate-300 underline-offset-4"
               >
                 清除
               </button>
               <button 
                onClick={handleToday}
                className="text-xs text-indigo-500 hover:text-indigo-600 transition-colors font-bold bg-indigo-50 hover:bg-indigo-100 px-4 py-1.5 rounded-full shadow-sm"
               >
                 今天
               </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
