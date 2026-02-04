import React from 'react';
import { motion } from 'framer-motion';
import { Calendar, Check, Trash2, Clock } from 'lucide-react';
import { Goal } from '../../../../types';
import { THEMES } from '../../../../hooks/useGoalStore';
import { formatDateForDisplay } from '../../../../api';
import MilestoneProgressBar from './milestone/MilestoneProgressBar';

interface GoalCardV2Props {
  goal: Goal;
  onClick: (id: string) => void;
  onDelete: (id: string) => void;
  onToggleStatus: (id: string) => void;
}

export const CategoryLabel = ({ children }: { children: React.ReactNode }) => {
  return (
    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/70 text-[10px] font-bold tracking-wider uppercase text-slate-600 backdrop-blur-sm">
      {children}
    </span>
  );
};

const GoalCardV2: React.FC<GoalCardV2Props> = ({
  goal,
  onClick,
  onDelete,
  onToggleStatus,
}) => {
  const isCompleted = goal.status === 'completed';
  const theme = THEMES[goal.theme] || THEMES.indigo;

  // Calculate days started
  const daysStarted = goal.startDate
    ? Math.max(0, Math.floor((Date.now() - new Date(goal.startDate).getTime()) / (1000 * 60 * 60 * 24)))
    : 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      onClick={() => onClick(goal.id)}
      className={`relative rounded-[1.25rem] transition-all duration-300 overflow-hidden cursor-pointer hover:shadow-lg ${
        isCompleted ? 'opacity-60 grayscale' : ''
      }`}
      style={{
        background: isCompleted
          ? '#f1f5f9'
          : `linear-gradient(135deg, ${theme.accentColor}10 0%, ${theme.accentColor}20 100%)`,
        border: `1px solid ${isCompleted ? '#e2e8f0' : theme.accentColor}20`,
      }}
      whileHover={{ y: -2 }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Theme Color Bar */}
      <div
        className="h-1 w-full"
        style={{ backgroundColor: theme.accentColor }}
      />

      <div className="p-5">
        {/* Header: Category & Actions */}
        <div className="flex items-start justify-between mb-3">
          <CategoryLabel>{goal.category || '未分类'}</CategoryLabel>

          {/* Action Buttons */}
          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
            <button
              onClick={(e) => { e.stopPropagation(); onDelete(goal.id); }}
              className="p-1.5 hover:bg-red-100/50 rounded-lg transition-colors text-slate-400 hover:text-red-500"
              title="删除"
            >
              <Trash2 size={14} />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onToggleStatus(goal.id); }}
              className="p-1.5 rounded-lg transition-colors flex items-center justify-center"
              style={{
                backgroundColor: isCompleted ? '#e2e8f0' : `${theme.accentColor}20`,
                color: isCompleted ? '#94a3b8' : theme.accentColor,
              }}
              title={isCompleted ? '标记为进行中' : '标记为完成'}
            >
              <Check size={14} />
            </button>
          </div>
        </div>

        {/* Title */}
        <div className="mb-4">
          <h3 className={`text-lg font-semibold leading-snug ${isCompleted ? 'text-slate-500 line-through' : 'text-slate-800'}`}>
            {goal.title}
          </h3>
        </div>

        {/* Stats Row */}
        <div className="flex items-center gap-4 mb-4">
          {/* Time Invested */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white/60 rounded-xl">
            <Clock size={14} className="text-slate-400" />
            <span className="text-lg font-bold tabular-nums text-slate-800">
              {goal.timeInvested}
            </span>
            <span className="text-[10px] font-medium text-slate-400 uppercase">
              {goal.unit || 'HRS'}
            </span>
          </div>

          {/* Days Started */}
          <div className="flex items-center gap-2 px-3 py-2 bg-white/60 rounded-xl">
            <Calendar size={14} className="text-slate-400" />
            <span className="text-lg font-bold tabular-nums text-slate-800">
              {daysStarted}
            </span>
            <span className="text-[10px] font-medium text-slate-400">天</span>
          </div>

          {/* Milestone Progress */}
          {goal.milestones && goal.milestones.length > 0 && (
            <div className="flex items-center gap-2 px-3 py-2 bg-white/60 rounded-xl">
              <MilestoneProgressBar
                milestones={goal.milestones}
                accentColor={theme.accentColor}
              />
            </div>
          )}
        </div>

        {/* Date Range */}
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <Calendar size={12} />
          <span className="font-medium">
            {formatDateForDisplay(goal.startDate)} — {formatDateForDisplay(goal.endDate)}
          </span>
        </div>
      </div>
    </motion.div>
  );
};

export default GoalCardV2;
