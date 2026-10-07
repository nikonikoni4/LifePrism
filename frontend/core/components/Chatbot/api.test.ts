import { afterEach, expect, it, vi } from 'vitest';
import { sendMessageStream } from './api';
import type { SSEEvent } from './types';

vi.mock('../../services/apiConfig', () => ({ createApiV2UrlGetter: () => () => '/chatbot' }));
afterEach(() => vi.unstubAllGlobals());

it('projects Runtime flat usage as turn usage without inventing a session total', async () => {
    const payload = 'data: {"type":"done","usage":{"input_tokens":4,"output_tokens":5,"total_tokens":9}}\n\n';
    const bytes = new TextEncoder().encode(payload);
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: true,
        body: new ReadableStream({ start(controller) { controller.enqueue(bytes); controller.close(); } }),
    }));
    const events: SSEEvent[] = [];
    await sendMessageStream(null, 'hi', event => events.push(event));
    expect(events[0].usage?.turn_usage).toEqual({ input_tokens: 4, output_tokens: 5, total_tokens: 9 });
    expect(events[0].usage?.session_usage).toBeUndefined();
});
