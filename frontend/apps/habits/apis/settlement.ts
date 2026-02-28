import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import { SettlementItem, BackfillCheckInRequest, CheckInResponse } from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

export const settlementApi = {
    /**
     * 打开习惯界面时的结算检查。如果触发了结算流程，后端自动处理相关习惯等级，返回结算汇总供用户查阅。
     */
    checkSettlements: async (): Promise<SettlementItem[]> => {
        const data = await fetchApi<SettlementItem[]>(`${getApiBase()}/check-settlements`, {
            method: 'POST',
        });
        return Array.isArray(data) ? data : [];
    },

    /**
     * 为给定的过去几天中某一天进行补录
     * 这是失败挽救流程重要的一步
     */
    backfillCheckIn: async (habitId: string, request: BackfillCheckInRequest): Promise<CheckInResponse> => {
        return fetchApi<CheckInResponse>(`${getApiBase()}/habits/${habitId}/checkins/backfill`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },
};
