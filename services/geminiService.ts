/**
 * Gemini Service
 * 
 * AI 聊天服务，调用 Gemini API
 */

const API_BASE = 'http://localhost:8000/api/v1';

/**
 * 发送消息到 Gemini API（流式响应）
 * 
 * @param message 用户消息
 * @returns 异步生成器，逐块返回 AI 响应
 */
export async function* sendMessageToGemini(message: string): AsyncGenerator<string, void, unknown> {
    try {
        const response = await fetch(`${API_BASE}/ai/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message }),
        });

        if (!response.ok) {
            throw new Error(`Chat request failed: ${response.statusText}`);
        }

        // 检查是否支持流式响应
        if (response.body) {
            const reader = response.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                yield chunk;
            }
        } else {
            // 非流式响应，直接返回完整文本
            const data = await response.json();
            yield data.response || data.message || 'No response from AI';
        }
    } catch (error) {
        console.error('Error sending message to Gemini:', error);
        yield 'Sorry, I encountered an error. Please try again later.';
    }
}

/**
 * 发送消息到 Gemini API（非流式响应）
 * 
 * @param message 用户消息
 * @returns AI 响应文本
 */
export async function sendMessageToGeminiSync(message: string): Promise<string> {
    try {
        const response = await fetch(`${API_BASE}/ai/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message }),
        });

        if (!response.ok) {
            throw new Error(`Chat request failed: ${response.statusText}`);
        }

        const data = await response.json();
        return data.response || data.message || 'No response from AI';
    } catch (error) {
        console.error('Error sending message to Gemini:', error);
        return 'Sorry, I encountered an error. Please try again later.';
    }
}
