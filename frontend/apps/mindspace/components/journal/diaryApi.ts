/**
 * 日记模块 API 服务
 * 对接后端 /diary 路由
 */
import { createApiV2UrlGetter } from '../../../../core/services/apiConfig';
import type {
  DiaryItem,
  DiaryMetaItem,
  DiaryAISummaryResponse,
  UpdateDiaryMetaRequest,
  SaveDiaryContentRequest,
  TemplateItem,
} from './diaryTypes';

const getApiBase = createApiV2UrlGetter('/diary');

export const DiaryAPI = {
  /** 获取指定日期日记（meta + content），不存在则自动创建 */
  async getDiary(date: string): Promise<DiaryItem> {
    const res = await fetch(`${getApiBase()}/${date}`);
    if (!res.ok) throw new Error(`获取日记失败: ${res.statusText}`);
    return res.json();
  },

  /** 更新日记 meta（心情、重要程度、自定义 tag） */
  async updateMeta(date: string, data: UpdateDiaryMetaRequest): Promise<DiaryItem> {
    const res = await fetch(`${getApiBase()}/${date}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`更新日记 meta 失败: ${res.statusText}`);
    return res.json();
  },

  /** 保存日记 md 内容 */
  async saveContent(date: string, data: SaveDiaryContentRequest): Promise<DiaryItem> {
    const res = await fetch(`${getApiBase()}/${date}/content`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`保存日记内容失败: ${res.statusText}`);
    return res.json();
  },

  /** 手动生成日记 AI 总结 */
  async generateAiSummary(date: string): Promise<DiaryAISummaryResponse> {
    const res = await fetch(`${getApiBase()}/${date}/ai_summary`, {
      method: 'POST',
    });
    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(errorText || `生成日记 AI 总结失败: ${res.statusText}`);
    }
    return res.json();
  },

  /** 获取日期范围内的日记列表（仅 meta） */
  async getList(startDate: string, endDate: string): Promise<DiaryMetaItem[]> {
    const params = new URLSearchParams({ start_date: startDate, end_date: endDate });
    const res = await fetch(`${getApiBase()}/list?${params}`);
    if (!res.ok) throw new Error(`获取日记列表失败: ${res.statusText}`);
    const data = await res.json();
    return data.items;
  },

  /** 获取模板列表 */
  async getTemplates(): Promise<string[]> {
    const res = await fetch(`${getApiBase()}/templates`);
    if (!res.ok) throw new Error(`获取模板列表失败: ${res.statusText}`);
    const data = await res.json();
    return data.items;
  },

  /** 获取模板内容 */
  async getTemplate(name: string): Promise<TemplateItem> {
    const res = await fetch(`${getApiBase()}/templates/${encodeURIComponent(name)}`);
    if (!res.ok) throw new Error(`获取模板失败: ${res.statusText}`);
    return res.json();
  },

  /** 创建模板 */
  async createTemplate(name: string, content: string = ''): Promise<TemplateItem> {
    const res = await fetch(`${getApiBase()}/templates`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, content }),
    });
    if (!res.ok) throw new Error(`创建模板失败: ${res.statusText}`);
    return res.json();
  },

  /** 更新模板 */
  async updateTemplate(name: string, content: string): Promise<TemplateItem> {
    const res = await fetch(`${getApiBase()}/templates/${encodeURIComponent(name)}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(`更新模板失败: ${res.statusText}`);
    return res.json();
  },

  /** 删除模板 */
  async deleteTemplate(name: string): Promise<void> {
    const res = await fetch(`${getApiBase()}/templates/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    });
    if (!res.ok) throw new Error(`删除模板失败: ${res.statusText}`);
  },
};
