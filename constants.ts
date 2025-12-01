
import { ActivityData, AppUsage, GoalItem, TimeDistribution, SubCategoryData, TimelineEvent, CategoryDef, ActivityRecord } from "./types";

export const COLORS = {
  WORK: '#5B8FF9',
  WORK_LIGHT: '#85A5FF',
  ENTERTAINMENT: '#FA8C16',
  ENTERTAINMENT_LIGHT: '#FFC069',
  OTHER: '#BFBFBF',
  OTHER_LIGHT: '#D9D9D9',
  UNTRACKED: '#E5E7EB'
};

export const MOCK_GOALS: GoalItem[] = [
  { id: '1', text: 'Complete React Dashboard', completed: false, trackedTime: '1h 20m', tag: 'Dev' },
  { id: '2', text: 'Review PRs for Team', completed: true, trackedTime: '45m', tag: 'Work' },
  { id: '3', text: 'Read "Atomic Habits"', completed: false, tag: 'Self' },
  { id: '4', text: 'Evening Gym Session', completed: false, tag: 'Health' },
];

export const PIE_DATA: ActivityData[] = [
  { name: 'Work/Study', value: 480, color: COLORS.WORK, key: 'work' },
  { name: 'Entertainment', value: 180, color: COLORS.ENTERTAINMENT, key: 'entertainment' },
  { name: 'Other', value: 120, color: COLORS.OTHER, key: 'other' },
];

// Generate 24h distribution (every 2 hours)
export const BAR_DATA: TimeDistribution[] = [
  { timeRange: '0-2', work: 0, entertainment: 30, other: 90 },
  { timeRange: '2-4', work: 0, entertainment: 0, other: 120 },
  { timeRange: '4-6', work: 0, entertainment: 0, other: 120 },
  { timeRange: '6-8', work: 30, entertainment: 0, other: 90 },
  { timeRange: '8-10', work: 100, entertainment: 10, other: 10 },
  { timeRange: '10-12', work: 110, entertainment: 5, other: 5 },
  { timeRange: '12-14', work: 30, entertainment: 60, other: 30 },
  { timeRange: '14-16', work: 120, entertainment: 0, other: 0 },
  { timeRange: '16-18', work: 100, entertainment: 10, other: 10 },
  { timeRange: '18-20', work: 20, entertainment: 80, other: 20 },
  { timeRange: '20-22', work: 0, entertainment: 100, other: 20 },
  { timeRange: '22-24', work: 0, entertainment: 60, other: 60 },
];

// Sub-category drill-down data
export const DRILLDOWN_DATA: Record<string, SubCategoryData> = {
  work: {
    title: 'Work Details',
    pieData: [
      { name: 'Programming', value: 300, color: COLORS.WORK, key: 'programming' },
      { name: 'Writing', value: 180, color: COLORS.WORK_LIGHT, key: 'writing' },
    ],
    barKeys: [
      { key: 'programming', color: COLORS.WORK, label: 'Programming' },
      { key: 'writing', color: COLORS.WORK_LIGHT, label: 'Writing' }
    ],
    barData: [
      { timeRange: '0-2', programming: 0, writing: 0 },
      { timeRange: '2-4', programming: 0, writing: 0 },
      { timeRange: '4-6', programming: 0, writing: 0 },
      { timeRange: '6-8', programming: 30, writing: 0 },
      { timeRange: '8-10', programming: 60, writing: 40 },
      { timeRange: '10-12', programming: 80, writing: 30 },
      { timeRange: '12-14', programming: 0, writing: 30 },
      { timeRange: '14-16', programming: 100, writing: 20 },
      { timeRange: '16-18', programming: 30, writing: 70 },
      { timeRange: '18-20', programming: 0, writing: 20 },
      { timeRange: '20-22', programming: 0, writing: 0 },
      { timeRange: '22-24', programming: 0, writing: 0 },
    ]
  },
  entertainment: {
    title: 'Entertainment Details',
    pieData: [
      { name: 'Video', value: 120, color: COLORS.ENTERTAINMENT, key: 'video' },
      { name: 'Games', value: 60, color: COLORS.ENTERTAINMENT_LIGHT, key: 'games' },
    ],
    barKeys: [
      { key: 'video', color: COLORS.ENTERTAINMENT, label: 'Video' },
      { key: 'games', color: COLORS.ENTERTAINMENT_LIGHT, label: 'Games' }
    ],
    barData: [
      { timeRange: '0-2', video: 30, games: 0 },
      { timeRange: '2-4', video: 0, games: 0 },
      { timeRange: '4-6', video: 0, games: 0 },
      { timeRange: '6-8', video: 0, games: 0 },
      { timeRange: '8-10', video: 10, games: 0 },
      { timeRange: '10-12', video: 5, games: 0 },
      { timeRange: '12-14', video: 40, games: 20 },
      { timeRange: '14-16', video: 0, games: 0 },
      { timeRange: '16-18', video: 10, games: 0 },
      { timeRange: '18-20', video: 40, games: 40 },
      { timeRange: '20-22', video: 60, games: 40 },
      { timeRange: '22-24', video: 60, games: 0 },
    ]
  },
  other: {
    title: 'Other Activity Details',
    pieData: [
      { name: 'Email', value: 40, color: COLORS.OTHER, key: 'email' },
      { name: 'Social', value: 80, color: COLORS.OTHER_LIGHT, key: 'social' },
    ],
    barKeys: [
      { key: 'email', color: COLORS.OTHER, label: 'Email' },
      { key: 'social', color: COLORS.OTHER_LIGHT, label: 'Social' }
    ],
    barData: [
      { timeRange: '0-2', email: 30, social: 60 },
      { timeRange: '2-4', email: 0, social: 120 },
      { timeRange: '4-6', email: 0, social: 120 },
      { timeRange: '6-8', email: 30, social: 60 },
      { timeRange: '8-10', email: 10, social: 0 },
      { timeRange: '10-12', email: 5, social: 0 },
      { timeRange: '12-14', email: 10, social: 20 },
      { timeRange: '14-16', email: 0, social: 0 },
      { timeRange: '16-18', email: 10, social: 0 },
      { timeRange: '18-20', email: 10, social: 10 },
      { timeRange: '20-22', email: 10, social: 10 },
      { timeRange: '22-24', email: 0, social: 60 },
    ]
  }
};

export const TOP_APPS: AppUsage[] = [
  { name: 'VS Code', duration: '4h 12m', percentage: 65 },
  { name: 'Google Chrome', duration: '2h 30m', percentage: 38 },
  { name: 'Figma', duration: '1h 15m', percentage: 20 },
  { name: 'Spotify', duration: '45m', percentage: 12 },
];

export const TOP_WINDOWS: AppUsage[] = [
  { name: 'GitHub - Project Alpha', duration: '1h 45m', percentage: 40 },
  { name: 'Stack Overflow - React Types', duration: '45m', percentage: 18 },
  { name: 'Youtube - Lofi Beats', duration: '2h 10m', percentage: 55 },
  { name: 'Localhost:3000', duration: '1h 10m', percentage: 28 },
];

export const TIMELINE_EVENTS: TimelineEvent[] = [
  { id: '1', title: 'Deep Sleep', startTime: 0, endTime: 7, category: 'other', description: 'Restorative sleep' },
  { id: '2', title: 'Morning Routine', startTime: 7, endTime: 8.5, category: 'other', description: 'Breakfast, Shower' },
  { id: '3', title: 'Commute', startTime: 8.5, endTime: 9, category: 'other', description: 'Listening to podcast' },
  { id: '4', title: 'Standup Meeting', startTime: 9, endTime: 9.5, category: 'work', linkedGoal: '2', description: 'Daily sync with engineering team' },
  { id: '5', title: 'Dashboard Development', startTime: 9.5, endTime: 12, category: 'work', linkedGoal: '1', description: 'Implementing React components' },
  { id: '6', title: 'Lunch Break', startTime: 12, endTime: 13, category: 'entertainment', description: 'Youtube & Lunch' },
  { id: '7', title: 'Code Review', startTime: 13, endTime: 14.5, category: 'work', linkedGoal: '2', description: 'Reviewing PRs #342 and #345' },
  { id: '8', title: 'Deep Focus: Backend', startTime: 14.5, endTime: 17, category: 'work', linkedGoal: '1', description: 'API integration' },
  { id: '9', title: 'Break / Social', startTime: 17, endTime: 17.5, category: 'other', description: 'Coffee chat' },
  { id: '10', title: 'Wrap up', startTime: 17.5, endTime: 18, category: 'work', description: 'Planning for tomorrow' },
  { id: '11', title: 'Gym', startTime: 18.5, endTime: 20, category: 'other', linkedGoal: '4', description: 'Upper body workout' },
  { id: '12', title: 'Gaming', startTime: 20.5, endTime: 22.5, category: 'entertainment', description: 'Cyberpunk 2077' },
];

// --- Mock Data for Categorization Page ---

export const MOCK_CATEGORIES: CategoryDef[] = [
  {
    id: 'work',
    name: 'Work',
    color: '#5B8FF9',
    subCategories: [
      { id: 'coding', name: 'Coding' },
      { id: 'meeting', name: 'Meetings' },
      { id: 'planning', name: 'Planning' },
      { id: 'research', name: 'Research' }
    ]
  },
  {
    id: 'entertainment',
    name: 'Entertainment',
    color: '#FA8C16',
    subCategories: [
      { id: 'video', name: 'Video Streaming' },
      { id: 'games', name: 'Gaming' },
      { id: 'social', name: 'Social Media' }
    ]
  },
  {
    id: 'other',
    name: 'Other',
    color: '#BFBFBF',
    subCategories: [
      { id: 'utilities', name: 'System Utilities' },
      { id: 'browsing', name: 'General Browsing' },
      { id: 'untracked', name: 'Untracked' }
    ]
  }
];

export const MOCK_ACTIVITY_RECORDS: ActivityRecord[] = [
  { id: '1', appName: 'Code.exe', windowTitle: 'App.tsx - LifeWatch - Visual Studio Code', timestamp: '10:42 AM', duration: '45m', aiDescription: 'AI: Likely active coding session in React', categoryId: 'work', subCategoryId: 'coding' },
  { id: '2', appName: 'Chrome', windowTitle: 'React Hooks Documentation - Google Chrome', timestamp: '11:15 AM', duration: '12m', aiDescription: 'AI: Researching development documentation', categoryId: 'work', subCategoryId: 'research' },
  { id: '3', appName: 'Slack', windowTitle: '#engineering - Huddle', timestamp: '09:00 AM', duration: '30m', aiDescription: 'AI: Team communication', categoryId: 'work', subCategoryId: 'meeting' },
  { id: '4', appName: 'Spotify', windowTitle: 'Daily Mix 1', timestamp: '02:00 PM', duration: '2h', aiDescription: 'AI: Background music application', categoryId: 'entertainment', subCategoryId: 'video' },
  { id: '5', appName: 'Steam', windowTitle: 'Cyberpunk 2077', timestamp: '08:30 PM', duration: '1h 20m', aiDescription: 'AI: Gaming activity detected', categoryId: 'entertainment', subCategoryId: 'games' },
  { id: '6', appName: 'Finder', windowTitle: 'Downloads', timestamp: '06:15 PM', duration: '5m', aiDescription: 'AI: File management', categoryId: 'other', subCategoryId: 'utilities' },
  { id: '7', appName: 'UnknownApp.exe', windowTitle: 'Untitled Window', timestamp: '04:00 PM', duration: '15m', aiDescription: 'AI: Could not determine activity type', categoryId: 'other', subCategoryId: 'untracked' },
];
