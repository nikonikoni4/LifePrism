const { autoUpdater } = require('electron-updater');

let mainWindow = null;
let pendingEvents = [];

// 安全地向渲染进程发送消息
function sendStatusToWindow(channel, data) {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(channel, data);
    } else {
        pendingEvents.push({ channel, data });
    }
}

// 设置主窗口引用，并 flush 缓冲事件
function setMainWindow(win) {
    mainWindow = win;
    if (pendingEvents.length > 0) {
        console.log(`[Updater] Flush ${pendingEvents.length} 条缓冲事件`);
        for (const { channel, data } of pendingEvents) {
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send(channel, data);
            }
        }
        pendingEvents = [];
    }
}

// 初始化 autoUpdater（仅打包环境）
function initUpdater(isPackaged) {
    if (!isPackaged) {
        console.log('[Updater] 开发模式，跳过 autoUpdater 初始化');
        return;
    }

    autoUpdater.autoDownload = false;
    autoUpdater.autoInstallOnAppQuit = true;

    autoUpdater.on('checking-for-update', () => {
        console.log('[Updater] 正在检查更新...');
        sendStatusToWindow('updater:status', { status: 'checking' });
    });

    autoUpdater.on('update-available', (info) => {
        console.log(`[Updater] 发现新版本: ${info.version}`);
        sendStatusToWindow('updater:status', {
            status: 'available',
            version: info.version,
            releaseNotes: info.releaseNotes || null,
        });
    });
    autoUpdater.on('update-not-available', () => {
        console.log('[Updater] 当前已是最新版本');
        sendStatusToWindow('updater:status', { status: 'not-available' });
    });

    autoUpdater.on('download-progress', (progress) => {
        sendStatusToWindow('updater:progress', {
            bytesPerSecond: progress.bytesPerSecond,
            percent: progress.percent,
            transferred: progress.transferred,
            total: progress.total,
        });
    });

    autoUpdater.on('update-downloaded', (info) => {
        console.log(`[Updater] 更新已下载: ${info.version}`);
        sendStatusToWindow('updater:status', {
            status: 'downloaded',
            version: info.version,
        });
    });

    autoUpdater.on('error', (err) => {
        console.error('[Updater] 更新出错:', err.message);
        sendStatusToWindow('updater:status', {
            status: 'error',
            message: err.message,
        });
    });

    console.log('[Updater] autoUpdater 初始化完成');
}

// 检查更新
async function checkForUpdates(isPackaged) {
    if (!isPackaged) {
        return { status: 'dev-mode', message: '开发模式下不支持自动更新' };
    }
    try {
        const result = await autoUpdater.checkForUpdates();
        return { status: 'checking', version: result?.updateInfo?.version };
    } catch (err) {
        console.error('[Updater] 检查更新失败:', err.message);
        return { status: 'error', message: err.message };
    }
}

// 下载更新
async function downloadUpdate(isPackaged) {
    if (!isPackaged) {
        return { status: 'dev-mode', message: '开发模式下不支持自动更新' };
    }
    try {
        sendStatusToWindow('updater:status', { status: 'downloading' });
        await autoUpdater.downloadUpdate();
        return { status: 'downloading' };
    } catch (err) {
        console.error('[Updater] 下载更新失败:', err.message);
        return { status: 'error', message: err.message };
    }
}

// 退出并安装
function quitAndInstall() {
    autoUpdater.quitAndInstall();
}

module.exports = {
    initUpdater,
    setMainWindow,
    checkForUpdates,
    downloadUpdate,
    quitAndInstall,
};
