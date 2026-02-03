import React from 'react';
import { motion } from 'framer-motion';
import { ArrowUpRight, Flame, Zap } from 'lucide-react';
import { HabitStats } from '../../../../types';
import CircularProgress from './CircularProgress';

interface StatCardsProps {
  stats: HabitStats | null;
  activeHabitsCount: number;
}

export const StatCards: React.FC<StatCardsProps> = ({ stats, activeHabitsCount }) => {
  if (!stats) {
    return (
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        {[1, 2, 3, 4].map(i => (
          <div key={i} className="h-28 bg-white rounded-2xl animate-pulse" />
        ))}
      </div>
    );
  }

  const total = stats.todayCompleted + stats.todayPending;
  const weeklyPercent = Math.round(stats.weeklyCompletionRate * 100);

  const cards = [
    {
      title: '今日进度',
      value: `${stats.todayCompleted}/${total}`,
      subtitle: `待完成 ${stats.todayPending}`,
      highlight: true,
      icon: <ArrowUpRight size={16} className="text-amber-600" />,
    },
    {
      title: '本周完成率',
      value: weeklyPercent,
      isCircular: true,
      subtitle: '周完成率',
      icon: null,
    },
    {
      title: '连续天数',
      value: `${stats.currentStreak}天`,
      subtitle: '保持势头',
      icon: <Flame size={16} className="text-orange-500" />,
      showFlame: stats.currentStreak >= 7,
    },
    {
      title: '活跃习惯',
      value: activeHabitsCount,
      subtitle: '个习惯',
      icon: <Zap size={16} className="text-stone-400" />,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      {cards.map((card, index) => (
        <motion.div
          key={card.title}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: index * 0.05 }}
          whileHover={{ y: -2, boxShadow: '0 10px 40px -10px rgba(251, 191, 36, 0.15)' }}
          className={`relative p-4 rounded-2xl border transition-all duration-300 cursor-default ${
            card.highlight
              ? 'bg-amber-50 border-amber-200'
              : 'bg-white border-stone-100 hover:border-stone-200'
          }`}
        >
          {/* Header */}
          <div className="flex items-start justify-between mb-2">
            <span className={`text-xs font-medium ${
              card.highlight ? 'text-amber-700' : 'text-stone-500'
            }`}>
              {card.title}
            </span>
            {card.icon && (
              <div className="opacity-60">
                {card.icon}
              </div>
            )}
          </div>

          {/* Value */}
          {card.isCircular ? (
            <div className="flex items-center gap-3">
              <CircularProgress percentage={card.value as number} size={44} strokeWidth={4} />
              <div>
                <div className="text-2xl font-bold text-stone-900">{card.value}%</div>
                <div className="text-[10px] text-stone-400">{card.subtitle}</div>
              </div>
            </div>
          ) : (
            <div>
              <div className={`text-3xl font-bold tracking-tight ${
                card.highlight ? 'text-amber-900' : 'text-stone-900'
              }`}>
                {card.value}
              </div>
              <div className="flex items-center gap-1 mt-1">
                {card.showFlame && <Flame size={12} className="text-orange-500" />}
                <span className="text-[10px] text-stone-400">{card.subtitle}</span>
              </div>
            </div>
          )}
        </motion.div>
      ))}
    </div>
  );
};

export default StatCards;
