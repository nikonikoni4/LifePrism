import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import { CheckSettlementsResponse, SettlementItem } from '../types/backend';
import { extractSettlementsFromResponse } from './settlementParser.js';

const getApiBase = createApiV2UrlGetter('/habit');

export const settlementApi = {
    /**
     * 打开习惯界面时的结算检查。如果触发了结算流程，后端自动处理相关习惯等级，返回结算汇总供用户查阅。
     */
    checkSettlements: async (): Promise<SettlementItem[]> => {
        const data = await fetchApi<CheckSettlementsResponse | SettlementItem[]>(`${getApiBase()}/check-settlements`, {
            method: 'POST',
        });
        return extractSettlementsFromResponse(data);
    },
};
