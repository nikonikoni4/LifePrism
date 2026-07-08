/**
 * SyncStatusSection 组件测试
 *
 * Seam 3: SyncStatusSection 组件 - 测试显示上次同步时间、状态徽章、记录数
 * Seam 4: 手动同步按钮 - 测试点击触发 API、同步中禁用
 * Seam 5: 相对时间格式化 - 测试各种时间差的格式化
 * 自动刷新: 测试轮询逻辑
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, cleanup, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

// Mock syncApi 模块
vi.mock('../syncApi', () => ({
  SyncConfigAPI: {
    getSyncStatus: vi.fn(),
    triggerSync: vi.fn(),
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
    span: ({ children, ...props }: any) => <span {...props}>{children}</span>,
  },
  AnimatePresence: ({ children }: any) => <>{children}</>,
}));

import { SyncStatusSection } from './SyncStatusSection';
import { SyncConfigAPI } from '../syncApi';
import { toast } from '../../../core/components';
import { formatRelativeTime } from '../syncUtils';

// 固定当前时间，使相对时间测试可重复
const FIXED_NOW = new Date('2026-07-09T10:05:00Z');
const FIXED_NOW_MS = FIXED_NOW.getTime();

// Helper: 创建 mock 同步状态
const createMockStatus = (overrides: Record<string, any> = {}) => ({
  last_sync_time: '2026-07-09T10:00:00Z', // 5 分钟前
  status: 'idle' as const,
  remote_url: 'https://cloud.example.com',
  tables: { mood_entries: 100, diary: 50, todo_list: 30 },
  ...overrides,
});

// Mock Date.now 用于非 fake-timer 测试
let dateNowSpy: ReturnType<typeof vi.spyOn>;

describe('SyncStatusSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    // 使用 spyOn 控制 Date.now，不依赖 fake timers
    dateNowSpy = vi.spyOn(Date, 'now').mockReturnValue(FIXED_NOW_MS);
    vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(createMockStatus());
    vi.mocked(SyncConfigAPI.triggerSync).mockResolvedValue({ message: '同步已触发', status: 'syncing' });
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    dateNowSpy?.mockRestore();
  });

  // ==================== Seam 3: 显示同步状态 ====================

  describe('Seam 3: 显示同步状态', () => {
    it('should render section title "同步状态"', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('同步状态')).toBeInTheDocument();
      });
    });

    it('should display last sync time in relative format', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        // 5 分钟前
        expect(screen.getByText(/5\s*分钟前/)).toBeInTheDocument();
      });
    });

    it('should show "从未同步" when last_sync_time is empty', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(
        createMockStatus({ last_sync_time: '' }),
      );

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('从未同步')).toBeInTheDocument();
      });
    });

    it('should show idle status badge as "已同步"', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('已同步')).toBeInTheDocument();
      });
    });

    it('should show syncing status badge as "同步中"', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(
        createMockStatus({ status: 'syncing' }),
      );

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('同步中')).toBeInTheDocument();
      });
    });

    it('should show error status badge as "同步错误"', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(
        createMockStatus({ status: 'error' }),
      );

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('同步错误')).toBeInTheDocument();
      });
    });

    it('should display sync record counts summary', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        // 检查摘要中的张表和条记录文本
        const tableText = screen.getByText('张表');
        expect(tableText).toBeInTheDocument();
        const recordText = screen.getByText('条记录');
        expect(recordText).toBeInTheDocument();
        // 检查父元素包含数字
        const summaryContainer = tableText.closest('div');
        expect(summaryContainer?.textContent).toContain('3');
        expect(summaryContainer?.textContent).toContain('180');
      });
    });

    it('should display individual table names and counts when expanded', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('已同步')).toBeInTheDocument();
      });

      // 默认展开时应该显示各表详情
      expect(screen.getByText('mood_entries')).toBeInTheDocument();
      expect(screen.getByText('diary')).toBeInTheDocument();
      expect(screen.getByText('todo_list')).toBeInTheDocument();
    });

    it('should collapse and expand table details', async () => {
      const user = userEvent.setup();
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('mood_entries')).toBeInTheDocument();
      });

      // 点击收起
      const toggleButton = screen.getByRole('button', { name: /收起/i });
      await user.click(toggleButton);

      await waitFor(() => {
        expect(screen.queryByText('mood_entries')).not.toBeInTheDocument();
      });

      // 点击展开
      const expandButton = screen.getByRole('button', { name: /展开/i });
      await user.click(expandButton);

      await waitFor(() => {
        expect(screen.getByText('mood_entries')).toBeInTheDocument();
      });
    });

    it('should show loading state initially', async () => {
      // 让 getSyncStatus 返回一个永不 resolve 的 Promise
      vi.mocked(SyncConfigAPI.getSyncStatus).mockImplementation(
        () => new Promise(() => {}),
      );

      render(<SyncStatusSection />);

      expect(screen.getByText(/加载中/i)).toBeInTheDocument();
    });

    it('should show error message when getSyncStatus fails', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockRejectedValue(
        new Error('网络错误'),
      );

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText(/网络错误/)).toBeInTheDocument();
      });
    });

    it('should display remote URL', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByText('https://cloud.example.com')).toBeInTheDocument();
      });
    });
  });

  // ==================== Seam 4: 手动同步按钮 ====================

  describe('Seam 4: 手动同步按钮', () => {
    it('should render manual sync button', async () => {
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });
    });

    it('should call triggerSync when button is clicked', async () => {
      const user = userEvent.setup();
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /手动同步/i }));

      await waitFor(() => {
        expect(SyncConfigAPI.triggerSync).toHaveBeenCalledTimes(1);
      });
    });

    it('should disable button and show loading during sync', async () => {
      const user = userEvent.setup();
      // 让 triggerSync 返回一个可控的 Promise
      let resolveTrigger: (value: any) => void;
      vi.mocked(SyncConfigAPI.triggerSync).mockImplementation(
        () => new Promise((resolve) => { resolveTrigger = resolve; }),
      );

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /手动同步/i }));

      await waitFor(() => {
        const button = screen.getByRole('button', { name: /同步中/i });
        expect(button).toBeDisabled();
      });

      // Resolve 以清理
      resolveTrigger!({ message: '同步已触发', status: 'syncing' });
    });

    it('should refresh status after sync completes', async () => {
      const user = userEvent.setup();
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });

      // 初始加载调用一次 getSyncStatus
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(1);

      await user.click(screen.getByRole('button', { name: /手动同步/i }));

      // 同步完成后应该再次调用 getSyncStatus 刷新状态
      await waitFor(() => {
        expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(2);
      });

      // 验证成功提示文案
      expect(toast.success).toHaveBeenCalledWith('同步已触发，正在后台执行');
    });

    it('should show error toast when sync fails', async () => {
      const user = userEvent.setup();
      vi.mocked(SyncConfigAPI.triggerSync).mockRejectedValue(
        new Error('同步失败: 服务器无响应'),
      );

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /手动同步/i }));

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalledWith('同步失败: 服务器无响应');
      });
    });

    it('should show success toast when sync is triggered', async () => {
      const user = userEvent.setup();
      vi.mocked(SyncConfigAPI.triggerSync).mockResolvedValue({
        message: '同步已触发',
        status: 'syncing',
      } as any);

      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /手动同步/i }));

      await waitFor(() => {
        expect(toast.success).toHaveBeenCalledWith('同步已触发，正在后台执行');
      });
    });

    it('should re-enable button after sync completes', async () => {
      const user = userEvent.setup();
      render(<SyncStatusSection />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /手动同步/i })).toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: /手动同步/i }));

      await waitFor(() => {
        const button = screen.getByRole('button', { name: /手动同步/i });
        expect(button).not.toBeDisabled();
      });
    });
  });

  // ==================== Seam 5: 相对时间格式化 ====================

  describe('Seam 5: formatRelativeTime', () => {
    it('should return "刚刚" for less than 1 minute ago', () => {
      const now = FIXED_NOW.toISOString();
      expect(formatRelativeTime(now)).toBe('刚刚');
    });

    it('should return "X 分钟前" for minutes', () => {
      // 5 分钟前
      const time = new Date('2026-07-09T10:00:00Z').toISOString();
      expect(formatRelativeTime(time)).toBe('5 分钟前');
    });

    it('should return "X 分钟前" for 59 minutes', () => {
      // 59 分钟前
      const time = new Date('2026-07-09T09:06:00Z').toISOString();
      expect(formatRelativeTime(time)).toBe('59 分钟前');
    });

    it('should return "X 小时前" for hours', () => {
      // 2 小时前
      const time = new Date('2026-07-09T08:05:00Z').toISOString();
      expect(formatRelativeTime(time)).toBe('2 小时前');
    });

    it('should return "X 小时前" for 23 hours', () => {
      // 23 小时前
      const time = new Date('2026-07-08T11:05:00Z').toISOString();
      expect(formatRelativeTime(time)).toBe('23 小时前');
    });

    it('should return "X 天前" for days', () => {
      // 3 天前
      const time = new Date('2026-07-06T10:05:00Z').toISOString();
      expect(formatRelativeTime(time)).toBe('3 天前');
    });

    it('should return "X 天前" for more than 30 days', () => {
      // 45 天前
      const time = new Date('2026-05-25T10:05:00Z').toISOString();
      expect(formatRelativeTime(time)).toBe('45 天前');
    });

    it('should return "从未同步" for empty timestamp', () => {
      expect(formatRelativeTime('')).toBe('从未同步');
    });

    it('should return "从未同步" for null/undefined', () => {
      expect(formatRelativeTime(null as any)).toBe('从未同步');
      expect(formatRelativeTime(undefined as any)).toBe('从未同步');
    });
  });

  // ==================== 自动刷新 ====================

  describe('自动刷新', () => {
    beforeEach(() => {
      // 自动刷新测试需要 fake timers
      dateNowSpy?.mockRestore();
      vi.useFakeTimers({ now: FIXED_NOW });
    });

    it('should poll getSyncStatus every 30 seconds when idle', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(createMockStatus());

      render(<SyncStatusSection />);

      // 初始加载：调用 1 次
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(1);

      // 30 秒后：调用 2 次
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(2);

      // 再过 30 秒：调用 3 次
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(3);
    });

    it('should poll getSyncStatus every 5 seconds when syncing', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(
        createMockStatus({ status: 'syncing' }),
      );

      render(<SyncStatusSection />);

      // 初始加载：调用 1 次
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(1);

      // 5 秒后：调用 2 次（同步中每 5 秒刷新）
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(2);

      // 再过 5 秒：调用 3 次
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(3);
    });

    it('should not poll at 30s interval when syncing (should be 5s)', async () => {
      vi.mocked(SyncConfigAPI.getSyncStatus).mockResolvedValue(
        createMockStatus({ status: 'syncing' }),
      );

      render(<SyncStatusSection />);

      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(1);

      // 30 秒后：同步中每 5 秒刷新，应该调用了 7 次（1 初始 + 6 次 5s 间隔）
      await act(async () => {
        await vi.advanceTimersByTimeAsync(30000);
      });
      expect(SyncConfigAPI.getSyncStatus).toHaveBeenCalledTimes(7);
    });
  });
});
