/**
 * Reports Page API
 * 
 * 报告统计相关接口
 */

import { DailyReportData, ReportResponse, DateRangeType } from './types';

const API_BASE = 'http://localhost:8000/api/v2';

/**
 * Daily Report API 响应类型（后端返回格式）
 */
interface DailyReportAPIResponse {
    date: string;
    sunburst_data: {
        title: string;
        sub_title: string;
        total_tracked_minutes: number;
        total_range_minutes?: number;
        pie_data: Array<{
            key: string;
            name: string;
            value: number;
            color: string;
            title?: string;
        }>;
        details?: Record<string, any>;
    } | null;
    todo_data: {
        total: number;
        completed: number;
        pending: number;
        procrastination_rate: number;
    } | null;
    goal_data: Array<{
        goal_id: string;
        goal_name: string;
        goal_color: string;
        time_invested: number;
        todo_total: number;
        todo_completed: number;
        todo_list: Array<{
            id: number;
            content: string;
            completed: boolean;
        }>;
    }> | null;
    daily_trend_data: Array<Record<string, any>> | null;
    state: string;
    data_version: number;
}

/**
 * 将后端响应转换为前端格式
 */
function transformDailyReportResponse(response: DailyReportAPIResponse): DailyReportData {
    // 获取分类配置（从 pie_data 提取）
    // 注意：key 使用 name，因为 daily_trend_data 中的数据直接用分类名称作为 key
    const categories = response.sunburst_data?.pie_data?.map(item => ({
        key: item.name,  // 使用分类名称作为 key，与 daily_trend_data 的字段名对应
        name: item.name,
        color: item.color,
    })) || [];

    // 转换时间分布数据（24小时趋势）
    const timeDistribution = response.daily_trend_data?.map(point => {
        const result: Record<string, any> = { label: point.label };
        // 复制所有分类数据
        for (const key of Object.keys(point)) {
            if (key !== 'label') {
                result[key] = point[key];
            }
        }
        return result;
    }) || [];

    // 转换旭日图数据
    const timeOverview = response.sunburst_data ? {
        title: response.sunburst_data.title,
        subTitle: response.sunburst_data.sub_title,
        totalTrackedMinutes: response.sunburst_data.total_tracked_minutes,
        totalRangeMinutes: response.sunburst_data.total_range_minutes,
        pieData: response.sunburst_data.pie_data.map(item => ({
            key: item.key,
            name: item.name,
            value: item.value,
            color: item.color,
            title: item.title,
        })),
        barData: [], // 无柱状图
        details: undefined,
    } : {
        title: '今日时间分布',
        subTitle: '暂无数据',
        totalTrackedMinutes: 0,
        pieData: [],
        barData: [],
    };

    // 转换 Goal 进度数据
    const goalProgress = response.goal_data?.map(goal => ({
        goalId: goal.goal_id,
        goalName: goal.goal_name,
        goalColor: goal.goal_color,
        timeInvested: goal.time_invested,
        todoTotal: goal.todo_total,
        todoCompleted: goal.todo_completed,
        todoList: goal.todo_list,
    })) || [];

    // 转换 Todo 统计
    const todoStats = response.todo_data || {
        total: 0,
        completed: 0,
        pending: 0,
        procrastinationRate: 0,
    };

    return {
        date: response.date,
        timeDistribution,
        categories,
        timeOverview,
        goalProgress,
        todoStats: {
            total: todoStats.total,
            completed: todoStats.completed,
            pending: todoStats.pending,
            procrastinationRate: todoStats.procrastination_rate,
        },
        aiSummary: '', // 目前后端没有返回 AI 总结
    };
}

/**
 * Reports API
 */
export const ReportsAPI = {
    /**
     * 获取日报告
     */
    async getDailyReport(date: string, forceRefresh: boolean = false): Promise<DailyReportData> {
        const params = new URLSearchParams({
            date,
            force_refresh: String(forceRefresh),
        });

        const response = await fetch(`${API_BASE}/report/daily?${params}`);

        if (!response.ok) {
            throw new Error(`获取日报告失败: ${response.statusText}`);
        }

        const data: DailyReportAPIResponse = await response.json();
        return transformDailyReportResponse(data);
    },

    /**
     * 删除日报告缓存
     */
    async deleteDailyReport(date: string): Promise<void> {
        const response = await fetch(`${API_BASE}/report/daily/${date}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`删除日报告失败: ${response.statusText}`);
        }
    },

    /**
     * 获取已完成的报告日期列表
     */
    async getCompletedReportDates(startDate: string, endDate: string): Promise<string[]> {
        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate,
        });

        const response = await fetch(`${API_BASE}/report/daily/completed-dates?${params}`);

        if (!response.ok) {
            throw new Error(`获取已完成报告日期失败: ${response.statusText}`);
        }

        const data = await response.json();
        return data.dates || [];
    },

    /**
     * 获取报告数据（旧接口，保留兼容）
     */
    async getReport(params: {
        type: DateRangeType;
        startDate?: string;
        endDate?: string;
    }): Promise<ReportResponse> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },

    /**
     * 导出报告
     */
    async exportReport(params: {
        type: DateRangeType;
        format: 'pdf' | 'csv' | 'json';
        startDate?: string;
        endDate?: string;
    }): Promise<Blob> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },
};
