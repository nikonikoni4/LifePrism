import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Clock } from 'lucide-react';
import { HabitAnchor } from '../../../../../types';
import { mockTimelineAnchors } from '../../../../../mockData';
import TimelineItem from './TimelineItem';
import AddToTimelineModal from './AddToTimelineModal';

interface AnchorTimelineProps {
  className?: string;
}

export const AnchorTimeline: React.FC<AnchorTimelineProps> = ({ className = '' }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [anchors] = useState<HabitAnchor[]>(mockTimelineAnchors);

  // 按时间排序的锚点
  const sortedAnchors = useMemo(() => {
    return [...anchors]
      .filter(a => a.anchorTime) // 只显示有时间的锚点
      .sort((a, b) => {
        const timeA = a.anchorTime || '00:00';
        const timeB = b.anchorTime || '00:00';
        return timeA.localeCompare(timeB);
      });
  }, [anchors]);

  // 按小时分组
  const groupedByHour = useMemo(() => {
    const groups: Record<string, HabitAnchor[]> = {};
    sortedAnchors.forEach(anchor => {
      const hour = anchor.anchorTime?.split(':')[0] || '00';
      const hourKey = `${hour}:00`;
      if (!groups[hourKey]) {
        groups[hourKey] = [];
      }
      groups[hourKey].push(anchor);
    });
    return groups;
  }, [sortedAnchors]);

  const hourKeys = Object.keys(groupedByHour).sort();

  return (
    <div className={`bg-white rounded-2xl border border-slate-100 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Clock size={16} className="text-teal-500" />
          <h3 className="font-semibold text-slate-800">时间锚点</h3>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setIsModalOpen(true)}
          className="flex items-center gap-1 text-xs font-medium text-teal-600 hover:text-teal-700 px-2 py-1 rounded-lg hover:bg-teal-50 transition-colors"
        >
          <Plus size={14} />
          添加
        </motion.button>
      </div>

      {/* Timeline Content */}
      <div className="p-4 max-h-[600px] overflow-y-auto scrollbar-hide">
        {hourKeys.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <Clock size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">暂无时间锚点</p>
            <p className="text-xs mt-1">点击上方添加按钮创建</p>
          </div>
        ) : (
          <div className="relative">
            {/* 时间轴线 */}
            <div className="absolute left-3 top-0 bottom-0 w-px bg-gradient-to-b from-teal-200 via-teal-300 to-teal-200" />

            {/* 时间段 */}
            <div className="space-y-6">
              {hourKeys.map((hourKey, hourIndex) => (
                <div key={hourKey} className="relative">
                  {/* 小时标记 */}
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-6 h-6 rounded-full bg-teal-100 border-2 border-teal-300 flex items-center justify-center z-10">
                      <div className="w-2 h-2 rounded-full bg-teal-500" />
                    </div>
                    <span className="text-xs font-bold text-slate-400 tracking-wider">
                      {hourKey}
                    </span>
                    <div className="flex-1 h-px bg-slate-100" />
                  </div>

                  {/* 该小时内的锚点 */}
                  <div className="ml-9 space-y-3">
                    <AnimatePresence>
                      {groupedByHour[hourKey].map((anchor, anchorIndex) => (
                        <motion.div
                          key={anchor.id}
                          initial={{ opacity: 0, x: -10 }}
                          animate={{ opacity: 1, x: 0 }}
                          exit={{ opacity: 0, x: 10 }}
                          transition={{ delay: anchorIndex * 0.05 }}
                        >
                          {anchor.nodes.map((node, nodeIndex) => (
                            <div key={node.id} className="mb-2">
                              <TimelineItem
                                node={node}
                                anchorTime={nodeIndex === 0 ? anchor.anchorTime : undefined}
                                showConnector={nodeIndex > 0}
                                onEdit={() => console.log('Edit node:', node.id)}
                              />
                            </div>
                          ))}

                          {/* 在稳固习惯后显示添加提示 */}
                          {shouldShowAddHint(anchor) && (
                            <motion.button
                              whileHover={{ scale: 1.02 }}
                              whileTap={{ scale: 0.98 }}
                              onClick={() => setIsModalOpen(true)}
                              className="w-full mt-2 p-2 border-2 border-dashed border-slate-200 rounded-lg text-xs text-slate-400 hover:text-teal-500 hover:border-teal-200 transition-colors flex items-center justify-center gap-1"
                            >
                              <Plus size={12} />
                              在此添加新习惯
                            </motion.button>
                          )}
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Add Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <AddToTimelineModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onSave={(data) => {
              console.log('Save timeline item:', data);
              setIsModalOpen(false);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

// 判断是否应该在锚点后显示添加提示（Lv.3+ 的习惯）
function shouldShowAddHint(anchor: HabitAnchor): boolean {
  // 简化逻辑：每隔一个锚点显示一次添加提示
  return anchor.nodes.some(node => {
    if (node.habitId) {
      // 这里应该检查习惯等级，简化处理
      return Math.random() > 0.7; // 模拟部分显示
    }
    return false;
  });
}

export default AnchorTimeline;
