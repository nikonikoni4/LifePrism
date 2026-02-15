/**
 * SliderModal - 水墨禅意滑块选择器弹窗
 * 布局：标题 → 水墨图样 → 墨点选择器 → 等级文字 → 确认
 */
import React, { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import type { SliderOption } from './diaryTypes';
import InkWashArt from './InkWashArt';
import { MOOD_OPTIONS } from './diaryConstants';

interface SliderModalProps<T extends string> {
  open: boolean;
  title: string;
  options: SliderOption<T>[];
  value: T | null;
  onConfirm: (value: T) => void;
  onClose: () => void;
}

const ease = [0.23, 1, 0.32, 1] as const;

function SliderModal<T extends string>({
  open, title, options, value, onConfirm, onClose,
}: SliderModalProps<T>) {
  const defaultIdx = value
    ? options.findIndex(o => o.value === value)
    : Math.floor(options.length / 2);
  const [index, setIndex] = useState(Math.max(0, defaultIdx));

  React.useEffect(() => {
    if (open) {
      const idx = value
        ? options.findIndex(o => o.value === value)
        : Math.floor(options.length / 2);
      setIndex(Math.max(0, idx));
    }
  }, [open, value, options]);

  const current = options[index];
  const max = options.length - 1;
  const artType = options.length === MOOD_OPTIONS.length ? 'mood' : 'importance';

  // 轨道渐变
  const trackGradient = useMemo(() => {
    const stops = options.map((o, i) =>
      `${o.color} ${(i / max) * 100}%`
    ).join(', ');
    return `linear-gradient(to right, ${stops})`;
  }, [options, max]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.35 }}
          className="fixed inset-0 z-[200] flex items-center justify-center"
          onClick={onClose}
        >
          {/* 遮罩 */}
          <div className="absolute inset-0 bg-black/8 backdrop-blur-2xl" />

          {/* 弹窗 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 16 }}
            transition={{ duration: 0.45, ease }}
            onClick={e => e.stopPropagation()}
            className="relative w-[400px] bg-white/70 backdrop-blur-3xl rounded-[36px] shadow-[0_24px_80px_-12px_rgba(0,0,0,0.1)] border border-white/50 overflow-hidden"
          >
            {/* 标题 */}
            <div className="pt-9 pb-4">
              <p className="text-[10px] text-gray-400 tracking-[0.35em] text-center font-medium">
                {title}
              </p>
            </div>

            {/* 水墨图样区域 */}
            <div className="px-10 pb-6">
              <div className="w-full h-40 flex items-center justify-center">
                <AnimatePresence mode="wait">
                  <motion.div
                    key={`${artType}-${index}`}
                    initial={{ opacity: 0, scale: 0.85 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ duration: 0.4, ease }}
                    className="w-full h-full"
                  >
                    <InkWashArt
                      type={artType}
                      index={index}
                      color={current.color}
                    />
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
            {/* 墨点选择器 */}
            <div className="px-12 pb-4">
              <div className="relative flex items-center justify-between">
                {/* 连接线 */}
                <div
                  className="absolute top-1/2 left-0 right-0 h-[1.5px] -translate-y-1/2 rounded-full opacity-25"
                  style={{ background: trackGradient }}
                />
                {/* 档位点 */}
                {options.map((o, i) => (
                  <button
                    key={o.value}
                    onClick={() => setIndex(i)}
                    className="relative z-10 flex items-center justify-center"
                    style={{ width: 32, height: 32 }}
                  >
                    <motion.div
                      animate={{
                        width: i === index ? 20 : 8,
                        height: i === index ? 20 : 8,
                        opacity: i === index ? 1 : 0.35,
                      }}
                      transition={{ duration: 0.35, ease }}
                      className="rounded-full"
                      style={{ backgroundColor: o.color }}
                    />
                    {/* 选中光晕 */}
                    {i === index && (
                      <motion.div
                        layoutId="ink-halo"
                        className="absolute rounded-full"
                        style={{
                          width: 32, height: 32,
                          backgroundColor: `${o.color}15`,
                          border: `1.5px solid ${o.color}30`,
                        }}
                        transition={{ duration: 0.35, ease }}
                      />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* 等级文字 */}
            <div className="text-center pb-4 h-12 flex items-center justify-center">
              <AnimatePresence mode="wait">
                <motion.p
                  key={current.value}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                  transition={{ duration: 0.25 }}
                  className="text-lg tracking-widest"
                  style={{ color: current.color }}
                >
                  {current.label}
                </motion.p>
              </AnimatePresence>
            </div>

            {/* 确认按钮 */}
            <div className="px-10 pb-9">
              <button
                onClick={() => onConfirm(current.value)}
                className="w-full py-3 rounded-2xl text-[10px] font-medium tracking-[0.3em] transition-all active:scale-[0.97]"
                style={{
                  backgroundColor: `${current.color}18`,
                  color: current.color,
                  border: `1px solid ${current.color}30`,
                }}
              >
                确认
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
}

export default SliderModal;
