/**
 * 自定义记录模块类型定义
 * 对应后端 schemas/custom_records_schemas.py
 */

// ==================== 字段定义 ====================

/** 字段类型：text 文本 / integer 整数 / float 浮点数 */
export type FieldType = 'text' | 'integer' | 'float';

export interface FieldDefinition {
  id?: string;
  field_name: string;
  field_key: string;
  field_type: FieldType;
  display_role?: string; // auto|title|main|chip|hidden
}

// ==================== 类型管理 ====================

export interface CustomRecordTypeItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  fields: FieldDefinition[];
  card_template?: string; // Slice 6: clean|paper|minimal|bold|metric
  icon?: string; // Slice 6: 图标名
  accent_color?: string; // Slice 6: 强调色
  created_at: string;
  updated_at: string;
}

export interface CustomRecordTypeListResponse {
  items: CustomRecordTypeItem[];
}

export interface CreateCustomRecordTypeRequest {
  name: string;
  slug: string;
  fields: FieldDefinition[];
  description?: string;
}

// ==================== 记录管理 ====================

export interface CustomRecordEntryItem {
  id: string;
  event_time: string;
  created_at: string;
  updated_at: string;
  [key: string]: string | number | undefined; // 动态字段（含数值字段）
}

export interface CustomRecordEntryListResponse {
  items: CustomRecordEntryItem[];
  total: number;
}

export interface CreateCustomRecordEntryRequest {
  data: Record<string, string | number>;
}

/**
 * 更新自定义记录请求（PATCH 三态语义）
 *
 * 顶层字段三态（由 Service model_dump(exclude_unset=True) 区分）：
 *   - data 未传（key 不在对象中） → 不修改任何字段值
 *   - data 传 null → 后端报错 422（不支持整体清空，前端不应传 null）
 *   - data 传 {} → 仅刷 updated_at
 *   - data 传 {key: null/val} → 按 dict 内 key 三态处理
 *   - event_time 未传 → 不修改 event_time
 *   - event_time 传 null → 后端报错 422（不允许清空，前端不应传 null）
 *   - event_time 传 str → 更新
 *
 * dict 内 key 三态（由前端 buildUpdatePayload diff 实现）：
 *   - key 不在 data 中 → 不修改该字段
 *   - key 在 data 中，值为 null → 清空该字段（写入 NULL）
 *   - key 在 data 中，值为具体值 → 更新该字段为新值
 */
export interface UpdateCustomRecordEntryRequest {
  data: Record<string, string | number | null>;
  event_time?: string; // UTC ISO 8601；不传=不修改，传 null=后端 422
}

export interface GetEntriesParams {
  start_time?: string;
  end_time?: string;
  page?: number;
  page_size?: number;
}

// ==================== 配置更新 (Slice 6) ====================

export interface UpdateTypeConfigRequest {
  card_template?: string;
  icon?: string;
  accent_color?: string;
}

export interface UpdateFieldRoleRequest {
  display_role: string;
}
