import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import {
    TodayOverviewResponse,
    WeeklyStatsResponse,
    HeatmapResponse,
} from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

interface TodayOverviewItem {
    isScheduledToday: boolean;
    todayCheckedIn: boolean;
}

interface TodayStatsApiResponse {
    overview: TodayOverviewItem[];
}

const normalizeTodayOverview = (raw: TodayStatsApiResponse): TodayOverviewResponse => {
    const items = raw.overview ?? [];
    const scheduledCount = items.filter(item => item.isScheduledToday).length;
    const completedCount = items.filter(item => item.todayCheckedIn).length;
    const completionRate = scheduledCount > 0 ? completedCount / scheduledCount : null;

    return {
        scheduledCount,
        completedCount,
        completionRate,
        isRestDay: scheduledCount === 0,
    };
};

export const statsApi = {
    /**
     * 获取全局今日概览
     */
    getTodayOverview: async (): Promise<TodayOverviewResponse> => {
        const raw = await fetchApi<TodayStatsApiResponse>(`${getApiBase()}/stats/today`);
        return normalizeTodayOverview(raw);
    },

    /**
     * 获取全局每周完成率趋势
     */
    getWeeklyOverview: async (weeks: number = 12): Promise<WeeklyStatsResponse> => {
        const queryParams = new URLSearchParams();
        queryParams.append('weeks', weeks.toString());

        return fetchApi<WeeklyStatsResponse>(`${getApiBase()}/stats/weekly?${queryParams.toString()}`);
    },

    /**
     * 获取热力图执行分布
     */
    getHeatmapOverview: async (days: number = 365): Promise<HeatmapResponse> => {
        const queryParams = new URLSearchParams();
        queryParams.append('days', days.toString());

        return fetchApi<HeatmapResponse>(`${getApiBase()}/stats/heatmap?${queryParams.toString()}`);
    },
};
