/**
 * API 配置管理
 * 支持从配置文件读取端口，并动态探测后端可用端口
 */

// 默认端口白名单
const DEFAULT_PORT_LIST = [8000, 8001, 8002, 8003, 8004];
const DEFAULT_HOST = 'localhost';

// 缓存探测到的端口
let cachedApiBaseUrl: string | null = null;
let isInitialized = false;
let initPromise: Promise<string> | null = null;

// 声明 electronAPI 类型
declare global {
    interface Window {
        electronAPI?: {
            getLifeprismDataPath: () => Promise<string>;
            getCustomDataPath: () => Promise<string>;
            isPackaged: () => Promise<boolean>;
            getConfig?: () => Promise<any>;
            selectDirectory: () => Promise<string | null>;
            selectFile: (filters?: Array<{name: string; extensions: string[]}>) => Promise<string | null>;
            getInstallPath: () => Promise<string | null>;
            quitApp: () => Promise<void>;
            openFloatingWindow: (windowId: string) => Promise<{ success: boolean; action?: string; reason?: string }>;
            closeFloatingWindow: (windowId: string) => Promise<{ success: boolean; reason?: string }>;
            openDialogWindow: (dialogId: string, options?: Record<string, unknown>) => Promise<{ success: boolean; action?: string; reason?: string }>;
            closeDialogWindow: (dialogId: string) => Promise<{ success: boolean; reason?: string }>;
            sendToFloating: (windowId: string, channel: string, data?: unknown) => Promise<{ success: boolean }>;
            sendToMain: (channel: string, data?: unknown) => Promise<{ success: boolean }>;
            sendToDialog: (dialogId: string, channel: string, data?: unknown) => Promise<{ success: boolean }>;
            onMessage: (channel: string, callback: (data: unknown) => void) => ((_event: unknown, data: unknown) => void);
            removeMessageListener: (channel: string, handler: ((_event: unknown, data: unknown) => void)) => void;
            resizeFloatingWindow: (windowId: string, size: { width?: number; height?: number }) => Promise<{ success: boolean }>;
        };
    }
}

/**
 * 初始化 API 配置（应在应用启动时调用）
 * 会探测可用的后端端口并缓存结果
 */
export async function initApiConfig(): Promise<string> {
    // 如果已经在初始化中，返回同一个 Promise
    if (initPromise) {
        return initPromise;
    }

    // 如果已经初始化完成，直接返回缓存值
    if (isInitialized && cachedApiBaseUrl) {
        return cachedApiBaseUrl;
    }

    initPromise = doInitialize();
    return initPromise;
}

async function doInitialize(): Promise<string> {
    let portList = DEFAULT_PORT_LIST;
    let host = DEFAULT_HOST;

    // 1. 尝试从配置文件读取（Electron 环境）
    try {
        if (window.electronAPI) {
            const dataPath = await (window.electronAPI.getLifeprismDataPath?.() ?? window.electronAPI.getCustomDataPath());
            const config = await loadConfigFromElectron(dataPath);
            if (config?.server) {
                host = config.server.host || DEFAULT_HOST;
                portList = config.server.portFallbackList || DEFAULT_PORT_LIST;
                // 用户配置的端口优先
                if (config.server.backendPort) {
                    const userPort = config.server.backendPort;
                    portList = [userPort, ...portList.filter(p => p !== userPort)];
                }
            }
            console.log('[ApiConfig] Electron 环境，端口列表:', portList);
        } else {
            console.log('[ApiConfig] 非 Electron 环境，使用默认配置');
        }
    } catch (e) {
        console.log('[ApiConfig] 配置读取失败，使用默认配置:', e);
    }

    // 2. 探测可用端口
    cachedApiBaseUrl = await discoverBackendPort(host, portList);
    isInitialized = true;
    console.log(`[ApiConfig] 后端地址已确定: ${cachedApiBaseUrl}`);

    return cachedApiBaseUrl;
}

/**
 * 从 Electron 环境加载配置文件
 */
async function loadConfigFromElectron(dataPath: string): Promise<any> {
    // 在 Electron 中，可以通过 Node.js 读取文件
    // 但由于 preload 的限制，我们通过 IPC 获取配置
    if (window.electronAPI?.getConfig) {
        return await window.electronAPI.getConfig();
    }

    // 备选方案：尝试通过 fetch 读取（开发模式）
    try {
        const response = await fetch('/lifeprismData/config/config.json');
        if (response.ok) {
            return await response.json();
        }
    } catch (e) {
        // 忽略错误
    }

    return null;
}

/**
 * 探测后端可用端口
 */
async function discoverBackendPort(host: string, portList: number[]): Promise<string> {
    console.log(`[ApiConfig] 开始探测后端端口，白名单: ${portList.join(', ')}`);

    for (const port of portList) {
        const baseUrl = `http://${host}:${port}`;
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 1000); // 1秒超时

            const response = await fetch(`${baseUrl}/health`, {
                method: 'GET',
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (response.ok) {
                console.log(`[ApiConfig] 端口 ${port} 可用`);
                return baseUrl;
            }
        } catch (e) {
            console.log(`[ApiConfig] 端口 ${port} 不可用`);
            // 端口不可用，继续尝试下一个
        }
    }

    // 所有端口都不可用，返回默认值
    console.warn('[ApiConfig] 未能探测到可用的后端端口，使用默认端口 8000');
    return `http://${host}:8000`;
}

/**
 * 获取 API 基础 URL（异步版本）
 * 首次调用会触发端口探测
 */
export async function getApiBaseUrl(): Promise<string> {
    if (!isInitialized) {
        return await initApiConfig();
    }
    return cachedApiBaseUrl!;
}

/**
 * 获取完整的 API v2 URL（异步版本）
 */
export async function getApiV2Url(): Promise<string> {
    const base = await getApiBaseUrl();
    return `${base}/api/v2`;
}

/**
 * 获取 API 基础 URL（同步版本）
 * 注意：此函数设计为延迟调用，会在 API 调用时动态获取 URL
 * 如果在初始化完成前调用，会返回默认值
 */
export function getApiBaseUrlSync(): string {
    console.log(`[ApiConfig DEBUG] getApiBaseUrlSync 被调用 - isInitialized=${isInitialized}, cachedUrl=${cachedApiBaseUrl}`);
    if (!isInitialized) {
        // 如果未初始化，使用默认值（用于开发模式代理或同步初始化场景）
        console.warn('[ApiConfig] 警告：API 配置尚未初始化，使用默认值 http://localhost:8000');
        console.trace('[ApiConfig] 调用堆栈:');
        return 'http://localhost:8000';
    }
    console.log(`[ApiConfig DEBUG] 返回缓存的 URL: ${cachedApiBaseUrl}`);
    return cachedApiBaseUrl!;
}

/**
 * 获取完整的 API v2 URL（同步版本）
 * 注意：此函数设计为延迟调用，会在 API 调用时动态获取 URL
 */
export function getApiV2UrlSync(): string {
    return `${getApiBaseUrlSync()}/api/v2`;
}

/**
 * 获取完整的 API v1 URL（同步版本）
 * 用于兼容 v1 API
 */
export function getApiV1UrlSync(): string {
    return `${getApiBaseUrlSync()}/api/v1`;
}

/**
 * 创建 API v2 URL getter 函数
 * 用于模块中替代常量定义，实现延迟求值
 * 
 * @param suffix 可选的路径后缀，如 '/chatbot' 或 '/goal'
 * @returns 一个返回完整 URL 的函数
 * 
 * @example
 * // 在模块中使用，替代:
 * // const API_BASE = getApiV2UrlSync();
 * // 使用:
 * const getApiBase = createApiV2UrlGetter();
 * // 然后在函数中调用 getApiBase() 获取 URL
 */
export function createApiV2UrlGetter(suffix: string = ''): () => string {
    return () => `${getApiBaseUrlSync()}/api/v2${suffix}`;
}

/**
 * 创建 API v1 URL getter 函数
 * 用于模块中替代常量定义，实现延迟求值
 */
export function createApiV1UrlGetter(suffix: string = ''): () => string {
    return () => `${getApiBaseUrlSync()}/api/v1${suffix}`;
}

/**
 * 检查 API 配置是否已初始化
 */
export function isApiConfigInitialized(): boolean {
    return isInitialized;
}

/**
 * 重置 API 配置（用于测试或重新探测）
 */
export function resetApiConfig(): void {
    cachedApiBaseUrl = null;
    isInitialized = false;
    initPromise = null;
}
