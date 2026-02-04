import React from 'react';
import { motion } from 'framer-motion';
import { HabitAnchor, getTriggerTypeConfig } from '../../../../../types';
import ChainNode from './ChainNode';
import ChainConnector from './ChainConnector';

interface ChainCardProps {
  chain: HabitAnchor;
  onEdit?: () => void;
}

export const ChainCard: React.FC<ChainCardProps> = ({ chain, onEdit }) => {
  const triggerConfig = getTriggerTypeConfig(chain.triggerType);

  // 排序节点
  const sortedNodes = [...chain.nodes].sort((a, b) => a.order - b.order);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className={`
        rounded-xl border p-4 transition-all cursor-pointer
        ${triggerConfig.bgColor} ${triggerConfig.borderColor}
        hover:shadow-md
      `}
      onClick={onEdit}
    >
      {/* 触发器类型标签 */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-base">{triggerConfig.icon}</span>
        <span className={`text-xs font-medium ${triggerConfig.textColor}`}>
          {triggerConfig.label}
        </span>
      </div>

      {/* 链条流程 */}
      <div className="flex items-center flex-wrap gap-1">
        {/* 触发器节点 */}
        <div className={`
          px-3 py-2 rounded-lg border-2 border-dashed
          ${triggerConfig.borderColor} bg-white/50
        `}>
          <div className="flex flex-col items-center gap-1">
            <span className="text-xs text-slate-500">触发</span>
            <span className={`text-xs font-medium ${triggerConfig.textColor}`}>
              {chain.triggerDescription}
            </span>
          </div>
        </div>

        {/* 连接线 */}
        <ChainConnector />

        {/* 习惯节点 */}
        {sortedNodes.map((node, index) => (
          <React.Fragment key={node.id}>
            <ChainNode
              node={node}
              onEdit={() => console.log('Edit node:', node.id)}
            />
            {index < sortedNodes.length - 1 && <ChainConnector />}
          </React.Fragment>
        ))}
      </div>
    </motion.div>
  );
};

export default ChainCard;
