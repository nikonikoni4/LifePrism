/**
 * Common API
 * 
 * 共享 API 方法（Activity Logs, Category Tree 等）
 */

import {
    CategoryTreeItem,
    CategoryTreeResponse,
    ActivityLogItem,
    ActivityLogsResponse,
    ActivityLogsParams
} from './types';

const API_BASE = 'http://localhost:8000/api/v2';

// ============================================================================
// Category API
// ============================================================================

export const CategoryAPI = {
    /**
     * 获取分类树形结构
     * 
     * @param depth 返回层级深度。1=仅主分类，2=主分类+子分类
     * @returns 分类树数据
     */
    async getTree(depth: number = 2): Promise<CategoryTreeItem[]> {
        const response = await fetch(`${API_BASE}/category/tree?depth=${depth}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch category tree: ${response.statusText}`);
        }

        const data: CategoryTreeResponse = await response.json();
        return data.data;
    },
};

// ============================================================================
// Activity Logs API
// ============================================================================

export const ActivityLogsAPI = {
    /**
     * 获取活动日志列表
     * 
     * @param params 请求参数
     * @returns 活动日志响应（带分页）
     */
    async getLogs(params: ActivityLogsParams): Promise<ActivityLogsResponse> {
        const searchParams = new URLSearchParams();

        searchParams.set('start_time', params.start_time);
        searchParams.set('end_time', params.end_time);

        if (params.device_filter) {
            searchParams.set('device_filter', params.device_filter);
        }
        if (params.category_id) {
            searchParams.set('category_id', params.category_id);
        }
        if (params.sub_category_id) {
            searchParams.set('sub_category_id', params.sub_category_id);
        }
        if (params.sort_by) {
            searchParams.set('sort_by', params.sort_by);
        }
        if (params.sort_order) {
            searchParams.set('sort_order', params.sort_order);
        }
        if (params.page !== undefined) {
            searchParams.set('page', params.page.toString());
        }
        if (params.page_size !== undefined) {
            searchParams.set('page_size', params.page_size.toString());
        }

        const response = await fetch(`${API_BASE}/activity/logs?${searchParams.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch activity logs: ${response.statusText}`);
        }

        return response.json();
    },
};
