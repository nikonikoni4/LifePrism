# LifePrism 运行与打包指南

本文档说明 LifePrism 的所有运行模式、启动方式和打包流程。

---

## 📋 目录

- [运行模式概览](#运行模式概览)
- [开发模式](#开发模式)
  - [方式 1：直接 Python 运行](#方式-1直接-python-运行)
  - [方式 2：使用 start.sh 脚本](#方式-2使用-startsh-脚本)
  - [方式 3：前端开发服务器](#方式-3前端开发服务器)
- [打包模式](#打包模式)
  - [Windows Electron 桌面版](#windows-electron-桌面版)
  - [Web-Demo 部署版](#web-demo-部署版)

---

## 运行模式概览

LifePrism 支持三种运行形态：

| 模式 | 说明 | 后端入口 | 前端形式 | 适用场景 |
|------|------|---------|---------|---------|
| **Desktop** | Windows 桌面完整版 | `lifeprism.server.main` | Electron 应用 | 本地开发、Windows 用户 |
| **Web-Demo** | Windows、Linux Web 演示版 | `lifeprism.server.main_web_demo` | 静态 HTML (dist/) | 在线演示、服务器部署 |
| **Agent-Only** | Windows、Linux Agent 独立版 | `lifeprism.server.main_agent_only` | 无前端 | 仅 Agent + 微信 Channel |

---

## 开发模式

### 方式 1：直接 Python 运行

#### Desktop 模式（本地开发）

```bash
# 激活 Python 环境
conda activate lifeprism_dev

# 启动后端（默认 127.0.0.1:8000）
python -m uvicorn lifeprism.server.main:app --host 127.0.0.1 --port 8000 --reload

# 启动前端（另一个终端）
cd frontend
npm run dev
```

**访问**：
- 前端：`http://localhost:5173`（Vite dev server）
- 后端 API 文档：`http://127.0.0.1:8000/docs`

#### Web-Demo 模式（服务器测试）

```bash
# 1. 生成演示数据（可选，首次启动时自动生成）
python scripts/demo/generate_demo_data.py

# 2. 启动后端（监听 0.0.0.0:8101，只读模式）
python -m uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101 --reload

# 3. 启动前端（测试弹窗等功能，另一个终端）
cd frontend
npm run dev
```

**访问**：
- 前端：`http://localhost:5173`
- 后端 API 文档：`http://服务器IP:8101/docs`

**注意**：
- Web-Demo 后端会拦截所有写操作（返回 403 + 提示信息）
- 演示数据默认覆盖过去 7 天，详见 [`scripts/demo/README.md`](../scripts/demo/README.md)

#### Agent-Only 模式（仅 Agent）

```bash
# 仅启动 Agent Loop + WeChat Channel
python -m lifeprism.server.main_agent_only
```

**说明**：无 Web 服务，适合微信机器人独立运行。

---

### 方式 2：使用 start.sh 脚本

`start.sh` 是统一启动脚本，支持三种模式的后台/前台启动。

#### 基本用法

```bash
./scripts/start.sh <mode> <action>
```

**参数说明**：

| 参数 | 可选值 | 说明 |
|------|--------|------|
| `mode` | `desktop` / `web-demo` / `agent-only` | 运行模式 |
| `action` | `start` / `stop` / `status` / `restart` / `foreground` | 操作 |

#### 常用命令

```bash
# Desktop 模式（前台调试）
./scripts/start.sh desktop foreground

# Web-Demo 模式（后台启动）
./scripts/start.sh web-demo start

# 查看 Web-Demo 状态
./scripts/start.sh web-demo status

# 停止 Web-Demo
./scripts/start.sh web-demo stop

# 重启 Agent-Only
./scripts/start.sh agent-only restart
```

#### 环境变量配置

```bash
# 自定义数据目录
export LIFEPRISM_DATA_PATH=/path/to/data

# 自定义监听地址和端口
export LIFEPRISM_HOST=0.0.0.0
export LIFEPRISM_PORT=8101

./scripts/start.sh web-demo start
```

**默认配置**：

| 模式 | 默认 Host | 默认 Port |
|------|----------|----------|
| Desktop | 127.0.0.1 | 8000 |
| Web-Demo | 0.0.0.0 | 8101 |
| Agent-Only | - | - |

---

### 方式 3：前端开发服务器

#### 开发模式（热更新）

```bash
cd frontend
npm run dev
```

**访问**：`http://localhost:5173`

#### 测试 Demo 弹窗（开发环境）

如果需要在开发时测试 Demo 引导弹窗：

1. **临时启用 Demo 模式**（创建 `.env.development`）：
   ```bash
   cd frontend
   echo "VITE_DEMO_MODE=true" > .env.development
   ```

2. **重启 dev server**：
   ```bash
   npm run dev
   ```

3. **清除 sessionStorage**（浏览器控制台）：
   ```javascript
   sessionStorage.clear();
   location.reload();
   ```

**注意**：测试完成后删除 `.env.development`，避免干扰正常开发。

---

## 打包模式

### Windows Electron 桌面版

#### 完整打包流程

```bash
# 1. 完整打包（后端 + 前端）
build.bat

# 2. 仅打包后端
build.bat backend

# 3. 仅打包前端（需要先打包后端）
build.bat frontend
```

#### 打包步骤详解

##### 1. 后端打包（PyInstaller）

```bash
build.bat backend
```

**输出位置**：`pyinstaller-dist/lifeprism-backend/`

**包含内容**：
- `lifeprism-backend.exe`（后端可执行文件）
- Python 运行时 + 依赖库
- 配置文件和资源

##### 2. 前端打包（Vite + Electron Builder）

```bash
build.bat frontend
```

**前置条件**：必须先执行 `build.bat backend`

**打包流程**：
1. Vite 构建前端静态资源 → `frontend/dist/`
2. Electron Builder 打包 → `frontend/release/`

**输出位置**：`frontend/release/`

**包含内容**：
- LifePrism-x.x.x-Setup.exe（NSIS 安装包）
- 前端 dist/ + Electron 运行时
- 嵌入的后端 exe（自动复制）

#### 安装包说明

**安装路径**：
- 程序：`%LOCALAPPDATA%\Programs\LifePrism\`
- 用户数据：`%LOCALAPPDATA%\LifePrism\lifeprismData\`
- 配置文件：`%LOCALAPPDATA%\LifePrism\config\`

**启动方式**：
- 开始菜单 → LifePrism
- 桌面快捷方式（可选）

---

### Web-Demo 部署版

#### 前端打包

##### Demo 模式打包（显示引导弹窗）

```bash
cd frontend
npm run build:demo
```

**环境变量**（读取 `.env.demo`）：
- `VITE_DEMO_MODE=true`（启用 Demo 引导弹窗）

**输出位置**：`frontend/dist/`

**包含内容**：
- `index.html`（入口页面）
- `assets/`（JS/CSS/字体/图片）
- `branding/`（品牌资源）

##### 普通模式打包（不显示弹窗）

```bash
cd frontend
npm run build
```

**环境变量**（读取 `.env.production`，默认）：
- `VITE_DEMO_MODE` 未设置或为 `false`

#### 后端启动

##### 方式 1：直接启动

```bash
# 1. 生成演示数据（首次或定期刷新）
python scripts/demo/generate_demo_data.py

# 2. 启动 Web-Demo 后端
python -m uvicorn lifeprism.server.main_web_demo:app \
    --host 0.0.0.0 \
    --port 8101
```

##### 方式 2：使用 start.sh

```bash
# 后台启动
./scripts/start.sh web-demo start

# 查看状态
./scripts/start.sh web-demo status
```

#### 演示数据管理

**初次生成**（手动）：
```bash
cd /path/to/LifeWatch-AI
python scripts/demo/generate_demo_data.py
```

**定时刷新**（每天凌晨 4 点）：
```bash
# 编辑 crontab
crontab -e

# 添加以下行（修改路径）
0 4 * * * cd /path/to/LifeWatch-AI && /path/to/venv/bin/python scripts/demo/generate_demo_data.py >> /path/to/LifeWatch-AI/localData/debug_logs/demo_cron.log 2>&1
```

**说明**：
- 演示数据覆盖过去 7 天（以今天为终点）
- 生成内容包括：日志、行为分析、待办、日记、目标、习惯等 21 张表 + 3 个文件
- 详细说明见 [`scripts/demo/README.md`](../scripts/demo/README.md)

#### 部署到服务器

##### 1. 上传文件

```bash
# 上传前端静态资源
scp -r frontend/dist/* user@server:/path/to/nginx/html/

# 上传后端代码（或使用 git pull）
scp -r lifeprism/ scripts/ user@server:/path/to/LifeWatch-AI/
```

##### 2. 配置 Nginx

```nginx
server {
    listen 80;
    server_name your-domain.com;
    root /path/to/nginx/html;
    index index.html;

    # 前端静态文件
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api {
        proxy_pass http://127.0.0.1:8101;
        proxy_http_version 1.1;
        
        # SSE 支持（Agent 输出流）
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        chunked_transfer_encoding on;
        
        # 超时设置
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
```

##### 3. 启动后端

```bash
# 服务器上执行
cd /path/to/LifeWatch-AI
./scripts/start.sh web-demo start
```

##### 4. 进程守护（可选）

**方式 A：systemd**（推荐）

创建 `/etc/systemd/system/lifeprism-web-demo.service`：

```ini
[Unit]
Description=LifePrism Web Demo
After=network.target

[Service]
Type=forking
User=your-user
WorkingDirectory=/path/to/LifeWatch-AI
Environment="LIFEPRISM_DATA_PATH=/path/to/data"
ExecStart=/path/to/LifeWatch-AI/scripts/start.sh web-demo start
ExecStop=/path/to/LifeWatch-AI/scripts/start.sh web-demo stop
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：
```bash
sudo systemctl daemon-reload
sudo systemctl enable lifeprism-web-demo
sudo systemctl start lifeprism-web-demo
sudo systemctl status lifeprism-web-demo
```

**方式 B：nohup 循环**（简单但不推荐）

```bash
# 自动重启脚本
while true; do
    ./scripts/start.sh web-demo foreground
    echo "[$(date)] 进程退出，10 秒后重启..." >> web-demo-guard.log
    sleep 10
done
```

---

## 🔍 常见问题

### Q1：Demo 弹窗不显示？

**原因**：前端打包时未启用 Demo 模式。

**解决**：
```bash
cd frontend
npm run build:demo  # 注意必须用 build:demo，不是 build
```

**验证**：
```bash
cd frontend/dist/assets
grep "isDemoMode" *.js
# 应该看到: const isDemoMode = "true" === "true"
```

### Q2：Web-Demo 后端可以写入数据？

**原因**：使用了错误的后端入口。

**检查**：
```bash
# ✅ 正确（只读模式）
python -m uvicorn lifeprism.server.main_web_demo:app ...

# ❌ 错误（可写）
python -m uvicorn lifeprism.server.main:app ...
```

### Q3：build.bat 失败？

**常见原因**：
1. **后端打包失败**：
   - 检查 conda 环境：`conda activate lifeprism_dev`
   - 检查 PyInstaller：`pip show pyinstaller`

2. **前端打包失败**：
   - 先运行 `build.bat backend`
   - 检查 `pyinstaller-dist/lifeprism-backend/lifeprism-backend.exe` 是否存在

### Q4：start.sh 无法启动？

**常见原因**：
1. **权限不足**：`chmod +x scripts/start.sh`
2. **Python 环境**：确保 `python` 命令可用（或激活 conda 环境）
3. **端口占用**：检查端口是否被占用 `netstat -tuln | grep 8101`

### Q5：演示数据过期（日期不对）？

**原因**：数据生成后未定期刷新。

**解决**：
```bash
# 手动刷新
python scripts/demo/generate_demo_data.py

# 或等待 cron 自动刷新（凌晨 4 点）
```

---

## 📚 相关文档

- [演示数据说明](../scripts/demo/README.md)
- [架构地图](./ARCHITECTURE.md)
- [编码规则](./coding-rules/index.md)
