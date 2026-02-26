import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Check, MoreVertical, Pause, Play, History, Edit2, Trash2, Anchor } from 'lucide-react';
import { Habit, getFrequencyText, getLevelConfig } from '../../../../types';
import { LevelBadge } from '../../../shared/LevelBadge';

interface HabitCardProps {
  habit: Habit;
  onCheckIn: (habitId: string) => void;
  onEdit: (habit: Habit) => void;
  onPause: (habitId: string) => void;
  onResume: (habitId: string) => void;
  onViewHistory: (habitId: string) => void;
  onDelete: (habitId: string) => void;
  isCheckedToday?: boolean;
}

const HabitCard: React.FC<HabitCardProps> = ({
  habit,
  onCheckIn,
  onEdit,
  onPause,
  onResume,
  onViewHistory,
  onDelete,
  isCheckedToday = false
}) => {
  const [showMenu, setShowMenu] = useState(false);
  const levelConfig = getLevelConfig(habit.currentLevel);
  const isPaused = habit.status === 'paused';

  const challengeProgress = habit.currentChallenge
    ? habit.currentChallenge.completedCount / habit.currentChallenge.requiredCompletions
    : 0;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      whileHover={{ y: -4, boxShadow: '0 20px 40px -12px rgba(251, 191, 36, 0.15)' }}
      className={`group relative bg-white rounded-3xl border transition-all duration-300 overflow-hidden ${
        isPaused
          ? 'border-stone-200 opacity-60'
          : 'border-stone-100 hover:border-amber-200'
      }`}
    >
      {/* Left side level indicator bar */}
      <div
        className="absolute top-4 bottom-4 left-0 w-1 rounded-r-full"
        style={{ backgroundColor: levelConfig.color }}
      />

      <div className="p-5 pl-5">
        {/* Header */}
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            {/* Level color indicator */}
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
              style={{ backgroundColor: `${levelConfig.color}20` }}
            >
              <div
                className="w-3 h-6 rounded-sm"
                style={{ backgroundColor: levelConfig.color }}
              />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <h3 className={`font-semibold text-stone-800 truncate ${isPaused ? 'line-through text-stone-400' : ''}`}>
                  {habit.name}
                </h3>
                {isPaused && (
                  <span className="px-2 py-0.5 bg-stone-100 text-stone-500 text-[10px] font-bold rounded-full flex-shrink-0">
                    已暂停
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2 text-xs text-stone-400">
                <span className="font-medium">{getFrequencyText(habit.frequency)}</span>
                {habit.anchorDescription && (
                  <>
                    <span>·</span>
                    <span className="flex items-center gap-1 truncate">
                      <Anchor size={10} />
                      {habit.anchorDescription}
                    </span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Menu */}
          <div className="relative flex-shrink-0">
            <button
              onClick={() => setShowMenu(!showMenu)}
              className="p-1.5 hover:bg-stone-100 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
            >
              <MoreVertical size={16} className="text-stone-400" />
            </button>

            {showMenu && (
              <>
                <div
                  className="fixed inset-0 z-10"
                  onClick={() => setShowMenu(false)}
                />
                <motion.div
                  initial={{ opacity: 0, scale: 0.95, y: -5 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  className="absolute right-0 top-full mt-1 z-20 bg-white rounded-xl shadow-xl border border-stone-100 py-1 min-w-[140px]"
                >
                  <button
                    onClick={() => { onEdit(habit); setShowMenu(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
                  >
                    <Edit2 size={14} />
                    编辑
                  </button>
                  {isPaused ? (
                    <button
                      onClick={() => { onResume(habit.id); setShowMenu(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-amber-600 hover:bg-amber-50"
                    >
                      <Play size={14} />
                      恢复
                    </button>
                  ) : (
                    <button
                      onClick={() => { onPause(habit.id); setShowMenu(false); }}
                      className="w-full flex items-center gap-2 px-3 py-2 text-sm text-amber-600 hover:bg-amber-50"
                    >
                      <Pause size={14} />
                      暂停
                    </button>
                  )}
                  <button
                    onClick={() => { onViewHistory(habit.id); setShowMenu(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-stone-600 hover:bg-stone-50"
                  >
                    <History size={14} />
                    历史记录
                  </button>
                  <div className="h-px bg-stone-100 my-1" />
                  <button
                    onClick={() => { onDelete(habit.id); setShowMenu(false); }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-sm text-red-500 hover:bg-red-50"
                  >
                    <Trash2 size={14} />
                    删除
                  </button>
                </motion.div>
              </>
            )}
          </div>
        </div>

        {/* Level & Challenge Progress */}
        <div className="space-y-3 mb-4">
          <div className="flex items-center justify-between">
            <LevelBadge level={habit.currentLevel} size="sm" />

            {habit.currentChallenge && (
              <span className="text-xs text-stone-400">
                {habit.currentChallenge.completedCount}/{habit.currentChallenge.requiredCompletions} 天
              </span>
            )}
          </div>

          {/* Challenge progress bar */}
          {habit.currentChallenge && (
            <div className="space-y-1.5">
              <div className="h-2 bg-stone-100 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(challengeProgress, 1) * 100}%` }}
                  transition={{ duration: 0.5, ease: 'easeOut' }}
                  className="h-full rounded-full bg-emerald-500"
                />
              </div>
              <div className="flex justify-between text-[10px] text-stone-400">
                <span>Lv.{habit.currentChallenge.fromLevel} {levelConfig.name}</span>
                <span>→ Lv.{habit.currentChallenge.toLevel}</span>
              </div>
            </div>
          )}
        </div>

        {/* Check-in button */}
        <motion.button
          whileHover={{ scale: isPaused ? 1 : 1.02 }}
          whileTap={{ scale: isPaused ? 1 : 0.98 }}
          onClick={() => !isPaused && onCheckIn(habit.id)}
          disabled={isPaused || isCheckedToday}
          className={`w-full py-3 rounded-2xl font-medium text-sm flex items-center justify-center gap-2 transition-all ${
            isCheckedToday
              ? 'bg-emerald-50 text-emerald-600 border border-emerald-100'
              : isPaused
              ? 'bg-stone-100 text-stone-400 cursor-not-allowed'
              : 'bg-amber-400 text-white hover:bg-amber-500 shadow-lg shadow-amber-400/25'
          }`}
        >
          <Check size={16} strokeWidth={2.5} />
          {isCheckedToday ? '今日已完成' : '打卡'}
        </motion.button>
      </div>
    </motion.div>
  );
};

export default HabitCard;
