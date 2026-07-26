/**
 * SyncConfigSection 组件测试
 *
 * Seam 1: 云端地址输入框 - 测试输入和保存
 * Seam 2: 生成配置按钮 - 测试点击调用 API
 * Seam 3: 根据 key_is_new 显示不同提示
 * Seam 4: Electron IPC open-folder-and-select
 * Seam 5: 连接方式切换（HTTP/HTTPS ↔ SSH）- 测试切换交互和自动保存
 * Seam 6: SSH 选项卡 UI 元素渲染（10 个元素）
 * Seam 7: SSH API 调用契约（enableSshTunnel / getPublicKey / testConnection）
 * Seam 8: 复制按钮剪贴板操作（navigator.clipboard）
 * Seam 9: 测试连接一次性结果展示（成功/失败 + 原因）
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
    enableSshTunnel: vi.fn(),
    getPublicKey: vi.fn(),
    testConnection: vi.fn(),
    saveConnectionMode: vi.fn(),
    getConnectionMode: vi.fn(),
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

// 测试用公钥（OpenSSH 格式，以 `ssh-ed25519 ` 开头）
const TEST_PUBLIC_KEY = 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJJhsYq+4Mo5lZ+8R9lPQ+aQ8bVJ3pY7r2d4X6nW8KxL test@lifeprism';
// 拼接后的配置命令（包含实际公钥值）
const TEST_CONFIG_COMMAND = `# 在云端服务器执行以下命令（追加 SSH 公钥）
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '${TEST_PUBLIC_KEY}' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys`;

describe('SyncConfigSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 默认 mock 返回空 URL
    vi.mocked(SyncConfigAPI.getRemoteUrl).mockResolvedValue('');
    vi.mocked(SyncConfigAPI.saveRemoteUrl).mockResolvedValue(undefined);
    vi.mocked(SyncConfigAPI.openFolderAndSelect).mockResolvedValue({ success: true });
    // SSH 相关默认 mock
    vi.mocked(SyncConfigAPI.getConnectionMode).mockResolvedValue('http');
    vi.mocked(SyncConfigAPI.saveConnectionMode).mockResolvedValue(undefined);
    vi.mocked(SyncConfigAPI.enableSshTunnel).mockResolvedValue({
      public_key: TEST_PUBLIC_KEY,
      is_new: true,
    });
    vi.mocked(SyncConfigAPI.getPublicKey).mockResolvedValue({
      public_key: TEST_PUBLIC_KEY,
    });
    vi.mocked(SyncConfigAPI.testConnection).mockResolvedValue({
      status: 'ok',
      remote_response: { status: 'healthy' },
    });
    // 默认 clipboard mock
    Object.defineProperty(navigator, 'clipboard', {
      value: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
      configurable: true,
      writable: true,
    });
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

  // ==================== Seam 5: 连接方式切换（HTTP/HTTPS ↔ SSH） ====================

  describe('Seam 5: 连接方式切换', () => {
    it('should render connection mode switcher with HTTP/HTTPS and SSH options', async () => {
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /HTTP\/HTTPS/i })).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });
    });

    it('should default to HTTP/HTTPS mode', async () => {
      render(<SyncConfigSection />);

      await waitFor(() => {
        const httpBtn = screen.getByRole('button', { name: /HTTP\/HTTPS/i });
        // HTTP 按钮应有选中样式（aria-pressed 或类名包含 border-blue）
        expect(httpBtn).toHaveAttribute('aria-pressed', 'true');
      });
    });

    it('should call saveConnectionMode("ssh") when switching to SSH mode', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.saveConnectionMode).toHaveBeenCalledWith('ssh');
      });
    });

    it('should call saveConnectionMode("http") when switching back to HTTP mode', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      // 切换到 SSH
      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));
      await waitFor(() => {
        expect(SyncConfigAPI.saveConnectionMode).toHaveBeenCalledWith('ssh');
      });

      // 切换回 HTTP
      await user.click(screen.getByRole('button', { name: /HTTP\/HTTPS/i }));
      await waitFor(() => {
        expect(SyncConfigAPI.saveConnectionMode).toHaveBeenCalledWith('http');
      });
    });

    it('should preserve SSH config when switching back to HTTP mode', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      // 切换到 SSH 模式
      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/SSH 主机/i)).toBeInTheDocument();
      });

      // 输入 SSH 配置
      await user.type(screen.getByLabelText(/SSH 主机/i), '1.2.3.4');
      await user.type(screen.getByLabelText(/SSH 用户名/i), 'lifeprism');

      // 切换回 HTTP 模式
      await user.click(screen.getByRole('button', { name: /HTTP\/HTTPS/i }));

      // 再切回 SSH 模式，配置应保留
      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/SSH 主机/i)).toHaveValue('1.2.3.4');
        expect(screen.getByLabelText(/SSH 用户名/i)).toHaveValue('lifeprism');
      });
    });
  });

  // ==================== Seam 6: SSH 选项卡 UI 元素渲染（10 个元素） ====================

  describe('Seam 6: SSH 选项卡 UI 元素渲染', () => {
    it('should render all 10 SSH UI elements when SSH mode is active', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      // 切换到 SSH 模式
      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      // 10 个 UI 元素：5 个输入框 + 2 个只读文本框 + 3 个按钮
      await waitFor(() => {
        // 1. SSH 主机
        expect(screen.getByLabelText(/SSH 主机/i)).toBeInTheDocument();
        // 2. SSH 端口
        expect(screen.getByLabelText(/SSH 端口/i)).toBeInTheDocument();
        // 3. SSH 用户名
        expect(screen.getByLabelText(/SSH 用户名/i)).toBeInTheDocument();
        // 4. 本地监听端口
        expect(screen.getByLabelText(/本地监听端口/i)).toBeInTheDocument();
        // 5. 远程目标端口
        expect(screen.getByLabelText(/远程目标端口/i)).toBeInTheDocument();
        // 6. 公钥展示区
        expect(screen.getByLabelText(/公钥/i)).toBeInTheDocument();
        // 7. 复制公钥按钮
        expect(screen.getByRole('button', { name: /复制公钥/i })).toBeInTheDocument();
        // 8. 配置命令展示区
        expect(screen.getByLabelText(/配置命令/i)).toBeInTheDocument();
        // 9. 复制命令按钮
        expect(screen.getByRole('button', { name: /复制命令/i })).toBeInTheDocument();
        // 10. 测试连接按钮
        expect(screen.getByRole('button', { name: /测试连接/i })).toBeInTheDocument();
      });
    });

    it('should default SSH port to 22', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/SSH 端口/i)).toHaveValue(22);
      });
    });

    it('should default local and remote ports to 8102', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/本地监听端口/i)).toHaveValue(8102);
        expect(screen.getByLabelText(/远程目标端口/i)).toHaveValue(8102);
      });
    });

    it('should not render SSH UI elements when HTTP mode is active', async () => {
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /HTTP\/HTTPS/i })).toBeInTheDocument();
      });

      // 默认 HTTP 模式，不应显示 SSH 元素
      expect(screen.queryByLabelText(/SSH 主机/i)).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /测试连接/i })).not.toBeInTheDocument();
    });

    it('should preserve HTTP/HTTPS UI (cloud URL input + generate button) when HTTP mode is active', async () => {
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByLabelText(/云端地址/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /生成云端配置/i })).toBeInTheDocument();
      });
    });
  });

  // ==================== Seam 7: SSH API 调用契约 ====================

  describe('Seam 7: SSH API 调用契约', () => {
    it('should call enableSshTunnel when switching to SSH mode', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.enableSshTunnel).toHaveBeenCalledTimes(1);
      });
    });

    it('should call getPublicKey after switching to SSH mode', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.getPublicKey).toHaveBeenCalledTimes(1);
      });
    });

    it('should call testConnection with form params when test button is clicked', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByLabelText(/SSH 主机/i)).toBeInTheDocument();
      });

      // 输入 SSH 参数
      await user.type(screen.getByLabelText(/SSH 主机/i), '1.2.3.4');
      await user.clear(screen.getByLabelText(/SSH 端口/i));
      await user.type(screen.getByLabelText(/SSH 端口/i), '22');
      await user.type(screen.getByLabelText(/SSH 用户名/i), 'lifeprism');

      // 点击测试连接
      await user.click(screen.getByRole('button', { name: /测试连接/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.testConnection).toHaveBeenCalledWith({
          host: '1.2.3.4',
          port: 22,
          username: 'lifeprism',
          local_port: 8102,
          remote_port: 8102,
        });
      });
    });
  });

  // ==================== Seam 8: 复制按钮剪贴板操作 ====================

  describe('Seam 8: 复制按钮剪贴板操作', () => {
    it('should copy public key to clipboard when "复制公钥" is clicked', async () => {
      const user = userEvent.setup();
      const writeTextSpy = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: writeTextSpy },
        configurable: true,
        writable: true,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      // 等待公钥加载
      await waitFor(() => {
        expect(screen.getByRole('button', { name: /复制公钥/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /复制公钥/i }));

      await waitFor(() => {
        expect(writeTextSpy).toHaveBeenCalledWith(TEST_PUBLIC_KEY);
      });
    });

    it('should copy full config command to clipboard when "复制命令" is clicked', async () => {
      const user = userEvent.setup();
      const writeTextSpy = vi.fn().mockResolvedValue(undefined);
      Object.defineProperty(navigator, 'clipboard', {
        value: { writeText: writeTextSpy },
        configurable: true,
        writable: true,
      });

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /复制命令/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /复制命令/i }));

      await waitFor(() => {
        expect(writeTextSpy).toHaveBeenCalledWith(TEST_CONFIG_COMMAND);
      });
    });
  });

  // ==================== Seam 9: 公钥展示 + 配置命令拼接 + 测试连接结果 ====================

  describe('Seam 9: 公钥展示 + 配置命令拼接', () => {
    it('should display full public key starting with "ssh-ed25519 "', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        const publicKeyField = screen.getByLabelText(/公钥/i);
        expect(publicKeyField).toHaveValue(TEST_PUBLIC_KEY);
        expect(TEST_PUBLIC_KEY.startsWith('ssh-ed25519 ')).toBe(true);
      });
    });

    it('should dynamically interpolate public key into config command template', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        const cmdField = screen.getByLabelText(/配置命令/i) as HTMLTextAreaElement;
        expect(cmdField).toHaveValue(TEST_CONFIG_COMMAND);
        // 配置命令应包含实际公钥值（不是占位符）
        expect(cmdField.value).toContain(TEST_PUBLIC_KEY);
      });
    });
  });

  // ==================== Seam 10: 测试连接结果展示 ====================

  describe('Seam 10: 测试连接结果展示', () => {
    it('should display success result when test connection succeeds', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /测试连接/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /测试连接/i }));

      await waitFor(() => {
        // 成功结果应显示成功标识
        expect(screen.getByText(/连接成功|测试成功|成功/i)).toBeInTheDocument();
      });
    });

    it('should display failure reason when test connection fails', async () => {
      vi.mocked(SyncConfigAPI.testConnection).mockResolvedValue({
        status: 'error',
        error: '密钥被拒绝',
        code: 'SSH_KEY_REJECTED',
      });

      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /测试连接/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /测试连接/i }));

      await waitFor(() => {
        // 失败结果应显示失败原因
        expect(screen.getByText(/密钥被拒绝/)).toBeInTheDocument();
      });
    });

    it('should show loading state and disable button during test connection', async () => {
      const user = userEvent.setup();
      // 让 testConnection 返回一个可控的 Promise
      let resolveTest: (value: any) => void;
      vi.mocked(SyncConfigAPI.testConnection).mockImplementation(
        () => new Promise((resolve) => { resolveTest = resolve; }),
      );

      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /测试连接/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /测试连接/i }));

      // 测试中：按钮应被禁用，显示 loading 文案
      await waitFor(() => {
        const testingBtn = screen.getByRole('button', { name: /测试中|测试连接/i });
        expect(testingBtn).toBeDisabled();
      });

      // Resolve 以清理
      resolveTest!({ status: 'ok', remote_response: {} });
    });

    it('should clear previous test result when starting a new test', async () => {
      const user = userEvent.setup();
      render(<SyncConfigSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /SSH 隧道/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /SSH 隧道/i }));

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /测试连接/i })).toBeInTheDocument();
      });

      // 第一次测试 - 成功
      await user.click(screen.getByRole('button', { name: /测试连接/i }));
      await waitFor(() => {
        expect(screen.getByText(/连接成功|测试成功|成功/i)).toBeInTheDocument();
      });

      // 改为失败 mock
      vi.mocked(SyncConfigAPI.testConnection).mockResolvedValue({
        status: 'error',
        error: '网络不通',
        code: 'SSH_NETWORK_UNREACHABLE',
      });

      // 第二次测试 - 失败（应替换之前成功结果）
      await user.click(screen.getByRole('button', { name: /测试连接/i }));
      await waitFor(() => {
        expect(screen.getByText(/网络不通/)).toBeInTheDocument();
      });
    });
  });

  // ==================== Seam 11: 初始加载 SSH 模式 ====================

  describe('Seam 11: 初始加载 SSH 模式', () => {
    it('should load public key on mount when connection_mode is ssh', async () => {
      vi.mocked(SyncConfigAPI.getConnectionMode).mockResolvedValue('ssh');

      render(<SyncConfigSection />);

      // 初始加载时应调用 getPublicKey（因为 connection_mode 已经是 ssh）
      await waitFor(() => {
        expect(SyncConfigAPI.getPublicKey).toHaveBeenCalledTimes(1);
      });
    });

    it('should display SSH tab as active when connection_mode is ssh on mount', async () => {
      vi.mocked(SyncConfigAPI.getConnectionMode).mockResolvedValue('ssh');

      render(<SyncConfigSection />);

      await waitFor(() => {
        const sshBtn = screen.getByRole('button', { name: /SSH 隧道/i });
        expect(sshBtn).toHaveAttribute('aria-pressed', 'true');
      });
    });
  });
});
