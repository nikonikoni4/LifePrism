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
    StandardResponse
} from './types';

const API_BASE = 'http://localhost:8000/api/v2/category';

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
        const response = await fetch(`${API_BASE}/tree?depth=${depth}`);

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
        const response = await fetch(`${API_BASE}/manage`, {
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
        const response = await fetch(`${API_BASE}/manage/${categoryId}`, {
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
        const response = await fetch(`${API_BASE}/manage/${categoryId}`, {
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
        const response = await fetch(`${API_BASE}/manage/${parentId}/sub`, {
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
        const response = await fetch(`${API_BASE}/manage/${parentId}/sub/${subId}`, {
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
        const response = await fetch(`${API_BASE}/manage/${parentId}/sub/${subId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to delete sub-category: ${response.statusText}`);
        }

        return response.json();
    },
};
