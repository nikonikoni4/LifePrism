import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Plus, Link2 } from 'lucide-react';
import { HabitAnchor, ChainTriggerType, TRIGGER_TYPES } from '../../../../../types';
import { mockHabitChains } from '../../../../../mockData';
import ChainCard from './ChainCard';
import AddChainModal from './AddChainModal';

interface HabitChainFlowProps {
  className?: string;
}

export const HabitChainFlow: React.FC<HabitChainFlowProps> = ({ className = '' }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [chains] = useState<HabitAnchor[]>(mockHabitChains);
  const [selectedTypes, setSelectedTypes] = useState<Set<ChainTriggerType>>(new Set());

  // 筛选后的链条
  const filteredChains = useMemo(() => {
    if (selectedTypes.size === 0) return chains;
    return chains.filter(chain => selectedTypes.has(chain.triggerType));
  }, [chains, selectedTypes]);

  // 切换筛选类型
  const toggleType = (type: ChainTriggerType) => {
    const newSet = new Set(selectedTypes);
    if (newSet.has(type)) {
      newSet.delete(type);
    } else {
      newSet.add(type);
    }
    setSelectedTypes(newSet);
  };

  // 清除所有筛选
  const clearFilters = () => {
    setSelectedTypes(new Set());
  };

  return (
    <div className={`bg-white rounded-2xl border border-slate-100 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-100">
        <div className="flex items-center gap-2">
          <Link2 size={16} className="text-teal-500" />
          <h3 className="font-semibold text-slate-800">习惯链条</h3>
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

      {/* Filter Tags */}
      <div className="px-4 py-3 border-b border-slate-50 flex items-center gap-2 flex-wrap">
        <button
          onClick={clearFilters}
          className={`
            px-3 py-1.5 rounded-full text-xs font-medium transition-colors
            ${selectedTypes.size === 0
              ? 'bg-teal-100 text-teal-700'
              : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
            }
          `}
        >
          全部
        </button>
        {TRIGGER_TYPES.map(type => (
          <button
            key={type.type}
            onClick={() => toggleType(type.type)}
            className={`
              px-3 py-1.5 rounded-full text-xs font-medium transition-colors
              flex items-center gap-1
              ${selectedTypes.has(type.type)
                ? `${type.bgColor} ${type.textColor} ring-1 ring-inset ${type.borderColor}`
                : 'bg-slate-100 text-slate-500 hover:bg-slate-200'
              }
            `}
          >
            <span>{type.icon}</span>
            {type.label}
          </button>
        ))}
      </div>

      {/* Chain List */}
      <div className="p-4 space-y-3 max-h-[400px] overflow-y-auto scrollbar-hide">
        {filteredChains.length === 0 ? (
          <div className="text-center py-8 text-slate-400">
            <Link2 size={32} className="mx-auto mb-2 opacity-50" />
            <p className="text-sm">暂无习惯链条</p>
            <p className="text-xs mt-1">点击上方添加按钮创建</p>
          </div>
        ) : (
          <AnimatePresence>
            {filteredChains.map((chain, index) => (
              <motion.div
                key={chain.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ delay: index * 0.05 }}
              >
                <ChainCard
                  chain={chain}
                  onEdit={() => console.log('Edit chain:', chain.id)}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        )}

        {/* Add New Chain Button */}
        <motion.button
          whileHover={{ scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          onClick={() => setIsModalOpen(true)}
          className="w-full p-4 border-2 border-dashed border-slate-200 rounded-xl text-slate-400 hover:text-teal-500 hover:border-teal-200 transition-colors flex items-center justify-center gap-2"
        >
          <Plus size={16} />
          <span className="text-sm font-medium">添加新链条</span>
        </motion.button>
      </div>

      {/* Add Modal */}
      <AnimatePresence>
        {isModalOpen && (
          <AddChainModal
            isOpen={isModalOpen}
            onClose={() => setIsModalOpen(false)}
            onSave={(data) => {
              console.log('Save chain:', data);
              setIsModalOpen(false);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

export default HabitChainFlow;
