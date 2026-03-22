import { createApiV2UrlGetter } from '../../../../core/services/apiConfig';
import type {
  ValueItem,
  ValueListResponse,
  CreateValueRequest,
  UpdateValueRequest,
} from './valueTypes';

const getValueBase = createApiV2UrlGetter('/value');

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
    if (typeof body.message === 'string') return body.message;
  } catch { /* ignore parse failure */ }
  return `${fallback}: ${res.statusText}`;
}

export const ValueAPI = {
  async getList(): Promise<ValueListResponse> {
    const res = await fetch(`${getValueBase()}/`);
    if (!res.ok) throw new Error(await parseError(res, '获取价值列表失败'));
    return res.json();
  },

  async create(req: CreateValueRequest): Promise<ValueItem> {
    const res = await fetch(`${getValueBase()}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(await parseError(res, '创建价值失败'));
    return res.json();
  },

  async update(id: string, req: UpdateValueRequest): Promise<ValueItem> {
    const res = await fetch(`${getValueBase()}/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(await parseError(res, '更新价值失败'));
    return res.json();
  },

  async delete(id: string, cascade: boolean = false): Promise<void> {
    const url = `${getValueBase()}/${id}${cascade ? '?cascade=true' : ''}`;
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new Error(await parseError(res, '删除价值失败'));
  },
};
