import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import {
    HabitListResponse,
    HabitDetailResponse,
    CreateHabitRequest,
    UpdateHabitRequest,
    SettlementActionRequest,
} from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

export const habitApi = {
    /**
     * 获取习惯列表
     */
    getHabits: async (status?: string): Promise<HabitListResponse> => {
        const queryParams = new URLSearchParams();
        if (status && status !== 'undefined') queryParams.append('status', status);

        const queryString = queryParams.toString();
        const url = queryString ? `${getApiBase()}/habits?${queryString}` : `${getApiBase()}/habits`;

        return fetchApi<HabitListResponse>(url);
    },

    /**
     * 获取指定习惯详情
     */
    getHabit: async (habitId: string): Promise<HabitDetailResponse> => {
        return fetchApi<HabitDetailResponse>(`${getApiBase()}/habits/${habitId}`);
    },

    /**
     * 创建习惯
     */
    createHabit: async (request: CreateHabitRequest): Promise<HabitDetailResponse> => {
        return fetchApi<HabitDetailResponse>(`${getApiBase()}/habits`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 更新习惯
     */
    updateHabit: async (habitId: string, request: UpdateHabitRequest): Promise<HabitDetailResponse> => {
        return fetchApi<HabitDetailResponse>(`${getApiBase()}/habits/${habitId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 暂停习惯
     */
    pauseHabit: async (
        habitId: string,
        settlementAction?: SettlementActionRequest,
    ): Promise<HabitDetailResponse> => {
        return fetchApi<HabitDetailResponse>(`${getApiBase()}/habits/${habitId}/pause`, {
            method: 'POST',
            ...(settlementAction
                ? {
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settlementAction),
                }
                : {}),
        });
    },

    /**
     * 恢复习惯
     */
    resumeHabit: async (
        habitId: string,
        settlementAction?: SettlementActionRequest,
    ): Promise<HabitDetailResponse> => {
        return fetchApi<HabitDetailResponse>(`${getApiBase()}/habits/${habitId}/resume`, {
            method: 'POST',
            ...(settlementAction
                ? {
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settlementAction),
                }
                : {}),
        });
    },

    /**
     * 删除习惯
     */
    deleteHabit: async (habitId: string): Promise<void> => {
        await fetchApi<void>(`${getApiBase()}/habits/${habitId}`, {
            method: 'DELETE',
        });
    },

    /**
     * 获取习惯挑战历史记录
     */
    getHabitHistory: async (habitId: string, status?: string): Promise<{ challenges: any[] }> => {
        const queryParams = new URLSearchParams();
        if (status) queryParams.append('status', status);

        const queryString = queryParams.toString();
        const url = queryString ? `${getApiBase()}/habits/${habitId}/challenges?${queryString}` : `${getApiBase()}/habits/${habitId}/challenges`;

        return fetchApi<{ challenges: any[] }>(url);
    },
};
