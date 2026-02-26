import React from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, CheckCircle2, Clock, Flame, Target } from 'lucide-react';
import { HabitStats } from '../../../../types';

interface HabitStatsCardProps {
  stats: HabitStats | null;
  className?: string;
}

const StatItem: React.FC<{
  icon: React.ElementType;
  label: string;
  value: string | number;
  subValue?: string;
  color: string;
  bgColor: string;
}> = ({ icon: Icon, label, value, subValue, color, bgColor }) => (
  <div className="flex items-center gap-3">
    <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${bgColor}`}>
      <Icon size={18} className={color} />
    </div>
    <div>
      <div className="flex items-baseline gap-1">
        <span className="text-2xl font-light text-slate-800 tabular-nums">{value}</span>
        {subValue && <span className="text-xs text-slate-400">{subValue}</span>}
      </div>
      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">{label}</p>
    </div>
  </div>
);

const HabitStatsCard: React.FC<HabitStatsCardProps> = ({ stats, className = '' }) => {
  if (!stats) {
    return (
      <div className={`bg-white/80 backdrop-blur-sm rounded-[1.5rem] border border-slate-100 p-6 ${className}`}>
        <div className="animate-pulse space-y-4">
          <div className="h-4 bg-slate-200 rounded w-1/3" />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-16 bg-slate-100 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  const completionPercent = Math.round(stats.weeklyCompletionRate * 100);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className={`bg-white/80 backdrop-blur-sm rounded-[1.5rem] border border-slate-100 shadow-sm overflow-hidden ${className}`}
    >
      {/* Header with gradient */}
      <div className="bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-white font-medium">今日习惯</h3>
            <p className="text-amber-100 text-sm mt-0.5">
              {stats.todayCompleted}/{stats.todayCompleted + stats.todayPending} 已完成
            </p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-light text-white tabular-nums">
              {stats.todayPending}
            </div>
            <p className="text-amber-100 text-xs">待完成</p>
          </div>
        </div>

        {/* Today's progress bar */}
        <div className="mt-3">
          <div className="h-2 bg-white/20 rounded-full overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{
                width: `${(stats.todayCompleted / (stats.todayCompleted + stats.todayPending || 1)) * 100}%`
              }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="h-full bg-white rounded-full"
            />
          </div>
        </div>
      </div>

      {/* Stats grid */}
      <div className="p-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          <StatItem
            icon={Target}
            label="活跃习惯"
            value={stats.activeHabitsCount}
            subValue="个"
            color="text-blue-500"
            bgColor="bg-blue-50"
          />
          <StatItem
            icon={TrendingUp}
            label="本周完成率"
            value={completionPercent}
            subValue="%"
            color="text-amber-500"
            bgColor="bg-amber-50"
          />
          <StatItem
            icon={CheckCircle2}
            label="累计打卡"
            value={stats.totalCheckIns}
            subValue="次"
            color="text-purple-500"
            bgColor="bg-purple-50"
          />
          <StatItem
            icon={Flame}
            label="当前连续"
            value={stats.currentStreak}
            subValue="天"
            color="text-orange-500"
            bgColor="bg-orange-50"
          />
        </div>
      </div>
    </motion.div>
  );
};

export default HabitStatsCard;
