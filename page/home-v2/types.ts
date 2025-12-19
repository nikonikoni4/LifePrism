/**
 * Home V2 Types
 * 
 * TypeScript 类型定义，对应后端 activity_v2_schemas.py
 */

// ============================================================================
// Activity Summary 相关类型
// ============================================================================

/** 每日活动数据项 */
export interface DailyActivityV2 {
    date: string;  // YYYY-MM-DD
    duration: number;  // 活动时长（秒）
    activeTimePercentage: number;  // 活动时长占比（%）
    color: string;  // 分类颜色
}

/** Activity Summary 响应数据 */
export interface ActivitySummaryDataV2 {
    dailyActivities: DailyActivityV2[];
}

// ============================================================================
// Time Overview 相关类型
// ============================================================================

/** 饼图/旭日图数据项 */
export interface ChartSegmentV2 {
    key: string;  // 分类唯一标识符
    name: string;  // 显示名称
    value: number;  // 时长（分钟）
    color: string;  // 颜色
    title?: string;  // app层的标题显示
}

/** 柱状图配置项 */
export interface BarConfigV2 {
    key: string;  // 数据键
    label: string;  // 图例标签
    color: string;  // 颜色
}

/** Time Overview 完整数据 */
export interface TimeOverviewDataV2 {
    title: string;
    subTitle: string;
    totalTrackedMinutes: number;
    pieData: ChartSegmentV2[];
    barKeys: BarConfigV2[];
    barData: Array<Record<string, any>>;  // 24小时分布数据
    details?: Record<string, TimeOverviewDataV2>;  // 子分类详情（递归结构）
}

// ============================================================================
// Top Title / Top App 相关类型
// ============================================================================

/** 热门标题数据 */
export interface TopTitleDataV2 {
    name: string;  // 窗口标题
    duration: number;  // 活跃时长（秒）
}

/** 热门应用数据 */
export interface TopAppDataV2 {
    name: string;  // 应用名称
    duration: number;  // 活跃时长（秒）
}

// ============================================================================
// TodoList 相关类型
// ============================================================================

/** 待办事项数据 */
export interface TodoListDataV2 {
    name: string;  // 待办事项名称
    isCompleted: boolean;  // 是否完成
}

// ============================================================================
// API 响应类型
// ============================================================================

/** GET /api/v2/activity/stats 响应 */
export interface ActivityStatsResponseV2 {
    activity_summary?: ActivitySummaryDataV2;
    time_overview?: TimeOverviewDataV2;
    top_title?: TopTitleDataV2[];
    top_app?: TopAppDataV2[];
    todolist?: TodoListDataV2[];
    query?: Record<string, any>;  // 查询参数回显
}

// ============================================================================
// 请求参数类型
// ============================================================================

/** 活动统计请求参数 */
export interface ActivityStatsParamsV2 {
    date: string;  // YYYY-MM-DD
    include?: string;  // 逗号分隔的模块列表
    history_number?: number;
    future_number?: number;
    category_id?: string;
    sub_category_id?: string;
}

// ============================================================================
// 分类相关类型（用于筛选器）
// ============================================================================

/** 子分类定义 */
export interface SubCategoryDefV2 {
    id: string;
    name: string;
    color?: string;
}

/** 分类定义 */
export interface CategoryDefV2 {
    id: string;
    name: string;
    color: string;
    subCategories?: SubCategoryDefV2[];
}
