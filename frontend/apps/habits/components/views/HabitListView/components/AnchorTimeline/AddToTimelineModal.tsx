import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { X, Clock, FileText } from 'lucide-react';

interface AddToTimelineModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: { anchorTime: string; customText?: string; habitId?: string }) => void;
}

export const AddToTimelineModal: React.FC<AddToTimelineModalProps> = ({
  isOpen,
  onClose,
  onSave
}) => {
  const [anchorTime, setAnchorTime] = useState('08:00');
  const [inputType, setInputType] = useState<'custom' | 'habit'>('custom');
  const [customText, setCustomText] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (inputType === 'custom' && customText.trim()) {
      onSave({ anchorTime, customText: customText.trim() });
    }
    // TODO: 支持选择已有习惯
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
        className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100">
          <h3 className="font-semibold text-slate-800">添加时间锚点</h3>
          <button
            onClick={onClose}
            className="p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X size={20} className="text-slate-400" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* 时间选择 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              <Clock size={14} className="inline mr-1" />
              锚点时间
            </label>
            <input
              type="time"
              value={anchorTime}
              onChange={e => setAnchorTime(e.target.value)}
              className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
            />
          </div>

          {/* 类型选择 */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              内容类型
            </label>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setInputType('custom')}
                className={`flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-colors ${
                  inputType === 'custom'
                    ? 'bg-teal-50 border-teal-200 text-teal-700'
                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                <FileText size={14} className="inline mr-1" />
                自由文本
              </button>
              <button
                type="button"
                onClick={() => setInputType('habit')}
                className={`flex-1 py-2 px-3 rounded-lg border text-sm font-medium transition-colors ${
                  inputType === 'habit'
                    ? 'bg-teal-50 border-teal-200 text-teal-700'
                    : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'
                }`}
              >
                ✨ 关联习惯
              </button>
            </div>
          </div>

          {/* 内容输入 */}
          {inputType === 'custom' ? (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                提醒内容
              </label>
              <input
                type="text"
                value={customText}
                onChange={e => setCustomText(e.target.value)}
                placeholder="例如：吃药、喝水、深呼吸..."
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent"
              />
            </div>
          ) : (
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                选择习惯
              </label>
              <select
                className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500 focus:border-transparent text-slate-600"
              >
                <option value="">请选择习惯...</option>
                <option value="habit-1">起床</option>
                <option value="habit-2">睡觉</option>
                <option value="habit-meditation">冥想</option>
              </select>
              <p className="text-xs text-slate-400 mt-1">
                关联已有习惯，等级颜色会自动同步
              </p>
            </div>
          )}

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
              添加
            </button>
          </div>
        </form>
      </motion.div>
    </motion.div>
  );
};

export default AddToTimelineModal;
