import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { statsApi } from '../apis/stats';
import { TodayOverviewResponse, WeeklyRateItem, HeatmapDayItem } from '../types/backend';

interface StatsStoreContextType {
    todayOverview: TodayOverviewResponse | null;
    weeklyData: WeeklyRateItem[];
    heatmapData: HeatmapDayItem[];
    isLoading: boolean;
    error: string | null;

    fetchTodayOverview: () => Promise<void>;
    fetchWeeklyData: (weeks?: number) => Promise<void>;
    fetchHeatmapData: (days?: number) => Promise<void>;
    fetchAllStats: () => Promise<void>;
}

const StatsStoreContext = createContext<StatsStoreContextType | undefined>(undefined);

export const StatsProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
    const [todayOverview, setTodayOverview] = useState<TodayOverviewResponse | null>(null);
    const [weeklyData, setWeeklyData] = useState<WeeklyRateItem[]>([]);
    const [heatmapData, setHeatmapData] = useState<HeatmapDayItem[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const fetchTodayOverview = useCallback(async () => {
        try {
            const data = await statsApi.getTodayOverview();
            setTodayOverview(data);
        } catch (err) {
            console.error('[StatsStore] Failed to fetch today overview:', err);
        }
    }, []);

    const fetchWeeklyData = useCallback(async (weeks: number = 4) => {
        try {
            const data = await statsApi.getWeeklyOverview(weeks);
            setWeeklyData(data.weeks || []);
        } catch (err) {
            console.error('[StatsStore] Failed to fetch weekly data:', err);
        }
    }, []);

    const fetchHeatmapData = useCallback(async (days: number = 365) => {
        try {
            const data = await statsApi.getHeatmapOverview(days);
            setHeatmapData(data.days || []);
        } catch (err) {
            console.error('[StatsStore] Failed to fetch heatmap data:', err);
        }
    }, []);

    const fetchAllStats = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        const results = await Promise.allSettled([
            fetchTodayOverview(),
            fetchWeeklyData(4),
            fetchHeatmapData(365),
        ]);
        const failed = results.filter(r => r.status === 'rejected');
        if (failed.length > 0) {
            setError('部分统计数据加载失败');
        }
        setIsLoading(false);
    }, [fetchTodayOverview, fetchWeeklyData, fetchHeatmapData]);

    const value: StatsStoreContextType = {
        todayOverview,
        weeklyData,
        heatmapData,
        isLoading,
        error,
        fetchTodayOverview,
        fetchWeeklyData,
        fetchHeatmapData,
        fetchAllStats,
    };

    return React.createElement(StatsStoreContext.Provider, { value }, children);
};

export const useStatsStore = () => {
    const context = useContext(StatsStoreContext);
    if (!context) {
        throw new Error('useStatsStore must be used within a StatsProvider');
    }
    return context;
};
