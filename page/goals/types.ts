
// ============================================================================
// TodoList Types (与后端 API 对齐)
// ============================================================================

export interface SubTodoItem {
    id: number;
    orderIndex: number;
    parentId: number;
    content: string;
    completed: boolean;
}

export interface TodoItem {
    id: number;
    orderIndex: number;
    content: string;
    color: string;
    completed: boolean;
    linkToGoal: number | null;
    date: string;
    expectedFinishedAt: string | null;
    actualFinishedAt: string | null;
    crossDay: boolean;
    subItems?: SubTodoItem[];
}

export interface TodoListResponse {
    dailyFocusContent: string | null;
    items: TodoItem[];
}

export interface SubTodoListResponse {
    items: SubTodoItem[];
}

// ============================================================================
// Plan Types (与后端 API 对齐)
// ============================================================================

export interface DailyPlanItem {
    id: number;
    date: string;
    dailyFocusContent: string;
    completionRate: number;
    todoList: TodoItem[];
}

export interface WeeklyPlanResponse {
    weeklyFocusContent: string;
    items: DailyPlanItem[];
}

export interface WeeklyPlanItem {
    id: number;
    startDate: string;
    endDate: string;
    weeklyFocusContent: string;
    completionRate: number;
}

export interface MonthlyPlanResponse {
    monthlyFocusContent: string;
    items: WeeklyPlanItem[];
}

// ============================================================================
// Legacy Types (保留用于其他组件)
// ============================================================================

export interface GoalItem {
    id: string;
    text: string;
    completed: boolean;
    trackedTime?: string; // e.g., "45m"
    tag?: string;
    linkToGoalId?: string;
    date?: string; // YYYY-MM-DD (Primary/Start Date)

    // New fields for hierarchical view
    startDate?: string;
    endDate?: string;
    color?: string;
    subItems?: GoalItem[];
}

export interface UserGoal {
    id: string;
    name: string;
    alias?: string;
    content: string;
    createdAt: string;
    expectedFinishedAt: string;
    expectedEndAt: string;
    estimatedDuration: string; // e.g. "40 hours"
    categoryId?: string;
}

export interface DailyPlan {
    id: string;
    date: string;
    content: string;
}

export interface RewardRecord {
    goalId: string;
    rewardContent: string;
    history: Array<{
        date: string;
        timeSpent: number; // minutes
        todoCount: number;
    }>;
}

export interface IdentityBeing {
    id: string;
    content: string;
}

export interface ActivityData {
    name: string;
    value: number; // minutes
    color: string;
    key?: string; // Used for linking to sub-data
    // Add index signature to satisfy Recharts data requirements
    [key: string]: any;
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

export interface TokenUsage {
    date: string;
    inputTokens: number;
    outputTokens: number;
    processedRecords: number;
}