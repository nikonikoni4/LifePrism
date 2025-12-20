/**
 * Common Types for Shared Components
 * 
 * 共享组件的类型定义
 */

// ============================================================================
// Time Overview 相关类型
// ============================================================================

/** 饼图/旭日图数据项 */
export interface ChartSegment {
    key: string;
    name: string;
    value: number;
    color: string;
    title?: string;  // app层的标题显示
}

/** 柱状图配置项 */
export interface BarConfig {
    key: string;
    label: string;
    color: string;
}

/** Time Overview 完整数据 (递归结构) */
export interface TimeOverviewData {
    title: string;
    subTitle: string;
    totalTrackedMinutes: number;
    totalRangeMinutes?: number;  // 时间范围总分钟数（用于计算百分比的分母）
    pieData: ChartSegment[];
    barKeys: BarConfig[];
    barData: Array<Record<string, any>>;
    details?: Record<string, TimeOverviewData>;
}

// ============================================================================
// Category 相关类型（树形结构）
// ============================================================================

/** 子分类树节点 */
export interface SubCategoryTreeItem {
    id: string;
    name: string;
    color: string;
}

/** 主分类树节点 */
export interface CategoryTreeItem {
    id: string;
    name: string;
    color: string;
    subcategories?: SubCategoryTreeItem[];
}

/** GET /category/tree 响应 */
export interface CategoryTreeResponse {
    data: CategoryTreeItem[];
}

// ============================================================================
// Activity Log 相关类型（日志列表）
// ============================================================================

/** 活动日志条目 */
export interface ActivityLogItem {
    id: string;
    start_time: string;
    end_time: string;
    app: string;
    title: string;
    duration: number;  // 秒
    category_id?: string;
    sub_category_id?: string;
    category?: string;
    sub_category?: string;
    app_description?: string;
    title_analysis?: string;
}

/** GET /activity/logs 响应 */
export interface ActivityLogsResponse {
    data: ActivityLogItem[];
    total: number;
    page: number;
    page_size: number;
}

/** 活动日志请求参数 */
export interface ActivityLogsParams {
    start_time: string;  // YYYY-MM-DD HH:MM:SS
    end_time: string;    // YYYY-MM-DD HH:MM:SS
    device_filter?: 'all' | 'pc' | 'mobile';
    category_id?: string;
    sub_category_id?: string;
    sort_by?: 'duration' | 'start_time' | 'app';
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
}
