import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import { CheckInResponse, CancelCheckInResponse } from '../types/backend';

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
};
