// 习惯系统 V2 Mock 数据
import { HabitAnchor, Habit } from './types';

// Mock 时间轴锚点数据
export const mockTimelineAnchors: HabitAnchor[] = [
  {
    id: 'anchor-1',
    triggerType: 'time',
    triggerDescription: '每天早上',
    anchorTime: '07:00',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'node-1', habitId: 'habit-1', order: 0 },
    ]
  },
  {
    id: 'anchor-2',
    triggerType: 'time',
    triggerDescription: '早餐后',
    anchorTime: '07:30',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'node-2', customText: '冥想 5 分钟', order: 0 },
    ]
  },
  {
    id: 'anchor-3',
    triggerType: 'time',
    triggerDescription: '上午',
    anchorTime: '08:30',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'node-3', habitId: 'habit-breakfast', order: 0 },
    ]
  },
  {
    id: 'anchor-4',
    triggerType: 'time',
    triggerDescription: '中午',
    anchorTime: '12:00',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'node-4', customText: '吃药', order: 0 },
    ]
  },
  {
    id: 'anchor-5',
    triggerType: 'time',
    triggerDescription: '午餐',
    anchorTime: '12:30',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'node-5', habitId: 'habit-lunch', order: 0 },
    ]
  },
  {
    id: 'anchor-6',
    triggerType: 'time',
    triggerDescription: '晚上',
    anchorTime: '22:00',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'node-6', habitId: 'habit-2', order: 0 },
    ]
  },
];

// Mock 习惯链条数据
export const mockHabitChains: HabitAnchor[] = [
  {
    id: 'chain-1',
    triggerType: 'time',
    triggerDescription: '每天 12:00',
    anchorTime: '12:00',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'cn-1', customText: '吃药', order: 0 },
    ]
  },
  {
    id: 'chain-2',
    triggerType: 'scene',
    triggerDescription: '每天回家后',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'cn-2', customText: '冥想 10 分钟', order: 0 },
    ]
  },
  {
    id: 'chain-3',
    triggerType: 'event',
    triggerDescription: '早上洗漱后',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'cn-3', customText: '打八段锦', order: 0 },
      { id: 'cn-4', customText: '吃早餐', order: 1 },
    ]
  },
  {
    id: 'chain-4',
    triggerType: 'habit',
    triggerDescription: '完成冥想后',
    linkedHabitId: 'habit-meditation',
    createdAt: '2026-01-01',
    updatedAt: '2026-01-01',
    nodes: [
      { id: 'cn-5', customText: '阅读 15 分钟', order: 0 },
    ]
  },
];

// Mock 习惯数据（用于关联显示等级颜色）
export const mockHabitsForAnchor: Pick<Habit, 'id' | 'name' | 'currentLevel'>[] = [
  { id: 'habit-1', name: '起床', currentLevel: 4 },
  { id: 'habit-2', name: '睡觉', currentLevel: 3 },
  { id: 'habit-meditation', name: '冥想', currentLevel: 2 },
  { id: 'habit-breakfast', name: '吃早餐', currentLevel: 4 },
  { id: 'habit-lunch', name: '午餐', currentLevel: 4 },
];

// 根据习惯ID获取习惯信息
export const getHabitById = (habitId: string): Pick<Habit, 'id' | 'name' | 'currentLevel'> | undefined => {
  return mockHabitsForAnchor.find(h => h.id === habitId);
};
