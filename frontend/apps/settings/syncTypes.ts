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
