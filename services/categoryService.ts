/**
 * Category API Client
 * 用于与后端 Category Settings API 交互
 */

import { CategoryDef, SubCategoryDef } from '../types';

const API_BASE_URL = 'http://127.0.0.1:8000/api/v2';

// ============ 类型定义 ============

interface CategoryListResponse {
    data: CategoryDef[];
}

interface StandardResponse {
    success: boolean;
    data: any;
    message: string;
}

// ============ API 客户端 ============

export class categoryPI {
    /**
     * 获取所有分类（使用 tree 接口）
     */
    static async getAllCategories(): Promise<CategoryDef[]> {
        try {
            const response = await fetch(`${API_BASE_URL}/category/tree?depth=2`);
            if (!response.ok) {
                throw new Error(`Failed to fetch categories: ${response.statusText}`);
            }
            const data: CategoryListResponse = await response.json();
            // 转换 tree 响应格式为 CategoryDef 格式
            return data.data.map(cat => ({
                ...cat,
                sub_categories: cat.subcategories || [],
            } as unknown as CategoryDef));
        } catch (error) {
            console.error('Error fetching categories:', error);
            throw error;
        }
    }

    /**
     * 创建主分类
     */
    static async createCategory(name: string, color: string): Promise<CategoryDef> {
        try {
            const response = await fetch(`${API_BASE_URL}/category/manage`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name, color }),
            });

            if (!response.ok) {
                throw new Error(`Failed to create category: ${response.statusText}`);
            }

            const data: StandardResponse = await response.json();
            return data.data;
        } catch (error) {
            console.error('Error creating category:', error);
            throw error;
        }
    }

    /**
     * 更新主分类
     */
    static async updateCategory(
        categoryId: string,
        updates: { name?: string; color?: string }
    ): Promise<CategoryDef> {
        try {
            const response = await fetch(`${API_BASE_URL}/category/manage/${categoryId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updates),
            });

            if (!response.ok) {
                throw new Error(`Failed to update category: ${response.statusText}`);
            }

            const data: StandardResponse = await response.json();
            return data.data;
        } catch (error) {
            console.error('Error updating category:', error);
            throw error;
        }
    }

    /**
     * 删除主分类
     */
    static async deleteCategory(categoryId: string): Promise<void> {
        try {
            const response = await fetch(`${API_BASE_URL}/category/manage/${categoryId}`, {
                method: 'DELETE',
            });

            if (!response.ok) {
                throw new Error(`Failed to delete category: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error deleting category:', error);
            throw error;
        }
    }

    /**
     * 创建子分类
     */
    static async createSubCategory(
        parentId: string,
        name: string
    ): Promise<SubCategoryDef> {
        try {
            const response = await fetch(`${API_BASE_URL}/category/manage/${parentId}/sub`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ name }),
            });

            if (!response.ok) {
                throw new Error(`Failed to create sub-category: ${response.statusText}`);
            }

            const data: StandardResponse = await response.json();
            return data.data;
        } catch (error) {
            console.error('Error creating sub-category:', error);
            throw error;
        }
    }

    /**
     * 更新子分类
     */
    static async updateSubCategory(
        parentId: string,
        subId: string,
        name: string
    ): Promise<SubCategoryDef> {
        try {
            const response = await fetch(
                `${API_BASE_URL}/category/manage/${parentId}/sub/${subId}`,
                {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ name }),
                }
            );

            if (!response.ok) {
                throw new Error(`Failed to update sub-category: ${response.statusText}`);
            }

            const data: StandardResponse = await response.json();
            return data.data;
        } catch (error) {
            console.error('Error updating sub-category:', error);
            throw error;
        }
    }

    /**
     * 删除子分类
     */
    static async deleteSubCategory(parentId: string, subId: string): Promise<void> {
        try {
            const response = await fetch(
                `${API_BASE_URL}/category/manage/${parentId}/sub/${subId}`,
                {
                    method: 'DELETE',
                }
            );

            if (!response.ok) {
                throw new Error(`Failed to delete sub-category: ${response.statusText}`);
            }
        } catch (error) {
            console.error('Error deleting sub-category:', error);
            throw error;
        }
    }
}
