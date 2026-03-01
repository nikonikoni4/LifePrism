/**
 * Common fetch wrapper for habits API.
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
                if (typeof errorBody.detail === 'string') {
                    errorMessage = errorBody.detail;
                } else if (Array.isArray(errorBody.detail) && errorBody.detail.length > 0) {
                    errorMessage = errorBody.detail[0].msg || JSON.stringify(errorBody.detail);
                } else if (typeof errorBody.detail === 'object') {
                    errorMessage = errorBody.detail.message || errorBody.detail.error_code || JSON.stringify(errorBody.detail);
                }
            }
        } catch (_e) {
            // Keep HTTP based fallback message.
        }
        throw new Error(errorMessage);
    }

    if (res.status === 204) {
        return undefined as T;
    }

    return res.json();
}
