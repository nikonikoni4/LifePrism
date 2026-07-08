---
version: 1.0
created_at: 2026-07-08
updated_at: 2026-07-08
last_updated: 创建 Linux 部署指南初稿
abstract: LifePrism Linux 服务器部署完整指南，覆盖系统要求、依赖安装、三种运行模式（Web Demo / Agent Only）的启动命令与环境变量配置。
---

# Linux 部署指南

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿 |

---

## 1. 系统要求

| 项目 | 要求 |
| ---- | ---- |
| 操作系统 | Ubuntu 22.04+ / Debian 12+ / CentOS 9+（或其他主流 Linux 发行版） |
| Python | 3.11+（推荐 3.13） |
| Node.js | 18+（仅 Web Demo 模式需要，用于构建前端） |
| 内存 | 最低 1GB，推荐 2GB+ |
| 磁盘 | 最低 500MB（不含数据） |

## 2. 安装系统依赖

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nodejs npm
```

### CentOS / RHEL

```bash
sudo dnf install -y python3 python3-pip nodejs npm
```

## 3. 获取代码并安装 Python 依赖

```bash
git clone <repository-url> lifeprism
cd lifeprism

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -e .
```

### 关于 Windows 专用依赖

`pyproject.toml` 中的 `mss` 和 `pynput` 在 Linux 上安装可能失败。如果遇到安装错误，可手动跳过：

```bash
pip install -e . --no-deps
pip install fastapi uvicorn pydantic pydantic-settings \
    httpx openai anthropic google-genai \
    Pillow python-multipart aiofiles \
    apscheduler schedule \
    beautifulsoup4 lxml markdown
```

> Monitor 模块（`lifeprism.monitor.windows_monitor`）在 Linux 上不会加载，因此 `mss`/`pynput`/`pywin32` 不是必需的。

## 4. 运行模式

LifePrism 在 Linux 上支持两种运行模式：

| 模式 | 入口文件 | 包含组件 | 适用场景 |
| ---- | -------- | -------- | -------- |
| **Web Demo** | `lifeprism.server.main_web_demo` | FastAPI + 全部 API 路由 + Agent + WeChat Channel | 需要 Web 界面的完整部署 |
| **Agent Only** | `lifeprism.server.main_agent_only` | Agent Loop + WeChat Channel | 仅需 AI 对话，无需 Web 界面 |

两种模式均**不包含** Monitor 模块（Windows 专用）和 ScheduleService（依赖 Monitor 数据）。

### 4.1 Web Demo 模式

#### 构建前端

```bash
cd frontend
npm install
npm run build
# 产物在 frontend/dist/
cd ..
```

#### 启动服务

```bash
# 使用启动脚本
chmod +x scripts/deployment/start_web_demo.sh
./scripts/deployment/start_web_demo.sh start

# 或直接启动
python -m uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101
```

#### 部署前端

将 `frontend/dist/` 复制到 Nginx Web 根目录，配置 Nginx 反向代理 `/api/*` 到后端 8101 端口。详见 [Nginx 配置指南](nginx-setup.md)。

#### 验证

```bash
# 健康检查
curl http://localhost:8101/health
# 预期: {"status":"healthy","service":"lifeprism-web-demo","version":"0.2.0"}

# API 文档
# 浏览器访问 http://your-server:8101/docs
```

### 4.2 Agent Only 模式

#### 启动服务

```bash
# 使用启动脚本
chmod +x scripts/deployment/start_agent_only.sh
./scripts/deployment/start_agent_only.sh start

# 或直接启动
python -m lifeprism.server.main_agent_only
```

#### 验证

```bash
# 查看日志
tail -f localData/lifeprism-agent-only.log

# 预期日志包含:
# "=== LifePrism Agent Only 模式启动 ==="
# "数据库初始化完成"
# "微信渠道启动成功"
# "AgentLoop started"
```

## 5. 环境变量

| 变量名 | 说明 | 默认值 | 必需 |
| ------ | ---- | ------ | ---- |
| `LIFEPRISM_DATA_PATH` | 数据目录路径（SQLite 数据库、日志、配置等） | `localData/` | 否 |
| `LIFEPRISM_HOST` | Web Demo 监听地址 | `0.0.0.0` | 否 |
| `LIFEPRISM_PORT` | Web Demo 监听端口 | `8101` | 否 |

### 配置优先级

数据路径解析优先级（高 → 低）：

1. `config.yaml` 中的 `lifeprism_data_path`
2. 环境变量 `LIFEPRISM_DATA_PATH`
3. 默认路径 `localData/`（开发环境 / Linux）

## 6. 启动脚本命令

两个启动脚本（`start_web_demo.sh` / `start_agent_only.sh`）支持相同的命令：

| 命令 | 说明 |
| ---- | ---- |
| `start` | 后台启动服务 |
| `stop` | 停止服务（先 SIGTERM，10 秒后 SIGKILL） |
| `status` | 查看运行状态 |
| `restart` | 重启服务 |

```bash
./scripts/deployment/start_web_demo.sh start
./scripts/deployment/start_web_demo.sh status
./scripts/deployment/start_web_demo.sh stop
./scripts/deployment/start_web_demo.sh restart
```

PID 文件位于 `localData/.lifeprism-web-demo.pid`，日志位于 `localData/lifeprism-web-demo.log`。

## 7. 进程管理（可选）

### 使用 systemd

创建 `/etc/systemd/system/lifeprism-web.service`：

```ini
[Unit]
Description=LifePrism Web Demo
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/lifeprism
Environment=LIFEPRISM_DATA_PATH=/opt/lifeprism/data
ExecStart=/opt/lifeprism/.venv/bin/python -m uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable lifeprism-web
sudo systemctl start lifeprism-web
```

## 8. 常见问题

### Q: `mss` 或 `pynput` 安装失败

这些是 Windows Monitor 模块的依赖，Linux 上不需要。跳过安装即可，Monitor 模块在非 Windows 平台会自动跳过。

### Q: 前端页面白屏

检查 Nginx 配置是否正确代理 `/api/*` 到后端 8101 端口。前端使用 HashRouter，不需要特殊处理前端路由。

### Q: Chatbot 流式响应卡顿

Nginx 需要关闭 `proxy_buffering`，否则 SSE 流式响应会被缓冲。详见 [Nginx 配置指南](nginx-setup.md)。

### Q: 数据库锁定错误

SQLite 在高并发下可能出现锁定。确保 `LIFEPRISM_DATA_PATH` 指向的目录有正确的读写权限，且只有一个实例在运行。

### Q: 微信通道无法启动

检查 `config.yaml` 中的微信配置（`wechat_channel` 节）是否正确填写了 `token`、`encoding_aes_key` 等参数。
