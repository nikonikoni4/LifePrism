/**
 * AI Service
 * 
 * 通用 AI 工具服务，提供非对话类 AI 功能
 * 例如：摘要生成、内容总结等
 */

import { createApiV1UrlGetter } from './apiConfig';

// 使用 getter 函数延迟求值，确保在初始化完成后获取正确的 URL
const getApiBase = createApiV1UrlGetter();

/**
 * 发送消息到 Gemini API（流式响应）
 * 
 * @param message 用户消息
 * @returns 异步生成器，逐块返回 AI 响应
 */
export async function* sendMessageToGemini(message: string): AsyncGenerator<string, void, unknown> {
    try {
        const response = await fetch(`${getApiBase()}/ai/chat`, {
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
        const response = await fetch(`${getApiBase()}/ai/chat`, {
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

// ============================================================================
// 未来扩展：通用 AI 工具函数
// ============================================================================

/**
 * 生成目标摘要（待实现）
 * 
 * @param goalContent 目标内容
 * @returns 生成的摘要
 */
export async function generateGoalSummary(goalContent: string): Promise<string> {
    // TODO: 实现目标摘要生成
    return sendMessageToGeminiSync(`请为以下目标生成一个简短的摘要：\n\n${goalContent}`);
}

/**
 * 生成每日总结（待实现）
 * 
 * @param activities 当日活动数据
 * @returns 生成的每日总结
 */
export async function generateDailySummary(activities: string): Promise<string> {
    // TODO: 实现每日总结生成
    return sendMessageToGeminiSync(`请根据以下活动数据生成一个每日总结：\n\n${activities}`);
}
