import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import { RagConfigSection } from './RagConfigSection';
import { RagAPI } from '../ragApi';

vi.mock('../ragApi', () => ({ RagAPI: { get: vi.fn(), update: vi.fn(), saveKey: vi.fn() } }));

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
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(RagAPI.get).mockResolvedValue(defaults);
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
});
