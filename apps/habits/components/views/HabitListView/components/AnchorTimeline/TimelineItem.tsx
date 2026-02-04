import React from 'react';
import { motion } from 'framer-motion';
import { HabitAnchorNode, getLevelTealBg, getLevelConfig } from '../../../../../types';
import { getHabitById } from '../../../../../mockData';

interface TimelineItemProps {
  node: HabitAnchorNode;
  anchorTime?: string;
  showConnector?: boolean;
  onEdit?: () => void;
}

export const TimelineItem: React.FC<TimelineItemProps> = ({
  node,
  anchorTime,
  showConnector = false,
  onEdit
}) => {
  // 获取习惯信息（如果是关联习惯）
  const habit = node.habitId ? getHabitById(node.habitId) : null;
  const level = habit?.currentLevel ?? -1;
  const levelConfig = level >= 0 ? getLevelConfig(level) : null;

  // 显示内容
  const displayName = habit?.name || node.customText || '未命名';
  const isCustomText = !node.habitId;

  // 等级进度条（5格）
  const renderLevelBar = () => {
    if (level < 0) return null;
    return (
      <div className="flex gap-0.5 ml-2">
        {[0, 1, 2, 3, 4].map(i => (
          <div
            key={i}
            className={`w-2 h-3 rounded-sm ${i <= level ? 'bg-teal-500' : 'bg-slate-200'}`}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="relative">
      {/* 连接线 */}
      {showConnector && (
        <div className="absolute left-1/2 -top-4 transform -translate-x-1/2 flex flex-col items-center">
          <div className="w-px h-3 bg-slate-300" />
          <div className="text-slate-400 text-xs">▼</div>
        </div>
      )}

      {/* 时间标签 */}
      {anchorTime && (
        <div className="text-xs font-medium text-slate-500 mb-1">
          {anchorTime}
        </div>
      )}

      {/* 习惯卡片 */}
      <motion.div
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={onEdit}
        className={`
          relative rounded-xl border p-3 cursor-pointer transition-all
          ${isCustomText
            ? 'bg-slate-50 border-slate-200 hover:border-slate-300'
            : `${getLevelTealBg(level)} border-teal-200 hover:border-teal-300`
          }
        `}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {/* 图标 */}
            <span className="text-lg">
              {isCustomText ? '📝' : getHabitEmoji(displayName)}
            </span>

            {/* 名称 */}
            <div>
              <div className={`font-medium text-sm ${isCustomText ? 'text-slate-700' : 'text-slate-800'}`}>
                {displayName}
              </div>
              {levelConfig && (
                <div className="text-xs text-slate-500">
                  Lv.{level} {levelConfig.name}
                </div>
              )}
            </div>
          </div>

          {/* 等级进度条 */}
          {renderLevelBar()}
        </div>
      </motion.div>
    </div>
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
  };

  for (const [key, emoji] of Object.entries(emojiMap)) {
    if (name.includes(key)) return emoji;
  }
  return '✨';
}

export default TimelineItem;
