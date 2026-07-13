/**
 * 心情模块 API 服务
 * 对接后端 /mood 路由
 */
import { createApiV2UrlGetter } from '../../../../core/services/apiConfig';
import type {
  MoodTypeItem,
  MoodEntryItem,
  MoodImpactItem,
  CreateMoodTypeRequest,
  UpdateMoodTypeRequest,
  CreateMoodEntryRequest,
  UpdateMoodEntryRequest,
  CreateMoodImpactRequest,
} from './types';

const getApiBase = createApiV2UrlGetter('/mood');

export const MoodAPI = {
  // ==================== 心情类型 ====================

  async getTypes(): Promise<MoodTypeItem[]> {
    const res = await fetch(`${getApiBase()}/types`);
    if (!res.ok) throw new Error(`获取心情类型失败: ${res.statusText}`);
    const data = await res.json();
    return data.items;
  },

  async createType(req: CreateMoodTypeRequest): Promise<MoodTypeItem> {
    const res = await fetch(`${getApiBase()}/types`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`创建心情类型失败: ${res.statusText}`);
    return res.json();
  },

  async updateType(id: string, req: UpdateMoodTypeRequest): Promise<MoodTypeItem> {
    const res = await fetch(`${getApiBase()}/types/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`更新心情类型失败: ${res.statusText}`);
    return res.json();
  },
  async deleteType(id: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/types/${id}`, { method: 'DELETE' });
    if (res.status === 400) {
      const data = await res.json();
      throw new Error(data.detail || '该心情类型下有关联记录，无法删除');
    }
    if (!res.ok) throw new Error(`删除心情类型失败: ${res.statusText}`);
  },

  // ==================== 影响因素 ====================

  async getImpacts(): Promise<MoodImpactItem[]> {
    const res = await fetch(`${getApiBase()}/impacts`);
    if (!res.ok) throw new Error(`获取影响因素失败: ${res.statusText}`);
    const data = await res.json();
    return data.items;
  },

  async createImpact(req: CreateMoodImpactRequest): Promise<MoodImpactItem> {
    const res = await fetch(`${getApiBase()}/impacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`创建影响因素失败: ${res.statusText}`);
    return res.json();
  },

  async deleteImpact(id: number): Promise<void> {
    const res = await fetch(`${getApiBase()}/impacts/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`删除影响因素失败: ${res.statusText}`);
  },

  // ==================== 心情记录 ====================

  async getEntries(startTime?: string, endTime?: string): Promise<MoodEntryItem[]> {
    const params = new URLSearchParams();
    if (startTime) params.set('start_time', startTime);
    if (endTime) params.set('end_time', endTime);
    const qs = params.toString();
    const res = await fetch(`${getApiBase()}/entries${qs ? `?${qs}` : ''}`);
    if (!res.ok) throw new Error(`获取心情记录失败: ${res.statusText}`);
    const data = await res.json();
    return data.items;
  },

  async getEntry(id: string): Promise<MoodEntryItem> {
    const res = await fetch(`${getApiBase()}/entries/${id}`);
    if (!res.ok) throw new Error(`获取心情记录失败: ${res.statusText}`);
    return res.json();
  },

  async createEntry(req: CreateMoodEntryRequest): Promise<MoodEntryItem> {
    const res = await fetch(`${getApiBase()}/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`创建心情记录失败: ${res.statusText}`);
    return res.json();
  },

  async updateEntry(id: string, req: UpdateMoodEntryRequest): Promise<MoodEntryItem> {
    const res = await fetch(`${getApiBase()}/entries/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(`更新心情记录失败: ${res.statusText}`);
    return res.json();
  },

  async deleteEntry(id: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/entries/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(`删除心情记录失败: ${res.statusText}`);
  },
};
