/**
 * 数据同步配置 API
 *
 * 提供云端配置生成和云端地址管理的接口：
 * - POST /api/sync/generate-cloud-config: 生成 cloud_init.yaml
 * - PATCH /api/v2/settings: 保存 sync_remote_url（复用设置 API）
 * - GET  /api/v2/settings: 读取 sync_remote_url
 * - GET  /api/sync/status: 获取同步状态
 * - POST /api/sync/trigger: 手动触发同步
 * - POST /api/sync/reset-sync-progress: 重置同步进度（清空 last_sync_time，下次同步变为全量同步）
 * - Electron IPC open-folder-and-select: 打开文件夹并选中文件
 */

import { createApiV2UrlGetter, getApiBaseUrlSync } from '../../core/services/apiConfig';
import type {
    ConnectionMode,
    EnableSshTunnelResponse,
    GenerateCloudConfigResponse,
    GetPublicKeyResponse,
    OpenFolderResult,
    ResetSyncProgressResponse,
    SSHTunnelTestParams,
    SSHTunnelTestResponse,
    SyncStatus,
    TriggerSyncResponse,
} from './syncTypes';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiV2Base = createApiV2UrlGetter();

export const SyncConfigAPI = {
    /**
     * 生成云端配置文件 cloud_init.yaml
     *
     * 调用后端 POST /api/sync/generate-cloud-config，
     * 从 keyring 读取所有 Key 并生成完整配置文件。
     *
     * @param replaceKey 是否强制重新生成 sync_api_key（默认 false）
     * @returns {cloud_config_path, key_is_new}
     */
    async generateCloudConfig(replaceKey?: boolean): Promise<GenerateCloudConfigResponse> {
        const response = await fetch(`${getApiBaseUrlSync()}/api/sync/generate-cloud-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ replace_key: replaceKey ?? false }),
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

    /**
     * 重置同步进度（清空 last_sync_time）
     *
     * 调用后端 POST /api/sync/reset-sync-progress，
     * 清空本地的 last_sync_time，使下次同步变为全量同步。
     * 适用场景：换服务器、云端数据库重置、本地数据库重置后需要全量同步。
     *
     * @returns 重置结果消息
     */
    async resetSyncProgress(): Promise<ResetSyncProgressResponse> {
        const response = await fetch(`${getApiBaseUrlSync()}/api/sync/reset-sync-progress`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (response.status === 409) {
            // 同步进行中，无法重置
            const data = await response.json();
            throw new Error(data.message || '同步正在进行中，无法重置进度');
        }
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `重置同步进度失败: ${response.statusText}`);
        }
        return response.json();
    },

    // ==================== SSH 隧道相关 API ====================

    /**
     * 启用 SSH 隧道模式（自动准备密钥）
     *
     * 调用后端 POST /api/v2/settings/ssh-tunnel/enable，
     * 如 keyring 中无私钥则自动生成 ed25519 密钥对（私钥存 keyring），
     * 如有私钥则保留不覆盖。返回当前公钥（从私钥实时派生）。
     *
     * @returns {public_key, is_new}
     */
    async enableSshTunnel(): Promise<EnableSshTunnelResponse> {
        const response = await fetch(`${getApiV2Base()}/settings/ssh-tunnel/enable`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `启用 SSH 隧道失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 获取 SSH 公钥（从 keyring 私钥实时派生）
     *
     * 调用后端 GET /api/v2/settings/ssh-tunnel/public-key，
     * 用于前端进入 SSH 配置页面时加载展示。keyring 无私钥时返回空字符串。
     *
     * @returns {public_key}
     */
    async getPublicKey(): Promise<GetPublicKeyResponse> {
        const response = await fetch(`${getApiV2Base()}/settings/ssh-tunnel/public-key`, {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' },
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `获取 SSH 公钥失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 测试 SSH 隧道连接 + 远程 8102 可达性
     *
     * 调用后端 POST /api/v2/settings/ssh-tunnel/test，
     * 一次性测试：建立 SSH 连接 → 启动本地端口转发 → 验证远程健康端点 → 关闭连接。
     * 私钥不通过请求体传递，从 keyring 读取。
     *
     * @param params SSH 连接参数（host/port/username/local_port/remote_port）
     * @returns 测试结果 {status: 'ok' | 'error', ...}
     */
    async testConnection(params: SSHTunnelTestParams): Promise<SSHTunnelTestResponse> {
        const response = await fetch(`${getApiV2Base()}/settings/ssh-tunnel/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params),
        });
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `测试 SSH 连接失败: ${response.statusText}`);
        }
        return response.json();
    },

    /**
     * 保存同步连接方式到 config.yaml::sync.connection_mode
     *
     * 复用 PATCH /api/v2/settings 接口，传入 sync_connection_mode 字段。
     * 切换 HTTP/HTTPS ↔ SSH 模式时自动调用，无需额外点击保存按钮。
     *
     * @param mode 连接方式：'http' | 'ssh'
     */
    async saveConnectionMode(mode: ConnectionMode): Promise<void> {
        const response = await fetch(`${getApiV2Base()}/settings`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ sync_connection_mode: mode }),
        });
        if (!response.ok) {
            throw new Error(`保存连接方式失败: ${response.statusText}`);
        }
    },

    /**
     * 从设置 API 读取同步连接方式
     *
     * @returns 连接方式：'http' | 'ssh'，未设置时返回 'http'（默认值）
     */
    async getConnectionMode(): Promise<ConnectionMode> {
        const response = await fetch(`${getApiV2Base()}/settings`);
        if (!response.ok) {
            throw new Error(`获取连接方式失败: ${response.statusText}`);
        }
        const data = await response.json();
        const mode = data.settings?.sync_connection_mode;
        return mode === 'ssh' ? 'ssh' : 'http';
    },
};
