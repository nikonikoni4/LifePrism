import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import {
    TodayOverviewResponse,
    WeeklyStatsResponse,
    HeatmapResponse,
} from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

export const statsApi = {
    /**
     * 获取全局今日概览
     */
    getTodayOverview: async (): Promise<TodayOverviewResponse> => {
        return fetchApi<TodayOverviewResponse>(`${getApiBase()}/stats/today`);
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
    getHeatmapOverview: async (startDate?: string, endDate?: string): Promise<HeatmapResponse> => {
        const queryParams = new URLSearchParams();
        if (startDate && startDate !== 'undefined') queryParams.append('start_date', startDate);
        if (endDate && endDate !== 'undefined') queryParams.append('end_date', endDate);

        const queryString = queryParams.toString();
        const url = queryString ? `${getApiBase()}/stats/heatmap?${queryString}` : `${getApiBase()}/stats/heatmap`;

        return fetchApi<HeatmapResponse>(url);
    },
};
