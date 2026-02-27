const { contextBridge, ipcRenderer } = require('electron');

// 安全地暴露 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
    // 获取 lifeprismData 文件夹路径
    getLifeprismDataPath: () => ipcRenderer.invoke('get-lifeprism-data-path'),

    // DEPRECATED: 保留向后兼容
    getCustomDataPath: () => ipcRenderer.invoke('get-custom-data-path'),

    // 获取应用是否为打包状态
    isPackaged: () => ipcRenderer.invoke('is-packaged'),

    // 获取配置文件（用于端口配置等）
    getConfig: () => ipcRenderer.invoke('get-config'),

    // 选择目录（文件夹选择对话框）
    selectDirectory: () => ipcRenderer.invoke('select-directory'),

    // 选择文件（文件选择对话框）
    selectFile: (filters) => ipcRenderer.invoke('select-file', filters),

    // 获取安装路径
    getInstallPath: () => ipcRenderer.invoke('get-install-path'),

    // 退出应用（数据迁移后调用）
    quitApp: () => ipcRenderer.invoke('app-quit'),

    // 在文件管理器中打开文件夹
    openFolder: (folderPath) => ipcRenderer.invoke('open-folder', folderPath),

    // 自动更新
    checkForUpdates: () => ipcRenderer.invoke('updater:check'),
    downloadUpdate: () => ipcRenderer.invoke('updater:download'),
    quitAndInstall: () => ipcRenderer.invoke('updater:quit-and-install'),
    onUpdaterStatus: (callback) => {
        const handler = (_event, data) => callback(data);
        ipcRenderer.on('updater:status', handler);
        return handler;
    },
    onUpdaterProgress: (callback) => {
        const handler = (_event, data) => callback(data);
        ipcRenderer.on('updater:progress', handler);
        return handler;
    },
    removeUpdaterListener: (channel, handler) => {
        ipcRenderer.removeListener(channel, handler);
    },

    // 浮窗管理
    openFloatingWindow: (windowId) => ipcRenderer.invoke('open-floating-window', windowId),
    closeFloatingWindow: (windowId) => ipcRenderer.invoke('close-floating-window', windowId),

    // 对话框窗口管理
    openDialogWindow: (dialogId, options) => ipcRenderer.invoke('open-dialog-window', dialogId, options),
    closeDialogWindow: (dialogId) => ipcRenderer.invoke('close-dialog-window', dialogId),

    // 窗口间通信
    sendToFloating: (windowId, channel, data) =>
        ipcRenderer.invoke('send-to-floating', windowId, channel, data),
    sendToMain: (channel, data) =>
        ipcRenderer.invoke('send-to-main', channel, data),
    sendToDialog: (dialogId, channel, data) =>
        ipcRenderer.invoke('send-to-dialog', dialogId, channel, data),
    onMessage: (channel, callback) => {
        const handler = (_event, data) => callback(data);
        ipcRenderer.on(channel, handler);
        return handler;
    },
    removeMessageListener: (channel, handler) => {
        ipcRenderer.removeListener(channel, handler);
    },

    // 浮窗大小调整
    resizeFloatingWindow: (windowId, size) =>
        ipcRenderer.invoke('resize-floating-window', windowId, size),
});

// 在控制台输出 Electron 环境信息
console.log('[Preload] Electron 预加载脚本已加载');
console.log('[Preload] electronAPI 已暴露到 window 对象');
