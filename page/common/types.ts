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
    pieData: ChartSegment[];
    barKeys: BarConfig[];
    barData: Array<Record<string, any>>;
    details?: Record<string, TimeOverviewData>;
}
