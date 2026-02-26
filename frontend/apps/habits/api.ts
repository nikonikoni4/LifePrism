// Habit System API Service
import { Habit, HabitCheckIn, HabitStats, HeatmapData, HabitHistory, CreateHabitForm } from './types';

// Mock data for development
const MOCK_HABITS: Habit[] = [
  {
    id: '1',
    name: '晨间冥想',
    description: '每天早上起床后进行10分钟冥想',
    frequency: { type: 'daily' },
    anchorType: 'time',
    anchorDescription: '起床后立即',
    currentLevel: 2,
    currentChallenge: {
      id: 'c1',
      habitId: '1',
      targetDays: 21,
      requiredCompletions: 18,
      fromLevel: 2,
      toLevel: 3,
      startDate: '2026-01-15',
      endDate: '2026-02-05',
      completedCount: 12,
      status: 'in_progress'
    },
    status: 'active',
    createdAt: '2025-12-01T00:00:00Z',
    updatedAt: '2026-01-30T00:00:00Z'
  },
  {
    id: '2',
    name: '阅读30分钟',
    description: '每天阅读至少30分钟',
    frequency: { type: 'daily' },
    anchorType: 'time',
    anchorDescription: '睡前',
    currentLevel: 1,
    currentChallenge: {
      id: 'c2',
      habitId: '2',
      targetDays: 14,
      requiredCompletions: 12,
      fromLevel: 1,
      toLevel: 2,
      startDate: '2026-01-20',
      endDate: '2026-02-03',
      completedCount: 8,
      status: 'in_progress'
    },
    status: 'active',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-30T00:00:00Z'
  },
  {
    id: '3',
    name: '健身锻炼',
    description: '每周进行4次力量训练',
    frequency: { type: 'weekly', timesPerWeek: 4 },
    anchorType: 'event',
    anchorDescription: '下班后',
    currentLevel: 3,
    status: 'active',
    createdAt: '2025-10-01T00:00:00Z',
    updatedAt: '2026-01-30T00:00:00Z'
  },
  {
    id: '4',
    name: '写日记',
    description: '记录每天的想法和感受',
    frequency: { type: 'weekdays' },
    anchorType: 'time',
    anchorDescription: '晚上9点',
    currentLevel: 0,
    currentChallenge: {
      id: 'c3',
      habitId: '4',
      targetDays: 7,
      requiredCompletions: 5,
      fromLevel: 0,
      toLevel: 1,
      startDate: '2026-01-27',
      endDate: '2026-02-03',
      completedCount: 3,
      status: 'in_progress'
    },
    status: 'active',
    createdAt: '2026-01-27T00:00:00Z',
    updatedAt: '2026-01-30T00:00:00Z'
  },
  {
    id: '5',
    name: '学习英语',
    description: '每天学习英语单词和语法',
    frequency: { type: 'daily' },
    currentLevel: 1,
    status: 'paused',
    createdAt: '2025-11-01T00:00:00Z',
    updatedAt: '2026-01-15T00:00:00Z'
  }
];

// Generate mock heatmap data for the last 12 weeks
const generateMockHeatmapData = (): HeatmapData[] => {
  const data: HeatmapData[] = [];
  const today = new Date();

  for (let i = 83; i >= 0; i--) {
    const date = new Date(today);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split('T')[0];

    const totalHabits = 4;
    const completedHabits = Math.floor(Math.random() * (totalHabits + 1));

    data.push({
      date: dateStr,
      totalHabits,
      completedHabits,
      completionRate: totalHabits > 0 ? completedHabits / totalHabits : 0
    });
  }

  return data;
};

const MOCK_HEATMAP_DATA = generateMockHeatmapData();

const MOCK_STATS: HabitStats = {
  todayPending: 2,
  todayCompleted: 2,
  weeklyCompletionRate: 0.78,
  activeHabitsCount: 4,
  totalCheckIns: 156,
  currentStreak: 5
};

// Simulate API delay
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// API functions
export const habitApi = {
  // 获取习惯列表
  getHabits: async (): Promise<Habit[]> => {
    await delay(300);
    return [...MOCK_HABITS];
  },

  // 获取单个习惯
  getHabit: async (id: string): Promise<Habit | null> => {
    await delay(200);
    return MOCK_HABITS.find(h => h.id === id) || null;
  },

  // 创建习惯
  createHabit: async (data: CreateHabitForm): Promise<Habit> => {
    await delay(300);
    const newHabit: Habit = {
      id: Date.now().toString(),
      name: data.name,
      description: data.description,
      frequency: data.frequency,
      anchorType: data.anchorType,
      anchorDescription: data.anchorDescription,
      currentLevel: 0,
      status: 'active',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      currentChallenge: data.initialChallenge ? {
        id: `c${Date.now()}`,
        habitId: Date.now().toString(),
        targetDays: data.initialChallenge.targetDays,
        requiredCompletions: data.initialChallenge.requiredCompletions,
        fromLevel: 0,
        toLevel: 1,
        startDate: new Date().toISOString().split('T')[0],
        endDate: new Date(Date.now() + data.initialChallenge.targetDays * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        completedCount: 0,
        status: 'in_progress'
      } : undefined
    };
    return newHabit;
  },

  // 更新习惯
  updateHabit: async (id: string, data: Partial<Habit>): Promise<Habit> => {
    await delay(300);
    const habit = MOCK_HABITS.find(h => h.id === id);
    if (!habit) throw new Error('Habit not found');
    return { ...habit, ...data, updatedAt: new Date().toISOString() };
  },

  // 删除习惯
  deleteHabit: async (id: string): Promise<void> => {
    await delay(200);
    // In real implementation, this would delete from backend
  },

  // 打卡
  checkIn: async (habitId: string, date: string, note?: string): Promise<HabitCheckIn> => {
    await delay(200);
    return {
      id: Date.now().toString(),
      habitId,
      date,
      completed: true,
      note,
      createdAt: new Date().toISOString()
    };
  },

  // 取消打卡
  uncheckIn: async (habitId: string, date: string): Promise<void> => {
    await delay(200);
    // In real implementation, this would remove the check-in
  },

  // 获取统计数据
  getStats: async (): Promise<HabitStats> => {
    await delay(200);
    return { ...MOCK_STATS };
  },

  // 获取热力图数据
  getHeatmap: async (habitId?: string): Promise<HeatmapData[]> => {
    await delay(300);
    // In real implementation, filter by habitId if provided
    return [...MOCK_HEATMAP_DATA];
  },

  // 获取习惯历史
  getHistory: async (habitId: string): Promise<HabitHistory> => {
    await delay(300);
    const habit = MOCK_HABITS.find(h => h.id === habitId);
    if (!habit) throw new Error('Habit not found');

    return {
      habit,
      checkIns: [],
      challenges: habit.currentChallenge ? [habit.currentChallenge] : [],
      totalCheckIns: Math.floor(Math.random() * 100) + 10,
      longestStreak: Math.floor(Math.random() * 30) + 5,
      currentStreak: Math.floor(Math.random() * 10) + 1
    };
  },

  // 暂停习惯
  pauseHabit: async (id: string): Promise<Habit> => {
    await delay(200);
    const habit = MOCK_HABITS.find(h => h.id === id);
    if (!habit) throw new Error('Habit not found');
    return { ...habit, status: 'paused', updatedAt: new Date().toISOString() };
  },

  // 恢复习惯
  resumeHabit: async (id: string): Promise<Habit> => {
    await delay(200);
    const habit = MOCK_HABITS.find(h => h.id === id);
    if (!habit) throw new Error('Habit not found');
    return { ...habit, status: 'active', updatedAt: new Date().toISOString() };
  },

  // 归档习惯
  archiveHabit: async (id: string): Promise<Habit> => {
    await delay(200);
    const habit = MOCK_HABITS.find(h => h.id === id);
    if (!habit) throw new Error('Habit not found');
    return { ...habit, status: 'archived', updatedAt: new Date().toISOString() };
  }
};

export default habitApi;
