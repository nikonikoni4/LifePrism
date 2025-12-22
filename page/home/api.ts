/**
 * Home API
 * 
 * 调用后端 /api/v2/activity 相关接口
 */

import { ActivityStatsResponse, ActivityStatsParams, CategoryTreeItem } from './types';

const API_BASE = 'http://localhost:8000/api/v2';

/**
 * Activity API
 */
export const ActivityAPI = {
    /**
     * 获取活动统计数据
     * 
     * @param params 请求参数
     * @returns 活动统计响应数据
     */
    async getStats(params: ActivityStatsParams): Promise<ActivityStatsResponse> {
        const searchParams = new URLSearchParams();

        searchParams.set('date', params.date);

        if (params.include) {
            searchParams.set('include', params.include);
        }
        if (params.history_number !== undefined) {
            searchParams.set('history_number', params.history_number.toString());
        }
        if (params.future_number !== undefined) {
            searchParams.set('future_number', params.future_number.toString());
        }
        if (params.category_id) {
            searchParams.set('category_id', params.category_id);
        }
        if (params.sub_category_id) {
            searchParams.set('sub_category_id', params.sub_category_id);
        }

        const response = await fetch(`${API_BASE}/activity/stats?${searchParams.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch activity stats: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 获取 Activity Summary 数据
     * 
     * @param date 中心日期
     * @param historyNumber 历史天数
     * @param futureNumber 未来天数
     * @param categoryId 主分类ID（可选）
     * @param subCategoryId 子分类ID（可选）
     */
    async getActivitySummary(
        date: string,
        historyNumber: number = 15,
        futureNumber: number = 14,
        categoryId?: string,
        subCategoryId?: string
    ): Promise<ActivityStatsResponse> {
        return this.getStats({
            date,
            include: 'activity_summary',
            history_number: historyNumber,
            future_number: futureNumber,
            category_id: categoryId,
            sub_category_id: subCategoryId,
        });
    },

    /**
     * 获取首页所有数据（统一调用）
     * 
     * @param date 中心日期
     * @param historyNumber 历史天数
     * @param futureNumber 未来天数
     */
    async getHomepageData(
        date: string,
        historyNumber: number = 15,
        futureNumber: number = 14
    ): Promise<ActivityStatsResponse> {
        return this.getStats({
            date,
            include: 'activity_summary,time_overview,top_title,top_app,todolist',
            history_number: historyNumber,
            future_number: futureNumber,
        });
    },
};

/**
 * Category API（复用 v2 接口，用于筛选器）
 */
export const CategoryAPI = {
    /**
     * 获取所有分类（带子分类）
     */
    async getAllCategories(): Promise<CategoryTreeItem[]> {
        const response = await fetch('http://localhost:8000/api/v2/category/tree?depth=2');

        if (!response.ok) {
            throw new Error(`Failed to fetch categories: ${response.statusText}`);
        }

        const data = await response.json();
        // 直接使用 v2 API 返回的 data 字段
        return data.data;
    },
};

/**
 * Sync API
 */
export const SyncAPI = {
    /**
     * 增量同步（从数据库最新时间开始同步到现在）
     */
    async incrementalSync(autoClassify: boolean = true): Promise<any> {
        const response = await fetch('http://localhost:8000/api/v2/sync/activitywatch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                auto_classify: autoClassify,
            }),
        });

        if (!response.ok) {
            throw new Error(`Sync failed: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 时间范围同步
     */
    async syncByTimeRange(params: {
        start_time: string;
        end_time: string;
        auto_classify?: boolean;
    }): Promise<any> {
        const response = await fetch('http://localhost:8000/api/v2/sync/activitywatch/timerange', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(params),
        });

        if (!response.ok) {
            throw new Error(`Sync failed: ${response.statusText}`);
        }

        return response.json();
    },
};
