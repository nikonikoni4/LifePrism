/**
 * Home Types
 * 
 * TypeScript 类型定义，对应后端 activity_schemas.py
 */

// ============================================================================
// Activity Summary 相关类型
// ============================================================================

/** 每日活动数据项 */
export interface DailyActivity {
    date: string;  // YYYY-MM-DD
    duration: number;  // 活动时长（秒）
    activeTimePercentage: number;  // 活动时长占比（%）
    color: string;  // 分类颜色
}

/** Activity Summary 响应数据 */
export interface ActivitySummaryData {
    dailyActivities: DailyActivity[];
}

// ============================================================================
// Time Overview 相关类型
// ============================================================================

/** 饼图/旭日图数据项 */
export interface ChartSegment {
    key: string;  // 分类唯一标识符
    name: string;  // 显示名称
    value: number;  // 时长（分钟）
    color: string;  // 颜色
    title?: string;  // app层的标题显示
}

/** 柱状图配置项 */
export interface BarConfig {
    key: string;  // 数据键
    label: string;  // 图例标签
    color: string;  // 颜色
}

/** Time Overview 完整数据 */
export interface TimeOverviewData {
    title: string;
    subTitle: string;
    totalTrackedMinutes: number;
    totalRangeMinutes?: number;  // 时间范围总分钟数（用于计算百分比的分母）
    pieData: ChartSegment[];
    barKeys: BarConfig[];
    barData: Array<Record<string, any>>;  // 时间分布数据
    details?: Record<string, TimeOverviewData>;  // 子分类详情（递归结构）
}

// ============================================================================
// Top Title / Top App 相关类型
// ============================================================================

/** 热门标题数据 */
export interface TopTitleData {
    name: string;  // 窗口标题
    duration: number;  // 活跃时长（秒）
    percentage: number;  // 活跃时长占比（%）
}

/** 热门应用数据 */
export interface TopAppData {
    name: string;  // 应用名称
    duration: number;  // 活跃时长（秒）
    percentage: number;  // 活跃时长占比（%）
}

// ============================================================================
// TodoList 相关类型
// ============================================================================

/** 待办事项数据 */
export interface TodoListData {
    id: number;
    name: string;  // 待办事项名称
    isCompleted: boolean;  // 是否完成
    linkToGoal: number;  // 关联目标ID
}

// ============================================================================
// API 响应类型
// ============================================================================

/** GET /api/v2/activity/stats 响应 */
export interface ActivityStatsResponse {
    activity_summary?: ActivitySummaryData;
    time_overview?: TimeOverviewData;
    top_title?: TopTitleData[];
    top_app?: TopAppData[];
    todolist?: TodoListData[];
    query?: Record<string, any>;  // 查询参数回显
}

// ============================================================================
// 请求参数类型
// ============================================================================

/** 活动统计请求参数 */
export interface ActivityStatsParams {
    date: string;  // YYYY-MM-DD
    include?: string;  // 逗号分隔的模块列表
    history_number?: number;
    future_number?: number;
    category_id?: string;
    sub_category_id?: string;
}

// ============================================================================
// 分类相关类型（从 common 重新导出）
// ============================================================================

export type { CategoryTreeItem, SubCategoryTreeItem } from '../common/types';
