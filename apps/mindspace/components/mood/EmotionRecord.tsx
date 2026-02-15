
import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Sun, Wind, Cloud, Moon, Heart, Plus, Flame, ShieldAlert, 
  Zap, Ghost, Star, Coffee, Music, Book, Camera, Gamepad, Smile, Meh, Frown,
  Filter, Edit3, Trash2
} from 'lucide-react';
import EmotionChart from './EmotionChart';
import { DateSelect } from './DateSelect';

const ICON_MAP: Record<string, any> = { 
  Sun, Wind, Cloud, Moon, Heart, Plus, Flame, ShieldAlert, 
  Zap, Ghost, Star, Coffee, Music, Book, Camera, Gamepad, Smile, Meh, Frown 
};

interface EmotionRecordProps {
  entries: any[];
  onNavigate?: (view: any) => void;
  onEdit?: (entry: any) => void;
  onDelete?: (id: string) => void;
}

const EmotionRecord: React.FC<EmotionRecordProps> = ({ entries, onNavigate, onEdit, onDelete }) => {
  const [filterDate, setFilterDate] = useState<string>('');

  // Filter entries based on the selected date string (YYYY-MM-DD)
  const filteredEntries = useMemo(() => {
    if (!filterDate) return entries;
    return entries.filter(entry => {
      // Ensure we are comparing dates correctly based on local time
      const entryDate = new Date(entry.timestamp);
      const year = entryDate.getFullYear();
      const month = String(entryDate.getMonth() + 1).padStart(2, '0');
      const day = String(entryDate.getDate()).padStart(2, '0');
      const dateString = `${year}-${month}-${day}`;
      return dateString === filterDate;
    });
  }, [entries, filterDate]);

  return (
    <motion.div 
      initial={{ opacity: 0 }} 
      animate={{ opacity: 1 }} 
      className="w-full h-full pt-24 px-4 md:px-8 lg:px-12 flex flex-col lg:flex-row gap-6 pb-6 overflow-hidden"
    >
      {/* Left Section: Mind Space Visualization (Chart) - 40% width on Desktop */}
      <div className="w-full lg:w-[45%] flex-shrink-0 h-[45%] lg:h-full min-h-[300px] flex flex-col rounded-[2.5rem] overflow-hidden shadow-lg bg-white/40 border border-white/50">
         <EmotionChart 
            entries={entries} 
            className="h-full w-full border-none shadow-none rounded-none bg-transparent" 
            selectedDate={filterDate}
            onSelectDate={setFilterDate}
         />
      </div>

      {/* Right Section: Journal Log (Mood, Diary, Being) - 60% width on Desktop */}
      <div className="w-full lg:w-[55%] flex-1 min-h-0 flex flex-col bg-white/60 backdrop-blur-2xl rounded-[2.5rem] border border-white/60 shadow-xl overflow-hidden ring-1 ring-white/40">
         <div className="px-8 py-5 border-b border-white/40 bg-white/40 z-10 sticky top-0 backdrop-blur-xl flex justify-between items-center shadow-sm">
            <div className="flex flex-col gap-1">
              <h3 className="text-xl font-bold text-slate-800 tracking-tight">Timeline</h3>
              <div className="flex items-center gap-2 text-[10px] tracking-[0.2em] uppercase font-semibold text-slate-400">
                <span>Journal</span>
                <span className="w-1 h-1 rounded-full bg-slate-300"></span>
                <span>Life Factors</span>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
                 {/* Custom Date Select Component */}
                 <DateSelect 
                    value={filterDate} 
                    onChange={setFilterDate}
                    entries={entries}
                 />

                 <div className="hidden sm:flex text-[10px] font-bold text-indigo-500 bg-indigo-50 px-3 py-1.5 rounded-full uppercase tracking-wider shadow-sm">
                    {filteredEntries.length} {filterDate ? 'Found' : 'Records'}
                 </div>
            </div>
         </div>

         <div className="flex-1 overflow-y-auto custom-scrollbar p-4 md:p-6 space-y-3">
            {filteredEntries.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center opacity-40 gap-6 min-h-[200px]">
                    <div className="w-16 h-16 rounded-[1.5rem] bg-indigo-50 flex items-center justify-center transform -rotate-3 transition-transform hover:rotate-0 shadow-inner">
                        {filterDate ? (
                             <Filter size={28} className="text-indigo-400" strokeWidth={1.5} />
                        ) : (
                             <Book size={28} className="text-indigo-400" strokeWidth={1.5} />
                        )}
                    </div>
                    <div className="text-center">
                        <span className="text-xs tracking-[0.3em] uppercase text-slate-500 block mb-2">
                            {filterDate ? 'No Entries Found' : 'Empty Journal'}
                        </span>
                        <span className="text-[10px] text-slate-400 font-light">
                            {filterDate ? `Nothing recorded on ${filterDate}` : 'Your story begins with the first word'}
                        </span>
                        {filterDate && (
                             <button 
                                onClick={() => setFilterDate('')}
                                className="mt-4 text-[10px] font-bold text-indigo-500 hover:text-indigo-600 uppercase tracking-widest border-b border-indigo-200 pb-0.5"
                             >
                                Clear Filter
                             </button>
                        )}
                    </div>
                </div>
            ) : (
                filteredEntries.slice().reverse().map((entry) => {
                const IconComp = ICON_MAP[entry.mood.icon] || Plus;
                return (
                    <motion.div 
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        key={entry.id} 
                        className="flex gap-5 items-start group p-5 rounded-[2rem] bg-white/80 hover:bg-white transition-all border border-white shadow-sm hover:shadow-md cursor-default ring-1 ring-slate-50 relative"
                    >
                        {/* Timestamp Column */}
                        <div className="w-12 shrink-0 pt-1 flex flex-col items-center gap-0.5">
                            <span className="text-sm font-bold text-slate-700">{new Date(entry.timestamp).toLocaleDateString([], {day: '2-digit'})}</span>
                            <span className="text-[9px] uppercase tracking-wider font-bold text-slate-400">{new Date(entry.timestamp).toLocaleDateString([], {month: 'short'})}</span>
                            <div className="h-full w-[1px] bg-indigo-100 my-2 group-last:hidden rounded-full" />
                        </div>
                        
                        {/* Content Column */}
                        <div className="flex-1 min-w-0 relative">
                            {/* Header: Mood & Time */}
                            <div className="flex items-center justify-between mb-3">
                                <div className="flex items-center gap-2.5">
                                    <div 
                                        className="w-8 h-8 rounded-xl flex items-center justify-center text-white shadow-sm ring-2 ring-white"
                                        style={{ backgroundColor: entry.mood.color }}
                                    >
                                        <IconComp size={14} strokeWidth={2.5} className={entry.mood.isDark ? 'text-white' : 'text-slate-800'} />
                                    </div>
                                    <span className="text-sm font-bold text-slate-800">{entry.mood.text}</span>
                                </div>
                                <div className="flex items-center gap-3">
                                  <span className="text-[10px] text-slate-400 font-medium bg-slate-50 px-2 py-1 rounded-full border border-slate-100">
                                      {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                  </span>
                                  
                                  {/* Actions - Visible on Hover */}
                                  <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                                     {onEdit && (
                                       <button 
                                         onClick={(e) => { e.stopPropagation(); onEdit(entry); }}
                                         className="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-full transition-colors"
                                         title="Edit Entry"
                                       >
                                         <Edit3 size={14} />
                                       </button>
                                     )}
                                     {onDelete && (
                                       <button 
                                         onClick={(e) => { e.stopPropagation(); onDelete(entry.id); }}
                                         className="p-1.5 text-slate-400 hover:text-rose-500 hover:bg-rose-50 rounded-full transition-colors"
                                         title="Delete Entry"
                                       >
                                         <Trash2 size={14} />
                                       </button>
                                     )}
                                  </div>
                                </div>
                            </div>
                            
                            {/* Body: Note */}
                            {entry.note && (
                                <p className="font-light text-sm leading-relaxed text-slate-600 mb-4 whitespace-pre-wrap break-words">
                                    {entry.note}
                                </p>
                            )}
                            
                            {/* Footer: Tags & Stats */}
                            <div className="flex flex-wrap items-center gap-3">
                                {entry.impacts?.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {entry.impacts.map((i: string) => (
                                            <span key={i} className="text-[9px] tracking-wider uppercase px-2.5 py-1 rounded-lg bg-indigo-50/80 text-indigo-600 font-bold border border-indigo-100/50">
                                                {i}
                                            </span>
                                        ))}
                                    </div>
                                )}
                                {entry.stats && (
                                    <div className="flex items-center gap-2 text-[9px] font-medium text-slate-400 border-l pl-3 border-slate-100">
                                        <span>Screen: {(entry.stats.screenTime.work + entry.stats.screenTime.entertainment + entry.stats.screenTime.other).toFixed(1)}h</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </motion.div>
                );
                })
            )}
         </div>
      </div>
    </motion.div>
  );
};

export default EmotionRecord;
