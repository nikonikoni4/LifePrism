
export interface GoalItem {
  id: string;
  text: string;
  completed: boolean;
  trackedTime?: string; // e.g., "45m"
  tag?: string;
}

export interface ActivityData {
  name: string;
  value: number; // minutes
  color: string;
  key?: string; // Used for linking to sub-data
}

export interface TimeDistribution {
  timeRange: string;
  [key: string]: string | number; // Allow dynamic keys for sub-categories
}

export interface AppUsage {
  name: string;
  duration: string;
  percentage: number;
  icon?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'model';
  text: string;
  isLoading?: boolean;
}

export interface SubCategoryData {
  title: string;
  pieData: ActivityData[];
  barData: TimeDistribution[];
  barKeys: { key: string; color: string; label: string }[];
}

export interface TimelineEvent {
  id: string;
  title: string;
  startTime: number; // Hour (0-24, float allowed e.g. 14.5)
  endTime: number;
  category: 'work' | 'entertainment' | 'other' | 'untracked';
  description?: string;
  linkedGoal?: string;
}
