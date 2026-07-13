/**
 * Timeline API
 * 
 * 调用后端 /api/v2/timeline 相关接口
 */

import {
    TimelineStatsResponse,
    TimelineTimeOverviewResponse,
    BehaviorAnalysisResponse,
} from './types';
import { createApiV2UrlGetter } from '../../../../core/services/apiConfig';
import { toISOStringUTC } from '../../../../core/utils/dateUtils';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiBase = createApiV2UrlGetter();

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
        // 就近转换：本地日期 → UTC 时间范围
        const startOfDay = new Date(`${date}T00:00:00`);
        const endOfDay = new Date(`${date}T23:59:59.999`);

        const params = new URLSearchParams({
            start_time: toISOStringUTC(startOfDay),
            end_time: toISOStringUTC(endOfDay),
            hour_granularity: hourGranularity.toString(),
            category_level: categoryLevel,
        });

        const response = await fetch(`${getApiBase()}/timeline/stats?${params.toString()}`);

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
        // 就近转换：本地日期+小时 → UTC 时间范围
        const startTime = new Date(`${date}T${String(startHour).padStart(2, '0')}:00:00`);
        const endTime = endHour === 24
            ? new Date(`${date}T23:59:59.999`)
            : new Date(`${date}T${String(endHour).padStart(2, '0')}:00:00`);

        const params = new URLSearchParams({
            start_time: toISOStringUTC(startTime),
            end_time: toISOStringUTC(endTime),
        });

        const response = await fetch(`${getApiBase()}/timeline/overview?${params.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch timeline overview: ${response.statusText}`);
        }

        return response.json();
    },
};

// ============================================================================
// 重导出 common API（用于非缩略图模式的活动日志）
// ============================================================================

export { ActivityLogsAPI, CategoryAPI } from '../../../../core/services/commonApi';

// ============================================================================
// Behavior Summary API
// ============================================================================

export const BehaviorAPI = {
    /**
     * 获取指定日期的行为分析数据
     *
     * @param date 查询日期 (YYYY-MM-DD)
     * @returns 行为分析列表
     */
    async getBehaviorSummary(date: string): Promise<BehaviorAnalysisResponse> {
        const params = new URLSearchParams({ date });
        const response = await fetch(
            `${getApiBase()}/timeline/behavior_summary?${params.toString()}`
        );

        if (!response.ok) {
            throw new Error(`Failed to fetch behavior summary: ${response.statusText}`);
        }

        return response.json();
    }
};
