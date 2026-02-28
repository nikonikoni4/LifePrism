/**
 * 习惯系统的通用 API Fetch 封装
 * 用于统一处理后端标准错误格式，提供对中文等业务异常的友好感知
 */
export async function fetchApi<T>(url: string, options?: RequestInit): Promise<T> {
    const res = await fetch(url, options);

    if (!res.ok) {
        let errorMessage = `请求失败: ${res.status} ${res.statusText}`;
        try {
            const errorBody = await res.json();
            if (errorBody && errorBody.message) {
                errorMessage = errorBody.message;
            } else if (errorBody && errorBody.detail) {
                // FastAPI 默认格式为 detail
                if (typeof errorBody.detail === 'string') {
                    errorMessage = errorBody.detail;
                } else if (Array.isArray(errorBody.detail) && errorBody.detail.length > 0) {
                    errorMessage = errorBody.detail[0].msg || JSON.stringify(errorBody.detail);
                }
            }
        } catch (e) {
            // Body 不是合法的 JSON 或读取错误，保留 HTTP 维度的 errorMessage
        }
        throw new Error(errorMessage);
    }

    if (res.status === 204) {
        return undefined as T;
    }

    return res.json();
}
