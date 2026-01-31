import React from 'react';
import { motion } from 'framer-motion';
import { Sprout, Leaf, TreeDeciduous, TreePine, Trees } from 'lucide-react';
import { getLevelConfig, HABIT_LEVELS } from '../../types';

interface LevelBadgeProps {
  level: number;
  showName?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const LEVEL_ICONS = [Sprout, Leaf, TreeDeciduous, TreePine, Trees];

export const LevelBadge: React.FC<LevelBadgeProps> = ({
  level,
  showName = true,
  size = 'md',
  className = ''
}) => {
  const config = getLevelConfig(level);
  const Icon = LEVEL_ICONS[level] || Sprout;

  const sizeClasses = {
    sm: 'px-2 py-0.5 text-[10px] gap-1',
    md: 'px-2.5 py-1 text-xs gap-1.5',
    lg: 'px-3 py-1.5 text-sm gap-2'
  };

  const iconSizes = {
    sm: 10,
    md: 12,
    lg: 14
  };

  return (
    <motion.span
      whileHover={{ scale: 1.05 }}
      className={`inline-flex items-center rounded-full font-bold tracking-wide ${config.bgColor} ${config.borderColor} border ${sizeClasses[size]} ${className}`}
      style={{ color: config.color }}
    >
      <Icon size={iconSizes[size]} />
      <span>Lv.{level}</span>
      {showName && <span className="opacity-80">· {config.name}</span>}
    </motion.span>
  );
};

interface LevelProgressProps {
  level: number;
  progress?: number;  // 0-1, progress towards next level
  showLabel?: boolean;
  className?: string;
}

export const LevelProgress: React.FC<LevelProgressProps> = ({
  level,
  progress = 0,
  showLabel = true,
  className = ''
}) => {
  const config = getLevelConfig(level);
  const nextConfig = level < 4 ? getLevelConfig(level + 1) : null;

  return (
    <div className={`space-y-1.5 ${className}`}>
      {showLabel && (
        <div className="flex items-center justify-between text-xs">
          <LevelBadge level={level} size="sm" />
          {nextConfig && (
            <span className="text-slate-400 font-medium">
              → Lv.{level + 1} {nextConfig.name}
            </span>
          )}
        </div>
      )}
      <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progress * 100}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
          className="h-full rounded-full"
          style={{ backgroundColor: config.color }}
        />
      </div>
    </div>
  );
};

interface LevelInfoProps {
  level: number;
  className?: string;
}

export const LevelInfo: React.FC<LevelInfoProps> = ({ level, className = '' }) => {
  const config = getLevelConfig(level);
  const Icon = LEVEL_ICONS[level] || Sprout;

  return (
    <div className={`flex items-center gap-3 p-3 rounded-xl ${config.bgColor} ${config.borderColor} border ${className}`}>
      <div
        className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ backgroundColor: config.color }}
      >
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <div className="flex items-center gap-2">
          <span className="font-bold" style={{ color: config.color }}>
            Lv.{level}
          </span>
          <span className="font-medium text-slate-700">{config.name}</span>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{config.description}</p>
      </div>
    </div>
  );
};

// Level selector for forms
interface LevelSelectorProps {
  value: number;
  onChange: (level: number) => void;
  className?: string;
}

export const LevelSelector: React.FC<LevelSelectorProps> = ({
  value,
  onChange,
  className = ''
}) => {
  return (
    <div className={`flex gap-2 ${className}`}>
      {HABIT_LEVELS.map((config) => {
        const Icon = LEVEL_ICONS[config.level];
        const isSelected = value === config.level;

        return (
          <motion.button
            key={config.level}
            type="button"
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onChange(config.level)}
            className={`relative w-10 h-10 rounded-full flex items-center justify-center transition-all ${
              isSelected
                ? 'ring-2 ring-offset-2'
                : 'opacity-60 hover:opacity-100'
            }`}
            style={{
              backgroundColor: config.color
            }}
          >
            <Icon size={18} className="text-white" />
            {isSelected && (
              <motion.div
                layoutId="level-indicator"
                className="absolute -bottom-5 text-[9px] font-bold text-slate-500"
              >
                {config.name}
              </motion.div>
            )}
          </motion.button>
        );
      })}
    </div>
  );
};

export default LevelBadge;
