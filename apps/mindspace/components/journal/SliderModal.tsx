/**
 * SliderModal - 通用滑块选择器弹窗
 * 用于心情和重要程度选择，禅意风格
 *
 * 布局：顶部色块 → 中间滑块 → 底部文字 + 确认
 */
import React, { useState, useCallback, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import type { SliderOption } from './diaryTypes';

interface SliderModalProps<T extends string> {
  open: boolean;
  title: string;
  options: SliderOption<T>[];
  value: T | null;
  onConfirm: (value: T) => void;
  onClose: () => void;
}

/** 两个十六进制颜色之间线性插值 */
function lerpColor(a: string, b: string, t: number): string {
  const parse = (hex: string) => {
    const h = hex.replace('#', '');
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  };
  const [r1, g1, b1] = parse(a);
  const [r2, g2, b2] = parse(b);
  const r = Math.round(r1 + (r2 - r1) * t);
  const g = Math.round(g1 + (g2 - g1) * t);
  const bl = Math.round(b1 + (b2 - b1) * t);
  return `rgb(${r}, ${g}, ${bl})`;
}

function SliderModal<T extends string>({
  open, title, options, value, onConfirm, onClose,
}: SliderModalProps<T>) {
  const defaultIndex = value ? options.findIndex(o => o.value === value) : Math.floor(options.length / 2);
  const [index, setIndex] = useState(Math.max(0, defaultIndex));

  // 当 value 变化时重置 index
  React.useEffect(() => {
    if (open) {
      const idx = value ? options.findIndex(o => o.value === value) : Math.floor(options.length / 2);
      setIndex(Math.max(0, idx));
    }
  }, [open, value, options]);

  const current = options[index];
  const max = options.length - 1;

  // 计算连续颜色（滑块在两个档位之间时平滑过渡）
  const continuousColor = useMemo(() => current.color, [current]);

  // 滑块轨道渐变
  const trackGradient = useMemo(() => {
    const stops = options.map((o, i) => `${o.color} ${(i / max) * 100}%`).join(', ');
    return `linear-gradient(to right, ${stops})`;
  }, [options, max]);

  const handleSlider = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setIndex(Number(e.target.value));
  }, []);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          className="fixed inset-0 z-[200] flex items-center justify-center"
          onClick={onClose}
        >
          {/* 背景遮罩 */}
          <div className="absolute inset-0 bg-black/5 backdrop-blur-xl" />

          {/* 弹窗主体 */}
          <motion.div
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.4, ease: [0.23, 1, 0.32, 1] }}
            onClick={e => e.stopPropagation()}
            className="relative w-[420px] bg-white/80 backdrop-blur-2xl rounded-[32px] shadow-[0_20px_60px_-10px_rgba(0,0,0,0.12)] border border-white/60 overflow-hidden"
          >
            {/* 标题 */}
            <div className="px-10 pt-10 pb-5">
              <p className="text-[11px] font-bold text-gray-400 uppercase tracking-[0.3em] text-center">{title}</p>
            </div>

            {/* 色块区域 */}
            <div className="px-10 pb-8">
              <motion.div
                animate={{ backgroundColor: continuousColor }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="w-full h-36 rounded-[20px]"
                style={{ backgroundColor: continuousColor }}
              />
            </div>

            {/* 滑块 */}
            <div className="px-12 pb-5">
              <div className="relative h-5 flex items-center">
                <div className="absolute inset-x-0 h-[3px] rounded-full" style={{ background: trackGradient }} />
                <input
                  type="range"
                  min={0}
                  max={max}
                  step={1}
                  value={index}
                  onChange={handleSlider}
                  className="slider-modal-range absolute inset-0 w-full appearance-none bg-transparent cursor-pointer"
                />
              </div>
              {/* 档位刻度 */}
              <div className="flex justify-between mt-3">
                {options.map((o, i) => (
                  <button
                    key={o.value}
                    onClick={() => setIndex(i)}
                    className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
                      i === index ? 'scale-150' : 'opacity-30 hover:opacity-60'
                    }`}
                    style={{ backgroundColor: o.color }}
                  />
                ))}
              </div>
            </div>

            {/* 当前等级文字 */}
            <div className="text-center pb-5">
              <motion.p
                key={current.value}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                className="text-xl font-serif italic"
                style={{ color: continuousColor }}
              >
                {current.label}
              </motion.p>
            </div>

            {/* 确认按钮 */}
            <div className="px-10 pb-10">
              <button
                onClick={() => onConfirm(current.value)}
                className="w-full py-3.5 bg-black/80 text-white text-[11px] font-bold rounded-2xl uppercase tracking-[0.3em] hover:bg-black hover:shadow-lg active:scale-[0.98] transition-all"
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
