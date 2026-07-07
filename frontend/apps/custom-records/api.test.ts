/**
 * 自定义记录模块 API 测试
 *
 * Seam: API 层 — 验证 fetch 调用的 URL、method、body，以及响应解析
 * Mock: globalThis.fetch + apiConfig (避免 window 引用)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock apiConfig 避免在 Node 环境中访问 window
vi.mock('../../core/services/apiConfig', () => ({
  createApiV2UrlGetter: (suffix: string) => () => `http://localhost:8000/api/v2${suffix}`,
}));

import { CustomRecordsAPI } from './api';
import type {
  CustomRecordTypeItem,
  CreateCustomRecordTypeRequest,
  CustomRecordEntryItem,
  CreateCustomRecordEntryRequest,
  UpdateTypeConfigRequest,
} from './types';

describe('CustomRecordsAPI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // ==================== Cycle 1: getTypes ====================

  describe('getTypes', () => {
    it('should call GET /custom-records/types and return items array', async () => {
      const mockTypes: CustomRecordTypeItem[] = [
        {
          id: 'crt-abc12345',
          name: '阅读记录',
          slug: 'reading',
          description: '',
          fields: [
            { field_name: '书名', field_key: 'book_title', field_type: 'text' },
            { field_name: '笔记', field_key: 'notes', field_type: 'text' },
          ],
          created_at: '2026-07-05T22:00:00',
          updated_at: '2026-07-05T22:00:00',
        },
      ];
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ items: mockTypes }),
      } as Response);

      const result = await CustomRecordsAPI.getTypes();

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types',
      );
      expect(result).toEqual(mockTypes);
      expect(result).toHaveLength(1);
      expect(result[0].fields).toHaveLength(2);
    });

    it('should return empty array when no types exist', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ items: [] }),
      } as Response);

      const result = await CustomRecordsAPI.getTypes();

      expect(result).toEqual([]);
    });

    it('should throw error when response is not ok', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      await expect(CustomRecordsAPI.getTypes()).rejects.toThrow('获取类型列表失败');
    });
  });

  // ==================== Cycle 2: createType ====================

  describe('createType', () => {
    it('should call POST /custom-records/types with correct body and return created type', async () => {
      const req: CreateCustomRecordTypeRequest = {
        name: '阅读记录',
        slug: 'reading',
        fields: [
          { field_name: '书名', field_key: 'book_title', field_type: 'text' },
          { field_name: '笔记', field_key: 'notes', field_type: 'text' },
        ],
      };
      const mockCreated: CustomRecordTypeItem = {
        id: 'crt-abc12345',
        name: '阅读记录',
        slug: 'reading',
        description: '',
        fields: req.fields,
        created_at: '2026-07-07T10:00:00',
        updated_at: '2026-07-07T10:00:00',
      };
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockCreated,
      } as Response);

      const result = await CustomRecordsAPI.createType(req);

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(req),
        },
      );
      expect(result).toEqual(mockCreated);
      expect(result.id).toBe('crt-abc12345');
    });

    it('should throw error on 422 validation error', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 422,
        statusText: 'Unprocessable Entity',
      } as Response);

      await expect(
        CustomRecordsAPI.createType({ name: '', slug: '', fields: [] }),
      ).rejects.toThrow('创建类型失败');
    });

    it('should throw error on 409 slug conflict', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 409,
        statusText: 'Conflict',
      } as Response);

      await expect(
        CustomRecordsAPI.createType({
          name: '重复',
          slug: 'reading',
          fields: [{ field_name: 'f', field_key: 'f', field_type: 'text' }],
        }),
      ).rejects.toThrow('创建类型失败');
    });
  });

  // ==================== Cycle 3: getTypeById + deleteType ====================

  describe('getTypeById', () => {
    it('should call GET /custom-records/types/{id} and return type with fields', async () => {
      const mockType: CustomRecordTypeItem = {
        id: 'crt-abc12345',
        name: '阅读记录',
        slug: 'reading',
        description: '',
        fields: [{ field_name: '书名', field_key: 'book_title', field_type: 'text' }],
        created_at: '2026-07-05T22:00:00',
        updated_at: '2026-07-05T22:00:00',
      };
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => mockType,
      } as Response);

      const result = await CustomRecordsAPI.getTypeById('crt-abc12345');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types/crt-abc12345',
      );
      expect(result).toEqual(mockType);
      expect(result.fields).toHaveLength(1);
    });

    it('should throw error on 404 not found', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      await expect(CustomRecordsAPI.getTypeById('nonexistent')).rejects.toThrow('获取类型详情失败');
    });
  });

  describe('deleteType', () => {
    it('should call DELETE /custom-records/types/{id}', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ message: '类型 crt-abc12345 已删除' }),
      } as Response);

      await CustomRecordsAPI.deleteType('crt-abc12345');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types/crt-abc12345',
        { method: 'DELETE' },
      );
    });

    it('should throw error on 404 not found', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      await expect(CustomRecordsAPI.deleteType('nonexistent')).rejects.toThrow('删除类型失败');
    });
  });

  // ==================== Cycle 4: getEntries ====================

  describe('getEntries', () => {
    it('should call GET /custom-records/{type_id}/entries and return items with total', async () => {
      const mockEntries: CustomRecordEntryItem[] = [
        { id: 'cre-001', created_at: '2026-07-07T10:00:00', updated_at: '', book_title: '百年孤独', notes: '精彩' },
        { id: 'cre-002', created_at: '2026-07-06T10:00:00', updated_at: '', book_title: '三体', notes: '震撼' },
      ];
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ items: mockEntries, total: 2 }),
      } as Response);

      const result = await CustomRecordsAPI.getEntries('crt-abc12345');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/crt-abc12345/entries',
      );
      expect(result.items).toEqual(mockEntries);
      expect(result.total).toBe(2);
    });

    it('should append date filter and pagination as query params', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      } as Response);

      await CustomRecordsAPI.getEntries('crt-abc12345', {
        start_date: '2026-07-01',
        end_date: '2026-07-07',
        page: 2,
        page_size: 10,
      });

      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('start_date=2026-07-01'),
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('end_date=2026-07-07'),
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('page=2'),
      );
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('page_size=10'),
      );
    });

    it('should not append query string when no params provided', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ items: [], total: 0 }),
      } as Response);

      await CustomRecordsAPI.getEntries('crt-abc12345');

      const callArgs = (fetch as any).mock.calls[0][0] as string;
      expect(callArgs).not.toContain('?');
    });

    it('should throw error on 404 type not found', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      await expect(CustomRecordsAPI.getEntries('nonexistent')).rejects.toThrow('获取记录列表失败');
    });
  });

  // ==================== Cycle 5: createEntry + deleteEntry ====================

  describe('createEntry', () => {
    it('should call POST /custom-records/{type_id}/entries with data body', async () => {
      const req: CreateCustomRecordEntryRequest = {
        data: { book_title: '百年孤独', notes: '马尔克斯的魔幻现实主义' },
      };
      const mockCreated: CustomRecordEntryItem = {
        id: 'cre-001',
        created_at: '2026-07-07T10:00:00',
        updated_at: '',
        book_title: '百年孤独',
        notes: '马尔克斯的魔幻现实主义',
      };
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        status: 201,
        json: async () => mockCreated,
      } as Response);

      const result = await CustomRecordsAPI.createEntry('crt-abc12345', req);

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/crt-abc12345/entries',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(req),
        },
      );
      expect(result).toEqual(mockCreated);
      expect(result.id).toBe('cre-001');
    });

    it('should throw error on 422 invalid field key', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 422,
        statusText: 'Unprocessable Entity',
      } as Response);

      await expect(
        CustomRecordsAPI.createEntry('crt-abc12345', { data: { invalid_key: 'x' } }),
      ).rejects.toThrow('创建记录失败');
    });
  });

  describe('deleteEntry', () => {
    it('should call DELETE /custom-records/{type_id}/entries/{entry_id}', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ message: '记录 cre-001 已删除' }),
      } as Response);

      await CustomRecordsAPI.deleteEntry('crt-abc12345', 'cre-001');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/crt-abc12345/entries/cre-001',
        { method: 'DELETE' },
      );
    });

    it('should throw error on 404 entry not found', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      await expect(CustomRecordsAPI.deleteEntry('crt-abc12345', 'nonexistent')).rejects.toThrow('删除记录失败');
    });
  });

  // ==================== Cycle 6: updateTypeConfig + updateFieldRole (Slice 6) ====================

  describe('updateTypeConfig', () => {
    it('should call PATCH /custom-records/types/{id} with correct body', async () => {
      const mockUpdated: CustomRecordTypeItem = {
        id: 'crt-abc12345',
        name: '阅读记录',
        slug: 'reading',
        description: '',
        fields: [],
        card_template: 'paper',
        icon: 'book',
        accent_color: 'amber',
        created_at: '2026-07-07T10:00:00',
        updated_at: '2026-07-07T11:00:00',
      };
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => mockUpdated,
      } as Response);

      const result = await CustomRecordsAPI.updateTypeConfig('crt-abc12345', {
        card_template: 'paper',
        icon: 'book',
        accent_color: 'amber',
      });

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types/crt-abc12345',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ card_template: 'paper', icon: 'book', accent_color: 'amber' }),
        },
      );
      expect(result.card_template).toBe('paper');
    });

    it('should work with partial update (only card_template)', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ id: 'crt-abc12345', name: 'test', slug: 't', description: '', fields: [], card_template: 'bold', created_at: '', updated_at: '' }),
      } as Response);

      await CustomRecordsAPI.updateTypeConfig('crt-abc12345', { card_template: 'bold' });

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types/crt-abc12345',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ card_template: 'bold' }),
        },
      );
    });

    it('should throw error on 404 type not found', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      await expect(
        CustomRecordsAPI.updateTypeConfig('nonexistent', { card_template: 'paper' }),
      ).rejects.toThrow('更新类型配置失败');
    });
  });

  describe('updateFieldRole', () => {
    it('should call PATCH /custom-records/types/{id}/fields/{field_id} with display_role', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ id: 'crt-abc12345', name: 'test', slug: 't', description: '', fields: [], created_at: '', updated_at: '' }),
      } as Response);

      await CustomRecordsAPI.updateFieldRole('crt-abc12345', 'crf-001', { display_role: 'main' });

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/custom-records/types/crt-abc12345/fields/crf-001',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ display_role: 'main' }),
        },
      );
    });

    it('should throw error on 404 field not found', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      } as Response);

      await expect(
        CustomRecordsAPI.updateFieldRole('crt-abc12345', 'nonexistent', { display_role: 'hidden' }),
      ).rejects.toThrow('更新字段角色失败');
    });
  });
});
