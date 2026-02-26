import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Plus, Trash2 } from 'lucide-react';
import { ChainTriggerType, TRIGGER_TYPES, HabitAnchorNode } from '../../../../../types';

interface AddChainModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: {
    triggerType: ChainTriggerType;
    triggerDescription: string;
    anchorTime?: string;
    nodes: { customText?: string; habitId?: string }[];
  }) => void;
}

export const AddChainModal: React.FC<AddChainModalProps> = ({
  isOpen,
  onClose,
  onSave
}) => {
  const [triggerType, setTriggerType] = useState<ChainTriggerType>('time');
  const [triggerDescription, setTriggerDescription] = useState('');
  const [anchorTime, setAnchorTime] = useState('08:00');
  const [nodes, setNodes] = useState<{ id: string; customText: string }[]>([
    { id: '1', customText: '' }
  ]);

  const handleAddNode = () => {
    setNodes([...nodes, { id: Date.now().toString(), customText: '' }]);
  };

  const handleRemoveNode = (id: string) => {
    if (nodes.length > 1) {
      setNodes(nodes.filter(n => n.id !== id));
    }
  };

  const handleNodeChange = (id: string, value: string) => {
    setNodes(nodes.map(n => n.id === id ? { ...n, customText: value } : n));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const validNodes = nodes.filter(n => n.customText.trim());
    if (triggerDescription.trim() && validNodes.length > 0) {
      onSave({
        triggerType,
        triggerDescription: triggerDescription.trim(),
        anchorTime: triggerType === 'time' ? anchorTime : undefined,
        nodes: validNodes.map(n => ({ customText: n.customText.trim() }))
      });
    }
  };

  const getPlaceholder = () => {
    switch (triggerType) {
      case 'time': return '例如：每天早上、每天 12:00';
      case 'scene': return '例如：回家后、到公司后';
      case 'event': return '例如：洗漱后、吃完饭后';
      case 'habit': return '例如：完成冥想后、运动后';
      default: return '描述触发条件...';
    }
  };

  if (!isOpen) return null;

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.95, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.95, opacity: 0 }}
        onClick={e => e.stopPropagation()}
        className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-800">添加习惯链条</h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* 触发器类型 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              触发类型
            </label>
            <div className="grid grid-cols-2 gap-2">
              {TRIGGER_TYPES.map(type => (
                <button
                  key={type.type}
                  type="button"
                  onClick={() => setTriggerType(type.type)}
                  className={`
                    py-2 px-3 rounded-lg border text-sm font-medium transition-colors
                    flex items-center gap-2
                    ${triggerType === type.type
                      ? `${type.bgColor} ${type.borderColor} ${type.textColor}`
                      : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                    }
                  `}
                >
                  <span>{type.icon}</span>
                  {type.label}
                </button>
              ))}
            </div>
          </div>

          {/* 时间选择（仅时间触发） */}
          {triggerType === 'time' && (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                触发时间
              </label>
              <input
                type="time"
                value={anchorTime}
                onChange={e => setAnchorTime(e.target.value)}
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              />
            </div>
          )}

          {/* 触发描述 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              触发描述
            </label>
            <input
              type="text"
              value={triggerDescription}
              onChange={e => setTriggerDescription(e.target.value)}
              placeholder={getPlaceholder()}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            />
          </div>

          {/* 链条节点 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              执行内容（按顺序）
            </label>
            <div className="space-y-2">
              {nodes.map((node, index) => (
                <div key={node.id} className="flex items-center gap-2">
                  <span className="text-xs text-slate-400 w-4">{index + 1}.</span>
                  <input
                    type="text"
                    value={node.customText}
                    onChange={e => handleNodeChange(node.id, e.target.value)}
                    placeholder="例如：冥想 5 分钟、喝杯水..."
                    className="flex-1 px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent text-sm"
                  />
                  {nodes.length > 1 && (
                    <button
                      type="button"
                      onClick={() => handleRemoveNode(node.id)}
                      className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                    >
                      <Trash2 size={16} />
                    </button>
                  )}
                </div>
              ))}
            </div>
            <button
              type="button"
              onClick={handleAddNode}
              className="mt-2 flex items-center gap-1 text-xs text-teal-600 hover:text-teal-700 font-medium"
            >
              <Plus size={14} />
              添加更多步骤
            </button>
          </div>

          {/* 提交按钮 */}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 px-4 border border-slate-200 rounded-lg text-slate-600 font-medium hover:bg-slate-50 transition-colors"
            >
              取消
            </button>
            <button
              type="submit"
              className="flex-1 py-2 px-4 bg-teal-500 text-white rounded-lg font-medium hover:bg-teal-600 transition-colors"
            >
              创建链条
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
};

export default AddChainModal;
