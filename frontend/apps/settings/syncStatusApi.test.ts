/**
 * 同步状态 API 测试
 *
 * Seam 1: getSyncStatus() API 调用 - 测试请求和响应解析
 * Seam 2: triggerSync() API 调用 - 测试请求
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock apiConfig 模块
vi.mock('../../core/services/apiConfig', () => ({
  getApiBaseUrlSync: vi.fn(() => 'http://localhost:8000'),
  createApiV2UrlGetter: vi.fn(() => () => 'http://localhost:8000/api/v2'),
}));

import { SyncConfigAPI } from './syncApi';
import { getApiBaseUrlSync } from '../../core/services/apiConfig';

describe('Sync Status API', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getApiBaseUrlSync).mockReturnValue('http://localhost:8000');
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // ==================== Seam 1: getSyncStatus ====================

  describe('Seam 1: getSyncStatus', () => {
    it('should call GET /api/sync/status and return parsed response', async () => {
      const mockResponse = {
        last_sync_time: '2026-07-09T10:00:00Z',
        status: 'idle' as const,
        remote_url: 'https://cloud.example.com',
        tables: { mood_entries: 100, diary: 50 },
      };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await SyncConfigAPI.getSyncStatus();

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/sync/status',
        expect.objectContaining({ method: 'GET' }),
      );
      expect(result).toEqual(mockResponse);
      expect(result.last_sync_time).toBe('2026-07-09T10:00:00Z');
      expect(result.status).toBe('idle');
      expect(result.tables).toEqual({ mood_entries: 100, diary: 50 });
    });

    it('should return syncing status correctly', async () => {
      const mockResponse = {
        last_sync_time: '2026-07-09T10:00:00Z',
        status: 'syncing' as const,
        remote_url: 'https://cloud.example.com',
        tables: {},
      };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await SyncConfigAPI.getSyncStatus();

      expect(result.status).toBe('syncing');
    });

    it('should return error status correctly', async () => {
      const mockResponse = {
        last_sync_time: '2026-07-09T10:00:00Z',
        status: 'error' as const,
        remote_url: 'https://cloud.example.com',
        tables: { mood_entries: 50 },
      };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await SyncConfigAPI.getSyncStatus();

      expect(result.status).toBe('error');
    });

    it('should handle empty tables object', async () => {
      const mockResponse = {
        last_sync_time: '',
        status: 'idle' as const,
        remote_url: '',
        tables: {},
      };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await SyncConfigAPI.getSyncStatus();

      expect(result.tables).toEqual({});
      expect(result.last_sync_time).toBe('');
    });

    it('should throw error with detail message when response is not ok', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({ detail: '服务器内部错误' }),
      });

      await expect(SyncConfigAPI.getSyncStatus()).rejects.toThrow('服务器内部错误');
    });

    it('should throw generic error when response is not ok and no detail', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: 'Not Found',
        json: () => Promise.resolve({}),
      });

      await expect(SyncConfigAPI.getSyncStatus()).rejects.toThrow();
    });
  });

  // ==================== Seam 2: triggerSync ====================

  describe('Seam 2: triggerSync', () => {
    it('should call POST /api/sync/trigger', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: '同步已触发', status: 'syncing' }),
      });

      await SyncConfigAPI.triggerSync();

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/sync/trigger',
        expect.objectContaining({ method: 'POST' }),
      );
    });

    it('should include Content-Type header', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ message: '同步已触发', status: 'syncing' }),
      });

      await SyncConfigAPI.triggerSync();

      expect(fetch).toHaveBeenCalledWith(
        expect.any(String),
        expect.objectContaining({
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        }),
      );
    });

    it('should return response data on success', async () => {
      const mockResponse = { message: '同步已触发', status: 'syncing' };
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await SyncConfigAPI.triggerSync();

      expect(result).toEqual(mockResponse);
    });

    it('should return data when response is 409', async () => {
      const mockResponse = { message: '同步正在进行中', status: 'syncing' };
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        statusText: 'Conflict',
        json: () => Promise.resolve(mockResponse),
      });

      const result = await SyncConfigAPI.triggerSync();

      expect(result).toEqual(mockResponse);
    });

    it('should throw error with detail when trigger fails', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: 'Bad Request',
        json: () => Promise.resolve({ detail: '同步已在进行中' }),
      });

      await expect(SyncConfigAPI.triggerSync()).rejects.toThrow('同步已在进行中');
    });

    it('should throw generic error when trigger fails without detail', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        statusText: 'Internal Server Error',
        json: () => Promise.resolve({}),
      });

      await expect(SyncConfigAPI.triggerSync()).rejects.toThrow();
    });
  });
});
