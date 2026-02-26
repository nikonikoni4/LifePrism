/**
 * Category V2 Types
 * 
 * TypeScript 类型定义，对应后端 category_schemas.py
 */

// ============================================================================
// Tree 端点专用类型（从 common 重新导出）
// ============================================================================

export type { CategoryTreeItem, SubCategoryTreeItem, CategoryTreeResponse } from '../../../../core/types/common-components';

// ============================================================================
// CRUD 请求类型
// ============================================================================

/** 创建主分类请求 */
export interface CreateCategoryRequest {
    name: string;
    color: string;
}

/** 更新主分类请求 */
export interface UpdateCategoryRequest {
    name?: string;
    color?: string;
}

/** 删除主分类请求 */
export interface DeleteCategoryRequest {
    reassign_to?: string;
}

/** 创建子分类请求 */
export interface CreateSubCategoryRequest {
    name: string;
}

/** 更新子分类请求 */
export interface UpdateSubCategoryRequest {
    name: string;
}

// ============================================================================
// 通用响应类型
// ============================================================================

/** 标准响应 */
export interface StandardResponse {
    success: boolean;
    data: any;
    message: string;
}

// ============================================================================
// 旧版兼容类型（用于 DataReviewTab）
// ============================================================================

/** 活动记录（用于 Data Review） */
export interface ActivityRecord {
    id: string;
    appName: string;
    windowTitle: string;
    timestamp: string;
    duration: string;
    aiDescription?: string;
    categoryId: string;
    subCategoryId: string;
}

// ============================================================================
// CategoryMapCache 类型（用于 Map Cache 选项卡）
// ============================================================================

/** CategoryMapCache 表项 */
export interface CategoryMapCacheItem {
    id: string;
    app: string;
    app_description: string | null;
    title: string;
    title_analysis: string | null;
    category: string | null;
    sub_category: string | null;
    category_id: string | null;
    sub_category_id: string | null;
    link_to_goal_id: string | null;
    link_to_goal: string | null;
    is_multipurpose_app: boolean;
    state: number;
    created_at: string | null;
}

/** GET /category_map 响应 */
export interface CategoryMapCacheResponse {
    data: CategoryMapCacheItem[];
    total: number;
    page: number;
    page_size: number;
    total_pages: number;
}

/** 更新单条 CategoryMapCache 记录请求 */
export interface UpdateCategoryMapCacheRequest {
    category_id?: string | null;
    sub_category_id?: string | null;
    app_description?: string | null;
    title_analysis?: string | null;
    link_to_goal_id?: string | null;
}

/** 批量更新 CategoryMapCache 记录请求 */
export interface BatchUpdateCategoryMapCacheRequest {
    ids: string[];
    category_id?: string | null;
    sub_category_id?: string | null;
    app_description?: string | null;
}
