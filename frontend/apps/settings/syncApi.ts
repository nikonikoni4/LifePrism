/**
 * 数据同步配置 API
 *
 * 提供云端配置生成和云端地址管理的接口：
 * - POST /api/sync/generate-cloud-config: 生成 cloud_init.yaml
 * - PATCH /api/v2/settings: 保存 sync_remote_url（复用设置 API）
 * - GET  /api/v2/settings: 读取 sync_remote_url
 * - GET  /api/sync/status: 获取同步状态
 * - POST /api/sync/trigger: 手动触发同步
 * - Electron IPC open-folder-and-select: 打开文件夹并选中文件
 */

import { createApiV2UrlGetter, getApiBaseUrlSync } from '../../core/services/apiConfig';
import type { GenerateCloudConfigResponse, OpenFolderResult, SyncStatus, TriggerSyncResponse } from './syncTypes';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiV2Base = createApiV2UrlGetter();

export const SyncConfigAPI = {
    /**
     * 生成云端配置文件 cloud_init.yaml
     *
     * 调用后端 POST /api/sync/generate-cloud-config，
     * 从 keyring 读取所有 Key 并生成完整配置文件。
     *
     * @returns {cloud_config_path, key_is_new}
     */
    async generateCloudConfig(): Promise<GenerateCloudConfigResponse> {
        const response = await fetch(`${getApiBaseUrlSync()}/api/sync/generate-cloud-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `生成云端配置失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 保存云端地址到 config.yaml::sync.remote_url
     *
     * 复用 PATCH /api/v2/settings 接口，传入 sync_remote_url 字段。
     *
     * @param url 云端服务器地址
     */
    async saveRemoteUrl(url: string): Promise<void> {
        const response = await fetch(`${getApiV2Base()}/settings`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sync_remote_url: url }),
        });
        if (!response.ok) {
            throw new Error(`保存云端地址失败: ${response.statusText}`);
        }
    },

    /**
     * 从设置 API 读取云端地址
     *
     * @returns 云端地址字符串，未设置时返回空字符串
     */
    async getRemoteUrl(): Promise<string> {
        const response = await fetch(`${getApiV2Base()}/settings`);
        if (!response.ok) {
            throw new Error(`获取云端地址失败: ${response.statusText}`);
        }
        const data = await response.json();
        return data.settings?.sync_remote_url || '';
    },

    /**
     * 调用 Electron IPC 打开文件夹并选中文件
     *
     * Windows 上使用 shell.showItemInFolder 在资源管理器中选中文件。
     * 非 Electron 环境下返回 {success: false}。
     *
     * @param filePath 要选中的文件完整路径
     * @returns 操作结果
     */
    async openFolderAndSelect(filePath: string): Promise<OpenFolderResult> {
        if (!window.electronAPI?.openFolderAndSelect) {
            return { success: false };
        }
        return window.electronAPI.openFolderAndSelect(filePath);
    },

    /**
     * 获取同步状态
     *
     * 调用后端 GET /api/sync/status，
     * 返回上次同步时间、同步状态、远程地址和各表记录数。
     *
     * @returns 同步状态信息
     */
    async getSyncStatus(): Promise<SyncStatus> {
        const response = await fetch(`${getApiBaseUrlSync()}/api/sync/status`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `获取同步状态失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 手动触发同步
     *
     * 调用后端 POST /api/sync/trigger，
     * 触发一次数据同步操作。
     *
     * @returns 触发结果
     */
    async triggerSync(): Promise<TriggerSyncResponse> {
        const response = await fetch(`${getApiBaseUrlSync()}/api/sync/trigger`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (response.status === 409) {
            // 同步已在进行中，视为预期情况而非错误
            const data = await response.json();
            return data;
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `触发同步失败: ${response.statusText}`);
        }
        return response.json();
    },
};
