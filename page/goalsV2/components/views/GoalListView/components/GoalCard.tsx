
import React from 'react';
import { motion } from 'framer-motion';
import { Calendar, Check, ArrowUpRight, Pencil, Trash2 } from 'lucide-react';
import { Goal } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';

interface GoalCardProps {
  goal: Goal;
  onClick: () => void;
  onToggleStatus?: (id: string) => void;
  onEdit?: (goal: Goal) => void;
  onDelete?: (id: string) => void;
}

export const CategoryLabel = ({ children, theme = 'indigo' }: { children: React.ReactNode, theme?: string }) => {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/70 text-[10px] font-bold tracking-wider uppercase text-slate-600 backdrop-blur-sm">
      {children}
    </span>
  );
};

const GoalCard: React.FC<GoalCardProps> = ({ goal, onClick, onToggleStatus, onEdit, onDelete }) => {
  const isCompleted = goal.status === 'completed';
  const theme = THEMES[goal.theme] || THEMES.indigo;

  // 计算里程碑进度
  const milestoneProgress = goal.milestones?.length
    ? goal.milestones.filter(m => m.state === 1).length / goal.milestones.length
    : 0;

  return (
    <motion.div
      layoutId={`card-${goal.id}`}
      onClick={onClick}
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -4, boxShadow: '0 20px 40px -15px rgba(0,0,0,0.15)' }}
      className={`group relative rounded-[1.25rem] transition-all duration-300 overflow-hidden cursor-pointer ${
        isCompleted ? 'opacity-50 grayscale' : ''
      }`}
      style={{
        background: isCompleted
          ? '#f1f5f9'
          : `linear-gradient(135deg, ${theme.accentColor}15 0%, ${theme.accentColor}30 100%)`,
        border: `1px solid ${isCompleted ? '#e2e8f0' : theme.accentColor}25`
      }}
    >
      <div className="p-5">
        {/* Header: Category & Actions */}
        <div className="flex items-start justify-between mb-3">
          <CategoryLabel theme={goal.theme}>{goal.category}</CategoryLabel>

          {/* Action Buttons */}
          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
            {onEdit && (
              <button
                onClick={(e) => { e.stopPropagation(); onEdit(goal); }}
                className="p-1.5 hover:bg-white/50 rounded-lg transition-colors text-slate-500 hover:text-slate-700"
                title="编辑"
              >
                <Pencil size={14} />
              </button>
            )}
            {onDelete && (
              <button
                onClick={(e) => { e.stopPropagation(); onDelete(goal.id); }}
                className="p-1.5 hover:bg-red-100/50 rounded-lg transition-colors text-slate-500 hover:text-red-500"
                title="删除"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
        </div>

        {/* Title */}
        <h3 className={`text-lg font-semibold leading-snug mb-3 line-clamp-2 ${
          isCompleted ? 'line-through text-slate-400' : 'text-slate-800'
        }`}>
          {goal.title}
        </h3>

        {/* Date Range */}
        <div className="flex items-center gap-1.5 text-xs text-slate-500 mb-4">
          <Calendar size={12} />
          <span className="font-medium">{goal.startDate} — {goal.endDate}</span>
        </div>

        {/* Progress Section */}
        <div className="space-y-3">
          {/* Milestone Progress */}
          {goal.milestones && goal.milestones.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex justify-between items-center text-xs">
                <span className="text-slate-500 font-medium">里程碑进度</span>
                <span className="text-slate-600 font-semibold">
                  {goal.milestones.filter(m => m.state === 1).length}/{goal.milestones.length}
                </span>
              </div>
              <div className="h-1.5 bg-white/50 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${milestoneProgress * 100}%` }}
                  transition={{ duration: 0.5, ease: 'easeOut' }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: theme.accentColor }}
                />
              </div>
            </div>
          )}

          {/* Stats Row */}
          <div className="flex items-center justify-between pt-3 border-t border-slate-200/50">
            <div className="flex items-center gap-4">
              {/* Time Invested */}
              <div className="flex items-baseline gap-1">
                <span className={`text-2xl font-bold tabular-nums ${isCompleted ? 'text-slate-400' : 'text-slate-800'}`}>
                  {goal.timeInvested}
                </span>
                <span className="text-xs font-medium text-slate-500 uppercase">
                  {goal.unit || 'HRS'}
                </span>
              </div>
            </div>

            {/* Toggle Status Button */}
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={(e) => { e.stopPropagation(); onToggleStatus && onToggleStatus(goal.id); }}
              className="flex items-center justify-center w-10 h-10 rounded-xl transition-all duration-200"
              style={{
                backgroundColor: isCompleted ? '#e2e8f0' : theme.accentColor,
                color: isCompleted ? '#94a3b8' : 'white',
                boxShadow: isCompleted ? 'none' : `0 4px 12px ${theme.accentColor}40`
              }}
            >
              {isCompleted ? <Check size={18} /> : <ArrowUpRight size={18} strokeWidth={2} />}
            </motion.button>
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default GoalCard;
