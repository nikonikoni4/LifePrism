/**
 * Custom Block Types
 * 
 * TypeScript 类型定义，对应后端 timeline_schemas.py 的 UserCustomBlock 相关类型
 */

// ============================================================================
// 自定义时间块 API 相关类型
// ============================================================================

/** 创建自定义时间块请求 */
export interface UserCustomBlockCreate {
    content: string;          // 活动内容描述
    start_time: string;       // 开始时间（ISO格式：YYYY-MM-DDTHH:MM:SS）
    end_time: string;         // 结束时间（ISO格式：YYYY-MM-DDTHH:MM:SS）
    duration: number;         // 持续时长（分钟）
    category_id?: string;     // 主分类ID（可选）
    sub_category_id?: string; // 子分类ID（可选）
    todo_id?: number;         // 关联的待办事项ID（可选）
    color?: string;           // 活动颜色（可选，前端随机生成）
}

/** 更新自定义时间块请求（所有字段可选） */
export interface UserCustomBlockUpdate {
    content?: string;
    start_time?: string;
    end_time?: string;
    duration?: number;
    category_id?: string;
    sub_category_id?: string;
    todo_id?: number;
    color?: string;
}

/** 自定义时间块完整数据（API 返回） */
export interface UserCustomBlock {
    id: number;               // 数据块ID
    content: string;          // 活动内容描述
    todo_id?: number;         // 关联的待办事项ID
    todo_content?: string;    // 关联的待办事项内容
    start_time: string;       // 开始时间
    end_time: string;         // 结束时间
    duration: number;         // 持续时长（分钟）
    category_id?: string;     // 主分类ID
    sub_category_id?: string; // 子分类ID
    category?: string;        // 主分类名称（映射后）
    sub_category?: string;    // 子分类名称（映射后）
    color?: string;           // 活动颜色
    created_at?: string;      // 创建时间
    updated_at?: string;      // 更新时间
}

/** 自定义时间块列表响应 */
export interface UserCustomBlockListResponse {
    data: UserCustomBlock[];
    total: number;
}

/** 单条自定义时间块响应 */
export interface UserCustomBlockResponse {
    data: UserCustomBlock;
}

// ============================================================================
// 前端组件内部使用的类型
// ============================================================================

/** 拖拽区域类型 */
export type DragZone = 'top' | 'bottom' | 'middle' | null;

/** 拖拽状态 */
export interface DragState {
    isDragging: boolean;
    dragZone: DragZone;
    blockId: number | null;
    initialY: number;
    initialStartTime: string;
    initialEndTime: string;
    currentStartTime: string;
    currentEndTime: string;
}

/** 自定义时间块样式信息（计算后） */
export interface CustomBlockStyle {
    top: number;           // 顶部位置（像素）
    height: number;        // 高度（像素）
    startHour: number;     // 开始小时（浮点数）
    endHour: number;       // 结束小时（浮点数）
}

/** Popover 编辑表单数据 */
export interface PopoverFormData {
    content: string;
    startTime: string;        // HH:MM 格式
    endTime: string;          // HH:MM 格式
    categoryId?: string;
    subCategoryId?: string;
    todoId?: number;
    color: string;            // Tailwind 200 系列颜色
}

// ============================================================================
// Todo 绑定相关类型
// ============================================================================

/** 待办事项选择项（用于下拉菜单） */
export interface TodoSelectItem {
    id: number;
    content: string;
}

// ============================================================================
// Tailwind 200 系列颜色常量
// ============================================================================

export const TAILWIND_200_COLORS = [
    '#fecaca', // red-200
    '#fed7aa', // orange-200
    '#fef08a', // yellow-200
    '#d9f99d', // lime-200
    '#bbf7d0', // green-200
    '#a5f3fc', // cyan-200
    '#bfdbfe', // blue-200
    '#c4b5fd', // violet-200
    '#f5d0fe', // fuchsia-200
    '#fbcfe8', // pink-200
];

/** 随机获取一个 Tailwind 200 系列颜色 */
export function getRandomColor(): string {
    return TAILWIND_200_COLORS[Math.floor(Math.random() * TAILWIND_200_COLORS.length)];
}
