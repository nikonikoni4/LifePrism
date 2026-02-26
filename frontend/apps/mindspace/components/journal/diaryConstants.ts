/**
 * 日记模块常量配置
 * 心情/重要程度的颜色方案和标签
 */
import type { MoodLevel, ImportanceLevel, SliderOption } from './diaryTypes';

export const MOOD_OPTIONS: SliderOption<MoodLevel>[] = [
  { value: 'very_happy', label: '非常愉悦', color: '#E8C170' },
  { value: 'happy',     label: '有点开心', color: '#B5D89A' },
  { value: 'calm',      label: '平静',     color: '#A8C4C2' },
  { value: 'bad',       label: '不太好',   color: '#8B9DC3' },
  { value: 'very_bad',  label: '非常不好', color: '#5B6B8A' },
];

export const IMPORTANCE_OPTIONS: SliderOption<ImportanceLevel>[] = [
  { value: 'important',   label: '重要', color: '#C4956A' },
  { value: 'normal',      label: '一般', color: '#B0A08A' },
  { value: 'unimportant', label: '平凡', color: '#C8C8C8' },
];

/** 根据 value 查找心情配置 */
export const getMoodOption = (value: MoodLevel) =>
  MOOD_OPTIONS.find(o => o.value === value);

/** 根据 value 查找重要程度配置 */
export const getImportanceOption = (value: ImportanceLevel) =>
  IMPORTANCE_OPTIONS.find(o => o.value === value);

/** 禅意预设背景色 */
export const BG_PRESETS = [
  { name: '象牙', h: 30, s: 15, l: 96 },
  { name: '薄墨', h: 0, s: 0, l: 92 },
  { name: '青磁', h: 170, s: 10, l: 92 },
  { name: '淡樱', h: 350, s: 20, l: 96 },
  { name: '枯草', h: 55, s: 15, l: 93 },
];
