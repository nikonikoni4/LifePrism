/**
 * Timeline API
 * 
 * 调用后端 /api/v2/timeline 相关接口
 */

import {
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
} from './types';

const API_BASE = 'http://localhost:8000/api/v2';

// ============================================================================
// Timeline V2 API - 缩略图相关
// ============================================================================

export const TimelineAPIV2 = {
    /**
     * 获取缩略图 Timeline 统计数据
     * 
     * @param date 查询日期 (YYYY-MM-DD)
     * @param hourGranularity 时间粒度（1-6 小时）
     * @param categoryLevel 分类级别 (main/sub)
     * @returns 时间块统计数据
     */
    async getStats(
        date: string,
        hourGranularity: number = 1,
        categoryLevel: 'main' | 'sub' = 'main'
    ): Promise<TimelineStatsResponse> {
        const params = new URLSearchParams({
            date,
            hour_granularity: hourGranularity.toString(),
            category_level: categoryLevel,
        });

        const response = await fetch(`${API_BASE}/timeline/stats?${params.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch timeline stats: ${response.statusText}`);
        }

        return response.json();
    },

    /**
     * 获取指定时间块的 Time Overview 详情
     * 
     * 点击缩略图时间块后，获取该时间范围内的详细活动分布
     * 
     * @param date 查询日期 (YYYY-MM-DD)
     * @param startHour 时间块开始小时（0-23）
     * @param endHour 时间块结束小时（1-24）
     * @returns TimeOverview 数据
     */
    async getOverview(
        date: string,
        startHour: number,
        endHour: number
    ): Promise<TimelineTimeOverviewResponse> {
        const params = new URLSearchParams({
            date,
            start_hour: startHour.toString(),
            end_hour: endHour.toString(),
        });

        const response = await fetch(`${API_BASE}/timeline/overview?${params.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch timeline overview: ${response.statusText}`);
        }

        return response.json();
    },
};

// ============================================================================
// 重导出 common API（用于非缩略图模式的活动日志）
// ============================================================================

export { ActivityLogsAPI, CategoryAPI } from '../common/api';
