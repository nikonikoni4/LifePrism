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
  UpdateTypeConfigRequest,
  UpdateFieldRoleRequest,
} from './types';

const getApiBase = createApiV2UrlGetter('/custom-records');

/**
 * 解析后端错误响应体，提取 message 字段
 * 后端返回格式: { "message": "具体错误", "details": {...} }
 */
async function parseError(res: Response, fallback: string): Promise<never> {
  try {
    const body = await res.json();
    throw new Error(body?.message || `${fallback}: ${res.statusText}`);
  } catch (e) {
    // 如果是我们自己抛的 Error，直接传递
    if (e instanceof Error && !e.message.includes('is not a function')) {
      throw e;
    }
    // res.json() 不可用，回退到 statusText
    throw new Error(`${fallback}: ${res.statusText}`);
  }
}

export const CustomRecordsAPI = {
  // ==================== 类型管理 ====================

  async getTypes(): Promise<CustomRecordTypeItem[]> {
    const res = await fetch(`${getApiBase()}/types`);
    if (!res.ok) await parseError(res, '获取类型列表失败');
    const data: CustomRecordTypeListResponse = await res.json();
    return data.items;
  },

  async createType(req: CreateCustomRecordTypeRequest): Promise<CustomRecordTypeItem> {
    const res = await fetch(`${getApiBase()}/types`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) await parseError(res, '创建类型失败');
    return res.json();
  },

  async getTypeById(typeId: string): Promise<CustomRecordTypeItem> {
    const res = await fetch(`${getApiBase()}/types/${typeId}`);
    if (!res.ok) await parseError(res, '获取类型详情失败');
    return res.json();
  },

  async deleteType(typeId: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/types/${typeId}`, { method: 'DELETE' });
    if (!res.ok) await parseError(res, '删除类型失败');
  },

  // ==================== 记录管理 ====================

  async getEntries(typeId: string, params?: GetEntriesParams): Promise<CustomRecordEntryListResponse> {
    const query = new URLSearchParams();
    if (params?.start_time) query.set('start_time', params.start_time);
    if (params?.end_time) query.set('end_time', params.end_time);
    if (params?.page) query.set('page', String(params.page));
    if (params?.page_size) query.set('page_size', String(params.page_size));
    const qs = query.toString();
    const res = await fetch(`${getApiBase()}/${typeId}/entries${qs ? `?${qs}` : ''}`);
    if (!res.ok) await parseError(res, '获取记录列表失败');
    return res.json();
  },

  async createEntry(typeId: string, req: CreateCustomRecordEntryRequest): Promise<CustomRecordEntryItem> {
    const res = await fetch(`${getApiBase()}/${typeId}/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) await parseError(res, '创建记录失败');
    return res.json();
  },

  async deleteEntry(typeId: string, entryId: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/${typeId}/entries/${entryId}`, { method: 'DELETE' });
    if (!res.ok) await parseError(res, '删除记录失败');
  },

  // ==================== 配置更新 ====================

  async updateTypeConfig(typeId: string, req: UpdateTypeConfigRequest): Promise<CustomRecordTypeItem> {
    const res = await fetch(`${getApiBase()}/types/${typeId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) await parseError(res, '更新类型配置失败');
    return res.json();
  },

  async updateFieldRole(typeId: string, fieldId: string, req: UpdateFieldRoleRequest): Promise<CustomRecordTypeItem> {
    const res = await fetch(`${getApiBase()}/types/${typeId}/fields/${fieldId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) await parseError(res, '更新字段角色失败');
    return res.json();
  },
};
