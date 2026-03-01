import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import {
    TodayOverviewResponse,
    WeeklyRateItem,
    WeeklyStatsResponse,
    HeatmapDayItem,
    HeatmapResponse,
} from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

interface TodayOverviewApiResponse {
    overview?: {
        items?: Array<{
            isScheduledToday?: boolean;
            todayCheckedIn?: boolean;
        }>;
        scheduledCount?: number;
        completedCount?: number;
        completionRate?: number | null;
        isRestDay?: boolean;
    } | Array<{
        isScheduledToday?: boolean;
        todayCheckedIn?: boolean;
    }>;
    items?: Array<{
        isScheduledToday?: boolean;
        todayCheckedIn?: boolean;
    }>;
    scheduledCount?: number;
    completedCount?: number;
    completionRate?: number | null;
    isRestDay?: boolean;
}

interface WeeklyStatsApiResponse {
    weeks?: WeeklyRateItem[];
    completion_rate?: number;
    completionRate?: number;
}

interface HeatmapApiResponse {
    days?: HeatmapDayItem[];
    heatmap?: Array<{ date: string; count: number }>;
}

const clampRate = (value: number): number => Math.min(1, Math.max(0, value));

const toUnitRate = (value: number | null | undefined): number | null => {
    if (value == null || Number.isNaN(value)) return null;
    if (value > 1 && value <= 100) return clampRate(value / 100);
    return clampRate(value);
};

const toDateString = (d: Date): string => {
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
};

const normalizeTodayOverview = (raw: TodayOverviewApiResponse): TodayOverviewResponse => {
    const source = raw.overview ?? raw;
    const items = Array.isArray(source)
        ? source
        : (Array.isArray(source.items) ? source.items : (raw.items ?? []));

    const scheduledCount = Array.isArray(source)
        ? items.length
        : (source.scheduledCount ?? items.filter(item => item.isScheduledToday !== false).length);
    const completedCount = Array.isArray(source)
        ? items.filter(item => item.todayCheckedIn).length
        : (source.completedCount ?? items.filter(item => item.todayCheckedIn).length);
    const inferredRate = scheduledCount > 0 ? clampRate(completedCount / scheduledCount) : null;
    const normalizedRate = Array.isArray(source)
        ? null
        : toUnitRate(source.completionRate);

    return {
        scheduledCount,
        completedCount,
        completionRate: normalizedRate ?? inferredRate,
        isRestDay: Array.isArray(source) ? scheduledCount === 0 : (source.isRestDay ?? scheduledCount === 0),
    };
};

const normalizeWeeklyStats = (raw: WeeklyStatsApiResponse): WeeklyStatsResponse => {
    if (Array.isArray(raw.weeks)) {
        return { weeks: raw.weeks };
    }

    const rate = clampRate(raw.completionRate ?? raw.completion_rate ?? 0);
    const today = new Date();
    const dayOfWeek = (today.getDay() + 6) % 7; // 将周一映射为 0
    const weekStart = new Date(today);
    weekStart.setDate(today.getDate() - dayOfWeek);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 6);

    return {
        weeks: [{
            weekStartDate: toDateString(weekStart),
            weekEndDate: toDateString(weekEnd),
            rate,
            habitCount: 0,
        }],
    };
};

const normalizeHeatmap = (raw: HeatmapApiResponse): HeatmapResponse => {
    if (Array.isArray(raw.days)) {
        return { days: raw.days };
    }

    const fallback = raw.heatmap ?? [];
    const maxCount = fallback.reduce((max, item) => Math.max(max, item.count), 0);
    const days = fallback.map((item) => {
        const completionRate = maxCount > 0 ? clampRate(item.count / maxCount) : 0;
        return {
            date: item.date,
            totalHabits: maxCount,
            completedHabits: item.count,
            completionRate,
            isRestDay: item.count === 0,
        };
    });

    return { days };
};

export const statsApi = {
    /**
     * 获取全局今日概览
     */
    getTodayOverview: async (): Promise<TodayOverviewResponse> => {
        const raw = await fetchApi<TodayOverviewApiResponse>(`${getApiBase()}/stats/today`);
        return normalizeTodayOverview(raw);
    },

    /**
     * 获取全局每周完成率趋势
     */
    getWeeklyOverview: async (weeks: number = 12): Promise<WeeklyStatsResponse> => {
        const queryParams = new URLSearchParams();
        queryParams.append('weeks', weeks.toString());

        const raw = await fetchApi<WeeklyStatsApiResponse>(`${getApiBase()}/stats/weekly?${queryParams.toString()}`);
        return normalizeWeeklyStats(raw);
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

        const raw = await fetchApi<HeatmapApiResponse>(url);
        return normalizeHeatmap(raw);
    },
};
