const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog, shell } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const log = require('electron-log');
const yaml = require('js-yaml');
const { initUpdater, setMainWindow, checkForUpdates, downloadUpdate, quitAndInstall } = require('./updater.cjs');

let mainWindow;
let backendProcess;
let tray = null;
let floatingWindows = {};

const MAX_LOG_SIZE = 5 * 1024 * 1024; // 5MB

// 获取配置基础路径（固定，不随数据迁移）
function getConfigBasePath() {
    if (app.isPackaged) {
        // 打包后：%LOCALAPPDATA%/LifePrism/lifeprismData
        return path.join(process.env.LOCALAPPDATA || app.getPath('appData'), 'LifePrism', 'lifeprismData');
    } else {
        // 开发时：项目根目录/localData
        return path.join(__dirname, '..', '..', 'localData');
    }
}

// 获取 lifeprismData 路径（可迁移，优先读取 yaml 配置）
function getLifeprismDataPath() {
    const configBasePath = getConfigBasePath();
    const configPath = path.join(configBasePath, 'config', 'config.yaml');

    // 优先级 1: 读取 yaml 配置
    if (fs.existsSync(configPath)) {
        try {
            const config = yaml.load(fs.readFileSync(configPath, 'utf8'));
            if (config && config.lifeprism_data_path) {
                return config.lifeprism_data_path;
            }
        } catch (e) {
            console.error('读取 yaml 配置失败:', e);
        }
    }

    // 优先级 2: 使用默认路径（与 configBasePath 相同）
    return configBasePath;
}

// DEPRECATED: 保留向后兼容
function getCustomDataPath() {
    return getLifeprismDataPath();
}

// 初始化前端日志文件
function initFrontendLog() {
    const logDir = path.join(getLifeprismDataPath(), 'debug_logs');
    if (!fs.existsSync(logDir)) {
        fs.mkdirSync(logDir, { recursive: true });
    }

    const logPath = path.join(logDir, 'electron.log');

    // 启动时清空旧日志
    try {
        if (fs.existsSync(logPath)) {
            fs.writeFileSync(logPath, '');
        }
    } catch (e) {
        console.error('清空日志文件失败:', e);
    }

    // 配置 electron-log
    log.transports.file.resolvePathFn = () => logPath;
    log.transports.file.level = 'info';
    log.transports.file.format = '{y}-{m}-{d} {h}:{i}:{s}.{ms} {level} {text}';
    log.transports.console.level = 'info';
    log.transports.console.format = '{y}-{m}-{d} {h}:{i}:{s}.{ms} {level} {text}';

    // 劫持 console，让所有 console.log/error/warn 都通过 electron-log
    console.log = log.info;
    console.error = log.error;
    console.warn = log.warn;
    console.info = log.info;
    console.debug = log.debug;

    log.info('Electron 日志系统初始化完成');
    log.info(`数据路径: ${getLifeprismDataPath()}`);
}

// 启动 Python 后端
function startBackend() {
    const lifeprismDataPath = getLifeprismDataPath();

    if (app.isPackaged) {
        const backendPath = path.join(process.resourcesPath, 'backend', 'lifeprism-backend.exe');
        console.log(`[Electron] 启动后端: ${backendPath}`);
        backendProcess = spawn(backendPath, [], {
            env: {
                ...process.env,
                LIFEPRISM_DATA_PATH: lifeprismDataPath,
                PYTHONIOENCODING: 'utf-8'
            },
            stdio: 'pipe'
        });
    } else {
        // 开发模式：直接运行 Python
        console.log('[Electron] 开发模式：启动 Python 后端...');
        backendProcess = spawn('python', ['-m', 'lifeprism.server.main'], {
            cwd: path.join(__dirname, '..', '..'),
            env: {
                ...process.env,
                LIFEPRISM_DATA_PATH: lifeprismDataPath,
                PYTHONIOENCODING: 'utf-8'
            },
            stdio: 'pipe',
            shell: true
        });
    }

    backendProcess.stdout.on('data', (data) => {
        const msg = data.toString().trim();
        console.log(`[Backend] ${msg}`);
        log.info(`[Backend stdout] ${msg}`);
    });

    backendProcess.stderr.on('data', (data) => {
        const msg = data.toString().trim();
        console.error(`[Backend Error] ${msg}`);
        log.error(`[Backend stderr] ${msg}`);
    });

    backendProcess.on('error', (err) => {
        console.error('[Backend] 启动失败:', err);
        log.error('[Backend] 启动失败:', err);
    });

    backendProcess.on('exit', (code) => {
        console.log(`[Backend] 进程退出，代码: ${code}`);
        log.info(`[Backend] 进程退出，代码: ${code}`);
    });
}

// 创建系统托盘
function createTray() {
    // 获取托盘图标路径
    let iconPath;
    if (app.isPackaged) {
        // 打包后，图标在 resources/app.asar 外部
        iconPath = path.join(process.resourcesPath, 'app.asar.unpacked', 'dist', 'branding', 'lifeprism.ico');
        // 如果上面路径不存在，尝试使用 public 目录
        if (!fs.existsSync(iconPath)) {
            iconPath = path.join(__dirname, '..', 'dist', 'branding', 'lifeprism.ico');
        }
        // 最后尝试 public 目录
        if (!fs.existsSync(iconPath)) {
            iconPath = path.join(__dirname, '..', 'public', 'branding', 'lifeprism.ico');
        }
    } else {
        iconPath = path.join(__dirname, '..', 'public', 'branding', 'lifeprism.ico');
    }

    console.log(`[Electron] 托盘图标路径: ${iconPath}`);

    // 创建托盘图标
    const trayIcon = nativeImage.createFromPath(iconPath);
    tray = new Tray(trayIcon.resize({ width: 16, height: 16 }));

    // 创建托盘右键菜单
    const contextMenu = Menu.buildFromTemplate([
        {
            label: '显示主窗口',
            click: () => {
                if (mainWindow) {
                    mainWindow.show();
                    mainWindow.focus();
                }
            }
        },
        {
            label: '隐藏窗口',
            click: () => {
                if (mainWindow) {
                    mainWindow.hide();
                }
            }
        },
        { type: 'separator' },
        {
            label: '退出 LifePrism',
            click: () => {
                // 标记为真正退出
                app.isQuitting = true;
                app.quit();
            }
        }
    ]);

    tray.setToolTip('LifePrism - 个人时间管理');
    tray.setContextMenu(contextMenu);

    // 点击托盘图标显示/隐藏窗口
    tray.on('click', () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });

    // 双击托盘图标显示窗口
    tray.on('double-click', () => {
        if (mainWindow) {
            mainWindow.show();
            mainWindow.focus();
        }
    });
}

// 创建窗口
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        icon: path.join(__dirname, '..', 'public', 'branding', 'lifeprism.png'),
        webPreferences: {
            preload: path.join(__dirname, 'preload.cjs'),
            nodeIntegration: false,
            contextIsolation: true
        },
        show: false, // 先隐藏，加载完成后显示
        autoHideMenuBar: true // 自动隐藏菜单栏
    });

    // 移除默认菜单栏
    mainWindow.setMenu(null);

    // 捕获 renderer 进程的 console 输出写入日志文件
    mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
        // 使用 electron-log 记录
        if (level === 3) { // ERROR
            log.error(`[Renderer] ${message}`, { source: sourceId, line });
        } else if (level === 2) { // WARN
            log.warn(`[Renderer] ${message}`, { source: sourceId, line });
        } else {
            log.info(`[Renderer] ${message}`, { source: sourceId, line });
        }
    });

    // 直接加载构建后的文件（npm run electron:dev 会先构建）
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));

    // 窗口加载完成后显示
    mainWindow.once('ready-to-show', () => {
        log.info('[Window] ready-to-show, calling show()');
        mainWindow.show();
        log.info('[Window] mainWindow shown');
    });

    // 点击关闭按钮时，隐藏窗口到托盘而不是关闭
    mainWindow.on('close', (event) => {
        log.info('[Window] close event', { isQuitting: app.isQuitting });
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
            log.info('[Window] mainWindow hidden to tray');
            // 可选：显示托盘通知（首次隐藏时）
            if (tray && !app.hasShownTrayNotification) {
                tray.displayBalloon({
                    iconType: 'info',
                    title: 'LifePrism',
                    content: '应用已最小化到系统托盘，点击托盘图标可重新打开。'
                });
                app.hasShownTrayNotification = true;
            }
        }
    });

    // 窗口焦点事件
    mainWindow.on('focus', () => {
        log.info('[Window] focus event');
    });

    mainWindow.on('blur', () => {
        log.info('[Window] blur event');
    });

    // 窗口不可见/可见事件
    mainWindow.on('unresponsive', () => {
        log.warn('[Window] unresponsive!');
    });

    mainWindow.on('responsive', () => {
        log.info('[Window] responsive again');
    });

    // 页面崩溃事件
    mainWindow.webContents.on('crashed', (event, killed) => {
        log.error('[Window] renderer crashed!', { killed });
    });

    mainWindow.webContents.on('render-process-gone', (event, details) => {
        log.error('[Window] render process gone', details);
    });

    // 开发时打开开发者工具
    if (!app.isPackaged) {
        mainWindow.webContents.openDevTools();
    }
}

// IPC: 获取 lifeprismData 路径
ipcMain.handle('get-lifeprism-data-path', () => getLifeprismDataPath());

// IPC: 获取 customData 路径（向后兼容）
ipcMain.handle('get-custom-data-path', () => getLifeprismDataPath());

// IPC: 获取应用是否打包
ipcMain.handle('is-packaged', () => app.isPackaged);

// IPC: 获取配置文件
ipcMain.handle('get-config', () => {
    const configPath = path.join(getConfigBasePath(), 'config', 'config.json');
    try {
        if (fs.existsSync(configPath)) {
            const content = fs.readFileSync(configPath, 'utf-8');
            return JSON.parse(content);
        }
    } catch (e) {
        console.log('[Electron] 读取配置文件失败:', e);
    }
    return null;
});

// IPC: 选择目录
ipcMain.handle('select-directory', async () => {
    if (!mainWindow) return null;
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory']
    });
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
});

// IPC: 选择文件
ipcMain.handle('select-file', async (_event, filters) => {
    if (!mainWindow) return null;
    const options = {
        properties: ['openFile']
    };
    if (filters) {
        options.filters = filters;
    }
    const result = await dialog.showOpenDialog(mainWindow, options);
    if (result.canceled || result.filePaths.length === 0) return null;
    return result.filePaths[0];
});

// IPC: 获取安装路径
ipcMain.handle('get-install-path', () => {
    if (app.isPackaged) {
        return path.dirname(app.getPath('exe'));
    }
    return null;
});

// IPC: 在文件管理器中打开文件夹
ipcMain.handle('open-folder', async (_event, folderPath) => {
    if (!folderPath) return { success: false };
    try {
        await shell.openPath(folderPath);
        return { success: true };
    } catch (e) {
        console.log('[Electron] 打开文件夹失败:', e);
        return { success: false };
    }
});

// IPC: 退出应用（数据迁移后调用）
ipcMain.handle('app-quit', () => {
    app.isQuitting = true;
    app.quit();
});

// IPC: 打开浮窗
ipcMain.handle('open-floating-window', (_event, windowId) => {
    if (!windowId || typeof windowId !== 'string') {
        return { success: false, reason: 'invalid windowId' };
    }

    // 已存在且未销毁 → show + focus
    const existing = floatingWindows[windowId];
    if (existing && !existing.isDestroyed()) {
        log.info(`[open-floating-window] 窗口已存在: ${windowId}`);
        log.info(`  isVisible: ${existing.isVisible()}`);
        log.info(`  isFocused: ${existing.isFocused()}`);
        log.info(`  isAlwaysOnTop: ${existing.isAlwaysOnTop()}`);

        existing.show();
        existing.focus();

        log.info(`  执行 show() + focus() 后:`);
        log.info(`  isVisible: ${existing.isVisible()}`);
        log.info(`  isFocused: ${existing.isFocused()}`);
        log.info(`  isAlwaysOnTop: ${existing.isAlwaysOnTop()}`);

        return { success: true, action: 'focused' };
    }

    log.info(`[open-floating-window] 创建新窗口: ${windowId}`);

    const win = new BrowserWindow({
        width: 320,
        height: 400,
        frame: false,
        alwaysOnTop: true,
        resizable: true,
        skipTaskbar: false,
        webPreferences: {
            preload: path.join(__dirname, 'preload.cjs'),
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    // 增强置顶策略：使用多种方法确保窗口永远置顶
    // 参考：https://github.com/electron/electron/issues/37865
    win.setAlwaysOnTop(true, 'screen-saver');  // 使用最高层级 screen-saver
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });  // 在所有工作区和全屏时可见

    log.info(`[open-floating-window] 置顶设置完成: alwaysOnTop=${win.isAlwaysOnTop()}`);

    // 加载浮窗页面（hash 路由）
    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'), {
        hash: `/floating/${windowId}`
    });

    // 右键菜单
    win.webContents.on('context-menu', () => {
        const menu = Menu.buildFromTemplate([
            {
                label: '关闭浮窗',
                click: () => {
                    if (!win.isDestroyed()) win.close();
                }
            }
        ]);
        menu.popup({ window: win });
    });

    // 关闭时清理引用
    win.on('closed', () => {
        delete floatingWindows[windowId];
    });

    floatingWindows[windowId] = win;
    return { success: true, action: 'created' };
});

// IPC: 关闭浮窗
ipcMain.handle('close-floating-window', (_event, windowId) => {
    const win = floatingWindows[windowId];
    if (win && !win.isDestroyed()) {
        win.close();
        return { success: true };
    }
    return { success: false, reason: 'window not found' };
});

// 存储对话框窗口
let dialogWindows = {};

// IPC: 打开对话框窗口
ipcMain.handle('open-dialog-window', (_event, dialogId, options = {}) => {
    if (!dialogId || typeof dialogId !== 'string') {
        return { success: false, reason: 'invalid dialogId' };
    }

    // 已存在且未销毁 → show + focus
    const existing = dialogWindows[dialogId];
    if (existing && !existing.isDestroyed()) {
        existing.show();
        existing.focus();
        return { success: true, action: 'focused' };
    }

    // 根据 dialogId 设置不同的窗口大小
    const dialogConfigs = {
        'todo-picker': { width: 500, height: 600 },
        'record-activity': { width: 400, height: 450 },
        'default': { width: 400, height: 500 }
    };
    const config = dialogConfigs[dialogId] || dialogConfigs['default'];

    const win = new BrowserWindow({
        width: config.width,
        height: config.height,
        frame: false,           // 无边框
        alwaysOnTop: true,      // 置顶
        resizable: true,
        skipTaskbar: false,
        center: true,           // 居中显示
        webPreferences: {
            preload: path.join(__dirname, 'preload.cjs'),
            nodeIntegration: false,
            contextIsolation: true
        }
    });

    // 加载对话框页面（hash 路由）
    const loadOptions = {
        hash: `/dialog/${dialogId}`
    };

    // 如果有 query 参数，附加到 hash 后面
    if (options.query) {
        loadOptions.hash += `?${options.query}`;
    }

    win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'), loadOptions);

    // 右键菜单
    win.webContents.on('context-menu', () => {
        const menu = Menu.buildFromTemplate([
            {
                label: '关闭对话框',
                click: () => {
                    if (!win.isDestroyed()) win.close();
                }
            }
        ]);
        menu.popup({ window: win });
    });

    // 关闭时清理引用，并通知所有浮窗对话框已关闭
    win.on('closed', () => {
        delete dialogWindows[dialogId];
        
        // 向所有浮窗广播 dialog-closed 消息，用于清理监听器
        for (const [floatingId, floatingWin] of Object.entries(floatingWindows)) {
            if (floatingWin && !floatingWin.isDestroyed()) {
                floatingWin.webContents.send('dialog-closed', { dialogId });
            }
        }
    });

    dialogWindows[dialogId] = win;
    return { success: true, action: 'created' };
});

// IPC: 关闭对话框窗口
ipcMain.handle('close-dialog-window', (_event, dialogId) => {
    const win = dialogWindows[dialogId];
    if (win && !win.isDestroyed()) {
        win.close();
        return { success: true };
    }
    return { success: false, reason: 'dialog not found' };
});

// IPC: 浮窗/对话框 → 指定浮窗
ipcMain.handle('send-to-floating', (_event, windowId, channel, data) => {
    const win = floatingWindows[windowId];
    if (win && !win.isDestroyed()) {
        win.webContents.send(channel, data);
        return { success: true };
    }
    return { success: false };
});

// IPC: 浮窗/对话框 → 主窗口
ipcMain.handle('send-to-main', (_event, channel, data) => {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.webContents.send(channel, data);
        return { success: true };
    }
    return { success: false };
});

// IPC: 主窗口 → 对话框
ipcMain.handle('send-to-dialog', (_event, dialogId, channel, data) => {
    const win = dialogWindows[dialogId];
    if (win && !win.isDestroyed()) {
        win.webContents.send(channel, data);
        return { success: true };
    }
    return { success: false };
});

// IPC: 调整浮窗大小
ipcMain.handle('resize-floating-window', (_event, windowId, { width, height }) => {
    const win = floatingWindows[windowId];
    if (win && !win.isDestroyed()) {
        const [currentWidth, currentHeight] = win.getSize();
        const newWidth = width ?? currentWidth;
        const newHeight = Math.round(height);

        win.setSize(newWidth, newHeight);

        return { success: true };
    }
    return { success: false };
});

// IPC: 获取浮窗当前尺寸
ipcMain.handle('get-floating-window-size', (_event, windowId) => {
    const win = floatingWindows[windowId];
    if (win && !win.isDestroyed()) {
        const [width, height] = win.getSize();
        return { success: true, width, height };
    }
    return { success: false };
});

// IPC: 检查更新
ipcMain.handle('updater:check', () => checkForUpdates(app.isPackaged));

// IPC: 显示确认对话框（避免原生 confirm 导致焦点丢失问题）
ipcMain.handle('show-confirm', (_event, options) => {
    const { message, title = '确认' } = options;
    const result = dialog.showMessageBoxSync(mainWindow, {
        type: 'question',
        buttons: ['取消', '确定'],
        defaultId: 0,
        cancelId: 0,
        title: title,
        message: message,
    });
    // 返回 true 表示点击了"确定"（index === 1）
    return result === 1;
});

// IPC: 显示消息对话框（避免原生 alert 导致焦点丢失问题）
ipcMain.handle('show-alert', (_event, options) => {
    const { message, title = '提示' } = options;
    dialog.showMessageBoxSync(mainWindow, {
        type: 'info',
        buttons: ['确定'],
        defaultId: 0,
        title: title,
        message: message,
    });
});

// IPC: 下载更新
ipcMain.handle('updater:download', () => downloadUpdate(app.isPackaged));

// IPC: 退出并安装更新
ipcMain.handle('updater:quit-and-install', () => {
    app.isQuitting = true;
    quitAndInstall();
});

app.whenReady().then(() => {
    // 初始化日志（必须在第一条 console.log 之前）
    initFrontendLog();

    console.log('[Electron] 应用启动中...');
    console.log(`[Electron] LifePrism 数据路径: ${getLifeprismDataPath()}`);

    // 初始化自动更新
    initUpdater(app.isPackaged);

    // 确保 lifeprismData 目录存在
    const dataPath = getLifeprismDataPath();
    const externalFilesPath = path.join(dataPath, 'external_files');

    if (!fs.existsSync(dataPath)) {
        fs.mkdirSync(dataPath, { recursive: true });
        console.log(`[Electron] 创建 lifeprismData 目录: ${dataPath}`);
    }

    if (!fs.existsSync(externalFilesPath)) {
        fs.mkdirSync(externalFilesPath, { recursive: true });
        console.log(`[Electron] 创建 external_files 目录: ${externalFilesPath}`);
    }

    // 创建系统托盘
    createTray();

    // 启动后端
    startBackend();

    // 等待后端启动后再创建窗口
    console.log('[Electron] 等待后端启动...');
    setTimeout(() => {
        createWindow();
        setMainWindow(mainWindow);
    }, 10000);
});

// 应用退出前的清理工作
app.on('before-quit', () => {
    console.log('[Electron] 应用即将退出...');
    app.isQuitting = true;

    // 关闭所有浮窗
    for (const [id, win] of Object.entries(floatingWindows)) {
        if (win && !win.isDestroyed()) {
            win.close();
        }
    }
    floatingWindows = {};

    // 关闭所有对话框窗口
    for (const [id, win] of Object.entries(dialogWindows)) {
        if (win && !win.isDestroyed()) {
            win.close();
        }
    }
    dialogWindows = {};

    // 关闭后端进程
    if (backendProcess) {
        console.log('[Electron] 正在关闭后端进程...');

        if (process.platform === 'win32') {
            // Windows: 使用 taskkill 杀死进程树（包括所有子进程）
            // 修复 bug: 防止监控子进程变成孤儿进程
            // 详见: docs/temp/bugs/2026-04-22-backend-orphan-process.md
            const { exec } = require('child_process');
            exec(`taskkill /pid ${backendProcess.pid} /T /F`, (error) => {
                if (error) {
                    console.error('[Electron] 杀死后端进程树失败:', error);
                    log.error('[Electron] 杀死后端进程树失败:', error);
                } else {
                    console.log('[Electron] 后端进程树已终止');
                    log.info('[Electron] 后端进程树已终止');
                }
            });
        } else {
            // Unix/Linux/macOS: 使用 SIGTERM
            backendProcess.kill();
        }
    }

    // 销毁托盘
    if (tray) {
        tray.destroy();
        tray = null;
    }
});

app.on('window-all-closed', () => {
    console.log('[Electron] 所有窗口已关闭');
    // Windows/Linux: 不要在窗口关闭时退出，因为我们有托盘
    // 只有 macOS 需要保持应用运行
    if (process.platform !== 'darwin') {
        // 不自动退出，让用户从托盘退出
    }
});

app.on('activate', () => {
    // macOS 上点击 dock 图标时重新创建窗口
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    } else if (mainWindow) {
        mainWindow.show();
    }
});

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
    console.error('[Electron] 未捕获的异常:', error);
});
