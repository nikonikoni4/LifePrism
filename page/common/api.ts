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
import { createApiV2UrlGetter } from '../../services/apiConfig';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiBase = createApiV2UrlGetter();

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
        const response = await fetch(`${getApiBase()}/category/tree?depth=${depth}`);

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

        const response = await fetch(`${getApiBase()}/activity/logs?${searchParams.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch activity logs: ${response.statusText}`);
        }

        return response.json();
    },

    /** 更新单条日志分类 */
    async updateCategory(logId: string, categoryId: string, subCategoryId?: string): Promise<{ success: boolean; message: string }> {
        const params = new URLSearchParams();
        params.set('category_id', categoryId);
        if (subCategoryId) params.set('sub_category_id', subCategoryId);

        const response = await fetch(`${getApiBase()}/activity/manage/logs/${logId}/category?${params.toString()}`, {
            method: 'PATCH',
        });
        if (!response.ok) throw new Error(`Failed to update category: ${response.statusText}`);
        return response.json();
    },

    /** 批量更新日志分类 */
    async batchUpdateCategory(logIds: string[], categoryId: string, subCategoryId?: string): Promise<{ success: boolean; data: { updated_count: number }; message: string }> {
        const params = new URLSearchParams();
        logIds.forEach(id => params.append('log_ids', id));
        params.set('category_id', categoryId);
        if (subCategoryId) params.set('sub_category_id', subCategoryId);

        const response = await fetch(`${getApiBase()}/activity/manage/logs/batch-category?${params.toString()}`, {
            method: 'POST',
        });
        if (!response.ok) throw new Error(`Failed to batch update: ${response.statusText}`);
        return response.json();
    },

    /** 删除单条日志 */
    async deleteLog(logId: string): Promise<{ success: boolean; message: string }> {
        const response = await fetch(`${getApiBase()}/activity/manage/logs/${logId}`, {
            method: 'DELETE',
        });
        if (!response.ok) throw new Error(`Failed to delete log: ${response.statusText}`);
        return response.json();
    },

    /** 批量删除日志 */
    async batchDeleteLogs(logIds: string[]): Promise<{ success: boolean; data: { deleted_count: number }; message: string }> {
        const params = new URLSearchParams();
        logIds.forEach(id => params.append('log_ids', id));

        const response = await fetch(`${getApiBase()}/activity/manage/logs/batch?${params.toString()}`, {
            method: 'DELETE',
        });
        if (!response.ok) throw new Error(`Failed to batch delete: ${response.statusText}`);
        return response.json();
    },
};

