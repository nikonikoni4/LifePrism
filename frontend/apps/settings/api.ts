/**
 * Settings Page API
 * 
 * 配置管理接口
 */

import {
    Settings,
    SettingsResponse,
    UpdateSettingsRequest,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
    ApiKeyStatusResponse,
    TestConnectionResponse,
    ValidatePathRequest,
    ValidatePathResponse,
    MigrateDataPathRequest,
    MigrateDataPathResponse,
} from './types';
import { createApiV2UrlGetter } from '../../core/services/apiConfig';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiBase = createApiV2UrlGetter();

/**
 * Settings API
 */
export const SettingsAPI = {
    /**
     * 获取配置
     */
    async getSettings(): Promise<Settings> {
        const response = await fetch(`${getApiBase()}/settings`);
        if (!response.ok) {
            throw new Error(`获取配置失败: ${response.statusText}`);
        }
        const data: SettingsResponse = await response.json();
        return data.settings;
    },

    /**
     * 更新配置 (部分更新)
     */
    async updateSettings(settings: UpdateSettingsRequest): Promise<Settings> {
        const response = await fetch(`${getApiBase()}/settings`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings),
        });
        if (!response.ok) {
            throw new Error(`更新配置失败: ${response.statusText}`);
        }
        const data: SettingsResponse = await response.json();
        return data.settings;
    },

    /**
     * 更新 API Key (安全存储到 keyring)
     * @param apiKey API Key
     * @param providerId 服务商 ID，如 aliyun, volcengine, openai 等
     */
    async updateApiKey(apiKey: string, providerId?: string): Promise<UpdateApiKeyResponse> {
        const response = await fetch(`${getApiBase()}/settings/api-key`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key: apiKey, provider_id: providerId } as UpdateApiKeyRequest),
        });
        if (!response.ok) {
            throw new Error(`更新 API Key 失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 检查 API Key 配置状态
     */
    async checkApiKeyStatus(): Promise<ApiKeyStatusResponse> {
        const response = await fetch(`${getApiBase()}/settings/api-key/status`);
        if (!response.ok) {
            throw new Error(`检查 API Key 状态失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 测试 LLM 连接
     */
    async testConnection(): Promise<TestConnectionResponse> {
        const response = await fetch(`${getApiBase()}/settings/test-connection`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `连接测试失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 删除模型历史记录
     * @param providerId 服务商 ID
     * @param model 模型名称/ID
     */
    async deleteModelHistory(providerId: string, model: string): Promise<{ success: boolean; message: string }> {
        const params = new URLSearchParams({ provider_id: providerId, model });
        const response = await fetch(`${getApiBase()}/settings/model-history?${params}`, {
            method: 'DELETE',
        });
        if (!response.ok) {
            throw new Error(`删除模型历史失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 验证路径有效性
     */
    async validatePath(request: ValidatePathRequest): Promise<ValidatePathResponse> {
        const response = await fetch(`${getApiBase()}/settings/validate-path`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
        if (!response.ok) {
            throw new Error(`路径验证失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 迁移数据路径
     * 将数据从当前路径迁移到新路径（自动追加 lifeprismData 子文件夹）
     */
    async migrateDataPath(request: MigrateDataPathRequest): Promise<MigrateDataPathResponse> {
        const response = await fetch(`${getApiBase()}/settings/migrate-data-path`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(request),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `数据迁移失败: ${response.statusText}`);
        }
        return response.json();
    },
};
