/**
 * RangeSummaryModal - 范围更新总结弹窗
 * 用于选择日期范围和更新模式，批量生成/更新日记 AI 总结
 */
import React, { useState } from 'react';
import { X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import type { ExistingSummaryMode } from './diaryTypes';
import { toLocalDateString } from '../../../../core/utils/dateUtils';

interface RangeSummaryModalProps {
  open: boolean;
  onClose: () => void;
  onSubmit: (payload: { start_date: string; end_date: string; existing_summary_mode: ExistingSummaryMode }) => void;
  initialDate: Date;
}

const MODE_OPTIONS: { value: ExistingSummaryMode; label: string; description: string }[] = [
  { value: 'regenerate_all', label: '全部重新生成', description: '为范围内所有日记重新生成 AI 总结' },
  { value: 'regenerate_changed', label: '仅更新已修改', description: '只对有内容变动的日记重新生成总结' },
  { value: 'skip_existing', label: '跳过已有', description: '仅对尚无总结的日记生成 AI 总结' },
];

const RangeSummaryModal: React.FC<RangeSummaryModalProps> = ({
  open,
  onClose,
  onSubmit,
  initialDate,
}) => {
  const [start, setStart] = useState(() => {
    const d = new Date(initialDate);
    d.setDate(1); // First day of month
    return d;
  });
  const [end, setEnd] = useState(initialDate);
  const [mode, setMode] = useState<ExistingSummaryMode>('regenerate_changed');

  const handleSubmit = () => {
    const startDate = toLocalDateString(start);
    const endDate = toLocalDateString(end);
    onSubmit({ start_date: startDate, end_date: endDate, existing_summary_mode: mode });
    onClose();
  };

  return (
    <AnimatePresence>
      {open && (
        <>
          {/* 遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-[200] bg-black/30 backdrop-blur-sm"
            onClick={onClose}
          />

          {/* 弹窗 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.25, ease: [0.23, 1, 0.32, 1] }}
            className="fixed z-[201] top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[420px] bg-white rounded-2xl shadow-2xl overflow-hidden"
          >
            {/* 头部 */}
            <div className="px-6 py-5 flex items-center justify-between border-b border-black/[0.06]">
              <h2 className="text-[15px] font-medium text-gray-800">范围更新总结</h2>
              <button
                onClick={onClose}
                className="p-1.5 rounded-full hover:bg-black/[0.04] transition-colors"
              >
                <X size={16} className="text-gray-400" />
              </button>
            </div>

            {/* 内容 */}
            <div className="px-6 py-5 space-y-5">
              {/* 日期范围 */}
              <div className="space-y-3">
                <label className="text-[11px] font-medium text-gray-500 uppercase tracking-wider">日期范围</label>
                <div className="flex items-center gap-3">
                  <input
                    type="date"
                    value={toLocalDateString(start)}
                    onChange={e => setStart(new Date(e.target.value))}
                    className="flex-1 px-3 py-2.5 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400 transition-colors"
                  />
                  <span className="text-gray-300 text-xs">至</span>
                  <input
                    type="date"
                    value={toLocalDateString(end)}
                    onChange={e => setEnd(new Date(e.target.value))}
                    className="flex-1 px-3 py-2.5 text-[13px] border border-gray-200 rounded-lg focus:outline-none focus:border-gray-400 transition-colors"
                  />
                </div>
              </div>

              {/* 更新模式 */}
              <div className="space-y-3">
                <label className="text-[11px] font-medium text-gray-500 uppercase tracking-wider">更新模式</label>
                <div className="space-y-2">
                  {MODE_OPTIONS.map(option => (
                    <button
                      key={option.value}
                      onClick={() => setMode(option.value)}
                      className={`w-full px-4 py-3 rounded-xl text-left transition-all ${
                        mode === option.value
                          ? 'bg-gray-800 text-white'
                          : 'bg-gray-50 text-gray-700 hover:bg-gray-100'
                      }`}
                    >
                      <div className={`text-[13px] font-medium ${mode === option.value ? 'text-white' : 'text-gray-800'}`}>
                        {option.label}
                      </div>
                      <div className={`text-[11px] mt-0.5 ${mode === option.value ? 'text-gray-300' : 'text-gray-400'}`}>
                        {option.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 底部 */}
            <div className="px-6 py-4 flex gap-3 border-t border-black/[0.06]">
              <button
                onClick={onClose}
                className="flex-1 py-2.5 text-[13px] text-gray-600 hover:bg-gray-50 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSubmit}
                className="flex-1 py-2.5 text-[13px] bg-gray-800 text-white rounded-lg hover:bg-gray-700 transition-colors"
              >
                开始生成
              </button>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default RangeSummaryModal;
