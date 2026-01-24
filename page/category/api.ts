/**
 * Category V2 API
 * 
 * 调用后端 /api/v2/category 相关接口
 */

import {
    CategoryTreeResponse,
    CategoryTreeItem,
    SubCategoryTreeItem,
    CreateCategoryRequest,
    UpdateCategoryRequest,
    CreateSubCategoryRequest,
    UpdateSubCategoryRequest,
    StandardResponse,
    CategoryMapCacheResponse,
    UpdateCategoryMapCacheRequest,
    BatchUpdateCategoryMapCacheRequest
} from './types';
import { createApiV2UrlGetter } from '../../services/apiConfig';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiBase = createApiV2UrlGetter('/category');

/**
 * Category V2 API Client
 */
export const CategoryAPI = {
    /**
     * 获取分类树形结构
     * 
     * @param depth 返回层级深度。1=仅主分类，2=主分类+子分类
     * @returns 分类树数据
     */
    async getTree(depth: number = 2): Promise<CategoryTreeItem[]> {
        const response = await fetch(`${getApiBase()}/tree?depth=${depth}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch category tree: ${response.statusText}`);
        }

        const data: CategoryTreeResponse = await response.json();
        return data.data;
    },

    /**
     * 创建主分类
     * 
     * @param request 创建请求
     * @returns 创建的分类
     */
    async createCategory(request: CreateCategoryRequest): Promise<CategoryTreeItem> {
        const response = await fetch(`${getApiBase()}/manage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`Failed to create category: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 更新主分类
     * 
     * @param categoryId 分类ID
     * @param request 更新请求
     * @returns 更新后的分类
     */
    async updateCategory(categoryId: string, request: UpdateCategoryRequest): Promise<CategoryTreeItem> {
        const response = await fetch(`${getApiBase()}/manage/${categoryId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`Failed to update category: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 删除主分类
     * 
     * @param categoryId 分类ID
     * @param reassignTo 重新分配到的分类ID（默认 'other'）
     * @returns 标准响应
     */
    async deleteCategory(categoryId: string, reassignTo: string = 'other'): Promise<StandardResponse> {
        const response = await fetch(`${getApiBase()}/manage/${categoryId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reassign_to: reassignTo }),
        });

        if (!response.ok) {
            throw new Error(`Failed to delete category: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 创建子分类
     * 
     * @param parentId 主分类ID
     * @param request 创建请求
     * @returns 创建的子分类
     */
    async createSubCategory(parentId: string, request: CreateSubCategoryRequest): Promise<SubCategoryTreeItem> {
        const response = await fetch(`${getApiBase()}/manage/${parentId}/sub`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`Failed to create sub-category: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 更新子分类
     * 
     * @param parentId 主分类ID
     * @param subId 子分类ID
     * @param request 更新请求
     * @returns 更新后的子分类
     */
    async updateSubCategory(
        parentId: string,
        subId: string,
        request: UpdateSubCategoryRequest
    ): Promise<SubCategoryTreeItem> {
        const response = await fetch(`${getApiBase()}/manage/${parentId}/sub/${subId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            throw new Error(`Failed to update sub-category: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 删除子分类
     * 
     * @param parentId 主分类ID
     * @param subId 子分类ID
     * @returns 标准响应
     */
    async deleteSubCategory(parentId: string, subId: string): Promise<StandardResponse> {
        const response = await fetch(`${getApiBase()}/manage/${parentId}/sub/${subId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to delete sub-category: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 切换主分类状态
     * 
     * @param categoryId 分类ID
     * @param state 新状态（1: 启用, 0: 禁用）
     * @returns 更新后的分类
     */
    async toggleCategoryState(categoryId: string, state: number): Promise<CategoryTreeItem> {
        const response = await fetch(`${getApiBase()}/manage/${categoryId}/state`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state }),
        });

        if (!response.ok) {
            throw new Error(`Failed to toggle category state: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 切换子分类状态
     * 
     * @param parentId 主分类ID
     * @param subId 子分类ID
     * @param state 新状态（1: 启用, 0: 禁用）
     * @returns 更新后的子分类
     */
    async toggleSubCategoryState(parentId: string, subId: string, state: number): Promise<SubCategoryTreeItem> {
        const response = await fetch(`${getApiBase()}/manage/${parentId}/sub/${subId}/state`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ state }),
        });

        if (!response.ok) {
            throw new Error(`Failed to toggle sub-category state: ${response.statusText}`);
        }

        return response.json();
    },
};

// ============================================================================
// CategoryMapCache API
// ============================================================================

export const CategoryMapCacheAPI = {
    /**
     * 获取分类缓存列表
     * 
     * @param params 请求参数
     * @returns 分页响应
     */
    async getList(params: {
        page?: number;
        page_size?: number;
        search?: string;
        state?: number;
        is_multipurpose_app?: boolean;
    } = {}): Promise<CategoryMapCacheResponse> {
        const searchParams = new URLSearchParams();

        if (params.page !== undefined) {
            searchParams.set('page', params.page.toString());
        }
        if (params.page_size !== undefined) {
            searchParams.set('page_size', params.page_size.toString());
        }
        if (params.search) {
            searchParams.set('search', params.search);
        }
        if (params.state !== undefined) {
            searchParams.set('state', params.state.toString());
        }
        if (params.is_multipurpose_app !== undefined) {
            searchParams.set('is_multipurpose_app', params.is_multipurpose_app.toString());
        }

        const response = await fetch(`${getApiBase()}/category_map?${searchParams.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch category map cache: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 更新单条记录
     * 
     * @param recordId 记录ID
     * @param data 更新数据
     * @returns 标准响应
     */
    async update(recordId: string, data: UpdateCategoryMapCacheRequest): Promise<StandardResponse> {
        const response = await fetch(`${getApiBase()}/category_map/${recordId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ id: recordId, ...data }),
        });

        if (!response.ok) {
            throw new Error(`Failed to update category map cache: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 批量更新记录
     * 
     * @param data 批量更新数据
     * @returns 标准响应
     */
    async batchUpdate(data: BatchUpdateCategoryMapCacheRequest): Promise<StandardResponse> {
        const response = await fetch(`${getApiBase()}/category_map/batch`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`Failed to batch update category map cache: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 删除单条记录
     * 
     * @param recordId 记录ID
     * @returns 标准响应
     */
    async delete(recordId: string): Promise<StandardResponse> {
        const response = await fetch(`${getApiBase()}/category_map/${recordId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to delete category map cache: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 批量删除记录
     * 
     * @param ids 记录ID列表
     * @returns 标准响应
     */
    async batchDelete(ids: string[]): Promise<StandardResponse> {
        const response = await fetch(`${getApiBase()}/category_map/batch`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ids }),
        });

        if (!response.ok) {
            throw new Error(`Failed to batch delete category map cache: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 根据缓存匹配条件更新日志分类
     * 
     * @param params 更新参数
     * @returns 标准响应 (包含 updated_count)
     */
    async updateLogsByCache(params: {
        app: string;
        title?: string | null;
        is_multipurpose_app: boolean;
        category_id: string;
        sub_category_id?: string | null;
        goal_id?: string | null;  // null=不修改, ""=清除, "goal-xxx"=设置
        start_date?: string;      // 可选，YYYY-MM-DD 格式
        end_date?: string;        // 可选，YYYY-MM-DD 格式
    }): Promise<StandardResponse> {
        const searchParams = new URLSearchParams();
        searchParams.set('app', params.app);
        searchParams.set('is_multipurpose_app', params.is_multipurpose_app.toString());
        searchParams.set('category_id', params.category_id);

        if (params.title) {
            searchParams.set('title', params.title);
        }
        if (params.sub_category_id) {
            searchParams.set('sub_category_id', params.sub_category_id);
        }
        // goal_id: null=不修改（不传参数）, ""=清除, "goal-xxx"=设置
        if (params.goal_id !== null && params.goal_id !== undefined) {
            searchParams.set('goal_id', params.goal_id);
        }
        if (params.start_date) {
            searchParams.set('start_date', params.start_date);
        }
        if (params.end_date) {
            searchParams.set('end_date', params.end_date);
        }

        const getActivityApiBase = createApiV2UrlGetter('/activity');
        const response = await fetch(`${getActivityApiBase()}/manage/logs/update-by-cache?${searchParams.toString()}`, {
            method: 'POST',
        });

        if (!response.ok) {
            throw new Error(`Failed to update logs by cache: ${response.statusText}`);
        }

        return response.json();
    },
};

