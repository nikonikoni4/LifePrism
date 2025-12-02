/**
 * Dashboard API Client
 * 用于与后端 Dashboard API 交互
 */

import { TimeOverviewResponse } from '../types';

// 使用与 categoryService.ts 相同的 BASE_URL
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export class DashboardAPI {
    /**
     * 获取 Time Overview 数据
     * @param date 日期 (YYYY-MM-DD)
     * @param parentId 可选，主分类ID（用于下钻）
     */
    static async getTimeOverview(
        date: string,
        parentId?: string
    ): Promise<TimeOverviewResponse> {
        try {
            const params = new URLSearchParams({ date });
            if (parentId) {
                params.append('parent_id', parentId);
            }

            const response = await fetch(
                `${API_BASE_URL}/dashboard/time-overview?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error(`Failed to fetch time overview: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching time overview:', error);
            throw error;
        }
    }
}
