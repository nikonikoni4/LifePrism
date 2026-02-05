/**
 * Settings Page Types
 * 
 * 与后端 setting_schemas.py 对应的类型定义
 */

/** 完整配置项 (对应后端 SettingItems) */
export interface Settings {
    user_name: string;
    api_key: string | null;  // 脱敏显示
    provider: string;
    provider_list: string[];  // 支持的模型服务商列表
    model: string;
    model_history: Record<string, string[]>;  // 按服务商存储的模型历史
    input_tokens_cost: number;
    output_tokens_cost: number;
    classification_mode: string;
    long_log_threshold: number;
    multi_purpose_app_names: string[];
    aw_db_path: string;
    lw_db_path: string;
    chat_db_path: string;
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
    input_tokens_cost?: number;
    output_tokens_cost?: number;
    classification_mode?: string;
    long_log_threshold?: number;
    multi_purpose_app_names?: string[];
    aw_db_path?: string;
    lw_db_path?: string;
    chat_db_path?: string;
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
