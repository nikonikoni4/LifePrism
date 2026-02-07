const { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let backendProcess;
let tray = null;

// 获取 lifeprismData 路径
function getLifeprismDataPath() {
    if (app.isPackaged) {
        // 打包后：%APPDATA%/LifePrism/lifeprismData
        return path.join(app.getPath('appData'), 'LifePrism', 'lifeprismData');
    } else {
        // 开发时：frontend/lifeprismData
        return path.join(__dirname, '..', 'lifeprismData');
    }
}

// DEPRECATED: 保留向后兼容
function getCustomDataPath() {
    return getLifeprismDataPath();
}

// 启动 Python 后端
function startBackend() {
    const lifeprismDataPath = getLifeprismDataPath();

    if (app.isPackaged) {
        const backendPath = path.join(process.resourcesPath, 'backend', 'lifeprism-backend.exe');
        console.log(`[Electron] 启动后端: ${backendPath}`);
        backendProcess = spawn(backendPath, [], {
            env: { ...process.env, LIFEPRISM_DATA_PATH: lifeprismDataPath },
            stdio: 'pipe'
        });
    } else {
        // 开发模式：直接运行 Python
        console.log('[Electron] 开发模式：启动 Python 后端...');
        backendProcess = spawn('python', ['-m', 'lifeprism.server.main'], {
            cwd: path.join(__dirname, '..', '..'),
            env: { ...process.env, LIFEPRISM_DATA_PATH: lifeprismDataPath },
            stdio: 'pipe',
            shell: true
        });
    }

    backendProcess.stdout.on('data', (data) => {
        console.log(`[Backend] ${data.toString().trim()}`);
    });

    backendProcess.stderr.on('data', (data) => {
        console.error(`[Backend Error] ${data.toString().trim()}`);
    });

    backendProcess.on('error', (err) => {
        console.error('[Backend] 启动失败:', err);
    });

    backendProcess.on('exit', (code) => {
        console.log(`[Backend] 进程退出，代码: ${code}`);
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

    // 直接加载构建后的文件（npm run electron:dev 会先构建）
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));

    // 窗口加载完成后显示
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // 点击关闭按钮时，隐藏窗口到托盘而不是关闭
    mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
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
    const configPath = path.join(getLifeprismDataPath(), 'config', 'config.json');
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

// IPC: 退出应用（数据迁移后调用）
ipcMain.handle('app-quit', () => {
    app.isQuitting = true;
    app.quit();
});

app.whenReady().then(() => {
    console.log('[Electron] 应用启动中...');
    console.log(`[Electron] LifePrism 数据路径: ${getLifeprismDataPath()}`);

    // 确保 lifeprismData 目录存在
    const dataPath = getLifeprismDataPath();
    const externalFilesPath = path.join(dataPath, 'external_files');

    if (!fs.existsSync(dataPath)) {
        fs.mkdirSync(dataPath, { recursive: true });
        console.log(`[Electron] 创建 lifeprismData 目录: ${dataPath}`);

        // 打包环境：从 resources/lifeprismData 复制模板数据
        if (app.isPackaged) {
            const templatePath = path.join(process.resourcesPath, 'lifeprismData');
            if (fs.existsSync(templatePath)) {
                fs.cpSync(templatePath, dataPath, { recursive: true });
                console.log(`[Electron] 已从模板复制初始数据到: ${dataPath}`);
            }
        }
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
    }, 3000);
});

// 应用退出前的清理工作
app.on('before-quit', () => {
    console.log('[Electron] 应用即将退出...');
    app.isQuitting = true;

    // 关闭后端进程
    if (backendProcess) {
        console.log('[Electron] 正在关闭后端进程...');
        backendProcess.kill();
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
