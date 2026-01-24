const { contextBridge, ipcRenderer } = require('electron');

// 安全地暴露 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
    // 获取 customData 文件夹路径
    getCustomDataPath: () => ipcRenderer.invoke('get-custom-data-path'),

    // 获取应用是否为打包状态
    isPackaged: () => ipcRenderer.invoke('is-packaged'),

    // 获取配置文件（用于端口配置等）
    getConfig: () => ipcRenderer.invoke('get-config'),

    // 可以在这里扩展更多 API
    // 例如：文件操作、系统通知等
});

// 在控制台输出 Electron 环境信息
console.log('[Preload] Electron 预加载脚本已加载');
console.log('[Preload] electronAPI 已暴露到 window 对象');
