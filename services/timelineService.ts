/**
 * Timeline API Client
 * 用于与后端 Timeline API 交互
 */

import { TimelineResponse } from '../types';

// 使用与其他服务相同的 BASE_URL
const API_BASE_URL = 'http://127.0.0.1:8000/api/v1';

export class TimelineAPI {
    /**
     * 获取指定日期的时间线数据
     * @param date 日期 (YYYY-MM-DD)
     * @param deviceFilter 设备过滤器 ('all' | 'pc' | 'mobile')
     */
    static async getTimelineData(
        date: string,
        deviceFilter: 'all' | 'pc' | 'mobile' = 'all'
    ): Promise<TimelineResponse> {
        try {
            const params = new URLSearchParams({
                date,
                device_filter: deviceFilter
            });

            const response = await fetch(
                `${API_BASE_URL}/dashboard/timeline?${params.toString()}`
            );

            if (!response.ok) {
                throw new Error(`Failed to fetch timeline data: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error fetching timeline data:', error);
            throw error;
        }
    }

    /**
     * 更新事件的分类
     * @param eventId 事件ID
     * @param categoryId 分类ID
     * @param subCategoryId 子分类ID (可选)
     */
    static async updateEventCategory(
        eventId: string,
        categoryId: string,
        subCategoryId?: string | null
    ): Promise<{ success: boolean; message: string }> {
        try {
            const params = new URLSearchParams({
                category_id: categoryId
            });
            if (subCategoryId) {
                params.append('sub_category_id', subCategoryId);
            }

            const response = await fetch(
                `${API_BASE_URL}/dashboard/timeline/events/${eventId}?${params.toString()}`,
                {
                    method: 'PATCH',
                    headers: {
                        'Content-Type': 'application/json',
                    }
                }
            );

            if (!response.ok) {
                throw new Error(`Failed to update event category: ${response.statusText}`);
            }

            return await response.json();
        } catch (error) {
            console.error('Error updating event category:', error);
            throw error;
        }
    }
}
