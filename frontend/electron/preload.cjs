const { contextBridge, ipcRenderer } = require('electron');

// 日志辅助函数
const preloadLog = (level, channel, data) => {
    const timestamp = new Date().toISOString();
    const dataStr = data !== undefined ? `, ${JSON.stringify(data)}` : '';
    console.log(`[${timestamp}] [Preload/${level}] ${channel}${dataStr}`);
};

// 安全地暴露 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
    // 获取 lifeprismData 文件夹路径
    getLifeprismDataPath: () => {
        preloadLog('INFO', 'invoke:get-lifeprism-data-path');
        return ipcRenderer.invoke('get-lifeprism-data-path');
    },

    // DEPRECATED: 保留向后兼容
    getCustomDataPath: () => {
        preloadLog('INFO', 'invoke:get-custom-data-path');
        return ipcRenderer.invoke('get-custom-data-path');
    },

    // 获取应用是否为打包状态
    isPackaged: () => {
        preloadLog('INFO', 'invoke:is-packaged');
        return ipcRenderer.invoke('is-packaged');
    },

    // 获取配置文件（用于端口配置等）
    getConfig: () => {
        preloadLog('INFO', 'invoke:get-config');
        return ipcRenderer.invoke('get-config');
    },

    // 选择目录（文件夹选择对话框）
    selectDirectory: () => {
        preloadLog('INFO', 'invoke:select-directory');
        return ipcRenderer.invoke('select-directory');
    },

    // 选择文件（文件选择对话框）
    selectFile: (filters) => {
        preloadLog('INFO', 'invoke:select-file', filters);
        return ipcRenderer.invoke('select-file', filters);
    },

    // 获取安装路径
    getInstallPath: () => {
        preloadLog('INFO', 'invoke:get-install-path');
        return ipcRenderer.invoke('get-install-path');
    },

    // 退出应用（数据迁移后调用）
    quitApp: () => {
        preloadLog('INFO', 'invoke:app-quit');
        return ipcRenderer.invoke('app-quit');
    },

    // 在文件管理器中打开文件夹
    openFolder: (folderPath) => {
        preloadLog('INFO', 'invoke:open-folder', folderPath);
        return ipcRenderer.invoke('open-folder', folderPath);
    },

    // 自动更新
    checkForUpdates: () => {
        preloadLog('INFO', 'invoke:updater:check');
        return ipcRenderer.invoke('updater:check');
    },
    downloadUpdate: () => {
        preloadLog('INFO', 'invoke:updater:download');
        return ipcRenderer.invoke('updater:download');
    },
    quitAndInstall: () => {
        preloadLog('INFO', 'invoke:updater:quit-and-install');
        return ipcRenderer.invoke('updater:quit-and-install');
    },
    onUpdaterStatus: (callback) => {
        preloadLog('INFO', 'on:updater:status');
        const handler = (_event, data) => callback(data);
        ipcRenderer.on('updater:status', handler);
        return handler;
    },
    onUpdaterProgress: (callback) => {
        preloadLog('INFO', 'on:updater:progress');
        const handler = (_event, data) => callback(data);
        ipcRenderer.on('updater:progress', handler);
        return handler;
    },
    removeUpdaterListener: (channel, handler) => {
        preloadLog('INFO', 'removeListener', channel);
        ipcRenderer.removeListener(channel, handler);
    },

    // 浮窗管理
    openFloatingWindow: (windowId) => {
        preloadLog('INFO', 'invoke:open-floating-window', windowId);
        return ipcRenderer.invoke('open-floating-window', windowId);
    },
    closeFloatingWindow: (windowId) => {
        preloadLog('INFO', 'invoke:close-floating-window', windowId);
        return ipcRenderer.invoke('close-floating-window', windowId);
    },

    // 对话框窗口管理
    openDialogWindow: (dialogId, options) => {
        preloadLog('INFO', 'invoke:open-dialog-window', { dialogId, options });
        return ipcRenderer.invoke('open-dialog-window', dialogId, options);
    },
    closeDialogWindow: (dialogId) => {
        preloadLog('INFO', 'invoke:close-dialog-window', dialogId);
        return ipcRenderer.invoke('close-dialog-window', dialogId);
    },

    // 窗口间通信
    sendToFloating: (windowId, channel, data) => {
        preloadLog('INFO', 'invoke:send-to-floating', { windowId, channel, data });
        return ipcRenderer.invoke('send-to-floating', windowId, channel, data);
    },
    sendToMain: (channel, data) => {
        preloadLog('INFO', 'invoke:send-to-main', { channel, data });
        return ipcRenderer.invoke('send-to-main', channel, data);
    },
    sendToDialog: (dialogId, channel, data) => {
        preloadLog('INFO', 'invoke:send-to-dialog', { dialogId, channel, data });
        return ipcRenderer.invoke('send-to-dialog', dialogId, channel, data);
    },
    onMessage: (channel, callback) => {
        preloadLog('INFO', 'on:message', channel);
        const handler = (_event, data) => callback(data);
        ipcRenderer.on(channel, handler);
        return handler;
    },
    removeMessageListener: (channel, handler) => {
        preloadLog('INFO', 'removeListener:message', channel);
        ipcRenderer.removeListener(channel, handler);
    },

    // 浮窗大小调整
    resizeFloatingWindow: (windowId, size) => {
        preloadLog('INFO', 'invoke:resize-floating-window', { windowId, size });
        return ipcRenderer.invoke('resize-floating-window', windowId, size);
    },

    // 获取浮窗当前尺寸
    getFloatingWindowSize: (windowId) => {
        preloadLog('INFO', 'invoke:get-floating-window-size', windowId);
        return ipcRenderer.invoke('get-floating-window-size', windowId);
    },

    // 显示确认对话框（避免原生 confirm 导致焦点丢失问题）
    showConfirm: (options) => {
        preloadLog('INFO', 'invoke:show-confirm', options);
        return ipcRenderer.invoke('show-confirm', options);
    },

    // 显示消息对话框（避免原生 alert 导致焦点丢失问题）
    showAlert: (options) => {
        preloadLog('INFO', 'invoke:show-alert', options);
        return ipcRenderer.invoke('show-alert', options);
    },
});

// 在控制台输出 Electron 环境信息
console.log('[Preload] Electron 预加载脚本已加载');
console.log('[Preload] electronAPI 已暴露到 window 对象');
