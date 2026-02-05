
import React, { useState, useMemo, useRef, useEffect } from 'react';
import { getMoodStyleByScore, MOOD_COLOR_POINTS } from '../../utils/moodColor';

interface EmotionChartProps {
  entries: any[];
  className?: string;
  selectedDate?: string;
  onSelectDate?: (date: string) => void;
}

const EmotionChart: React.FC<EmotionChartProps> = ({ entries, className, selectedDate, onSelectDate }) => {
  const [timeScale, setTimeScale] = useState('week'); 
  const [activeMainTab, setActiveMainTab] = useState<'status' | 'factors'>('status'); 
  const [activeTag, setActiveTag] = useState<string | null>(null);
  
  const chartAreaRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 600, height: 280 });

  useEffect(() => {
    if (chartAreaRef.current) {
        const resizeObserver = new ResizeObserver((entries) => {
            if (entries[0]) {
                setDimensions({
                    width: entries[0].contentRect.width,
                    height: entries[0].contentRect.height
                });
            }
        });
        resizeObserver.observe(chartAreaRef.current);
        return () => resizeObserver.disconnect();
    }
  }, []);

  // Process entries into points
  const allPoints = useMemo(() => {
    return entries.map(e => {
        const d = new Date(e.timestamp);
        const y = d.getFullYear();
        const m = d.getMonth();
        const day = d.getDate();
        
        // Use Local Start of Day for X-axis alignment
        const normalizedTimestamp = new Date(y, m, day).getTime();

        return {
            timestamp: e.timestamp,
            normalizedTimestamp, 
            dateIso: `${y}-${String(m + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
            value: e.mood.score,
            tags: e.impacts || [],
            mood: e.mood,
            stats: e.stats || { screenTime: { work: 0, entertainment: 0, other: 0 }, sleep: 0 }
        };
    }).sort((a, b) => a.timestamp - b.timestamp);
  }, [entries]);

  // Extract all unique tags
  const allTags = useMemo(() => {
    const tags = new Set<string>();
    allPoints.forEach(p => p.tags.forEach((t: string) => tags.add(t)));
    return Array.from(tags);
  }, [allPoints]);

  // Calculate Time Config
  const timeConfig = useMemo(() => {
    let anchor = new Date();
    if (selectedDate) {
        const [y, m, d] = selectedDate.split('-').map(Number);
        anchor = new Date(y, m - 1, d);
    }
    anchor.setHours(0, 0, 0, 0);

    let startDate: Date, endDate: Date;
    let ticks: { ts: number, label: string }[] = [];

    if (timeScale === 'week') {
      const day = anchor.getDay(); // 0 is Sunday
      // Align to Monday (or Sunday depending on preference, using Monday here for standard work week view)
      const diff = anchor.getDate() - day + (day === 0 ? -6 : 1);
      startDate = new Date(anchor);
      startDate.setDate(diff);
      
      endDate = new Date(startDate);
      endDate.setDate(startDate.getDate() + 6);
      endDate.setHours(23, 59, 59, 999);
      
      for (let i = 0; i < 7; i++) {
          const t = new Date(startDate);
          t.setDate(startDate.getDate() + i);
          ticks.push({
              ts: t.getTime(),
              label: t.toLocaleDateString('en-US', { weekday: 'short' })
          });
      }
    } else if (timeScale === 'month') {
      startDate = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
      endDate = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0);
      endDate.setHours(23, 59, 59, 999);
      
      const totalDays = endDate.getDate();
      // Show ~6 ticks
      const step = Math.ceil(totalDays / 6);
      for (let i = 1; i <= totalDays; i += step) {
          const t = new Date(startDate);
          t.setDate(i);
          ticks.push({
              ts: t.getTime(),
              label: `${t.getMonth() + 1}/${t.getDate()}`
          });
      }
    } else {
       // Year or 6 Months fallback
       startDate = new Date(anchor.getFullYear(), 0, 1);
       endDate = new Date(anchor.getFullYear(), 11, 31);
       endDate.setHours(23, 59, 59, 999);
       
       for (let i = 0; i < 12; i++) {
           const t = new Date(anchor.getFullYear(), i, 1);
           ticks.push({
               ts: t.getTime(),
               label: t.toLocaleDateString('en-US', { month: 'narrow' })
           });
       }
    }

    return { startDate, endDate, ticks };
  }, [timeScale, selectedDate]);

  const filteredPoints = useMemo(() => {
    return allPoints.filter(d => d.normalizedTimestamp >= timeConfig.startDate.getTime() && d.normalizedTimestamp <= timeConfig.endDate.getTime());
  }, [allPoints, timeConfig]);

  // --- Chart Drawing Logic ---
  const { width, height } = dimensions;
  const paddingLeft = 40; 
  const paddingRight = 20;
  const bottomLabelHeight = 30;

  // Split View Configuration
  const isSplitView = activeMainTab === 'factors';
  
  // Calculate vertical space
  const availableHeight = height - bottomLabelHeight - 20; // 20 for top padding
  
  // Mood Chart Area (Top)
  const moodTop = 20;
  // If split, take ~50% of available space roughly.
  // availableHeight is total usable.
  // Let's use exactly half of available space for consistency.
  const gap = 20;
  const halfH = (availableHeight - gap) / 2;
  
  const moodBottom = isSplitView ? (moodTop + halfH) : (height - bottomLabelHeight - 10);
  const moodHeight = Math.max(0, moodBottom - moodTop);

  // Bar Chart Area (Bottom)
  const barTop = isSplitView ? (moodBottom + gap) : height; 
  const barBottom = height - bottomLabelHeight;
  const barHeight = Math.max(0, barBottom - barTop);

  // Helper to get day index relative to start (Integer days)
  const getDayIndex = (ts: number, startTs: number) => {
      const d = new Date(ts); d.setHours(0,0,0,0);
      const start = new Date(startTs); start.setHours(0,0,0,0);
      // Rounding handles DST crossing (e.g. 23h or 25h days)
      return Math.round((d.getTime() - start.getTime()) / 86400000);
  };

  const getX = (timestamp: number) => {
    if (timeScale === 'year') {
         const range = timeConfig.endDate.getTime() - timeConfig.startDate.getTime() || 1;
         return paddingLeft + ((timestamp - timeConfig.startDate.getTime()) * (width - paddingLeft - paddingRight)) / range;
    }

    // Integer Day Logic for Week/Month
    const idx = getDayIndex(timestamp, timeConfig.startDate.getTime());
    
    // How many days in view?
    let totalDays = 7;
    if (timeScale === 'month') {
        const d = new Date(timeConfig.startDate);
        totalDays = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
    }
    
    const range = totalDays; // Maps 0..6 to 0..6/7 of width
    // To make sure bars are centered on ticks:
    // If we use grid ticks at specific days, we map idx directly.
    return paddingLeft + (idx / range) * (width - paddingLeft - paddingRight);
  };

  const getMoodY = (value: number) => moodBottom - (value * moodHeight) / 100;

  const maxFactorValue = 16; 
  const getBarHeight = (val: number) => (val / maxFactorValue) * barHeight;

  return (
    <div className={`bg-white/60 backdrop-blur-md rounded-[2.5rem] shadow-xl overflow-hidden border border-white/60 text-slate-800 flex flex-col h-full ${className}`}>
      
      {/* Top Controls */}
      <div className="p-8 pb-4 flex-shrink-0 bg-white/40 backdrop-blur-sm border-b border-slate-100/50">
        <div className="flex flex-col gap-2 mb-6">
          <h1 className="text-2xl font-bold text-slate-900 tracking-tight">Mind Space</h1>
          <div className="flex items-center gap-2 text-[10px] tracking-[0.2em] uppercase font-semibold text-slate-400">
                <span>Mood</span>
                <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                <span>Journal</span>
                <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                <span>Being</span>
          </div>
        </div>
        
        <div className="flex items-center justify-between mb-4">
            <div className="flex bg-slate-100/80 p-1 rounded-xl">
                {['week', 'month', 'year'].map((id) => {
                const labels: Record<string, string> = { week: 'W', month: 'M', year: 'Y' };
                return (
                    <button
                    key={id}
                    onClick={() => setTimeScale(id)}
                    className={`px-3 py-1.5 rounded-lg text-[10px] font-bold transition-all ${
                        timeScale === id ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'
                    }`}
                    >
                    {labels[id]}
                    </button>
                );
                })}
            </div>
            
            <span className="text-slate-300 text-[10px] font-bold uppercase tracking-wide">
               {timeConfig.startDate.toLocaleDateString()} — {timeConfig.endDate.toLocaleDateString()}
            </span>
        </div>
      </div>

      {/* Chart Area */}
      <div className="px-2 py-4 relative flex-grow min-h-[180px]" ref={chartAreaRef}>
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-visible transition-all duration-700">
          <defs>
            <linearGradient id="appleMoodGradient" x1="0" y1="1" x2="0" y2="0">
              {MOOD_COLOR_POINTS.map(stop => (
                <stop key={stop.p} offset={`${stop.p}%`} stopColor={stop.color} />
              ))}
            </linearGradient>
            <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                <feGaussianBlur stdDeviation="3" result="blur" />
                <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>
          </defs>

          {/* --- Shared X Axis Labels --- */}
          {timeConfig.ticks.map((tick, i) => (
            <text
              key={i}
              x={getX(tick.ts)}
              y={height - 10}
              textAnchor="middle"
              className="text-[10px] fill-slate-400 font-semibold"
            >
              {tick.label}
            </text>
          ))}

          {/* --- Mood Chart Layer (Top) --- */}
          <g className="transition-all duration-700">
             {/* Y Axis Bar for Mood (Range Indicator) */}
             <rect x={paddingLeft - 10} y={moodTop} width="4" height={moodHeight} fill="url(#appleMoodGradient)" rx="2" className="opacity-80 transition-all duration-700" />
             
             {/* Horizontal Grid Lines */}
             {[0, 50, 100].map(v => (
                <line 
                  key={v} 
                  x1={paddingLeft} 
                  y1={getMoodY(v)} 
                  x2={width - paddingRight} 
                  y2={getMoodY(v)} 
                  stroke="#e2e8f0" 
                  strokeWidth="1" 
                  strokeDasharray="4 4"
                  className="transition-all duration-700" 
                />
             ))}

             {/* Mood Points */}
             {filteredPoints.map((d, i) => {
                const isMatch = !activeTag || d.tags.includes(activeTag);
                const isSelected = selectedDate === d.dateIso;
                const moodStyle = getMoodStyleByScore(d.value);
                const r = isSelected ? "8" : (isMatch ? (activeTag ? "7" : "5") : "3");
                const strokeWidth = isSelected ? "3" : (isMatch ? "2" : "0");
                
                return (
                  <circle
                    key={i}
                    // FIXED: Use normalizedTimestamp (via integer day index logic) to align with ticks and bars
                    cx={getX(d.normalizedTimestamp)}
                    cy={getMoodY(d.value)}
                    r={r}
                    fill={moodStyle.color}
                    opacity={isMatch || isSelected ? "1" : "0.3"}
                    stroke="white"
                    strokeWidth={strokeWidth}
                    className="transition-all duration-500 cursor-pointer ease-out hover:scale-125"
                    filter={isMatch ? "url(#glow)" : ""}
                    onClick={() => onSelectDate && onSelectDate(d.dateIso)}
                  />
                );
             })}
          </g>

          {/* --- Life Factors Chart Layer (Bottom) --- */}
          <g className={`transition-all duration-700 ${isSplitView ? 'opacity-100' : 'opacity-0'}`}>
             {isSplitView && (
                <>
                   {/* Y Axis Line for Factors */}
                   <line x1={paddingLeft} y1={barTop} x2={paddingLeft} y2={barBottom} stroke="#e2e8f0" strokeWidth="2" />
                   
                   {/* Stacked Bars */}
                   {filteredPoints.map((d, i) => {
                      // FIXED: Use normalizedTimestamp
                      const x = getX(d.normalizedTimestamp);
                      // Adjust bar width based on scale to look good
                      const barWidth = timeScale === 'week' ? 16 : 8;
                      
                      // Data
                      const workH = getBarHeight(d.stats.screenTime.work);
                      const entH = getBarHeight(d.stats.screenTime.entertainment);
                      const otherH = getBarHeight(d.stats.screenTime.other);
                      
                      return (
                         <g key={`bar-${i}`} onClick={() => onSelectDate && onSelectDate(d.dateIso)} className="cursor-pointer group">
                            {/* Work Bar (Bottom) */}
                            <rect 
                                x={x - barWidth/2} 
                                y={barBottom - workH} 
                                width={barWidth} 
                                height={workH} 
                                fill="#6366f1" 
                                rx="2"
                                className="transition-all hover:opacity-80"
                            />
                            {/* Entertainment Bar (Middle) */}
                            <rect 
                                x={x - barWidth/2} 
                                y={barBottom - workH - entH - 1} 
                                width={barWidth} 
                                height={entH} 
                                fill="#fb7185" 
                                rx="2"
                                className="transition-all hover:opacity-80"
                            />
                            {/* Other Bar (Top) */}
                            <rect 
                                x={x - barWidth/2} 
                                y={barBottom - workH - entH - otherH - 2} 
                                width={barWidth} 
                                height={otherH} 
                                fill="#94a3b8" 
                                rx="2"
                                className="transition-all hover:opacity-80"
                            />
                            
                            {/* Selection Indicator */}
                            {selectedDate === d.dateIso && (
                               <rect 
                                  x={x - barWidth/2 - 3} 
                                  y={barTop} 
                                  width={barWidth + 6} 
                                  height={barHeight} 
                                  fill="transparent" 
                                  stroke="#6366f1" 
                                  strokeWidth="1" 
                                  rx="4"
                                  strokeDasharray="3 3"
                               />
                            )}
                         </g>
                      );
                   })}
                   
                   {/* Factor Legend Label */}
                   <text x={width - paddingRight} y={barTop - 12} textAnchor="end" className="text-[10px] font-bold uppercase fill-slate-400 tracking-wider">
                      DAILY SCREEN TIME (HRS)
                   </text>
                </>
             )}
          </g>

        </svg>
      </div>

      {/* Bottom Tabs */}
      <div className="px-8 py-5 flex-shrink-0 bg-white/40 border-t border-slate-100/50">
        <div className="flex bg-slate-100/80 p-1.5 rounded-2xl mb-3">
          <button
            onClick={() => setActiveMainTab('status')}
            className={`flex-1 py-2 text-[10px] font-bold rounded-xl transition-all capitalize ${
              activeMainTab === 'status' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveMainTab('factors')}
            className={`flex-1 py-2 text-[10px] font-bold rounded-xl transition-all capitalize ${
              activeMainTab === 'factors' ? 'bg-white text-indigo-600 shadow-sm' : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            Life Factors
          </button>
        </div>

        {/* Details Content */}
        <div className="min-h-[80px] max-h-[100px] overflow-y-auto custom-scrollbar pr-1">
          {activeMainTab === 'factors' ? (
             <div className="animate-in fade-in slide-in-from-right-2 duration-300">
                 {/* Factor Legend */}
                 <div className="flex items-center justify-between mb-2 px-2">
                     <span className="text-[10px] uppercase font-bold text-slate-400">Categories</span>
                     <div className="flex gap-3">
                         <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-indigo-500"></div><span className="text-[9px] text-slate-500">Work</span></div>
                         <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-rose-400"></div><span className="text-[9px] text-slate-500">Ent.</span></div>
                         <div className="flex items-center gap-1"><div className="w-2 h-2 rounded-full bg-slate-400"></div><span className="text-[9px] text-slate-500">Other</span></div>
                     </div>
                 </div>
                 <div className="grid grid-cols-2 gap-2 mt-3">
                    <button className="p-2 bg-white border border-indigo-100 rounded-xl text-left shadow-sm">
                        <span className="block text-[9px] uppercase font-bold text-indigo-400">Active Time</span>
                        <span className="text-sm font-bold text-slate-700">6.4h <span className="text-[9px] font-normal text-slate-400">/ day</span></span>
                    </button>
                    <button className="p-2 bg-white border border-transparent hover:border-slate-100 rounded-xl text-left opacity-60 hover:opacity-100">
                         <span className="block text-[9px] uppercase font-bold text-slate-400">Total Logs</span>
                         <span className="text-sm font-bold text-slate-700">{entries.length}</span>
                    </button>
                 </div>
             </div>
          ) : (
             <div className="animate-in fade-in slide-in-from-left-2 duration-300">
                <div className="flex flex-wrap gap-2">
                  {allTags.length > 0 ? allTags.map(tagName => {
                    const count = filteredPoints.filter(d => d.tags.includes(tagName)).length;
                    if (count === 0) return null;
                    return (
                        <div 
                        key={tagName}
                        onClick={() => setActiveTag(activeTag === tagName ? null : tagName)}
                        className={`px-3 py-2 rounded-xl flex justify-between items-center cursor-pointer transition-all border ${
                            activeTag === tagName ? 'bg-indigo-50 border-indigo-200' : 'bg-white border-transparent hover:border-indigo-100 hover:shadow-sm'
                        }`}
                        >
                        <span className={`text-[10px] font-bold ${activeTag === tagName ? 'text-indigo-700' : 'text-slate-600'}`}>{tagName}</span>
                        <div className="flex items-center gap-2 ml-2">
                            <span className="text-[9px] font-semibold text-slate-400 bg-slate-100 px-1.5 py-0.5 rounded-full">{count}</span>
                        </div>
                        </div>
                    )
                  }) : (
                    <div className="text-center text-[10px] text-slate-400 py-2 italic w-full">No impacts recorded</div>
                  )}
                </div>
             </div>
          )}
        </div>
      </div>
      
      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 3px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
      `}</style>
    </div>
  );
};

export default EmotionChart;
