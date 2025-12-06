/**
 * Dashboard API Client
 * 用于与后端 Dashboard API 交互
 */

import { TimeOverviewResponse, DashboardResponse, ActivitySummaryResponse, HomepageResponse } from '../types';

// 使用与 categoryService.ts 相同的 BASE_URL
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export class DashboardAPI {
    /**
     * 获取 Time Overview 数据
     * @param date 日期 (YYYY-MM-DD)
     * @param parentId 可选，主分类ID（用于下钻）
     */
    static async getTimeOverview(
        date: string
    ): Promise<TimeOverviewResponse> {
        try {
            const params = new URLSearchParams({ date });

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
    /**
     * 获取仪表盘数据
     * @param date 日期 (YYYY-MM-DD)
     */
    static async getDashboardData(date: string): Promise<DashboardResponse> {
        try {
            const params = new URLSearchParams({ date });
            const response = await fetch(
                `${API_BASE_URL}/dashboard?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error(`Failed to fetch dashboard data: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            throw error;
        }
    }
    /**
     * 获取活动总结数据
     * @param date 日期 (YYYY-MM-DD)
     * @param historyNumber 历史数据数量
     * @param futureNumber 未来数据数量
     */
    static async getActivitySummaryData(date: string, historyNumber: number, futureNumber: number): Promise<ActivitySummaryResponse> {
        try {
            const params = new URLSearchParams({ date, historyNumber: historyNumber.toString(), futureNumber: futureNumber.toString() });
            const response = await fetch(
                `${API_BASE_URL}/activity-summary?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error(`Failed to fetch activity summary: ${response.statusText}`);
            }
            return await response.json();
        } catch (error) {
            console.error('Error fetching activity summary:', error);
            throw error;
        }
    }

    /**
     * 获取首页统一数据（整合三个API调用）
     * @param date 日期 (YYYY-MM-DD)
     * @param historyNumber 历史数据天数 (默认15)
     * @param futureNumber 未来数据天数 (默认14)
     */
    static async getHomepageData(
        date: string,
        historyNumber: number = 15,
        futureNumber: number = 14
    ): Promise<HomepageResponse> {
        try {
            const params = new URLSearchParams({
                date,
                history_number: historyNumber.toString(),
                future_number: futureNumber.toString()
            });
            const response = await fetch(
                `${API_BASE_URL}/dashboard/homepage?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error(`Failed to fetch homepage data: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching homepage data:', error);
            throw error;
        }
    }

    /**
     * 获取指定时间范围的 Timeline Overview 数据
     * @param date 日期 (YYYY-MM-DD)
     * @param startHour 开始小时 (浮点数，如 12.5 = 12:30)
     * @param endHour 结束小时 (浮点数)
     */
    static async getTimelineOverview(
        date: string,
        startHour: number,
        endHour: number
    ): Promise<TimeOverviewResponse> {
        try {
            const params = new URLSearchParams({
                date,
                start_hour: startHour.toString(),
                end_hour: endHour.toString()
            });

            const response = await fetch(
                `${API_BASE_URL}/timeline/overview?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error(`Failed to fetch timeline overview: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching timeline overview:', error);
            throw error;
        }
    }
}

