import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import { RagConfigSection } from './RagConfigSection';
import { RagAPI } from '../ragApi';

vi.mock('../ragApi', () => ({
  RagAPI: {
    get: vi.fn(),
    update: vi.fn(),
    saveKey: vi.fn(),
    indexStatus: vi.fn(),
    buildIndex: vi.fn(),
    testConnection: vi.fn(),
  },
}));

const defaults = {
  enabled: false,
  rerank_enabled: false,
  index_directories: ['user', 'diary'],
  embedding: {
    model: 'doubao-embedding-vision',
    base_url: 'https://ark.example/v3',
    configured: false,
  },
  rerank: {
    model: 'qwen3.7-text-rerank',
    base_url: 'https://aliyun.example/rerank',
    configured: false,
  },
};

describe('RagConfigSection', () => {
  it('edits base URL while model stays fixed and runs each connection probe independently', async () => {
    vi.mocked(RagAPI.get).mockResolvedValue({
      ...defaults,
      embedding: { ...defaults.embedding, configured: true },
      rerank: { ...defaults.rerank, configured: true },
    });
    vi.mocked(RagAPI.update).mockResolvedValue({
      ...defaults,
      embedding: { ...defaults.embedding, configured: true, base_url: 'https://custom.example/v3' },
      rerank: { ...defaults.rerank, configured: true },
    });
    vi.mocked(RagAPI.testConnection).mockResolvedValue({ success: true, message: '连接成功' });
    render(<RagConfigSection />);
    fireEvent.change(await screen.findByLabelText('豆包嵌入地址'), {
      target: { value: 'https://custom.example/v3' },
    });
    expect(screen.getByLabelText('豆包嵌入模型')).toHaveAttribute('readonly');
    fireEvent.click(screen.getByRole('button', { name: '保存豆包嵌入地址' }));
    await waitFor(() =>
      expect(RagAPI.update).toHaveBeenCalledWith({
        embedding_base_url: 'https://custom.example/v3',
      })
    );
    fireEvent.click(screen.getByRole('button', { name: '测试豆包嵌入连接' }));
    await waitFor(() => expect(RagAPI.testConnection).toHaveBeenCalledWith('embedding'));
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '测试阿里云重排连接' })).toBeEnabled()
    );
    fireEvent.click(screen.getByRole('button', { name: '测试阿里云重排连接' }));
    await waitFor(() => expect(RagAPI.testConnection).toHaveBeenCalledWith('rerank'));
  });
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(RagAPI.get).mockResolvedValue(defaults);
    vi.mocked(RagAPI.indexStatus).mockResolvedValue({
      last_index_time: null,
      building: false,
      error: null,
      can_build: false,
    });
  });
  afterEach(cleanup);

  it('shows default directories and fixed model fields; requires embedding key to enable', async () => {
    render(<RagConfigSection />);
    expect(await screen.findByLabelText('索引目录')).toHaveValue('user\ndiary');
    expect(screen.getByLabelText('豆包嵌入模型')).toHaveAttribute('readonly');
    expect(screen.getByLabelText('启用 RAG')).toBeDisabled();
  });

  it('saves an independent key without submitting model or base URL', async () => {
    vi.mocked(RagAPI.saveKey).mockResolvedValue({
      ...defaults,
      embedding: { ...defaults.embedding, configured: true },
    });
    render(<RagConfigSection />);
    fireEvent.change(await screen.findByLabelText('豆包嵌入 API Key'), {
      target: { value: 'new-key' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存豆包嵌入密钥' }));
    await waitFor(() => expect(RagAPI.saveKey).toHaveBeenCalledWith('embedding', 'new-key'));
    expect(screen.getByLabelText('启用 RAG')).not.toBeDisabled();
    expect(screen.getByLabelText('豆包嵌入 API Key')).toHaveValue('');
  });

  it('reports failed directory updates without replacing saved settings', async () => {
    vi.mocked(RagAPI.update).mockRejectedValue(new Error('目录越界'));
    render(<RagConfigSection />);
    fireEvent.change(await screen.findByLabelText('索引目录'), { target: { value: '../user' } });
    fireEvent.click(screen.getByRole('button', { name: '保存索引目录' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('目录越界');
  });

  it('shows never indexed and disables manual build without available local configuration', async () => {
    render(<RagConfigSection />);
    expect(await screen.findByText('尚未索引')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '立即更新索引' })).toBeDisabled();
  });

  it('starts a manual build and disables repeat requests while building', async () => {
    vi.mocked(RagAPI.get).mockResolvedValue({
      ...defaults,
      enabled: true,
      embedding: { ...defaults.embedding, configured: true },
    });
    vi.mocked(RagAPI.indexStatus).mockResolvedValue({
      last_index_time: '2026-10-08T01:02:03Z',
      building: false,
      error: null,
      can_build: true,
    });
    vi.mocked(RagAPI.buildIndex).mockResolvedValue({
      last_index_time: '2026-10-08T01:02:03Z',
      building: true,
      error: null,
      can_build: true,
    });
    render(<RagConfigSection />);
    await waitFor(() => expect(screen.getByRole('button', { name: '立即更新索引' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: '立即更新索引' }));
    await waitFor(() => expect(RagAPI.buildIndex).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('button', { name: '索引中…' })).toBeDisabled();
    expect(screen.getByText(/只更新本地索引/)).toBeInTheDocument();
  });

  it('shows background failure together with the previous successful index time', async () => {
    vi.mocked(RagAPI.indexStatus).mockResolvedValue({
      last_index_time: '2026-10-08T01:02:03Z',
      building: false,
      error: '索引构建失败，旧索引已保留',
      can_build: true,
    });
    localStorage.setItem('lifeprism_timezone', 'Asia/Hong_Kong');
    render(<RagConfigSection />);
    expect(await screen.findByText('索引构建失败，旧索引已保留')).toBeInTheDocument();
    expect(screen.getByText(/09:02:03/)).toBeInTheDocument();
    localStorage.removeItem('lifeprism_timezone');
  });

  it('refreshes successful time after a background build completes', async () => {
    vi.mocked(RagAPI.get).mockResolvedValue({
      ...defaults,
      enabled: true,
      embedding: { ...defaults.embedding, configured: true },
    });
    vi.mocked(RagAPI.indexStatus).mockResolvedValue({
      last_index_time: null,
      building: false,
      error: null,
      can_build: true,
    });
    vi.mocked(RagAPI.buildIndex).mockResolvedValue({
      last_index_time: null,
      building: true,
      error: null,
      can_build: true,
    });
    localStorage.setItem('lifeprism_timezone', 'Asia/Hong_Kong');
    render(<RagConfigSection />);
    await waitFor(() => expect(screen.getByRole('button', { name: '立即更新索引' })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: '立即更新索引' }));
    expect(await screen.findByRole('button', { name: '索引中…' })).toBeDisabled();
    vi.mocked(RagAPI.indexStatus).mockResolvedValue({
      last_index_time: '2026-10-08T02:03:04Z',
      building: false,
      error: null,
      can_build: true,
    });
    expect(await screen.findByText(/10:03:04/, {}, { timeout: 3500 })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '立即更新索引' })).toBeEnabled();
    localStorage.removeItem('lifeprism_timezone');
  });
});
