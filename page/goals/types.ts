/**
 * Goals Page Types
 * 
 * 目标管理相关类型定义
 */

/** 目标项 */
export interface Goal {
    id: string;
    name: string;
    description?: string;
    targetMinutes: number;  // 目标时长（分钟）
    currentMinutes: number;  // 当前进度（分钟）
    category?: string;  // 关联分类
    deadline?: string;  // 截止日期
    isCompleted: boolean;
    createdAt: string;
    updatedAt: string;
}

/** 目标进度统计 */
export interface GoalProgress {
    goalId: string;
    date: string;
    minutes: number;
}

/** 目标列表响应 */
export interface GoalsResponse {
    goals: Goal[];
    totalCount: number;
}
