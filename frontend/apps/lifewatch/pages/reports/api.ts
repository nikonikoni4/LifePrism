/**
 * Reports Page API
 * 
 * 报告统计相关接口
 */

import { DailyReportData, WeeklyReportData, MonthlyReportData, ReportResponse, DateRangeType, ComparisonData, TimeDistributionPoint } from './types';
import { ReportCacheService } from '../../../../core/services/reportCacheService';
import { createApiV2UrlGetter } from '../../../../core/services/apiConfig';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiBase = createApiV2UrlGetter();

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
            id: string;
            content: string;
            completed: boolean;
        }>;
    }> | null;
    daily_trend_data: Array<Record<string, any>> | null;
    comparison_data: {
        current_start: string;
        current_end: string;
        previous_start: string;
        previous_end: string;
        category_comparison: Array<{
            category_id: string;
            category_name: string;
            current_duration: number;
            previous_duration: number;
            change_seconds: number;
            change_percentage?: number | null;
            children?: Array<{
                category_id: string;
                category_name: string;
                current_duration: number;
                previous_duration: number;
                change_seconds: number;
                change_percentage?: number | null;
            }>;
        }>;
        goal_comparison: Array<{
            goal_id: string;
            goal_name: string;
            current_duration: number;
            previous_duration: number;
            change_seconds: number;
        }>;
    } | null;
    ai_summary: string | null;
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
    const timeDistribution: TimeDistributionPoint[] = response.daily_trend_data?.map(point => {
        const result: Record<string, any> = { label: point.label };
        // 复制所有分类数据
        for (const key of Object.keys(point)) {
            if (key !== 'label') {
                result[key] = point[key];
            }
        }
        return result as TimeDistributionPoint;
    }) || [];

    // 递归转换旭日图数据的 details
    const transformSunburstDetails = (details: Record<string, any> | undefined): Record<string, any> | undefined => {
        if (!details) return undefined;
        const result: Record<string, any> = {};
        for (const [key, value] of Object.entries(details)) {
            result[key] = {
                title: value.title,
                subTitle: value.sub_title,
                totalTrackedMinutes: value.total_tracked_minutes,
                totalRangeMinutes: value.total_range_minutes,
                pieData: value.pie_data?.map((item: any) => ({
                    key: item.key,
                    name: item.name,
                    value: item.value,
                    color: item.color,
                    title: item.title,
                })) || [],
                barData: [],
                details: transformSunburstDetails(value.details),
            };
        }
        return result;
    };

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
        barData: [],
        details: transformSunburstDetails(response.sunburst_data.details),
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
        procrastination_rate: 0,
    };

    // 转换环比对比数据
    const comparisonData: ComparisonData | undefined = response.comparison_data ? {
        currentStart: response.comparison_data.current_start,
        currentEnd: response.comparison_data.current_end,
        previousStart: response.comparison_data.previous_start,
        previousEnd: response.comparison_data.previous_end,
        categoryComparison: response.comparison_data.category_comparison.map(cat => ({
            categoryId: cat.category_id,
            categoryName: cat.category_name,
            currentDuration: cat.current_duration,
            previousDuration: cat.previous_duration,
            changeSeconds: cat.change_seconds,
            changePercentage: cat.change_percentage ?? null,
            children: cat.children?.map(child => ({
                categoryId: child.category_id,
                categoryName: child.category_name,
                currentDuration: child.current_duration,
                previousDuration: child.previous_duration,
                changeSeconds: child.change_seconds,
                changePercentage: child.change_percentage ?? null,
            })),
        })),
        goalComparison: response.comparison_data.goal_comparison.map(goal => ({
            goalId: goal.goal_id,
            goalName: goal.goal_name,
            currentDuration: goal.current_duration,
            previousDuration: goal.previous_duration,
            changeSeconds: goal.change_seconds,
        })),
    } : undefined;

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
        comparisonData,
        aiSummary: response.ai_summary || '',
    };
}

/**
 * Weekly Report API 响应类型（后端返回格式）
 */
interface WeeklyReportAPIResponse {
    week_start_date: string;
    week_end_date: string;
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
            id: string;
            content: string;
            completed: boolean;
        }>;
    }> | null;
    daily_trend_data: Array<Record<string, any>> | null;
    comparison_data: {
        current_start: string;
        current_end: string;
        previous_start: string;
        previous_end: string;
        category_comparison: Array<{
            category_id: string;
            category_name: string;
            current_duration: number;
            previous_duration: number;
            change_seconds: number;
            change_percentage?: number | null;
            children?: Array<{
                category_id: string;
                category_name: string;
                current_duration: number;
                previous_duration: number;
                change_seconds: number;
                change_percentage?: number | null;
            }>;
        }>;
        goal_comparison: Array<{
            goal_id: string;
            goal_name: string;
            current_duration: number;
            previous_duration: number;
            change_seconds: number;
        }>;
    } | null;
    ai_summary: string | null;
    state: string;
    data_version: number;
}

/**
 * 将后端周报告响应转换为前端格式
 */
function transformWeeklyReportResponse(response: WeeklyReportAPIResponse): WeeklyReportData {
    // 获取分类配置（从 pie_data 提取）
    const categories = response.sunburst_data?.pie_data?.map(item => ({
        key: item.name,
        name: item.name,
        color: item.color,
    })) || [];

    // 转换周趋势数据（7天每天的分布）
    const weeklyTrend: TimeDistributionPoint[] = response.daily_trend_data?.map(point => {
        const result: Record<string, any> = {
            label: point.label,
            date: point.date  // 保留日期字段用于图表点击导航
        };
        for (const key of Object.keys(point)) {
            if (key !== 'label' && key !== 'date') {
                result[key] = point[key];
            }
        }
        return result as TimeDistributionPoint;
    }) || [];

    // 递归转换旭日图数据的 details
    const transformSunburstDetails = (details: Record<string, any> | undefined): Record<string, any> | undefined => {
        if (!details) return undefined;
        const result: Record<string, any> = {};
        for (const [key, value] of Object.entries(details)) {
            result[key] = {
                title: value.title,
                subTitle: value.sub_title,
                totalTrackedMinutes: value.total_tracked_minutes,
                totalRangeMinutes: value.total_range_minutes,
                pieData: value.pie_data?.map((item: any) => ({
                    key: item.key,
                    name: item.name,
                    value: item.value,
                    color: item.color,
                    title: item.title,
                })) || [],
                barData: [],
                details: transformSunburstDetails(value.details),
            };
        }
        return result;
    };

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
        barData: [],
        details: transformSunburstDetails(response.sunburst_data.details),
    } : {
        title: '本周时间分布',
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
        procrastination_rate: 0,
    };

    // 转换环比对比数据
    const comparisonData: ComparisonData | undefined = response.comparison_data ? {
        currentStart: response.comparison_data.current_start,
        currentEnd: response.comparison_data.current_end,
        previousStart: response.comparison_data.previous_start,
        previousEnd: response.comparison_data.previous_end,
        categoryComparison: response.comparison_data.category_comparison.map(cat => ({
            categoryId: cat.category_id,
            categoryName: cat.category_name,
            currentDuration: cat.current_duration,
            previousDuration: cat.previous_duration,
            changeSeconds: cat.change_seconds,
            changePercentage: cat.change_percentage ?? null,
            children: cat.children?.map(child => ({
                categoryId: child.category_id,
                categoryName: child.category_name,
                currentDuration: child.current_duration,
                previousDuration: child.previous_duration,
                changeSeconds: child.change_seconds,
                changePercentage: child.change_percentage ?? null,
            })),
        })),
        goalComparison: response.comparison_data.goal_comparison.map(goal => ({
            goalId: goal.goal_id,
            goalName: goal.goal_name,
            currentDuration: goal.current_duration,
            previousDuration: goal.previous_duration,
            changeSeconds: goal.change_seconds,
        })),
    } : undefined;

    return {
        startDate: response.week_start_date,
        endDate: response.week_end_date,
        weeklyTrend,
        categories,
        timeOverview,
        goalProgress,
        todoStats: {
            total: todoStats.total,
            completed: todoStats.completed,
            pending: todoStats.pending,
            procrastinationRate: todoStats.procrastination_rate,
        },
        comparisonData,
        aiSummary: response.ai_summary || '',
    };
}

/**
 * Monthly Report API 响应类型（后端返回格式）
 */
interface MonthlyReportAPIResponse {
    month_start_date: string;
    month_end_date: string;
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
            id: string;
            content: string;
            completed: boolean;
        }>;
    }> | null;
    daily_trend_data: Array<Record<string, any>> | null;
    heatmap_data: Array<{
        date: string;
        total_minutes: number;
        category_breakdown?: Record<string, number>;
    }> | null;
    comparison_data: {
        current_start: string;
        current_end: string;
        previous_start: string;
        previous_end: string;
        category_comparison: Array<{
            category_id: string;
            category_name: string;
            current_duration: number;
            previous_duration: number;
            change_seconds: number;
            change_percentage?: number | null;
            children?: Array<{
                category_id: string;
                category_name: string;
                current_duration: number;
                previous_duration: number;
                change_seconds: number;
                change_percentage?: number | null;
            }>;
        }>;
        goal_comparison: Array<{
            goal_id: string;
            goal_name: string;
            current_duration: number;
            previous_duration: number;
            change_seconds: number;
        }>;
    } | null;
    ai_summary: string | null;
    state: string;
    data_version: number;
}

/**
 * 将后端月报告响应转换为前端格式
 */
function transformMonthlyReportResponse(response: MonthlyReportAPIResponse): MonthlyReportData {
    // 获取分类配置（从 pie_data 提取）
    const categories = response.sunburst_data?.pie_data?.map(item => ({
        key: item.name,
        name: item.name,
        color: item.color,
    })) || [];

    // 递归转换旭日图数据的 details
    const transformSunburstDetails = (details: Record<string, any> | undefined): Record<string, any> | undefined => {
        if (!details) return undefined;
        const result: Record<string, any> = {};
        for (const [key, value] of Object.entries(details)) {
            result[key] = {
                title: value.title,
                subTitle: value.sub_title,
                totalTrackedMinutes: value.total_tracked_minutes,
                totalRangeMinutes: value.total_range_minutes,
                pieData: value.pie_data?.map((item: any) => ({
                    key: item.key,
                    name: item.name,
                    value: item.value,
                    color: item.color,
                    title: item.title,
                })) || [],
                barData: [],
                details: transformSunburstDetails(value.details),
            };
        }
        return result;
    };

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
        barData: [],
        details: transformSunburstDetails(response.sunburst_data.details),
    } : {
        title: '本月时间分布',
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
        procrastination_rate: 0,
    };

    // 转换热力图数据
    const heatmapData = response.heatmap_data?.map(item => ({
        date: item.date,
        value: item.total_minutes,
        categoryBreakdown: item.category_breakdown,
    })) || [];

    // 转换月度趋势数据（用于折线图）
    const monthlyTrend: TimeDistributionPoint[] = response.daily_trend_data?.map(point => {
        const result: Record<string, any> = {
            label: point.label,
            date: point.date  // 保留日期字段用于图表点击导航
        };
        for (const key of Object.keys(point)) {
            if (key !== 'label' && key !== 'date') {
                result[key] = point[key];
            }
        }
        return result as TimeDistributionPoint;
    }) || [];

    // 从 month_start_date 提取 YYYY-MM 格式的月份
    const month = response.month_start_date.substring(0, 7);

    // 转换环比对比数据
    const comparisonData: ComparisonData | undefined = response.comparison_data ? {
        currentStart: response.comparison_data.current_start,
        currentEnd: response.comparison_data.current_end,
        previousStart: response.comparison_data.previous_start,
        previousEnd: response.comparison_data.previous_end,
        categoryComparison: response.comparison_data.category_comparison.map(cat => ({
            categoryId: cat.category_id,
            categoryName: cat.category_name,
            currentDuration: cat.current_duration,
            previousDuration: cat.previous_duration,
            changeSeconds: cat.change_seconds,
            changePercentage: cat.change_percentage ?? null,
            children: cat.children?.map(child => ({
                categoryId: child.category_id,
                categoryName: child.category_name,
                currentDuration: child.current_duration,
                previousDuration: child.previous_duration,
                changeSeconds: child.change_seconds,
                changePercentage: child.change_percentage ?? null,
            })),
        })),
        goalComparison: response.comparison_data.goal_comparison.map(goal => ({
            goalId: goal.goal_id,
            goalName: goal.goal_name,
            currentDuration: goal.current_duration,
            previousDuration: goal.previous_duration,
            changeSeconds: goal.change_seconds,
        })),
    } : undefined;

    return {
        month,
        monthlyTrend,
        heatmapData,
        categories,
        timeOverview,
        goalProgress,
        todoStats: {
            total: todoStats.total,
            completed: todoStats.completed,
            pending: todoStats.pending,
            procrastinationRate: todoStats.procrastination_rate,
        },
        carryOverItems: [], // 后端暂无此数据
        comparisonData,
        aiSummary: response.ai_summary || '',
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
        // 如果不是强制刷新,先尝试从缓存获取
        if (!forceRefresh) {
            const cachedData = ReportCacheService.getDailyReport(date);
            // 只有当缓存存在且包含 AI 总结时才使用缓存
            // 如果缓存没有 AI 总结，则从后端获取完整数据（后端可能已有 AI 总结）
            if (cachedData && cachedData.aiSummary) {
                console.log(`[API] 从缓存加载日报告: ${date}`);
                return cachedData;
            }
            // 如果缓存存在但没有 AI 总结，记录日志并继续从后端获取
            if (cachedData) {
                console.log(`[API] 缓存中的日报告缺少 AI 总结，从后端同步: ${date}`);
            }
        }

        // 缓存未命中或强制刷新或缓存缺少 AI 总结,调用 API
        console.log(`[API] 从服务器加载日报告: ${date}`);
        const params = new URLSearchParams({
            date,
            force_refresh: String(forceRefresh),
        });

        const response = await fetch(`${getApiBase()}/report/daily?${params}`);

        if (!response.ok) {
            throw new Error(`获取日报告失败: ${response.statusText}`);
        }

        const data: DailyReportAPIResponse = await response.json();
        const transformedData = transformDailyReportResponse(data);

        // 缓存结果
        ReportCacheService.cacheDailyReport(date, transformedData);
        console.log(`[API] 已缓存日报告: ${date}`);

        return transformedData;
    },

    /**
     * 删除日报告缓存
     */
    async deleteDailyReport(date: string): Promise<void> {
        const response = await fetch(`${getApiBase()}/report/daily/${date}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`删除日报告失败: ${response.statusText}`);
        }

        // 同时删除本地缓存
        ReportCacheService.removeDailyReport(date);
        console.log(`[API] 已删除日报告缓存: ${date}`);
    },

    /**
     * 获取已完成的报告日期列表
     */
    async getCompletedReportDates(startDate: string, endDate: string): Promise<string[]> {
        const params = new URLSearchParams({
            start_date: startDate,
            end_date: endDate,
        });

        const response = await fetch(`${getApiBase()}/report/daily/completed-dates?${params}`);

        if (!response.ok) {
            throw new Error(`获取已完成报告日期失败: ${response.statusText}`);
        }

        const data = await response.json();
        return data.dates || [];
    },

    /**
     * 获取周报告
     */
    async getWeeklyReport(weekStartDate: string, forceRefresh: boolean = false): Promise<WeeklyReportData> {
        // 如果不是强制刷新,先尝试从缓存获取
        if (!forceRefresh) {
            const cachedData = ReportCacheService.getWeeklyReport(weekStartDate);
            // 只有当缓存存在且包含 AI 总结时才使用缓存
            // 如果缓存没有 AI 总结，则从后端获取完整数据（后端可能已有 AI 总结）
            if (cachedData && cachedData.aiSummary) {
                console.log(`[API] 从缓存加载周报告: ${weekStartDate}`);
                return cachedData;
            }
            // 如果缓存存在但没有 AI 总结，记录日志并继续从后端获取
            if (cachedData) {
                console.log(`[API] 缓存中的周报告缺少 AI 总结，从后端同步: ${weekStartDate}`);
            }
        }

        // 缓存未命中或强制刷新或缓存缺少 AI 总结,调用 API
        console.log(`[API] 从服务器加载周报告: ${weekStartDate}`);
        const params = new URLSearchParams({
            week_start_date: weekStartDate,
            force_refresh: String(forceRefresh),
        });

        const response = await fetch(`${getApiBase()}/report/weekly?${params}`);

        if (!response.ok) {
            throw new Error(`获取周报告失败: ${response.statusText}`);
        }

        const data: WeeklyReportAPIResponse = await response.json();
        const transformedData = transformWeeklyReportResponse(data);

        // 缓存结果
        ReportCacheService.cacheWeeklyReport(weekStartDate, transformedData);
        console.log(`[API] 已缓存周报告: ${weekStartDate}`);

        return transformedData;
    },

    /**
     * 后台同步周报告的 AI 总结
     */
    async syncWeeklyAISummaryInBackground(weekStartDate: string): Promise<void> {
        try {
            console.log(`[API] 后台检查周报告 AI 总结: ${weekStartDate}`);
            const params = new URLSearchParams({
                week_start_date: weekStartDate,
                force_refresh: 'false',
            });
            const response = await fetch(`${getApiBase()}/report/weekly?${params}`);
            if (response.ok) {
                const data: WeeklyReportAPIResponse = await response.json();
                if (data.ai_summary) {
                    this.updateWeeklyAISummaryCache(weekStartDate, data.ai_summary);
                    console.log(`[API] 后台同步周报告 AI 总结成功: ${weekStartDate}`);
                }
            }
        } catch (error) {
            console.warn(`[API] 后台同步周报告 AI 总结失败:`, error);
        }
    },

    /**
     * 删除周报告缓存
     */
    async deleteWeeklyReport(weekStartDate: string): Promise<void> {
        const response = await fetch(`${getApiBase()}/report/weekly/${weekStartDate}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`删除周报告失败: ${response.statusText}`);
        }

        // 同时删除本地缓存
        ReportCacheService.removeWeeklyReport(weekStartDate);
        console.log(`[API] 已删除周报告缓存: ${weekStartDate}`);
    },

    /**
     * 获取月报告
     */
    async getMonthlyReport(month: string, forceRefresh: boolean = false): Promise<MonthlyReportData> {
        // 如果不是强制刷新,先尝试从缓存获取
        if (!forceRefresh) {
            const cachedData = ReportCacheService.getMonthlyReport(month);
            // 只有当缓存存在且包含 AI 总结时才使用缓存
            // 如果缓存没有 AI 总结，则从后端获取完整数据（后端可能已有 AI 总结）
            if (cachedData && cachedData.aiSummary) {
                console.log(`[API] 从缓存加载月报告: ${month}`);
                return cachedData;
            }
            // 如果缓存存在但没有 AI 总结，记录日志并继续从后端获取
            if (cachedData) {
                console.log(`[API] 缓存中的月报告缺少 AI 总结，从后端同步: ${month}`);
            }
        }

        // 缓存未命中或强制刷新或缓存缺少 AI 总结,调用 API
        console.log(`[API] 从服务器加载月报告: ${month}`);
        const params = new URLSearchParams({
            month,
            force_refresh: String(forceRefresh),
        });

        const response = await fetch(`${getApiBase()}/report/monthly?${params}`);

        if (!response.ok) {
            throw new Error(`获取月报告失败: ${response.statusText}`);
        }

        const data: MonthlyReportAPIResponse = await response.json();
        const transformedData = transformMonthlyReportResponse(data);

        // 缓存结果
        ReportCacheService.cacheMonthlyReport(month, transformedData);
        console.log(`[API] 已缓存月报告: ${month}`);

        return transformedData;
    },

    /**
     * 后台同步月报告的 AI 总结
     */
    async syncMonthlyAISummaryInBackground(month: string): Promise<void> {
        try {
            console.log(`[API] 后台检查月报告 AI 总结: ${month}`);
            const params = new URLSearchParams({
                month,
                force_refresh: 'false',
            });
            const response = await fetch(`${getApiBase()}/report/monthly?${params}`);
            if (response.ok) {
                const data: MonthlyReportAPIResponse = await response.json();
                if (data.ai_summary) {
                    this.updateMonthlyAISummaryCache(month, data.ai_summary);
                    console.log(`[API] 后台同步月报告 AI 总结成功: ${month}`);
                }
            }
        } catch (error) {
            console.warn(`[API] 后台同步月报告 AI 总结失败:`, error);
        }
    },

    /**
     * 删除月报告缓存
     */
    async deleteMonthlyReport(monthStartDate: string): Promise<void> {
        const response = await fetch(`${getApiBase()}/report/monthly/${monthStartDate}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`删除月报告失败: ${response.statusText}`);
        }

        // 同时删除本地缓存
        ReportCacheService.removeMonthlyReport(monthStartDate);
        console.log(`[API] 已删除月报告缓存: ${monthStartDate}`);
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

    /**
     * 获取 AI 总结
     */
    async getAISummary(date: string, pattern: string = 'complex'): Promise<{
        content: string;
        tokensUsage: {
            inputTokens: number;
            outputTokens: number;
            totalTokens: number;
        };
    }> {
        const response = await fetch(`${getApiBase()}/report/daily/ai_summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                date,
                pattern,
            }),
        });

        if (!response.ok) {
            throw new Error(`获取 AI 总结失败: ${response.statusText}`);
        }

        const data = await response.json();
        const result = {
            content: data.content,
            tokensUsage: {
                inputTokens: data.tokens_usage.input_tokens,
                outputTokens: data.tokens_usage.output_tokens,
                totalTokens: data.tokens_usage.total_tokens,
            },
        };

        // 更新前端缓存中的 AI 总结
        this.updateDailyAISummaryCache(date, result.content);

        return result;
    },

    /**
     * 更新日报告缓存中的 AI 总结
     */
    updateDailyAISummaryCache(date: string, aiSummary: string): void {
        const cached = ReportCacheService.getDailyReport(date);
        if (cached) {
            cached.aiSummary = aiSummary;
            ReportCacheService.cacheDailyReport(date, cached);
            console.log(`[API] 已更新日报告缓存中的 AI 总结: ${date}`);
        }
    },

    /**
     * 获取周 AI 总结
     */
    async getWeeklyAISummary(weekStartDate: string, weekEndDate: string, pattern: string = 'complex'): Promise<{
        content: string;
        tokensUsage: {
            inputTokens: number;
            outputTokens: number;
            totalTokens: number;
        };
    }> {
        const response = await fetch(`${getApiBase()}/report/weekly/ai_summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                week_start_date: weekStartDate,
                week_end_date: weekEndDate,
                pattern,
            }),
        });

        if (!response.ok) {
            throw new Error(`获取周 AI 总结失败: ${response.statusText}`);
        }

        const data = await response.json();
        const result = {
            content: data.content,
            tokensUsage: {
                inputTokens: data.tokens_usage.input_tokens,
                outputTokens: data.tokens_usage.output_tokens,
                totalTokens: data.tokens_usage.total_tokens,
            },
        };

        // 更新前端缓存中的 AI 总结
        this.updateWeeklyAISummaryCache(weekStartDate, result.content);

        return result;
    },

    /**
     * 更新周报告缓存中的 AI 总结
     */
    updateWeeklyAISummaryCache(weekStartDate: string, aiSummary: string): void {
        const cached = ReportCacheService.getWeeklyReport(weekStartDate);
        if (cached) {
            cached.aiSummary = aiSummary;
            ReportCacheService.cacheWeeklyReport(weekStartDate, cached);
            console.log(`[API] 已更新周报告缓存中的 AI 总结: ${weekStartDate}`);
        }
    },

    /**
     * 获取月 AI 总结
     */
    async getMonthlyAISummary(monthStartDate: string, monthEndDate: string, pattern: string = 'complex'): Promise<{
        content: string;
        tokensUsage: {
            inputTokens: number;
            outputTokens: number;
            totalTokens: number;
        };
    }> {
        const response = await fetch(`${getApiBase()}/report/monthly/ai_summary`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                month_start_date: monthStartDate,
                month_end_date: monthEndDate,
                pattern,
            }),
        });

        if (!response.ok) {
            throw new Error(`获取月 AI 总结失败: ${response.statusText}`);
        }

        const data = await response.json();
        const result = {
            content: data.content,
            tokensUsage: {
                inputTokens: data.tokens_usage.input_tokens,
                outputTokens: data.tokens_usage.output_tokens,
                totalTokens: data.tokens_usage.total_tokens,
            },
        };

        // 更新前端缓存中的 AI 总结
        // 从 monthStartDate 提取月份 (YYYY-MM)
        const month = monthStartDate.substring(0, 7);
        this.updateMonthlyAISummaryCache(month, result.content);

        return result;
    },

    /**
     * 更新月报告缓存中的 AI 总结
     */
    updateMonthlyAISummaryCache(month: string, aiSummary: string): void {
        const cached = ReportCacheService.getMonthlyReport(month);
        if (cached) {
            cached.aiSummary = aiSummary;
            ReportCacheService.cacheMonthlyReport(month, cached);
            console.log(`[API] 已更新月报告缓存中的 AI 总结: ${month}`);
        }
    },
};
