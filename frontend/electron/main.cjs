const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog, shell, powerMonitor, net } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const http = require('http');
const log = require('electron-log');
const yaml = require('js-yaml');
const { initUpdater, setMainWindow, checkForUpdates, downloadUpdate, quitAndInstall } = require('./updater.cjs');

let mainWindow;
let backendProcess;
let backendPort = null; // 后端实际监听端口（从启动日志解析）
let tray = null;
let floatingWindows = {};

// 优雅关闭相关常量
const SHUTDOWN_HTTP_TIMEOUT_MS = 3000; // 调用 /shutdown 端点的 HTTP 超时
const SHUTDOWN_FORCE_KILL_TIMEOUT_MS = 5 * 60 * 1000; // 5 分钟超时后强制杀进程（参考思源 15 分钟 UI 超时）
const QUICK_SHUTDOWN_HTTP_TIMEOUT_MS = 2000; // 关机场景调用 /quick-shutdown 的 HTTP 超时（更短）
const QUICK_SHUTDOWN_FORCE_KILL_TIMEOUT_MS = 4000; // 关机场景 4 秒超时后强杀（Windows 只给 5 秒）
const RESUME_SYNC_HTTP_TIMEOUT_MS = 5000; // 唤醒后触发同步的 HTTP 超时

// 场景标志位（区分关机/睡眠/主动退出）
let isSystemShutdown = false; // Windows 关机/重启触发
let isSuspending = false; // 系统进入睡眠

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

        // 从 uvicorn 启动日志解析实际端口
        // 匹配 "Uvicorn running on http://0.0.0.0:8000" 或 "http://127.0.0.1:8000"
        const portMatch = msg.match(/Uvicorn running on http:\/\/[\d.]+:(\d+)/);
        if (portMatch && portMatch[1]) {
            backendPort = parseInt(portMatch[1], 10);
            log.info(`[Backend] 检测到后端实际监听端口: ${backendPort}`);
        }
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

// 调用后端 /api/v2/system/shutdown 端点触发优雅关闭
// 返回 Promise<boolean>：true 表示 HTTP 请求成功发出，false 表示请求失败
// 调用后端关闭端点（/shutdown 或 /quick-shutdown）
// endpoint: API 路径（如 '/api/v2/system/shutdown'）
// timeoutMs: HTTP 超时毫秒
// 返回 Promise<boolean>：true 表示 HTTP 请求成功发出，false 表示请求失败
function callBackendShutdown(endpoint, timeoutMs) {
    return new Promise((resolve) => {
        if (!backendPort) {
            log.warn(`[Shutdown] 后端端口未检测到，跳过 HTTP 调用 ${endpoint}，直接强杀`);
            resolve(false);
            return;
        }

        const postData = JSON.stringify({});
        const options = {
            hostname: '127.0.0.1',
            port: backendPort,
            path: endpoint,
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(postData),
            },
            timeout: timeoutMs,
        };

        const req = http.request(options, (res) => {
            let body = '';
            res.on('data', (chunk) => { body += chunk; });
            res.on('end', () => {
                log.info(`[Shutdown] ${endpoint} 响应: ${res.statusCode} ${body}`);
                resolve(res.statusCode === 202);
            });
        });

        req.on('error', (err) => {
            log.error(`[Shutdown] ${endpoint} 请求失败: ${err.message}`);
            resolve(false);
        });

        req.on('timeout', () => {
            log.warn(`[Shutdown] ${endpoint} 请求超时，可能后端已无响应`);
            req.destroy();
            resolve(false);
        });

        req.write(postData);
        req.end();
    });
}

// 强制杀死后端进程树（兜底方案，参考 docs/temp/bugs/2026-04-22-backend-orphan-process.md）
// 返回 Promise<void>，resolve 后表示 taskkill / kill 已完成（避免孤儿进程）
function forceKillBackend() {
    return new Promise((resolve) => {
        if (!backendProcess) {
            resolve();
            return;
        }

        log.warn('[Shutdown] 执行强制杀死后端进程树（兜底）');

        if (process.platform === 'win32') {
            // Windows: 使用 taskkill 杀死进程树（包括所有子进程，防止监控进程变孤儿）
            exec(`taskkill /pid ${backendProcess.pid} /T /F`, (error) => {
                if (error) {
                    log.error('[Shutdown] 强制杀死后端进程树失败:', error);
                } else {
                    log.info('[Shutdown] 后端进程树已强制终止');
                }
                resolve();
            });
        } else {
            // Unix/Linux/macOS: 使用 SIGKILL
            backendProcess.kill('SIGKILL');
            resolve();
        }
    });
}

// 优雅关闭后端：根据场景分流到完整关闭或快速关闭
async function gracefulShutdownBackend() {
    if (!backendProcess) {
        log.info('[Shutdown] 无后端进程，直接返回');
        return;
    }

    // 已退出（exit 事件已触发）
    if (backendProcess.exitCode !== null || backendProcess.killed) {
        log.info(`[Shutdown] 后端已退出（exitCode=${backendProcess.exitCode}, killed=${backendProcess.killed}），跳过关闭流程`);
        return;
    }

    // 根据场景选择关闭策略
    if (isSystemShutdown) {
        // Windows 关机场景：调用 quick-shutdown（跳过 sync_once，只发 offline 心跳）
        // 原因：Windows 只给 5 秒，sync_once 需要 1-3 分钟，中途被杀会导致 parent_hash 不一致
        log.info('[Shutdown] 检测到系统关机场景，执行快速关闭（跳过 sync_once）');
        await shutdownBackendWithStrategy(
            '/api/v2/system/quick-shutdown',
            QUICK_SHUTDOWN_HTTP_TIMEOUT_MS,
            QUICK_SHUTDOWN_FORCE_KILL_TIMEOUT_MS,
            '快速关闭'
        );
    } else {
        // 用户主动退出场景：完整优雅关闭（含 sync_once，5 分钟超时兜底）
        log.info('[Shutdown] 用户主动退出场景，执行完整优雅关闭（含 sync_once）');
        await shutdownBackendWithStrategy(
            '/api/v2/system/shutdown',
            SHUTDOWN_HTTP_TIMEOUT_MS,
            SHUTDOWN_FORCE_KILL_TIMEOUT_MS,
            '完整优雅关闭'
        );
    }
}

// 通用关闭策略：调用指定端点 → 监听 exit 事件 → 超时强杀兜底
// 抽取自 fullGracefulShutdownBackend 和 quickShutdownBackend 的共同逻辑
// label: 日志标识，用于区分"完整优雅关闭"和"快速关闭"
async function shutdownBackendWithStrategy(endpoint, httpTimeoutMs, forceKillTimeoutMs, label) {
    log.info(`[Shutdown] 开始${label}流程（endpoint=${endpoint}）`);

    // 1. 调用后端关闭端点（HTTP 请求立即返回 202，后端异步触发 SIGINT）
    const httpOk = await callBackendShutdown(endpoint, httpTimeoutMs);

    if (!httpOk) {
        // HTTP 请求失败，直接强杀
        log.warn(`[Shutdown] HTTP 调用 ${endpoint} 失败，直接强杀后端`);
        await forceKillBackend();
        return;
    }

    // 2. 监听后端进程 exit 事件（lifespan shutdown 完成后进程退出）
    //    使用 timeoutId 变量让 exitPromise 能在 resolve 时清理 timeout（避免 timer 泄漏）
    let timeoutId = null;

    const exitPromise = new Promise((resolve) => {
        if (backendProcess.exitCode !== null || backendProcess.killed) {
            // 已经退出（防止在 once 注册前退出的竞态）
            log.info(`[Shutdown] 后端进程已退出（${label}），代码: ${backendProcess.exitCode}`);
            resolve();
            return;
        }
        backendProcess.once('exit', (code) => {
            log.info(`[Shutdown] 后端进程已退出（${label}），代码: ${code}`);
            resolve();
        });
    });

    const timeoutPromise = new Promise((resolve) => {
        timeoutId = setTimeout(async () => {
            log.warn(`[Shutdown] ${label}超时（${forceKillTimeoutMs / 1000}s），执行强杀`);
            await forceKillBackend();
            resolve();
        }, forceKillTimeoutMs);
    });

    // 3. 竞速：任一 Promise resolve 后立即清理 timeout（避免 timer 泄漏）
    //    - exitPromise 先 resolve：clearTimeout 取消未触发的 setTimeout
    //    - timeoutPromise 先 resolve：setTimeout 已触发，clearTimeout 为 no-op
    await Promise.race([exitPromise, timeoutPromise]);
    if (timeoutId) clearTimeout(timeoutId);
    log.info(`[Shutdown] ${label}流程完成`);
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

// IPC: 在文件管理器中打开文件夹并选中指定文件
// Windows: shell.showItemInFolder(filePath)
ipcMain.handle('open-folder-and-select', (_event, filePath) => {
    if (!filePath) return { success: false };
    try {
        shell.showItemInFolder(filePath);
        return { success: true };
    } catch (e) {
        console.log('[Electron] 打开文件夹并选中文件失败:', e);
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

    // ========== 电源事件监听（参考思源 powerMonitor 设计） ==========
    // 必须在 whenReady 里面注册，否则 Linux 端可能无法正常启动

    // 系统关机/重启：设置标志位，让 before-quit 走快速关闭流程
    powerMonitor.on('shutdown', () => {
        log.info('[PowerMonitor] 系统关机/重启事件触发');
        isSystemShutdown = true;
    });

    // 系统进入睡眠/挂起：记录状态
    powerMonitor.on('suspend', () => {
        log.info('[PowerMonitor] 系统进入睡眠/挂起');
        isSuspending = true;
    });

    // 系统从睡眠唤醒：检查网络连通性后触发同步（参考思源 resume 设计）
    powerMonitor.on('resume', async () => {
        log.info('[PowerMonitor] 系统从睡眠唤醒');
        isSuspending = false;

        // 唤醒后检查网络连通性，再触发同步
        // 参考：https://github.com/siyuan-note/siyuan/issues/6687
        const checkAndSync = async () => {
            try {
                // 等待 2 秒让网络恢复连接
                await new Promise(resolve => setTimeout(resolve, 2000));

                const online = await net.isOnline();
                if (!online) {
                    log.warn('[PowerMonitor] 唤醒后网络未连接，跳过同步触发');
                    return;
                }

                if (!backendPort) {
                    log.warn('[PowerMonitor] 后端端口未检测到，跳过同步触发');
                    return;
                }

                log.info(`[PowerMonitor] 唤醒后网络已连接，触发后端同步 (port=${backendPort})`);

                // 调用后端 /api/sync/trigger 触发一次同步（后台线程执行，立即返回 202）
                const triggerReq = http.request({
                    hostname: '127.0.0.1',
                    port: backendPort,
                    path: '/api/sync/trigger',
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    timeout: RESUME_SYNC_HTTP_TIMEOUT_MS,
                }, (res) => {
                    let body = '';
                    res.on('data', (chunk) => { body += chunk; });
                    res.on('end', () => {
                        log.info(`[PowerMonitor] /api/sync/trigger 响应: ${res.statusCode} ${body}`);
                    });
                });

                triggerReq.on('error', (err) => {
                    log.error(`[PowerMonitor] /api/sync/trigger 请求失败: ${err.message}`);
                });

                triggerReq.on('timeout', () => {
                    log.warn('[PowerMonitor] /api/sync/trigger 请求超时');
                    triggerReq.destroy();
                });

                triggerReq.write('{}');
                triggerReq.end();
            } catch (err) {
                log.error('[PowerMonitor] 唤醒后同步触发异常:', err);
            }
        };

        checkAndSync();
    });

    // 系统锁屏（可选处理，目前只记录日志）
    powerMonitor.on('lock-screen', () => {
        log.info('[PowerMonitor] 系统锁屏');
    });
});

// 应用退出前的清理工作
let isShuttingDown = false; // 防止 before-quit 重入

app.on('before-quit', async (event) => {
    console.log('[Electron] 应用即将退出...');

    // 防止重入：异步关闭流程进行中再次触发退出时，允许默认行为
    if (isShuttingDown) {
        console.log('[Electron] 关闭流程进行中，允许退出');
        return;
    }

    app.isQuitting = true;
    isShuttingDown = true;

    // 阻止默认退出，等后端优雅关闭完成后再退出
    event.preventDefault();

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

    // 通知主窗口显示"正在同步并退出"提示（参考思源 util.PushMsg 设计）
    // 关机场景跳过 UI 通知（Windows 只给 5 秒，没时间等前端渲染遮罩）
    if (!isSystemShutdown && mainWindow && !mainWindow.isDestroyed()) {
        try {
            mainWindow.webContents.send('backend-shutdown-started');
            log.info('[Shutdown] 已通知前端显示关闭提示');
        } catch (e) {
            log.warn('[Shutdown] 通知前端失败:', e);
        }
    } else if (isSystemShutdown) {
        log.info('[Shutdown] 关机场景，跳过 UI 通知，直接快速关闭');
    }

    // 优雅关闭后端（参考思源 Close(false) 设计：等待同步完成才退出）
    try {
        await gracefulShutdownBackend();
    } catch (e) {
        log.error('[Shutdown] 优雅关闭流程异常:', e);
        // 异常时也强制杀进程（必须 await，避免 taskkill 未完成就 app.quit 导致孤儿进程）
        await forceKillBackend();
    }

    // 销毁托盘
    if (tray) {
        tray.destroy();
        tray = null;
    }

    // 后端已退出，现在可以真正退出 Electron
    log.info('[Electron] 后端关闭完成，退出 Electron');
    app.quit();
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
