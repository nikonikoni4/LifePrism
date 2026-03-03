import { createApiV2UrlGetter } from '../../../core/services/apiConfig';
import { fetchApi } from './utils';
import {
    ChainListResponse,
    CreateChainRequest,
    UpdateChainRequest,
    CreateChainNodeRequest,
    UpdateChainNodeRequest,
    ReorderNodesRequest,
    TimelineResponse,
    ChainListItem,
    ChainNodeObject
} from '../types/backend';

const getApiBase = createApiV2UrlGetter('/habit');

export const chainApi = {
    // ---------------------------------
    // Chains
    // ---------------------------------

    /**
     * S9: 获取链条列表 (GET /chains)
     */
    getChains: async (showInTimeline?: boolean): Promise<ChainListResponse> => {
        const queryParams = new URLSearchParams();
        if (typeof showInTimeline === 'boolean') {
            queryParams.append('showInTimeline', String(showInTimeline));
        }

        const queryString = queryParams.toString();
        const url = queryString ? `${getApiBase()}/chains?${queryString}` : `${getApiBase()}/chains`;
        return fetchApi<ChainListResponse>(url);
    },

    /**
     * 获取单条链条记录 (GET /chains/:id)
     */
    getChain: async (chainId: number): Promise<ChainListItem> => {
        return fetchApi<ChainListItem>(`${getApiBase()}/chains/${chainId}`);
    },

    /**
     * S9: 创建新链条 (POST /chains)
     */
    createChain: async (request: CreateChainRequest): Promise<ChainListItem> => {
        return fetchApi<ChainListItem>(`${getApiBase()}/chains`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 基础链条更新：更新链条基本信息与 Timeline 状态 (PATCH /chains/:id)
     */
    updateChain: async (chainId: number, request: UpdateChainRequest): Promise<ChainListItem> => {
        return fetchApi<ChainListItem>(`${getApiBase()}/chains/${chainId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * S9: 删除链条 (DELETE /chains/:id)
     */
    deleteChain: async (chainId: number): Promise<void> => {
        await fetchApi<void>(`${getApiBase()}/chains/${chainId}`, {
            method: 'DELETE',
        });
    },

    // ---------------------------------
    // Chain Nodes
    // ---------------------------------

    /**
     * S10: 为链条插入子节点 (POST /chains/:id/nodes)
     */
    addChainNode: async (chainId: number, request: CreateChainNodeRequest): Promise<ChainNodeObject> => {
        return fetchApi<ChainNodeObject>(`${getApiBase()}/chains/${chainId}/nodes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 更新节点，可用于 Timeline 中更新单独触发时间 (PATCH /chains/:id/nodes/:nodeId)
     */
    updateChainNode: async (chainId: number, nodeId: number, request: UpdateChainNodeRequest): Promise<ChainNodeObject> => {
        return fetchApi<ChainNodeObject>(`${getApiBase()}/chains/${chainId}/nodes/${nodeId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 批量重新排序链条内的节点 (PATCH /chains/:id/nodes/reorder)
     */
    reorderNodes: async (chainId: number, request: ReorderNodesRequest): Promise<void> => {
        await fetchApi<void>(`${getApiBase()}/chains/${chainId}/nodes/reorder`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
    },

    /**
     * 删除链条内的单一节点 (DELETE /chains/:id/nodes/:nodeId)
     */
    deleteChainNode: async (chainId: number, nodeId: number): Promise<void> => {
        await fetchApi<void>(`${getApiBase()}/chains/${chainId}/nodes/${nodeId}`, {
            method: 'DELETE',
        });
    },

    // ---------------------------------
    // Timeline
    // ---------------------------------

    /**
     * S11: 获取时间轴展示，提取当前开启 showInTimeline=true 的全集 (GET /chains/timeline)
     */
    getTimeline: async (): Promise<TimelineResponse> => {
        return fetchApi<TimelineResponse>(`${getApiBase()}/chains/timeline`);
    }
};
