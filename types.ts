
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
  subCategoryId?: string; // Linked to SubCategoryDef.id
  description?: string;
  linkedGoal?: string;
}

// New types for Categorization Page
export interface SubCategoryDef {
  id: string;
  name: string;
}

export interface CategoryDef {
  id: string;
  name: string;
  color: string;
  subCategories: SubCategoryDef[];
}

export interface ActivityRecord {
  id: string;
  appName: string;
  windowTitle: string;
  timestamp: string;
  duration: string;
  aiDescription?: string;
  categoryId: string; // e.g., 'work'
  subCategoryId: string; // e.g., 'programming'
}

// Dashboard API Types
export interface ChartSegment {
  key: string;
  name: string;
  value: number;
  color: string;
}

export interface BarConfig {
  key: string;
  label: string;
  color: string;
}

export interface TimeOverviewResponse {
  title: string;
  subTitle: string;
  totalTrackedMinutes: number;
  pieData: ChartSegment[];
  barKeys: BarConfig[];
  barData: TimeDistribution[];
}

export interface TopItem {
  name: string;
  duration: number; // seconds
  percentage: number;
}

export interface CategorySummary {
  category: string;
  duration: number; // seconds
  percentage: number;
}

export interface DashboardSummary {
  top_apps: TopItem[];
  top_titles: TopItem[];
  categories_by_default: CategorySummary[];
  categories_by_goals: CategorySummary[];
}

export interface DashboardResponse {
  date: string;
  total_active_time: number; // seconds
  summary: DashboardSummary;
}

export interface DaylyActivitiesResponse{
  data:string;
  activeTimePercentage:number; // percentage of total active time
}

export interface ActivitySummaryResponse {
  DaylyActivities: DaylyActivitiesResponse[];
}
