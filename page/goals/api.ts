
import { ActivityData, AppUsage, GoalItem, TimeDistribution, SubCategoryData, TimelineEvent, CategoryDef, ActivityRecord, TokenUsage, UserGoal, DailyPlan, RewardRecord, RewardItem, RewardStatsResponse, IdentityBeing, TodoItem, SubTodoItem, TodoListResponse, SubTodoListResponse, WeeklyPlanResponse, MonthlyPlanResponse, CreateGoalRequest, UpdateGoalRequest, GoalListResponse, CategoryTreeResponse, ActiveGoalNamesResponse } from "./types";

const API_BASE = '/api/v2/goal';

// ============================================================================
// TodoList API - 真实后端接口
// ============================================================================

// 辅助函数：处理 snake_case 到 camelCase 的转换
const toCamelCase = (data: any): any => {
    if (Array.isArray(data)) {
        return data.map(toCamelCase);
    }
    if (data !== null && typeof data === 'object') {
        return Object.keys(data).reduce((acc, key) => {
            const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
            acc[camelKey] = toCamelCase(data[key]);
            return acc;
        }, {} as any);
    }
    return data;
};

// 辅助函数：处理 camelCase 到 snake_case 的转换
const toSnakeCase = (data: any): any => {
    if (Array.isArray(data)) {
        return data.map(toSnakeCase);
    }
    if (data !== null && typeof data === 'object') {
        return Object.keys(data).reduce((acc, key) => {
            const snakeKey = key.replace(/([A-Z])/g, '_$1').toLowerCase();
            acc[snakeKey] = toSnakeCase(data[key]);
            return acc;
        }, {} as any);
    }
    return data;
};

export const todoApi = {
    // 获取任务列表
    getTodos: async (date: string, includeCrossDay = true): Promise<TodoListResponse> => {
        const res = await fetch(`${API_BASE}/todos?date=${date}&include_cross_day=${includeCrossDay}`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 获取任务详情
    getTodoDetail: async (id: number): Promise<TodoItem> => {
        const res = await fetch(`${API_BASE}/todos/${id}`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 创建任务
    createTodo: async (data: {
        content: string;
        date?: string | null;
        color?: string;
        state?: 'active' | 'inactive';
        linkToGoalId?: string | null;
        expectedFinishedAt?: string | null;
        crossDay?: boolean;
    }): Promise<TodoItem> => {
        const res = await fetch(`${API_BASE}/todos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 更新任务
    updateTodo: async (id: number, data: Partial<{
        content: string;
        color: string;
        state: 'active' | 'completed' | 'inactive';
        linkToGoalId: string | null;
        date: string | null;
        expectedFinishedAt: string | null;
        crossDay: boolean;
    }>): Promise<TodoItem> => {
        const res = await fetch(`${API_BASE}/todos/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 删除任务
    deleteTodo: async (id: number): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/todos/${id}`, { method: 'DELETE' });
        return res.ok;
    },

    // 重排序任务
    reorderTodos: async (todoIds: number[]): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/todos/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ todo_ids: todoIds })
        });
        return res.ok;
    },

    // 获取子任务列表
    getSubTodos: async (parentId: number): Promise<SubTodoListResponse> => {
        const res = await fetch(`${API_BASE}/todos/${parentId}/subtodos`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 创建子任务
    createSubTodo: async (parentId: number, content: string): Promise<SubTodoItem> => {
        const res = await fetch(`${API_BASE}/subtodos`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parent_id: parentId, content })
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 更新子任务
    updateSubTodo: async (id: number, data: Partial<{
        content: string;
        completed: boolean;
    }>): Promise<SubTodoItem> => {
        const res = await fetch(`${API_BASE}/subtodos/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 删除子任务
    deleteSubTodo: async (id: number): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/subtodos/${id}`, { method: 'DELETE' });
        return res.ok;
    },

    // 重排序子任务
    reorderSubTodos: async (parentId: number, subTodoIds: number[]): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/subtodos/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ parent_id: parentId, sub_todo_ids: subTodoIds })
        });
        return res.ok;
    },

    // ============ Task Pool API ============

    // 获取任务池任务列表
    getPoolTodos: async (): Promise<TodoListResponse> => {
        const res = await fetch(`${API_BASE}/todos/pool`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 重排序任务池任务
    reorderPoolTodos: async (todoIds: number[]): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/todos/pool/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ todo_ids: todoIds })
        });
        return res.ok;
    },

    // 移动任务到文件夹
    moveTodoToFolder: async (todoId: number, folderId: number | null): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/todos/${todoId}/move`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_id: folderId })
        });
        return res.ok;
    }
};

// ============================================================================
// Folder API - 任务池文件夹接口
// ============================================================================

import { TaskFolder, TaskFolderListResponse } from './types';

export const folderApi = {
    // 获取所有文件夹
    getFolders: async (): Promise<TaskFolder[]> => {
        const res = await fetch(`${API_BASE}/pool/folders`);
        const data = await res.json();
        const result = toCamelCase(data) as TaskFolderListResponse;
        return result.items;
    },

    // 创建文件夹
    createFolder: async (name: string): Promise<TaskFolder> => {
        const res = await fetch(`${API_BASE}/pool/folders`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        const data = await res.json();
        return toCamelCase(data);
    },

    // 更新文件夹
    updateFolder: async (id: number, data: Partial<{ name: string; isExpanded: boolean }>): Promise<TaskFolder> => {
        const res = await fetch(`${API_BASE}/pool/folders/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 删除文件夹
    deleteFolder: async (id: number): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/pool/folders/${id}`, { method: 'DELETE' });
        return res.ok;
    },

    // 重排序文件夹
    reorderFolders: async (folderIds: number[]): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/pool/folders/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ folder_ids: folderIds })
        });
        return res.ok;
    }
};

// ============================================================================
// Plan API - 真实后端接口
// ============================================================================

export const planApi = {
    // 获取周计划
    getWeeklyPlan: async (year: number, month: number, weekNum: number): Promise<WeeklyPlanResponse> => {
        const res = await fetch(`${API_BASE}/plan/weekly?year=${year}&month=${month}&week_num=${weekNum}`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 获取月计划
    getMonthlyPlan: async (year: number, month: number): Promise<MonthlyPlanResponse> => {
        const res = await fetch(`${API_BASE}/plan/monthly?year=${year}&month=${month}`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 更新日焦点
    upsertDailyFocus: async (date: string, content: string): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/plan/daily-focus`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ date, content })
        });
        return res.ok;
    },

    // 更新周焦点
    upsertWeeklyFocus: async (year: number, month: number, weekNum: number, content: string): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/plan/weekly-focus`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ year, month, week_num: weekNum, content })
        });
        return res.ok;
    }
};

// ============================================================================
// Goal API - 真实后端接口
// ============================================================================

const CATEGORY_API_BASE = '/api/v2/category';

export const goalApi = {
    // 获取目标列表
    getGoals: async (params?: {
        status?: string;
        categoryId?: string;
        page?: number;
        pageSize?: number;
    }): Promise<GoalListResponse> => {
        const queryParams = new URLSearchParams();
        if (params?.status) queryParams.append('status', params.status);
        if (params?.categoryId) queryParams.append('category_id', params.categoryId);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.pageSize) queryParams.append('page_size', params.pageSize.toString());

        const queryString = queryParams.toString();
        const url = queryString ? `${API_BASE}/goals?${queryString}` : `${API_BASE}/goals`;
        const res = await fetch(url);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 获取目标详情
    getGoalDetail: async (id: string): Promise<UserGoal> => {
        const res = await fetch(`${API_BASE}/goals/${id}`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 创建目标
    createGoal: async (data: CreateGoalRequest): Promise<UserGoal> => {
        const res = await fetch(`${API_BASE}/goals`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 更新目标
    updateGoal: async (id: string, data: UpdateGoalRequest): Promise<UserGoal> => {
        const res = await fetch(`${API_BASE}/goals/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 删除目标
    deleteGoal: async (id: string): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/goals/${id}`, { method: 'DELETE' });
        return res.ok;
    },

    // 重排序目标
    reorderGoals: async (goalIds: string[]): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/goals/reorder`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ goal_ids: goalIds })
        });
        return res.ok;
    },

    // 获取活跃目标名称列表（用于下拉选择）
    getActiveGoalNames: async (): Promise<ActiveGoalNamesResponse> => {
        const res = await fetch(`${API_BASE}/goals/active-names`);
        const data = await res.json();
        return toCamelCase(data);
    }
};

// ============================================================================
// Category API - 真实后端接口
// ============================================================================

export const categoryApi = {
    // 获取分类树形结构
    getCategoryTree: async (depth: number = 2): Promise<CategoryTreeResponse> => {
        const res = await fetch(`${CATEGORY_API_BASE}/tree?depth=${depth}`);
        const data = await res.json();
        return toCamelCase(data);
    }
};

// ============================================================================
// Reward API - 真实后端接口
// ============================================================================

export const rewardApi = {
    // 获取所有奖励列表
    getRewards: async (): Promise<RewardItem[]> => {
        const res = await fetch(`${API_BASE}/rewards`);
        const data = await res.json();
        const result = toCamelCase(data);
        return result.items || [];
    },

    // 获取单个奖励详情
    getRewardDetail: async (id: number): Promise<RewardItem> => {
        const res = await fetch(`${API_BASE}/rewards/${id}`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 获取奖励统计数据（含历史累积数据）
    getRewardStats: async (id: number): Promise<RewardStatsResponse> => {
        const res = await fetch(`${API_BASE}/rewards/${id}/stats`);
        const data = await res.json();
        return toCamelCase(data);
    },

    // 创建奖励
    createReward: async (data: {
        goalId: string;
        name: string;
        startTime: string;
        targetHours?: number;
    }): Promise<RewardItem> => {
        const res = await fetch(`${API_BASE}/rewards`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 更新奖励
    updateReward: async (id: number, data: Partial<{
        goalId: string;
        name: string;
        startTime: string;
        targetHours: number;
    }>): Promise<RewardItem> => {
        const res = await fetch(`${API_BASE}/rewards/${id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(toSnakeCase(data))
        });
        const result = await res.json();
        return toCamelCase(result);
    },

    // 删除奖励
    deleteReward: async (id: number): Promise<boolean> => {
        const res = await fetch(`${API_BASE}/rewards/${id}`, { method: 'DELETE' });
        return res.ok;
    }
};

// ============================================================================
// Mock Data (保留用于其他组件)
// ============================================================================

export const COLORS = {
    WORK: '#5B8FF9',
    WORK_LIGHT: '#85A5FF',
    ENTERTAINMENT: '#FA8C16',
    ENTERTAINMENT_LIGHT: '#FFC069',
    OTHER: '#BFBFBF',
    OTHER_LIGHT: '#D9D9D9',
    UNTRACKED: '#E5E7EB'
};

// MOCK_GOALS_LIST 已弃用，使用 goalApi.getGoals() 替代
// 保留空数组导出以兼容其他组件（RewardTabView, TodoTabView），待后续迭代更新
export const MOCK_GOALS_LIST: UserGoal[] = [];

export const MOCK_TODOS: GoalItem[] = [
    {
        id: 't1',
        text: 'Setup project structure',
        completed: true,
        trackedTime: '1h',
        tag: 'Dev',
        date: '2025-12-01',
        linkToGoalId: 'g2',
        color: '#E0F2FE', // Light Blue
        startDate: '2025-12-01',
        endDate: '2025-12-01',
        subItems: [
            { id: 't1-1', text: 'Initialize Git repo', completed: true },
            { id: 't1-2', text: 'Install dependencies', completed: true },
            { id: 't1-3', text: 'Configure Tailwind', completed: false },
        ]
    },
    {
        id: 't2',
        text: 'Implement Auth',
        completed: false,
        trackedTime: '2h',
        tag: 'Dev',
        date: '2025-12-01',
        linkToGoalId: 'g2',
        color: '#FAE8FF', // Light Purple
        subItems: []
    },
    {
        id: 't3',
        text: 'Read React Docs',
        completed: true,
        trackedTime: '45m',
        tag: 'Study',
        date: '2025-12-02',
        linkToGoalId: 'g1',
        color: '#DCFCE7', // Light Green
        subItems: [
            { id: 't3-1', text: 'Read about Server Components', completed: true },
            { id: 't3-2', text: 'Try out useActionState', completed: false }
        ]
    },
    {
        id: 't4',
        text: 'Morning Meditation',
        completed: false,
        trackedTime: '15m',
        tag: 'Health',
        date: '2025-12-01',
        color: '#FEF3C7', // Light Amber
        subItems: []
    },
    {
        id: 't5',
        text: 'Call Accountant',
        completed: false,
        trackedTime: '10m',
        date: '2025-12-01',
        color: '#F3F4F6', // Grey
        subItems: []
    },
];

export const MOCK_PLANS: DailyPlan[] = [
    { id: 'p1', date: '2025-12-01', content: 'Focus on backend integration and API security.' },
    { id: 'p2', date: '2025-12-02', content: 'Design the UI components for the main dashboard.' },
];

export const MOCK_REWARDS: RewardRecord[] = [
    {
        goalId: 'g1',
        rewardContent: 'Buy a new mechanical keyboard',
        history: [
            { date: '11-20', timeSpent: 30, todoCount: 1 },
            { date: '11-21', timeSpent: 90, todoCount: 3 },
            { date: '11-22', timeSpent: 160, todoCount: 4 },
            { date: '11-23', timeSpent: 220, todoCount: 6 },
            { date: '11-24', timeSpent: 340, todoCount: 9 },
            { date: '11-25', timeSpent: 410, todoCount: 12 },
            { date: '11-26', timeSpent: 550, todoCount: 15 },
        ]
    }
];

export const MOCK_BEING: IdentityBeing[] = [
    { id: 'b1', content: 'I want to be a world-class engineer who builds products that help millions.' },
    { id: 'b2', content: 'I want to be physically fit and mentally resilient.' },
];

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

export const DRILLDOWN_DATA: Record<string, SubCategoryData> = {
    work: {
        title: 'Work Details',
        pieData: [
            { name: 'Coding', value: 300, color: COLORS.WORK, key: 'coding' },
            { name: 'Meetings', value: 100, color: COLORS.WORK_LIGHT, key: 'meeting' },
            { name: 'Research', value: 80, color: '#A5C5FF', key: 'research' },
        ],
        barKeys: [
            { key: 'coding', color: COLORS.WORK, label: 'Coding' },
            { key: 'meeting', color: COLORS.WORK_LIGHT, label: 'Meeting' },
            { key: 'research', color: '#A5C5FF', label: 'Research' }
        ],
        barData: [
            { timeRange: '0-2', coding: 0, meeting: 0, research: 0 },
            { timeRange: '2-4', coding: 0, meeting: 0, research: 0 },
            { timeRange: '4-6', coding: 0, meeting: 0, research: 0 },
            { timeRange: '6-8', coding: 30, meeting: 0, research: 0 },
            { timeRange: '8-10', coding: 60, meeting: 40, research: 0 },
            { timeRange: '10-12', coding: 80, meeting: 30, research: 0 },
            { timeRange: '12-14', coding: 0, meeting: 30, research: 0 },
            { timeRange: '14-16', coding: 100, meeting: 20, research: 0 },
            { timeRange: '16-18', coding: 30, meeting: 10, research: 60 },
            { timeRange: '18-20', coding: 0, meeting: 0, research: 20 },
            { timeRange: '20-22', coding: 0, meeting: 0, research: 0 },
            { timeRange: '22-24', coding: 0, meeting: 0, research: 0 },
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
            { name: 'Browsing', value: 40, color: COLORS.OTHER, key: 'browsing' },
            { name: 'Utilities', value: 80, color: COLORS.OTHER_LIGHT, key: 'utilities' },
        ],
        barKeys: [
            { key: 'browsing', color: COLORS.OTHER, label: 'Browsing' },
            { key: 'utilities', color: COLORS.OTHER_LIGHT, label: 'System' }
        ],
        barData: [
            { timeRange: '0-2', browsing: 30, utilities: 60 },
            { timeRange: '2-4', browsing: 0, utilities: 120 },
            { timeRange: '4-6', browsing: 0, utilities: 120 },
            { timeRange: '6-8', browsing: 30, utilities: 60 },
            { timeRange: '8-10', browsing: 10, utilities: 0 },
            { timeRange: '10-12', browsing: 5, utilities: 0 },
            { timeRange: '12-14', browsing: 10, utilities: 20 },
            { timeRange: '14-16', browsing: 0, utilities: 0 },
            { timeRange: '16-18', browsing: 10, utilities: 0 },
            { timeRange: '18-20', browsing: 10, utilities: 10 },
            { timeRange: '20-22', browsing: 10, utilities: 10 },
            { timeRange: '22-24', browsing: 0, utilities: 60 },
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
    { id: '1', title: 'Deep Sleep', startTime: 0, endTime: 7, category: 'other', subCategoryId: 'utilities', description: 'Restorative sleep' },
    { id: '2', title: 'Morning Routine', startTime: 7, endTime: 8.5, category: 'other', subCategoryId: 'utilities', description: 'Breakfast, Shower' },
    { id: '3', title: 'Commute', startTime: 8.5, endTime: 9, category: 'other', subCategoryId: 'browsing', description: 'Listening to podcast' },
    { id: '4', title: 'Standup Meeting', startTime: 9, endTime: 9.5, category: 'work', subCategoryId: 'meeting', linkedGoal: '2', description: 'Daily sync with engineering team' },
    { id: '5', title: 'Dashboard Development', startTime: 9.5, endTime: 12, category: 'work', subCategoryId: 'coding', linkedGoal: '1', description: 'Implementing React components' },
    { id: '6', title: 'Lunch Break', startTime: 12, endTime: 13, category: 'entertainment', subCategoryId: 'video', description: 'Youtube & Lunch' },
    { id: '7', title: 'Code Review', startTime: 13, endTime: 14.5, category: 'work', subCategoryId: 'coding', linkedGoal: '2', description: 'Reviewing PRs #342 and #345' },
    { id: '8', title: 'Deep Focus: Backend', startTime: 14.5, endTime: 17, category: 'work', subCategoryId: 'coding', linkedGoal: '1', description: 'API integration' },
    { id: '9', title: 'Break / Social', startTime: 17, endTime: 17.5, category: 'other', subCategoryId: 'browsing', description: 'Coffee chat' },
    { id: '10', title: 'Wrap up', startTime: 17.5, endTime: 18, category: 'work', subCategoryId: 'planning', description: 'Planning for tomorrow' },
    { id: '11', title: 'Gym', startTime: 18.5, endTime: 20, category: 'other', subCategoryId: 'utilities', linkedGoal: '4', description: 'Upper body workout' },
    { id: '12', title: 'Gaming', startTime: 20.5, endTime: 22.5, category: 'entertainment', subCategoryId: 'games', description: 'Cyberpunk 2077' },
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

export const MOCK_USAGE_HISTORY: TokenUsage[] = [
    { date: '11-25', inputTokens: 4200, outputTokens: 1500, processedRecords: 120 },
    { date: '11-26', inputTokens: 5100, outputTokens: 2100, processedRecords: 155 },
    { date: '11-27', inputTokens: 3800, outputTokens: 1100, processedRecords: 95 },
    { date: '11-28', inputTokens: 6200, outputTokens: 2800, processedRecords: 190 },
    { date: '11-29', inputTokens: 4900, outputTokens: 1800, processedRecords: 140 },
    { date: '11-30', inputTokens: 7500, outputTokens: 3200, processedRecords: 210 },
    { date: '12-01', inputTokens: 5800, outputTokens: 2400, processedRecords: 168 },
];