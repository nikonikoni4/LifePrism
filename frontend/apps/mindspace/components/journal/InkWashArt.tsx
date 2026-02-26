/**
 * InkWashArt - 水墨意象 SVG 组件
 * 心情：紧缩墨团 → 褶皱墨滴 → 正圆墨滴 → 舒展叶片 → 绽放墨花
 * 重要程度：小圆点 → 中等圆环 → 星芒光晕
 */
import React from 'react';
import { motion } from 'framer-motion';

interface InkWashArtProps {
  type: 'mood' | 'importance';
  index: number;
  color: string;
}

const transition = { duration: 0.6, ease: [0.23, 1, 0.32, 1] as [number, number, number, number] };

/** SVG 滤镜：水墨质感 */
const InkFilter: React.FC<{ id: string }> = ({ id }) => (
  <defs>
    <filter id={`ink-${id}`} x="-30%" y="-30%" width="160%" height="160%">
      <feTurbulence type="fractalNoise" baseFrequency="0.035" numOctaves="4" seed={2} result="noise" />
      <feDisplacementMap in="SourceGraphic" in2="noise" scale="6" result="displaced" />
      <feGaussianBlur in="displaced" stdDeviation="1.2" />
    </filter>
    <filter id={`glow-${id}`} x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="8" result="blur" />
      <feComposite in="SourceGraphic" in2="blur" operator="over" />
    </filter>
    <radialGradient id={`grad-${id}`} cx="50%" cy="50%" r="50%">
      <stop offset="0%" stopOpacity="0.9" />
      <stop offset="60%" stopOpacity="0.6" />
      <stop offset="100%" stopOpacity="0" />
    </radialGradient>
  </defs>
);

/* ─── 心情图样 ─── */

/** very_bad: 紧缩墨团 - 多个小圆向中心聚拢 */
const MoodVeryBad: React.FC<{ color: string }> = ({ color }) => (
  <g filter="url(#ink-mood)">
    {[
      { cx: 100, cy: 100, r: 18 },
      { cx: 88, cy: 90, r: 14 },
      { cx: 112, cy: 92, r: 13 },
      { cx: 95, cy: 112, r: 12 },
      { cx: 108, cy: 108, r: 11 },
      { cx: 92, cy: 98, r: 10 },
    ].map((c, i) => (
      <motion.circle
        key={i}
        cx={c.cx} cy={c.cy} r={c.r}
        fill={color} opacity={0.7}
        initial={{ scale: 0 }}
        animate={{ scale: 1 }}
        transition={{ ...transition, delay: i * 0.05 }}
      />
    ))}
  </g>
);

/** bad: 褶皱墨滴 - 不规则下垂水滴 */
const MoodBad: React.FC<{ color: string }> = ({ color }) => (
  <g filter="url(#ink-mood)">
    <motion.ellipse
      cx={100} cy={96} fill={color} opacity={0.75}
      initial={{ rx: 0, ry: 0 }}
      animate={{ rx: 26, ry: 30 }}
      transition={transition}
    />
    <motion.ellipse
      cx={100} cy={108} fill={color} opacity={0.5}
      initial={{ rx: 0, ry: 0 }}
      animate={{ rx: 18, ry: 22 }}
      transition={{ ...transition, delay: 0.1 }}
    />
    <motion.circle
      cx={100} cy={126} r={0} fill={color} opacity={0.4}
      animate={{ r: 8 }}
      transition={{ ...transition, delay: 0.15 }}
    />
  </g>
);

/** calm: 正圆墨滴 - 完美宁静的圆 */
const MoodCalm: React.FC<{ color: string }> = ({ color }) => (
  <g filter="url(#ink-mood)">
    <motion.circle
      cx={100} cy={100} fill={`url(#grad-mood)`} opacity={0.3}
      initial={{ r: 0 }} animate={{ r: 44 }}
      transition={transition}
      style={{ fill: color, opacity: 0.15 }}
    />
    <motion.circle
      cx={100} cy={100} fill={color} opacity={0.65}
      initial={{ r: 0 }} animate={{ r: 28 }}
      transition={transition}
    />
  </g>
);

/** happy: 舒展叶片 - 两侧展开的有机曲线 */
const MoodHappy: React.FC<{ color: string }> = ({ color }) => (
  <g filter="url(#ink-mood)">
    <motion.circle
      cx={100} cy={100} fill={color} opacity={0.6}
      initial={{ r: 0 }} animate={{ r: 20 }}
      transition={transition}
    />
    {/* 左叶 */}
    <motion.ellipse
      cx={72} cy={96} fill={color} opacity={0.45}
      initial={{ rx: 0, ry: 0 }}
      animate={{ rx: 22, ry: 12 }}
      transition={{ ...transition, delay: 0.1 }}
      transform="rotate(-20 72 96)"
    />
    {/* 右叶 */}
    <motion.ellipse
      cx={128} cy={96} fill={color} opacity={0.45}
      initial={{ rx: 0, ry: 0 }}
      animate={{ rx: 22, ry: 12 }}
      transition={{ ...transition, delay: 0.1 }}
      transform="rotate(20 128 96)"
    />
  </g>
);
/** very_happy: 绽放墨花 - 花瓣径向展开 */
const MoodVeryHappy: React.FC<{ color: string }> = ({ color }) => {
  const petals = 6;
  return (
    <g filter="url(#ink-mood)">
      <motion.circle
        cx={100} cy={100} fill={color} opacity={0.7}
        initial={{ r: 0 }} animate={{ r: 16 }}
        transition={transition}
      />
      {Array.from({ length: petals }).map((_, i) => {
        const angle = (i * 360) / petals - 90;
        const rad = (angle * Math.PI) / 180;
        const px = 100 + Math.cos(rad) * 30;
        const py = 100 + Math.sin(rad) * 30;
        return (
          <motion.ellipse
            key={i}
            cx={px} cy={py}
            fill={color}
            opacity={0.4}
            transform={`rotate(${angle} ${px} ${py})`}
            initial={{ rx: 0, ry: 0 }}
            animate={{ rx: 16, ry: 10 }}
            transition={{ ...transition, delay: i * 0.06 }}
          />
        );
      })}
    </g>
  );
};

/* ─── 重要程度图样 ─── */

/** unimportant: 小圆点 */
const ImpUnimportant: React.FC<{ color: string }> = ({ color }) => (
  <g filter="url(#ink-importance)">
    <motion.circle
      cx={100} cy={100} fill={color} opacity={0.5}
      initial={{ r: 0 }} animate={{ r: 14 }}
      transition={transition}
    />
  </g>
);

/** normal: 中等圆环 */
const ImpNormal: React.FC<{ color: string }> = ({ color }) => (
  <g filter="url(#ink-importance)">
    <motion.circle
      cx={100} cy={100} fill="none" stroke={color}
      strokeWidth={4} opacity={0.55}
      initial={{ r: 0 }} animate={{ r: 28 }}
      transition={transition}
    />
    <motion.circle
      cx={100} cy={100} fill={color} opacity={0.4}
      initial={{ r: 0 }} animate={{ r: 10 }}
      transition={{ ...transition, delay: 0.1 }}
    />
  </g>
);
/** important: 星芒光晕 - 放射线 + 脉动 */
const ImpImportant: React.FC<{ color: string }> = ({ color }) => {
  const rays = 8;
  return (
    <g filter="url(#ink-importance)">
      <motion.circle
        cx={100} cy={100} fill={color} opacity={0.6}
        initial={{ r: 0 }} animate={{ r: 14 }}
        transition={transition}
      />
      {/* 光晕 */}
      <motion.circle
        cx={100} cy={100} fill={color} opacity={0.12}
        initial={{ r: 0 }} animate={{ r: 40 }}
        transition={{ ...transition, delay: 0.1 }}
      />
      {/* 放射线 */}
      {Array.from({ length: rays }).map((_, i) => {
        const angle = (i * 360) / rays;
        const rad = (angle * Math.PI) / 180;
        const x2 = 100 + Math.cos(rad) * 36;
        const y2 = 100 + Math.sin(rad) * 36;
        return (
          <motion.line
            key={i}
            x1={100} y1={100} x2={x2} y2={y2}
            stroke={color} strokeWidth={2} strokeLinecap="round"
            opacity={0.45}
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ ...transition, delay: 0.08 + i * 0.04 }}
          />
        );
      })}
    </g>
  );
};

/* ─── 主组件 ─── */

const moodComponents = [MoodVeryHappy, MoodHappy, MoodCalm, MoodBad, MoodVeryBad];
const impComponents = [ImpImportant, ImpNormal, ImpUnimportant];

const InkWashArt: React.FC<InkWashArtProps> = ({ type, index, color }) => {
  const filterId = type;
  const components = type === 'mood' ? moodComponents : impComponents;
  const Comp = components[Math.min(index, components.length - 1)];

  return (
    <svg viewBox="0 0 200 200" className="w-full h-full">
      <InkFilter id={filterId} />
      <Comp color={color} />
    </svg>
  );
};

export default InkWashArt;
