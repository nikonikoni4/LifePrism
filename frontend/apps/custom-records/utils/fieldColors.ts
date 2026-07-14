/**
 * 字段配色工具
 * 使用稳定哈希算法从 field_key 派生颜色，同一 field_key 永远获得同一颜色
 */

export interface FieldColor {
  bg: string;
  text: string;
  border: string;
  dot: string;
  solid: string;
}

// 10 色循环调色板
export const FIELD_COLORS: FieldColor[] = [
  { bg: 'bg-cyan-50', text: 'text-cyan-700', border: 'border-cyan-100', dot: 'bg-cyan-400', solid: 'bg-cyan-500' },
  { bg: 'bg-violet-50', text: 'text-violet-700', border: 'border-violet-100', dot: 'bg-violet-400', solid: 'bg-violet-500' },
  { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-100', dot: 'bg-amber-400', solid: 'bg-amber-500' },
  { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-100', dot: 'bg-emerald-400', solid: 'bg-emerald-500' },
  { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-100', dot: 'bg-rose-400', solid: 'bg-rose-500' },
  { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-100', dot: 'bg-blue-400', solid: 'bg-blue-500' },
  { bg: 'bg-orange-50', text: 'text-orange-700', border: 'border-orange-100', dot: 'bg-orange-400', solid: 'bg-orange-500' },
  { bg: 'bg-teal-50', text: 'text-teal-700', border: 'border-teal-100', dot: 'bg-teal-400', solid: 'bg-teal-500' },
  { bg: 'bg-pink-50', text: 'text-pink-700', border: 'border-pink-100', dot: 'bg-pink-400', solid: 'bg-pink-500' },
  { bg: 'bg-indigo-50', text: 'text-indigo-700', border: 'border-indigo-100', dot: 'bg-indigo-400', solid: 'bg-indigo-500' },
];

// P2: 与 FIELD_COLORS 一一对应的 hex 调色板（供 recharts 使用）
export const FIELD_HEX_COLORS: string[] = [
  '#06b6d4', // cyan-500
  '#8b5cf6', // violet-500
  '#f59e0b', // amber-500
  '#10b981', // emerald-500
  '#f43f5e', // rose-500
  '#3b82f6', // blue-500
  '#f97316', // orange-500
  '#14b8a6', // teal-500
  '#ec4899', // pink-500
  '#6366f1', // indigo-500
];

/**
 * 稳定哈希函数 — 将字符串转为非负整数
 * 同一输入永远产生同一输出
 */
export const hashStr = (s: string): number => {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0; // 转为 32 位整数
  }
  return Math.abs(h);
};

/**
 * 根据 field_key 获取稳定的颜色对象
 * 同一 field_key 永远获得同一颜色
 */
export const getFieldColor = (fieldKey: string): FieldColor => {
  return FIELD_COLORS[hashStr(fieldKey) % FIELD_COLORS.length];
};

/**
 * 根据 field_key 获取稳定的 hex 颜色（供 recharts 等需要 hex 值的场景使用）
 * 与 getFieldColor 共享同一哈希，确保 Tailwind 类名与 hex 颜色一致
 */
export const getFieldHexColor = (fieldKey: string): string => {
  return FIELD_HEX_COLORS[hashStr(fieldKey) % FIELD_HEX_COLORS.length];
};
