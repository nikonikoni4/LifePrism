import { createApiV2UrlGetter } from '../../../../core/services/apiConfig';
import type {
  CommitmentItem,
  CommitmentListResponse,
  CreateCommitmentRequest,
  UpdateCommitmentRequest,
  ValueOption,
} from './commitmentTypes';

const getCommitmentBase = createApiV2UrlGetter('/commitment');
const getValueBase = createApiV2UrlGetter('/value');

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    if (typeof body.detail === 'string') return body.detail;
    if (typeof body.message === 'string') return body.message;
  } catch { /* ignore parse failure */ }
  return `${fallback}: ${res.statusText}`;
}

export const CommitmentAPI = {
  async getList(status?: string, valueId?: string): Promise<CommitmentListResponse> {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (valueId) params.set('value_id', valueId);
    const qs = params.toString();
    const url = `${getCommitmentBase()}/${qs ? `?${qs}` : ''}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error(await parseError(res, '获取承诺列表失败'));
    return res.json();
  },

  async create(req: CreateCommitmentRequest): Promise<CommitmentItem> {
    const res = await fetch(`${getCommitmentBase()}/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(await parseError(res, '创建承诺失败'));
    return res.json();
  },

  async update(id: string, req: UpdateCommitmentRequest): Promise<CommitmentItem> {
    const res = await fetch(`${getCommitmentBase()}/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error(await parseError(res, '更新承诺失败'));
    return res.json();
  },

  async delete(id: string): Promise<void> {
    const res = await fetch(`${getCommitmentBase()}/${id}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(await parseError(res, '删除承诺失败'));
  },
};

export const ValueAPI = {
  async getOptions(): Promise<ValueOption[]> {
    const res = await fetch(`${getValueBase()}/`);
    if (!res.ok) throw new Error(await parseError(res, '获取价值列表失败'));
    const data = await res.json();
    return (data.items ?? []).map((v: any) => ({ id: v.id, keywords: v.keywords }));
  },
};
