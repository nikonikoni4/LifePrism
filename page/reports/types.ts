/**
 * Reports Page Types
 * 
 * 报告统计相关类型定义
 */


// ============================================================================
// Common Types
// ============================================================================

/** 时间范围类型 */
export type DateRangeType = 'day' | 'week' | 'month' | 'year' | 'custom';

/** 报告 Tab 类型 */
export type ReportTabType = 'daily' | 'weekly' | 'monthly';

/** 时间分布折线图数据点 */
export interface TimeDistributionPoint {
    /** 时间标签 (e.g., "0", "6", "12" for daily; "Mon", "Tue" for weekly) */
    label: string;
    /** 各分类的时间数据 (分钟) */
    [categoryKey: string]: string | number;
}

/** 分类配置 */
export interface CategoryConfig {
    key: string;
    name: string;
    color: string;
}

/** Goal 进度数据 */
export interface GoalProgressData {
    goalId: string;
    goalName: string;
    goalColor: string;
    timeInvested: number;  // 分钟
    todoTotal: number;
    todoCompleted: number;
    todoList: Array<{
        id: number;
        content: string;
        completed: boolean;
    }>;
}

/** Todo 统计数据 */
export interface TodoStatsData {
    total: number;
    completed: number;
    pending: number;
    procrastinationRate: number;
}

/** 热力图单日数据 */
export interface HeatmapDay {
    date: string;  // YYYY-MM-DD
    value: number;  // 活跃时长 (分钟)
    categoryBreakdown?: Record<string, number>;
}

/** 月度 Todo 追踪 */
export interface MonthlyTodoTracking {
    completionRate: number;
    totalCompleted: number;
    totalPending: number;
    carryOverItems: Array<{
        id: number;
        content: string;
        goalName?: string;
    }>;
}

// ============================================================================
// Daily Review Types
// ============================================================================

export interface DailyReportData {
    date: string;
    /** 0-24h 时间分布折线图数据 */
    timeDistribution: TimeDistributionPoint[];
    /** 时间分布的分类配置 */
    categories: CategoryConfig[];
    /** 旭日图数据 */
    timeOverview: TimeOverviewData;
    /** Goal 进度 */
    goalProgress: GoalProgressData[];
    /** Todo 统计 */
    todoStats: TodoStatsData;
    /** AI 智能总结 */
    aiSummary: string;
}

// ============================================================================
// Weekly Review Types
// ============================================================================

export interface WeeklyReportData {
    startDate: string;
    endDate: string;
    /** 周一至周日趋势数据 */
    weeklyTrend: TimeDistributionPoint[];
    /** 趋势图的分类配置 */
    categories: CategoryConfig[];
    /** 周度旭日图 */
    timeOverview: TimeOverviewData;
    /** 周度 Goal 进度 */
    goalProgress: GoalProgressData[];
    /** Todo 统计数据 */
    todoStats: TodoStatsData;
    /** AI 规律总结 */
    aiSummary: string;
}

// ============================================================================
// Monthly Review Types
// ============================================================================

export interface MonthlyReportData {
    month: string;  // YYYY-MM
    /** 热力图数据 */
    heatmapData: HeatmapDay[];
    /** 热力图分类选择器 */
    categories: CategoryConfig[];
    /** 月度旭日图 */
    timeOverview: TimeOverviewData;
    /** 月度 Goal 投入 */
    goalProgress: GoalProgressData[];
    /** 月度 Todo 追踪 */
    todoStats: TodoStatsData;
    /** 需滚动事项 (保留原始追踪结构中的事项) */
    carryOverItems: Array<{
        id: number;
        content: string;
        goalName?: string;
    }>;
    /** AI 全局总结 */
    aiSummary: string;
}

// ============================================================================
// Legacy Types (保留兼容)
// ============================================================================

/** 报告数据项 */
export interface ReportDataPoint {
    date: string;
    totalMinutes: number;
    categoryBreakdown: Record<string, number>;
}

/** 趋势数据 */
export interface TrendData {
    current: number;
    previous: number;
    changePercent: number;
    trend: 'up' | 'down' | 'stable';
}

/** 报告响应 */
export interface ReportResponse {
    dateRange: {
        start: string;
        end: string;
        type: DateRangeType;
    };
    summary: {
        totalMinutes: number;
        averageMinutesPerDay: number;
        mostProductiveDay: string;
        topCategory: string;
    };
    dailyData: ReportDataPoint[];
    trends: {
        productivity: TrendData;
        focusTime: TrendData;
    };
}

/** 饼图/旭日图数据项 */
export interface ChartSegment {
    key: string;
    name: string;
    value: number;
    color: string;
    title?: string;  // app层的标题显示
}

/** Time Overview 完整数据 (递归结构) */
export interface TimeOverviewData {
    title: string;
    subTitle: string;
    totalTrackedMinutes: number;
    totalRangeMinutes?: number;  // 时间范围总分钟数（用于计算百分比的分母）
    pieData: ChartSegment[];
    barData: Array<Record<string, any>>;
    details?: Record<string, TimeOverviewData>;
}

