import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';

const getValueBase = createApiV2UrlGetter('/value');
const getCommitmentBase = createApiV2UrlGetter('/commitment');

export interface ValueOption {
    id: string;
    keyword: string;
}

export interface CommitmentOption {
    id: string;
    content: string;
    value_id: string;
}

export const mindspaceApi = {
    getValues: async (): Promise<ValueOption[]> => {
        const response: any = await fetchApi(`${getValueBase()}/`);
        return (response.items || []).map((v: any) => ({
            id: v.id,
            keyword: v.keyword,
        }));
    },
    getCommitments: async (valueId?: string): Promise<CommitmentOption[]> => {
        const queryParams = new URLSearchParams();
        if (valueId) queryParams.append('value_id', valueId);

        const queryString = queryParams.toString();
        const url = queryString ? `${getCommitmentBase()}/?${queryString}` : `${getCommitmentBase()}/`;

        const response: any = await fetchApi(url);
        return (response.items || []).map((c: any) => ({
            id: c.id,
            content: c.content,
            value_id: c.value_id,
        }));
    }
};
