/**
 * Custom Block API Service
 * 
 * 调用后端 /api/v2/timeline/custom-blocks 相关接口
 */

import {
    UserCustomBlock,
    UserCustomBlockCreate,
    UserCustomBlockUpdate,
    UserCustomBlockListResponse,
    UserCustomBlockResponse,
} from './types';

const API_BASE = 'http://localhost:8000/api/v2';

export const CustomBlockAPI = {
    /**
     * 创建自定义时间块
     * 
     * @param data 创建数据
     * @returns 创建的时间块（包含服务端生成的 id、category/sub_category 名称、color）
     */
    async create(data: UserCustomBlockCreate): Promise<UserCustomBlock> {
        const response = await fetch(`${API_BASE}/timeline/custom-blocks`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`Failed to create custom block: ${response.statusText}`);
        }

        const result: UserCustomBlockResponse = await response.json();
        return result.data;
    },

    /**
     * 按日期获取自定义时间块列表
     * 
     * @param date 查询日期 (YYYY-MM-DD)
     * @returns 时间块列表
     */
    async getByDate(date: string): Promise<UserCustomBlock[]> {
        const params = new URLSearchParams({ date });
        const response = await fetch(`${API_BASE}/timeline/custom-blocks?${params.toString()}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch custom blocks: ${response.statusText}`);
        }

        const result: UserCustomBlockListResponse = await response.json();
        return result.data;
    },

    /**
     * 获取单条自定义时间块
     * 
     * @param blockId 时间块 ID
     * @returns 时间块数据
     */
    async getById(blockId: number): Promise<UserCustomBlock> {
        const response = await fetch(`${API_BASE}/timeline/custom-blocks/${blockId}`);

        if (!response.ok) {
            throw new Error(`Failed to fetch custom block: ${response.statusText}`);
        }

        const result: UserCustomBlockResponse = await response.json();
        return result.data;
    },

    /**
     * 更新自定义时间块
     * 
     * @param blockId 时间块 ID
     * @param data 更新数据（部分更新）
     * @returns 更新后的时间块
     */
    async update(blockId: number, data: UserCustomBlockUpdate): Promise<UserCustomBlock> {
        const response = await fetch(`${API_BASE}/timeline/custom-blocks/${blockId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            throw new Error(`Failed to update custom block: ${response.statusText}`);
        }

        const result: UserCustomBlockResponse = await response.json();
        return result.data;
    },

    /**
     * 删除自定义时间块
     * 
     * @param blockId 时间块 ID
     * @returns 删除成功状态
     */
    async delete(blockId: number): Promise<boolean> {
        const response = await fetch(`${API_BASE}/timeline/custom-blocks/${blockId}`, {
            method: 'DELETE',
        });

        if (!response.ok) {
            throw new Error(`Failed to delete custom block: ${response.statusText}`);
        }

        const result = await response.json();
        return result.success;
    },
};
