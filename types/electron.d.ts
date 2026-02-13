// Electron API 类型定义
// 这些类型对应 electron/preload.cjs 中暴露的 API

interface ElectronAPI {
    // 获取 lifeprismData 文件夹路径
    getLifeprismDataPath: () => Promise<string>;

    // DEPRECATED: 保留向后兼容
    getCustomDataPath: () => Promise<string>;

    // 获取应用是否为打包状态
    isPackaged: () => Promise<boolean>;

    // 获取配置文件（用于端口配置等）
    getConfig: () => Promise<Record<string, unknown> | null>;

    // 选择目录（文件夹选择对话框）
    selectDirectory: () => Promise<string | null>;

    // 选择文件（文件选择对话框）
    selectFile: (filters?: Array<{ name: string; extensions: string[] }>) => Promise<string | null>;

    // 获取安装路径
    getInstallPath: () => Promise<string | null>;

    // 退出应用（数据迁移后调用）
    quitApp: () => Promise<void>;

    // 浮窗管理
    openFloatingWindow: (windowId: string) => Promise<{ success: boolean; action?: string; reason?: string }>;
    closeFloatingWindow: (windowId: string) => Promise<{ success: boolean; reason?: string }>;

    // 对话框窗口管理
    openDialogWindow: (dialogId: string, options?: Record<string, unknown>) => Promise<{ success: boolean; action?: string; reason?: string }>;
    closeDialogWindow: (dialogId: string) => Promise<{ success: boolean; reason?: string }>;

    // 窗口间通信
    sendToFloating: (windowId: string, channel: string, data?: unknown) => Promise<{ success: boolean }>;
    sendToMain: (channel: string, data?: unknown) => Promise<{ success: boolean }>;
    sendToDialog: (dialogId: string, channel: string, data?: unknown) => Promise<{ success: boolean }>;
    onMessage: (channel: string, callback: (data: unknown) => void) => ((_event: unknown, data: unknown) => void);
    removeMessageListener: (channel: string, handler: ((_event: unknown, data: unknown) => void)) => void;

    // 浮窗大小调整
    resizeFloatingWindow: (windowId: string, size: { width?: number; height?: number }) => Promise<{ success: boolean }>;
}

interface Window {
    electronAPI?: ElectronAPI;
}
