/**
 * SyncConfigSection 组件测试
 *
 * Seam 1: 云端地址输入框 - 测试输入和保存
 * Seam 2: 生成配置按钮 - 测试点击调用 API
 * Seam 3: 根据 key_is_new 显示不同提示
 * Seam 4: Electron IPC open-folder-and-select
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock syncApi 模块
vi.mock('../syncApi', () => ({
  SyncConfigAPI: {
    generateCloudConfig: vi.fn(),
    saveRemoteUrl: vi.fn(),
    getRemoteUrl: vi.fn(),
    openFolderAndSelect: vi.fn(),
  },
}));

// Mock toast
vi.mock('../../../core/components', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

// Mock framer-motion（简化渲染）
vi.mock('framer-motion', () => ({
  motion: {
    div: ({ children, ...props }: any) => <div {...props}>{children}</div>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import { SyncConfigSection } from './SyncConfigSection';
import { SyncConfigAPI } from '../syncApi';
import { toast } from '../../../core/components';

describe('SyncConfigSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 默认 mock 返回空 URL
    vi.mocked(SyncConfigAPI.getRemoteUrl).mockResolvedValue('');
    vi.mocked(SyncConfigAPI.saveRemoteUrl).mockResolvedValue(undefined);
    vi.mocked(SyncConfigAPI.openFolderAndSelect).mockResolvedValue({ success: true });
  });

  afterEach(() => {
    cleanup();
  });

  // ==================== Seam 1: 云端地址输入框 ====================

  describe('Seam 1: 云端地址输入框', () => {
    it('should render cloud URL input field', async () => {
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByLabelText(/云端地址/i)).toBeInTheDocument();
      });
    });

    it('should load and display existing remote URL on mount', async () => {
      vi.mocked(SyncConfigAPI.getRemoteUrl).mockResolvedValue('https://cloud.example.com');

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByLabelText(/云端地址/i)).toHaveValue('https://cloud.example.com');
      });
    });

    it('should save remote URL on blur', async () => {
      const user = userEvent.setup();
      vi.mocked(SyncConfigAPI.getRemoteUrl).mockResolvedValue('');

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByLabelText(/云端地址/i)).toBeInTheDocument();
      });

      const input = screen.getByLabelText(/云端地址/i);
      await user.type(input, 'https://my-cloud.example.com');
      fireEvent.blur(input);

      await waitFor(() => {
        expect(SyncConfigAPI.saveRemoteUrl).toHaveBeenCalledWith('https://my-cloud.example.com');
      });
    });
  });

  // ==================== Seam 2: 生成配置按钮 ====================

  describe('Seam 2: 生成配置按钮', () => {
    it('should render generate cloud config button', async () => {
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });
    });

    it('should call generateCloudConfig API when button is clicked', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockResolvedValue({
        cloud_config_path: 'C:\\data\\cloud_init.yaml',
        key_is_new: false,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      const button = screen.getByRole('button', { name: /生成云端配置/i });
      await userEvent.setup().click(button);

      // 选择框出现后点击"保留当前 Key"
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /保留当前 Key/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /保留当前 Key/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.generateCloudConfig).toHaveBeenCalledWith(false);
      });
    });

    it('should call openFolderAndSelect with returned cloud_config_path', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockResolvedValue({
        cloud_config_path: 'C:\\Users\\data\\cloud_init.yaml',
        key_is_new: false,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /保留当前 Key/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /保留当前 Key/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.openFolderAndSelect).toHaveBeenCalledWith('C:\\Users\\data\\cloud_init.yaml');
      });
    });

    it('should show loading state during generation', async () => {
      let resolveGenerate: (value: any) => void;
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockImplementation(
        () => new Promise((resolve) => { resolveGenerate = resolve; })
      );

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /保留当前 Key/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /保留当前 Key/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成中/i })).toBeDisabled();
      });

      // Resolve to cleanup
      resolveGenerate!({
        cloud_config_path: 'C:\\data\\cloud_init.yaml',
        key_is_new: false,
      });
    });

    it('should show error toast when generation fails', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockRejectedValue(new Error('keyring 不可用'));

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /保留当前 Key/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /保留当前 Key/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('keyring 不可用');
      });
    });
  });

  // ==================== Seam 3: 根据 key_is_new 显示不同提示 ====================

  describe('Seam 3: 根据 key_is_new 显示不同提示', () => {
    it('should show success message when key_is_new is false', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockResolvedValue({
        cloud_config_path: 'C:\\data\\cloud_init.yaml',
        key_is_new: false,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /保留当前 Key/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /保留当前 Key/i }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith(
          expect.stringContaining('配置已生成'),
        );
      });
    });

    it('should show warning message when key_is_new is true', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockResolvedValue({
        cloud_config_path: 'C:\\data\\cloud_init.yaml',
        key_is_new: true,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      // 选择"更换 Key 并生成"
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /更换 Key 并生成/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /更换 Key 并生成/i }));

      await waitFor(() => {
        expect(toast.warning).toHaveBeenCalledWith(
          expect.stringContaining('reinit-config'),
        );
      });
    });

    it('should display result info panel with cloud_config_path after generation', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockResolvedValue({
        cloud_config_path: 'C:\\Users\\data\\cloud_init.yaml',
        key_is_new: false,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /保留当前 Key/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /保留当前 Key/i }));

      await waitFor(() => {
        expect(screen.getByText(/C:\\Users\\data\\cloud_init.yaml/)).toBeInTheDocument();
      });
    });

    it('should show warning styling when key_is_new is true', async () => {
      vi.mocked(SyncConfigAPI.generateCloudConfig).mockResolvedValue({
        cloud_config_path: 'C:\\data\\cloud_init.yaml',
        key_is_new: true,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });

      await userEvent.setup().click(screen.getByRole('button', { name: /生成云端配置/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /更换 Key 并生成/i })).toBeInTheDocument();
      });
      await userEvent.setup().click(screen.getByRole('button', { name: /更换 Key 并生成/i }));

      await waitFor(() => {
        // 警告提示应包含 reinit-config 指令
        expect(screen.getByText(/reinit-config/)).toBeInTheDocument();
      });
    });
  });
});
