/**
 * 数据同步配置类型定义
 */

/** 生成云端配置响应 */
export interface GenerateCloudConfigResponse {
    /** 生成的配置文件路径 */
    cloud_config_path: string;
    /** 同步 API Key 是否为新生成 */
    key_is_new: boolean;
}

/** 打开文件夹并选中文件的结果 */
export interface OpenFolderResult {
    success: boolean;
}

/** 同步状态 */
export interface SyncStatus {
    /** 上次同步时间（ISO 8601 格式） */
    last_sync_time: string;
    /** 同步状态：idle=空闲/已同步, syncing=同步中, error=同步错误 */
    status: 'idle' | 'syncing' | 'error';
    /** 远程服务器地址 */
    remote_url: string;
    /** 各表的同步记录数 */
    tables: Record<string, number>;
}

/** 手动触发同步的响应 */
export interface TriggerSyncResponse {
    /** 提示消息 */
    message: string;
    /** 同步状态 */
    status: string;
}

/** 重置同步进度的响应 */
export interface ResetSyncProgressResponse {
    /** 提示消息 */
    message: string;
}

// ==================== SSH 隧道相关类型 ====================

/** 同步连接方式 */
export type ConnectionMode = 'http' | 'ssh';

/** SSH 隧道配置参数（用户输入） */
export interface SSHTunnelConfig {
    /** SSH 服务器地址（如 1.2.3.4） */
    host: string;
    /** SSH 端口，默认 22 */
    port: number;
    /** SSH 用户名（如 lifeprism） */
    username: string;
    /** 本地监听端口，默认 8102 */
    local_port: number;
    /** 远程目标端口，默认 8102 */
    remote_port: number;
}

/** POST /api/v2/settings/ssh-tunnel/enable 响应 */
export interface EnableSshTunnelResponse {
    /** 公钥字符串（OpenSSH 格式，以 `ssh-ed25519 ` 开头） */
    public_key: string;
    /** 本次是否新生成了密钥对（True=新生成，False=保留已有私钥） */
    is_new: boolean;
}

/** GET /api/v2/settings/ssh-tunnel/public-key 响应 */
export interface GetPublicKeyResponse {
    /** 公钥字符串（OpenSSH 格式），无私钥时为空字符串 */
    public_key: string;
}

/** POST /api/v2/settings/ssh-tunnel/test 请求参数 */
export interface SSHTunnelTestParams {
    /** SSH 服务器地址 */
    host: string;
    /** SSH 端口 */
    port: number;
    /** SSH 用户名 */
    username: string;
    /** 本地监听端口 */
    local_port: number;
    /** 远程目标端口 */
    remote_port: number;
}

/** POST /api/v2/settings/ssh-tunnel/test 响应 */
export interface SSHTunnelTestResponse {
    /** 测试结果：ok=成功，error=失败 */
    status: 'ok' | 'error';
    /** 成功时远程服务响应（健康检查数据） */
    remote_response?: Record<string, unknown>;
    /** 失败时的错误消息 */
    error?: string;
    /** 失败时的错误码（如 SSH_KEY_REJECTED / SSH_NETWORK_UNREACHABLE 等） */
    code?: string;
}
