/**
 * 自定义记录模块类型定义
 * 对应后端 schemas/custom_records_schemas.py
 */

// ==================== 字段定义 ====================

export interface FieldDefinition {
  id?: string;
  field_name: string;
  field_key: string;
  field_type: string;
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
  created_at: string;
  updated_at: string;
  [key: string]: string; // 动态字段
}

export interface CustomRecordEntryListResponse {
  items: CustomRecordEntryItem[];
  total: number;
}

export interface CreateCustomRecordEntryRequest {
  data: Record<string, string>;
}

export interface GetEntriesParams {
  start_date?: string;
  end_date?: string;
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
