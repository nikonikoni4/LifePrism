import { createApiV2UrlGetter } from '../../core/services/apiConfig';

export interface RagModelInfo {
  model: string;
  base_url: string;
  configured: boolean;
}
export interface RagSettings {
  enabled: boolean;
  rerank_enabled: boolean;
  index_directories: string[];
  embedding: RagModelInfo;
  rerank: RagModelInfo;
}
export type RagSettingsPatch = Partial<
  Pick<RagSettings, 'enabled' | 'rerank_enabled' | 'index_directories'>
>;

export interface RagIndexStatus {
  last_index_time: string | null;
  building: boolean;
  error: string | null;
  can_build: boolean;
}

const getApiBase = createApiV2UrlGetter();

async function request<T = RagSettings>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${getApiBase()}/settings/rag${path}`, init);
  if (!response.ok) {
    const body: { detail?: string | { msg: string }[]; message?: string } = await response
      .json()
      .catch(() => ({}));
    const detail =
      typeof body.detail === 'string'
        ? body.detail
        : body.detail?.map((item) => item.msg).join('；');
    throw new Error(detail || body.message || 'RAG 配置操作失败');
  }
  return response.json();
}

export const RagAPI = {
  indexStatus: () => request<RagIndexStatus>('/index'),
  buildIndex: () => request<RagIndexStatus>('/index', { method: 'POST' }),
  get: () => request(''),
  update: (patch: RagSettingsPatch) =>
    request('', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch),
    }),
  saveKey: (purpose: 'embedding' | 'rerank', apiKey: string) =>
    request(`/keys/${purpose}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: apiKey }),
    }),
};
