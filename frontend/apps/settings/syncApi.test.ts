/**
 * 数据同步配置 API 测试
 *
 * Seam: API 层 — 验证 fetch 调用的 URL、method、body，以及响应解析
 * Mock: globalThis.fetch + apiConfig (避免 window 引用)
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock apiConfig 避免在 Node 环境中访问 window
vi.mock('../../core/services/apiConfig', () => ({
  createApiV2UrlGetter: (suffix: string = '') => () => `http://localhost:8000/api/v2${suffix || ''}`,
  getApiBaseUrlSync: () => 'http://localhost:8000',
}));

import { SyncConfigAPI } from './syncApi';

describe('SyncConfigAPI', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // ==================== generateCloudConfig ====================

  describe('generateCloudConfig', () => {
    it('should call POST /api/sync/generate-cloud-config and return cloud_config_path + key_is_new', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({
          cloud_config_path: 'C:\\Users\\data\\cloud_init.yaml',
          key_is_new: false,
        }),
      } as Response);

      const result = await SyncConfigAPI.generateCloudConfig();

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/sync/generate-cloud-config',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ replace_key: false }),
        },
      );
      expect(result.cloud_config_path).toBe('C:\\Users\\data\\cloud_init.yaml');
      expect(result.key_is_new).toBe(false);
    });

    it('should return key_is_new=true when a new key is generated', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({
          cloud_config_path: '/home/user/data/cloud_init.yaml',
          key_is_new: true,
        }),
      } as Response);

      const result = await SyncConfigAPI.generateCloudConfig();

      expect(result.key_is_new).toBe(true);
      expect(result.cloud_config_path).toBe('/home/user/data/cloud_init.yaml');
    });

    it('should throw error when response is not ok', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: async () => { throw new Error('parse error'); },
      } as unknown as Response);

      await expect(SyncConfigAPI.generateCloudConfig()).rejects.toThrow('生成云端配置失败');
    });

    it('should throw error with detail message when available', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 400,
        statusText: 'Bad Request',
        json: async () => ({ detail: 'keyring 不可用' }),
      } as Response);

      await expect(SyncConfigAPI.generateCloudConfig()).rejects.toThrow('keyring 不可用');
    });
  });

  // ==================== saveRemoteUrl ====================

  describe('saveRemoteUrl', () => {
    it('should call PATCH /api/v2/settings with sync_remote_url', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({
          settings: {},
          message: '配置已更新',
        }),
      } as Response);

      await SyncConfigAPI.saveRemoteUrl('https://cloud.example.com');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/settings',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sync_remote_url: 'https://cloud.example.com' }),
        },
      );
    });

    it('should save empty string when url is empty', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({ settings: {}, message: '配置已更新' }),
      } as Response);

      await SyncConfigAPI.saveRemoteUrl('');

      expect(fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/v2/settings',
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sync_remote_url: '' }),
        },
      );
    });

    it('should throw error when response is not ok', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      await expect(SyncConfigAPI.saveRemoteUrl('https://cloud.example.com')).rejects.toThrow('保存云端地址失败');
    });
  });

  // ==================== getRemoteUrl ====================

  describe('getRemoteUrl', () => {
    it('should extract sync_remote_url from settings response', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({
          settings: {
            user_name: 'test',
            sync_remote_url: 'https://cloud.example.com',
          },
          message: 'success',
        }),
      } as Response);

      const result = await SyncConfigAPI.getRemoteUrl();

      expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/v2/settings');
      expect(result).toBe('https://cloud.example.com');
    });

    it('should return empty string when sync_remote_url is not set', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: true,
        json: async () => ({
          settings: { user_name: 'test' },
          message: 'success',
        }),
      } as Response);

      const result = await SyncConfigAPI.getRemoteUrl();

      expect(result).toBe('');
    });

    it('should throw error when response is not ok', async () => {
      vi.spyOn(globalThis, 'fetch').mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      } as Response);

      await expect(SyncConfigAPI.getRemoteUrl()).rejects.toThrow('获取云端地址失败');
    });
  });

  // ==================== openFolderAndSelect ====================

  describe('openFolderAndSelect', () => {
    it('should call window.electronAPI.openFolderAndSelect with file path', async () => {
      const mockOpenFolderAndSelect = vi.fn().mockResolvedValue({ success: true });
      Object.defineProperty(window, 'electronAPI', {
        value: { openFolderAndSelect: mockOpenFolderAndSelect },
        writable: true,
        configurable: true,
      });

      await SyncConfigAPI.openFolderAndSelect('C:\\data\\cloud_init.yaml');

      expect(mockOpenFolderAndSelect).toHaveBeenCalledWith('C:\\data\\cloud_init.yaml');
    });

    it('should resolve to {success: false} when electronAPI is not available', async () => {
      Object.defineProperty(window, 'electronAPI', {
        value: undefined,
        writable: true,
        configurable: true,
      });

      const result = await SyncConfigAPI.openFolderAndSelect('C:\\data\\cloud_init.yaml');

      expect(result.success).toBe(false);
    });
  });
});
