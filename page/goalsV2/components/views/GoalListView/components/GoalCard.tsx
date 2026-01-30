
import React from 'react';
import { motion } from 'framer-motion';
import { Calendar, Check, ArrowUpRight } from 'lucide-react';
import { Goal } from '../../../shared/types';
import { THEMES } from '../../../../hooks/useGoalStore';

interface GoalCardProps {
  goal: Goal;
  onClick: () => void;
  onToggleStatus?: (id: string) => void;
}

export const CategoryLabel = ({ children, theme = 'indigo' }: { children: React.ReactNode, theme?: string }) => {
  const themeConfig = THEMES[theme] || THEMES.indigo;
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/60 border border-white/60 text-[10px] font-bold tracking-widest uppercase backdrop-blur-sm shadow-sm transition-colors duration-300 ${themeConfig.meta}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${themeConfig.progressBg} shadow-sm group-hover:bg-white`}></span>
      {children}
    </span>
  );
};

const GoalCard: React.FC<GoalCardProps> = ({ goal, onClick, onToggleStatus }) => {
  const isCompleted = goal.status === 'completed';
  const theme = THEMES[goal.theme] || THEMES.indigo;

  return (
    <motion.div
      layoutId={`card-${goal.id}`}
      onClick={onClick}
      whileHover="hover"
      className={`group relative w-full h-60 overflow-hidden rounded-[1.5rem] border transition-all duration-500 ease-out flex flex-col justify-between cursor-pointer
        ${isCompleted 
          ? 'bg-slate-50/50 border-slate-100 opacity-60 grayscale' 
          : `${theme.container} shadow-[0_8px_30px_rgb(0,0,0,0.04)] hover:shadow-[0_20px_50px_rgb(0,0,0,0.12)]`
        }
      `}
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${theme.gradient} opacity-50 group-hover:opacity-0 transition-opacity duration-500 pointer-events-none`} />
      
      {/* Highlight Effect */}
      <motion.div 
        variants={{ hover: { x: '200%' } }}
        transition={{ duration: 1.2, ease: "easeInOut" }}
        className="absolute top-0 left-[-100%] w-full h-full bg-gradient-to-br from-transparent via-white/20 to-transparent skew-x-[-20deg] pointer-events-none z-10" 
      />

      <div className="relative z-20 p-5 flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <CategoryLabel theme={goal.theme}>{goal.category}</CategoryLabel>
        </div>

        <h3 className={`text-xl font-serif tracking-tight leading-snug transition-all duration-300 line-clamp-2 ${isCompleted ? 'line-through decoration-slate-300 text-slate-400' : theme.title}`}>
          {goal.title}
        </h3>
      </div>

      <div className="px-5">
        <div className={`h-px w-full border-t border-dashed transition-colors duration-300 ${isCompleted ? 'border-slate-200' : 'border-slate-200 group-hover:border-white/20'}`}></div>
      </div>

      <div className="relative z-20 p-5 pt-3 flex items-end justify-between">
        <div className="flex flex-col gap-1">
          <div className={`text-[10px] font-bold uppercase tracking-widest flex items-center gap-1.5 mb-1 transition-colors duration-300 ${theme.meta}`}>
            <Calendar size={10} />
            {goal.startDate} - {goal.endDate}
          </div>
          
          <div className="flex items-baseline gap-1">
             <span className={`text-3xl font-light tabular-nums tracking-tighter transition-colors duration-300 ${isCompleted ? 'text-slate-400' : theme.title}`}>
               {goal.timeInvested}
             </span>
             <div className="flex flex-col">
               <span className={`text-[9px] font-bold uppercase tracking-widest transition-colors duration-300 ${theme.meta}`}>
                 {goal.unit || 'HRS'}
               </span>
               <div className={`h-0.5 w-full rounded-full mt-0.5 transition-colors duration-300 ${isCompleted ? 'bg-slate-200' : `${theme.progressBg} opacity-30 group-hover:bg-white group-hover:opacity-40`}`}></div>
             </div>
          </div>
        </div>

        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={(e) => { e.stopPropagation(); onToggleStatus && onToggleStatus(goal.id); }}
          className={`relative flex items-center justify-center w-10 h-10 rounded-2xl border transition-all duration-300 shadow-sm
            ${isCompleted 
              ? 'bg-slate-100 border-slate-200 text-slate-400' 
              : theme.button
            }`}
        >
          {isCompleted ? <Check size={18} /> : <ArrowUpRight size={18} strokeWidth={1.5} />}
        </motion.button>
      </div>
    </motion.div>
  );
};

export default GoalCard;
