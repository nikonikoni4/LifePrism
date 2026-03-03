import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import {
    CheckInResponse,
    CancelCheckInResponse,
    BackfillCheckInRequest,
    BackfillAvailabilityRequest,
    BackfillAvailabilityResponse,
} from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

export const checkinApi = {
    /**
     * 今日打卡
     */
    checkInToday: async (habitId: string): Promise<CheckInResponse> => {
        return fetchApi<CheckInResponse>(`${getApiBase()}/habits/${habitId}/checkins`, {
            method: 'POST',
        });
    },

    /**
     * 取消某日的打卡
     * @param date format: YYYY-MM-DD
     */
    undoCheckIn: async (habitId: string, date: string): Promise<CancelCheckInResponse> => {
        return fetchApi<CancelCheckInResponse>(`${getApiBase()}/habits/${habitId}/checkins/${date}`, {
            method: 'DELETE',
        });
    },

    /**
     * 补录某日的打卡（用于挽救失败的挑战）
     */
    backfillCheckIn: async (habitId: string, request: BackfillCheckInRequest): Promise<CheckInResponse> => {
        return fetchApi<CheckInResponse>(`${getApiBase()}/habits/${habitId}/checkins/backfill`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 获取补录界面的可选日期（近7天）
     */
    getBackfillAvailability: async (request: BackfillAvailabilityRequest): Promise<BackfillAvailabilityResponse> => {
        return fetchApi<BackfillAvailabilityResponse>(`${getApiBase()}/checkins/backfill/availability`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },
};
