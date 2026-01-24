const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow;
let backendProcess;

// 获取 customData 路径（安装目录内）
function getCustomDataPath() {
    if (app.isPackaged) {
        // 打包后：resources/customData
        return path.join(process.resourcesPath, 'customData');
    } else {
        // 开发时：frontend/customData
        return path.join(__dirname, '..', 'customData');
    }
}

// 启动 Python 后端
function startBackend() {
    const customDataPath = getCustomDataPath();

    if (app.isPackaged) {
        const backendPath = path.join(process.resourcesPath, 'backend', 'lifeprism-backend.exe');
        console.log(`[Electron] 启动后端: ${backendPath}`);
        backendProcess = spawn(backendPath, [], {
            env: { ...process.env, CUSTOM_DATA_PATH: customDataPath },
            stdio: 'pipe'
        });
    } else {
        // 开发模式：直接运行 Python
        console.log('[Electron] 开发模式：启动 Python 后端...');
        backendProcess = spawn('python', ['-m', 'lifeprism.server.main'], {
            cwd: path.join(__dirname, '..', '..'),
            env: { ...process.env, CUSTOM_DATA_PATH: customDataPath },
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
        show: false // 先隐藏，加载完成后显示
    });

    // 直接加载构建后的文件（npm run electron:dev 会先构建）
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));

    // 窗口加载完成后显示
    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // 开发时打开开发者工具
    if (!app.isPackaged) {
        mainWindow.webContents.openDevTools();
    }
}

// IPC: 获取 customData 路径
ipcMain.handle('get-custom-data-path', () => getCustomDataPath());

// IPC: 获取应用是否打包
ipcMain.handle('is-packaged', () => app.isPackaged);

// IPC: 获取配置文件
ipcMain.handle('get-config', () => {
    const configPath = path.join(getCustomDataPath(), 'config', 'config.json');
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

app.whenReady().then(() => {
    console.log('[Electron] 应用启动中...');
    console.log(`[Electron] CustomData 路径: ${getCustomDataPath()}`);

    // 确保 customData 目录存在
    const customDataPath = getCustomDataPath();
    const externalFilesPath = path.join(customDataPath, 'external_files');

    if (!fs.existsSync(customDataPath)) {
        fs.mkdirSync(customDataPath, { recursive: true });
        console.log(`[Electron] 创建 customData 目录: ${customDataPath}`);
    }

    if (!fs.existsSync(externalFilesPath)) {
        fs.mkdirSync(externalFilesPath, { recursive: true });
        console.log(`[Electron] 创建 external_files 目录: ${externalFilesPath}`);
    }

    // 启动后端
    startBackend();

    // 等待后端启动后再创建窗口
    console.log('[Electron] 等待后端启动...');
    setTimeout(() => {
        createWindow();
    }, 3000);
});

app.on('window-all-closed', () => {
    console.log('[Electron] 所有窗口已关闭');

    // 关闭后端进程
    if (backendProcess) {
        console.log('[Electron] 正在关闭后端进程...');
        backendProcess.kill();
    }

    app.quit();
});

app.on('activate', () => {
    // macOS 上点击 dock 图标时重新创建窗口
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});

// 处理未捕获的异常
process.on('uncaughtException', (error) => {
    console.error('[Electron] 未捕获的异常:', error);
});
