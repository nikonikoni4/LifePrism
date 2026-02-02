import React from 'react';
import { motion } from 'framer-motion';
import { HabitAnchorNode, getLevelTealBg } from '../../../../../types';
import { getHabitById } from '../../../../../mockData';

interface ChainNodeProps {
  node: HabitAnchorNode;
  onEdit?: () => void;
}

export const ChainNode: React.FC<ChainNodeProps> = ({ node, onEdit }) => {
  // 获取习惯信息（如果是关联习惯）
  const habit = node.habitId ? getHabitById(node.habitId) : null;
  const level = habit?.currentLevel ?? -1;
  const isCustomText = !node.habitId;

  // 显示内容
  const displayName = habit?.name || node.customText || '未命名';

  return (
    <motion.div
      whileHover={{ scale: 1.05, y: -2 }}
      whileTap={{ scale: 0.95 }}
      onClick={onEdit}
      className={`
        px-3 py-2 rounded-lg border cursor-pointer transition-all shadow-sm
        ${isCustomText
          ? 'bg-white border-slate-200 hover:border-slate-300 hover:shadow-md'
          : `${getLevelTealBg(level)} border-teal-200 hover:border-teal-300 hover:shadow-md`
        }
      `}
    >
      <div className="flex flex-col items-center gap-1">
        {/* 图标 */}
        <span className="text-lg">
          {isCustomText ? '📝' : getHabitEmoji(displayName)}
        </span>

        {/* 名称 */}
        <span className={`text-xs font-medium text-center leading-tight ${
          isCustomText ? 'text-slate-600' : 'text-slate-700'
        }`}>
          {displayName}
        </span>
      </div>
    </motion.div>
  );
};

// 根据习惯名称返回对应的 emoji
function getHabitEmoji(name: string): string {
  const emojiMap: Record<string, string> = {
    '起床': '☀️',
    '睡觉': '😴',
    '冥想': '🧘',
    '吃早餐': '🍳',
    '午餐': '🍱',
    '晚餐': '🍽️',
    '运动': '🏃',
    '阅读': '📖',
    '学习': '📚',
    '工作': '💼',
    '吃药': '💊',
    '八段锦': '🥋',
  };

  for (const [key, emoji] of Object.entries(emojiMap)) {
    if (name.includes(key)) return emoji;
  }
  return '✨';
}

export default ChainNode;
