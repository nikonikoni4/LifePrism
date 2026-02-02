// Habit System Type Definitions

// 习惯频率类型
export type FrequencyType = 'daily' | 'weekdays' | 'weekly' | 'custom';

// 习惯频率配置
export interface HabitFrequency {
  type: FrequencyType;
  timesPerWeek?: number;      // 每周次数 (weekly 类型)
  specificDays?: number[];    // 具体星期几 1-7, 1=周一 (custom 类型)
}

// 习惯挑战
export interface HabitChallenge {
  id: string;
  habitId: string;
  targetDays: number;         // 目标天数
  requiredCompletions: number; // 需要完成的次数
  fromLevel: number;          // 起始等级
  toLevel: number;            // 目标等级
  startDate: string;          // ISO date string
  endDate: string;            // ISO date string
  completedCount: number;     // 已完成次数
  status: 'in_progress' | 'succeeded' | 'failed';
}

// 习惯状态
export type HabitStatus = 'active' | 'paused' | 'archived';

// 习惯
export interface Habit {
  id: string;
  name: string;
  description?: string;
  frequency: HabitFrequency;
  anchorType?: 'time' | 'event' | 'scene';
  anchorDescription?: string;
  currentLevel: number;       // 0-4
  currentChallenge?: HabitChallenge;
  status: HabitStatus;
  goalId?: string;            // 关联目标 (V2)
  valueId?: string;           // 关联价值 (V2)
  commitmentId?: string;      // 关联承诺 (V2)
  createdAt: string;
  updatedAt: string;
}

// 打卡记录
export interface HabitCheckIn {
  id: string;
  habitId: string;
  date: string;               // ISO date string (YYYY-MM-DD)
  completed: boolean;
  note?: string;
  createdAt: string;
}

// 热力图数据
export interface HeatmapData {
  date: string;               // YYYY-MM-DD
  totalHabits: number;
  completedHabits: number;
  completionRate: number;     // 0-1
}

// 统计数据
export interface HabitStats {
  todayPending: number;
  todayCompleted: number;
  weeklyCompletionRate: number;
  activeHabitsCount: number;
  totalCheckIns: number;
  currentStreak: number;
}

// 习惯历史记录
export interface HabitHistory {
  habit: Habit;
  checkIns: HabitCheckIn[];
  challenges: HabitChallenge[];
  totalCheckIns: number;
  longestStreak: number;
  currentStreak: number;
}

// 等级配置
export interface LevelConfig {
  level: number;
  name: string;
  color: string;
  bgColor: string;
  borderColor: string;
  description: string;
}

// 等级常量
export const HABIT_LEVELS: LevelConfig[] = [
  {
    level: 0,
    name: '萌芽',
    color: '#FCD34D',
    bgColor: 'bg-amber-100',
    borderColor: 'border-amber-200',
    description: '习惯刚刚开始'
  },
  {
    level: 1,
    name: '生根',
    color: '#FBBF24',
    bgColor: 'bg-amber-200',
    borderColor: 'border-amber-300',
    description: '习惯开始扎根'
  },
  {
    level: 2,
    name: '成长',
    color: '#F59E0B',
    bgColor: 'bg-amber-300',
    borderColor: 'border-amber-400',
    description: '习惯稳定成长'
  },
  {
    level: 3,
    name: '稳固',
    color: '#D97706',
    bgColor: 'bg-amber-400',
    borderColor: 'border-amber-500',
    description: '习惯已经稳固'
  },
  {
    level: 4,
    name: '根深蒂固',
    color: '#B45309',
    bgColor: 'bg-amber-500',
    borderColor: 'border-amber-600',
    description: '习惯已成为本能'
  },
];

// 获取等级配置
export const getLevelConfig = (level: number): LevelConfig => {
  return HABIT_LEVELS[Math.min(Math.max(level, 0), 4)];
};

// 频率显示文本
export const getFrequencyText = (frequency: HabitFrequency): string => {
  switch (frequency.type) {
    case 'daily':
      return '每天';
    case 'weekdays':
      return '工作日';
    case 'weekly':
      return `每周 ${frequency.timesPerWeek || 1} 次`;
    case 'custom':
      if (frequency.specificDays && frequency.specificDays.length > 0) {
        const dayNames = ['一', '二', '三', '四', '五', '六', '日'];
        const days = frequency.specificDays.map(d => dayNames[d - 1]).join('、');
        return `周${days}`;
      }
      return '自定义';
    default:
      return '未知';
  }
};

// 创建习惯表单数据
export interface CreateHabitForm {
  name: string;
  description?: string;
  frequency: HabitFrequency;
  anchorType?: 'time' | 'event' | 'scene';
  anchorDescription?: string;
  initialChallenge?: {
    targetDays: number;
    requiredCompletions: number;
  };
}

// ============================================
// 习惯系统 V2 - 时间轴与链条类型定义
// ============================================

// 触发器类型
export type ChainTriggerType = 'time' | 'scene' | 'event' | 'habit';

// 链条节点：可以是正式习惯或自由文本提醒
export interface HabitAnchorNode {
  id: string;
  habitId?: string;          // 关联已有习惯
  customText?: string;       // 自由文本提醒（如"喝杯水"、"深呼吸3次"）
  order: number;             // 在链条中的顺序
}

// 习惯锚点/链条（时间轴和链条共用同一数据结构）
export interface HabitAnchor {
  id: string;
  triggerType: ChainTriggerType;
  triggerDescription: string;  // "每天12:00" / "回家后" / "洗漱后" / "冥想后"
  anchorTime?: string;         // 锚点时间 "HH:mm"（仅时间触发有）
  linkedHabitId?: string;      // 习惯触发时，关联的前置习惯ID
  nodes: HabitAnchorNode[];    // 节点数组，支持多个节点串联
  createdAt: string;
  updatedAt: string;
}

// 触发器类型配置
export interface TriggerTypeConfig {
  type: ChainTriggerType;
  label: string;
  icon: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
}

// 触发器类型常量
export const TRIGGER_TYPES: TriggerTypeConfig[] = [
  {
    type: 'time',
    label: '时间触发',
    icon: '⏰',
    bgColor: 'bg-blue-50',
    borderColor: 'border-blue-200',
    textColor: 'text-blue-600'
  },
  {
    type: 'scene',
    label: '场景触发',
    icon: '🏠',
    bgColor: 'bg-purple-50',
    borderColor: 'border-purple-200',
    textColor: 'text-purple-600'
  },
  {
    type: 'event',
    label: '事件触发',
    icon: '📋',
    bgColor: 'bg-orange-50',
    borderColor: 'border-orange-200',
    textColor: 'text-orange-600'
  },
  {
    type: 'habit',
    label: '习惯触发',
    icon: '🔗',
    bgColor: 'bg-teal-50',
    borderColor: 'border-teal-200',
    textColor: 'text-teal-600'
  }
];

// 获取触发器类型配置
export const getTriggerTypeConfig = (type: ChainTriggerType): TriggerTypeConfig => {
  return TRIGGER_TYPES.find(t => t.type === type) || TRIGGER_TYPES[0];
};

// 等级对应的 teal 颜色（用于时间轴）
export const LEVEL_TEAL_COLORS: Record<number, string> = {
  0: 'bg-teal-100',
  1: 'bg-teal-200',
  2: 'bg-teal-300',
  3: 'bg-teal-400',
  4: 'bg-teal-500'
};

// 获取等级对应的 teal 背景色
export const getLevelTealBg = (level: number): string => {
  return LEVEL_TEAL_COLORS[Math.min(Math.max(level, 0), 4)] || 'bg-slate-100';
};
