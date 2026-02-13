/**
 * SettingsPopover - 底部设置上拉菜单
 * 包含"背景颜色"和"模板管理"两个入口
 */
import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Palette, FileText } from 'lucide-react';

interface SettingsPopoverProps {
  open: boolean;
  onClose: () => void;
  onSelectColor: () => void;
  onSelectTemplate: () => void;
  /** 锚点位置（按钮的位置信息） */
  anchorRect?: DOMRect | null;
}

const SettingsPopover: React.FC<SettingsPopoverProps> = ({
  open, onClose, onSelectColor, onSelectTemplate, anchorRect,
}) => {
  return (
    <AnimatePresence>
      {open && (
        <>
          {/* 透明遮罩 */}
          <div className="fixed inset-0 z-[150]" onClick={onClose} />

          {/* 上拉菜单 */}
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.25, ease: [0.23, 1, 0.32, 1] }}
            className="fixed z-[151] w-48 bg-white backdrop-blur-2xl rounded-2xl shadow-[0_8px_30px_-5px_rgba(0,0,0,0.15)] border border-black/[0.06] overflow-hidden"
            style={{
              bottom: anchorRect ? window.innerHeight - anchorRect.top + 8 : 80,
              left: anchorRect ? anchorRect.left + anchorRect.width / 2 - 96 : 'auto',
            }}
          >
            <button
              onClick={() => { onSelectColor(); onClose(); }}
              className="w-full flex items-center gap-3 px-5 py-3.5 text-[12px] text-gray-600 hover:bg-black/[0.03] transition-colors tracking-wider"
            >
              <Palette size={15} className="opacity-40" />
              背景颜色
            </button>
            <div className="mx-4 h-[0.5px] bg-black/[0.04]" />
            <button
              onClick={() => { onSelectTemplate(); onClose(); }}
              className="w-full flex items-center gap-3 px-5 py-3.5 text-[12px] text-gray-600 hover:bg-black/[0.03] transition-colors tracking-wider"
            >
              <FileText size={15} className="opacity-40" />
              模板管理
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
};

export default SettingsPopover;
