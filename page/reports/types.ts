/**
 * Reports Page Types
 * 
 * 报告统计相关类型定义
 */

/** 时间范围类型 */
export type DateRangeType = 'day' | 'week' | 'month' | 'year' | 'custom';

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
