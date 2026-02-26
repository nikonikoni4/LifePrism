import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Calendar, TrendingUp, Award, CheckCircle2, XCircle } from 'lucide-react';
import { Habit, HabitHistory, HabitChallenge, getLevelConfig } from '../../../../types';
import { habitApi } from '../../../../api';
import { LevelBadge, LevelInfo } from '../../../shared/LevelBadge';

interface HabitHistoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  habitId: string | null;
}

const ChallengeItem: React.FC<{ challenge: HabitChallenge }> = ({ challenge }) => {
  const isSuccess = challenge.status === 'succeeded';
  const isFailed = challenge.status === 'failed';
  const isInProgress = challenge.status === 'in_progress';

  return (
    <div className={`p-4 rounded-xl border ${
      isSuccess ? 'bg-green-50 border-green-200' :
      isFailed ? 'bg-red-50 border-red-200' :
      'bg-slate-50 border-slate-200'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {isSuccess && <CheckCircle2 size={16} className="text-green-500" />}
          {isFailed && <XCircle size={16} className="text-red-500" />}
          {isInProgress && <TrendingUp size={16} className="text-blue-500" />}
          <span className={`text-sm font-medium ${
            isSuccess ? 'text-green-700' :
            isFailed ? 'text-red-700' :
            'text-slate-700'
          }`}>
            Lv.{challenge.fromLevel} → Lv.{challenge.toLevel}
          </span>
        </div>
        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
          isSuccess ? 'bg-green-100 text-green-600' :
          isFailed ? 'bg-red-100 text-red-600' :
          'bg-blue-100 text-blue-600'
        }`}>
          {isSuccess ? '成功' : isFailed ? '失败' : '进行中'}
        </span>
      </div>

      <div className="text-xs text-slate-500 space-y-1">
        <div className="flex justify-between">
          <span>目标: {challenge.targetDays} 天内完成 {challenge.requiredCompletions} 次</span>
          <span>实际: {challenge.completedCount} 次</span>
        </div>
        <div className="flex justify-between">
          <span>{challenge.startDate}</span>
          <span>→</span>
          <span>{challenge.endDate}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="mt-2 h-1.5 bg-white rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${
            isSuccess ? 'bg-green-500' :
            isFailed ? 'bg-red-400' :
            'bg-blue-500'
          }`}
          style={{ width: `${Math.min(challenge.completedCount / challenge.requiredCompletions, 1) * 100}%` }}
        />
      </div>
    </div>
  );
};

const HabitHistoryModal: React.FC<HabitHistoryModalProps> = ({
  isOpen,
  onClose,
  habitId
}) => {
  const [history, setHistory] = useState<HabitHistory | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (isOpen && habitId) {
      setIsLoading(true);
      habitApi.getHistory(habitId)
        .then(data => setHistory(data))
        .catch(err => console.error('Failed to load history:', err))
        .finally(() => setIsLoading(false));
    }
  }, [isOpen, habitId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
      />

      <motion.div
        initial={{ scale: 0.95, opacity: 0, y: 20 }}
        animate={{ scale: 1, opacity: 1, y: 0 }}
        exit={{ scale: 0.95, opacity: 0, y: 20 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="relative w-full max-w-lg bg-white/95 backdrop-blur-xl border border-white/60 shadow-[0_25px_50px_-12px_rgba(0,0,0,0.15)] rounded-[2rem] overflow-hidden flex flex-col max-h-[85vh]"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 pb-4 border-b border-slate-100">
          <div>
            <h2 className="text-xl font-serif text-slate-800">
              {history?.habit.name || '习惯历史'}
            </h2>
            <p className="text-xs text-slate-400 mt-1">查看习惯的成长历程</p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-slate-100 rounded-xl transition-colors"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-20 bg-slate-100 rounded-xl animate-pulse" />
              ))}
            </div>
          ) : history ? (
            <>
              {/* Current Level */}
              <div>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
                  当前等级
                </h3>
                <LevelInfo level={history.habit.currentLevel} />
              </div>

              {/* Stats */}
              <div>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
                  统计数据
                </h3>
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-slate-50 rounded-xl p-4 text-center">
                    <div className="text-2xl font-light text-slate-800">{history.totalCheckIns}</div>
                    <div className="text-[10px] font-bold text-slate-400 uppercase mt-1">累计打卡</div>
                  </div>
                  <div className="bg-orange-50 rounded-xl p-4 text-center">
                    <div className="text-2xl font-light text-orange-600">{history.currentStreak}</div>
                    <div className="text-[10px] font-bold text-orange-400 uppercase mt-1">当前连续</div>
                  </div>
                  <div className="bg-purple-50 rounded-xl p-4 text-center">
                    <div className="text-2xl font-light text-purple-600">{history.longestStreak}</div>
                    <div className="text-[10px] font-bold text-purple-400 uppercase mt-1">最长连续</div>
                  </div>
                </div>
              </div>

              {/* Challenge History */}
              <div>
                <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                  <Award size={12} />
                  挑战记录
                </h3>
                {history.challenges.length > 0 ? (
                  <div className="space-y-3">
                    {history.challenges.map(challenge => (
                      <ChallengeItem key={challenge.id} challenge={challenge} />
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-slate-400 text-sm">
                    暂无挑战记录
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="text-center py-8 text-slate-400">
              加载失败
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-slate-100 bg-slate-50/50">
          <button
            onClick={onClose}
            className="w-full py-3 rounded-xl text-slate-600 font-medium hover:bg-slate-100 transition-colors text-sm"
          >
            关闭
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default HabitHistoryModal;
