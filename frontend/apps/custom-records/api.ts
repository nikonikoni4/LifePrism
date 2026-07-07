/**
 * 自定义记录模块 API 服务
 * 对接后端 /custom-records 路由
 */
import { createApiV2UrlGetter } from '../../core/services/apiConfig';
import type {
  CustomRecordTypeItem,
  CustomRecordTypeListResponse,
  CreateCustomRecordTypeRequest,
  CustomRecordEntryItem,
  CustomRecordEntryListResponse,
  CreateCustomRecordEntryRequest,
  GetEntriesParams,
} from './types';

const getApiBase = createApiV2UrlGetter('/custom-records');

export const CustomRecordsAPI = {
  // ==================== 类型管理 ====================

  async getTypes(): Promise<CustomRecordTypeItem[]> {
    const res = await fetch(`${getApiBase()}/types`);
    if (!res.ok) throw new Error(`获取类型列表失败: ${res.statusText}`);
    const data: CustomRecordTypeListResponse = await res.json();
    return data.items;
  },

  async createType(req: CreateCustomRecordTypeRequest): Promise<CustomRecordTypeItem> {
    const res = await fetch(`${getApiBase()}/types`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`创建类型失败: ${res.statusText}`);
    return res.json();
  },

  async getTypeById(typeId: string): Promise<CustomRecordTypeItem> {
    const res = await fetch(`${getApiBase()}/types/${typeId}`);
    if (!res.ok) throw new Error(`获取类型详情失败: ${res.statusText}`);
    return res.json();
  },

  async deleteType(typeId: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/types/${typeId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`删除类型失败: ${res.statusText}`);
  },

  // ==================== 记录管理 ====================

  async getEntries(typeId: string, params?: GetEntriesParams): Promise<CustomRecordEntryListResponse> {
    const query = new URLSearchParams();
    if (params?.start_date) query.set('start_date', params.start_date);
    if (params?.end_date) query.set('end_date', params.end_date);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    const qs = query.toString();
    const res = await fetch(`${getApiBase()}/${typeId}/entries${qs ? `?${qs}` : ''}`);
    if (!res.ok) throw new Error(`获取记录列表失败: ${res.statusText}`);
    return res.json();
  },

  async createEntry(typeId: string, req: CreateCustomRecordEntryRequest): Promise<CustomRecordEntryItem> {
    const res = await fetch(`${getApiBase()}/${typeId}/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`创建记录失败: ${res.statusText}`);
    return res.json();
  },

  async deleteEntry(typeId: string, entryId: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/${typeId}/entries/${entryId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`删除记录失败: ${res.statusText}`);
  },
};
