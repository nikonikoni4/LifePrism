/**
 * Category V2 Types
 * 
 * TypeScript 类型定义，对应后端 category_v2_schemas.py
 */

// ============================================================================
// Tree 端点专用类型（从 common 重新导出）
// ============================================================================

export type { CategoryTreeItem, SubCategoryTreeItem, CategoryTreeResponse } from '../common/types';

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
