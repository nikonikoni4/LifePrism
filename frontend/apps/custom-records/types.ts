/**
 * 自定义记录模块类型定义
 * 对应后端 schemas/custom_records_schemas.py
 */

// ==================== 字段定义 ====================

export interface FieldDefinition {
  field_name: string;
  field_key: string;
  field_type: string;
}

// ==================== 类型管理 ====================

export interface CustomRecordTypeItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  fields: FieldDefinition[];
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
