/**
 * Goals Page API
 * 
 * 目标管理相关接口（占位）
 */

import { Goal, GoalsResponse } from './types';

const API_BASE = 'http://localhost:8000/api/v2';

/**
 * Goals API
 */
export const GoalsAPI = {
    /**
     * 获取所有目标
     */
    async getGoals(): Promise<GoalsResponse> {
        // TODO: 实现真实 API 调用
        return {
            goals: [],
            totalCount: 0,
        };
    },

    /**
     * 创建目标
     */
    async createGoal(goal: Omit<Goal, 'id' | 'createdAt' | 'updatedAt'>): Promise<Goal> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },

    /**
     * 更新目标
     */
    async updateGoal(id: string, updates: Partial<Goal>): Promise<Goal> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },

    /**
     * 删除目标
     */
    async deleteGoal(id: string): Promise<void> {
        // TODO: 实现真实 API 调用
        throw new Error('Not implemented');
    },
};
