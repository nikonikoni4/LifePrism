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
});

// 在控制台输出 Electron 环境信息
console.log('[Preload] Electron 预加载脚本已加载');
console.log('[Preload] electronAPI 已暴露到 window 对象');
