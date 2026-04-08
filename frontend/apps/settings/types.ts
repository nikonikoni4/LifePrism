/**
 * Settings Page Types
 * 
 * 与后端 setting_schemas.py 对应的类型定义
 */

export interface ProviderModelHistory {
    api_base: string;
    models: string[];
}

export interface ProviderInfo {
    name: string;
    display_name: string;
    default_model: string;
    default_api_base: string;
    has_api_key: boolean;
}

export interface ProviderListResponse {
    providers: ProviderInfo[];
}

/** 完整配置项 (对应后端 SettingItems) */
export interface Settings {
    user_name: string;
    api_key: string | null;  // 脱敏显示
    provider: string;
    provider_list: string[];  // 支持的模型服务商列表
    provider_id_map: Record<string, string>;  // 服务商显示名称到 ID 的映射
    model: string;
    api_base: string;
    model_history: Record<string, ProviderModelHistory>;  // 按服务商存储的模型历史
    input_tokens_cost: number;
    output_tokens_cost: number;
    classification_mode: string;
    long_log_threshold: number;
    multi_purpose_app_names: string[];
    aw_db_path: string;
    lifeprism_data_path: string;
    config_base_path: string;
    data_cleaning_threshold: number;
}

/** 获取配置响应 */
export interface SettingsResponse {
    settings: Settings;
    message: string;
}

/** 更新配置请求 (部分更新) */
export interface UpdateSettingsRequest {
    user_name?: string;
    provider?: string;
    model?: string;
    api_base?: string;
    input_tokens_cost?: number;
    output_tokens_cost?: number;
    classification_mode?: string;
    long_log_threshold?: number;
    multi_purpose_app_names?: string[];
    aw_db_path?: string;
    lifeprism_data_path?: string;
    data_cleaning_threshold?: number;
}

/** 更新 API Key 请求 */
export interface UpdateApiKeyRequest {
    api_key: string;
    provider_id?: string;
}

/** 更新 API Key 响应 */
export interface UpdateApiKeyResponse {
    success: boolean;
    message: string;
}

/** API Key 状态响应 */
export interface ApiKeyStatusResponse {
    configured: boolean;
    message: string;
}

/** LLM 连接测试响应 */
export interface TestConnectionResponse {
    success: boolean;
    message: string;
    model_response: string | null;
}

/** 路径验证请求 */
export interface ValidatePathRequest {
    path: string;
    path_type: 'lifeprism_data' | 'aw_db';
}

/** 路径验证响应 */
export interface ValidatePathResponse {
    valid: boolean;
    message: string;
}

/** 数据路径迁移请求 */
export interface MigrateDataPathRequest {
    target_base_path: string;
    migrate_data?: boolean;
}

/** 数据路径迁移响应 */
export interface MigrateDataPathResponse {
    success: boolean;
    message: string;
    new_path: string | null;
}
