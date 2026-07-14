---
version: 1.0
created_at: 2026-07-14
abstract: LifePrism 云端同步 API 的 HTTPS 部署完整配置。覆盖两种模式——Nginx 反向代理（推荐）和 uvicorn 直连 HTTPS。本章节作为部署参考模板，云端 AI 在部署时可依据当前环境选择合适方案。
---

# 云端同步 API 的 HTTPS 部署配置

> ⚠ 本文档是**部署参考模板**。云端 AI 在部署时应依据当前服务器的实际环境（系统发行版、已有 Nginx、防火墙类型等）进行适配。所有代码仅供参考。

---

## 两种 HTTPS 模式

### 模式 A：Nginx 反向代理（推荐）

Nginx 在 443 端口接收 HTTPS 请求，解密后转发到 uvicorn 的 8102 端口（内部 HTTP）。

**优点**：证书热重载不停服、端口统一管理、生产环境标准做法

```
本地 SyncClient ──HTTPS(443)──→ 公网 ──→ Nginx:443 ──→ uvicorn:8102 (内部 HTTP)
```

**本地 `sync.remote_url` 配置**：`https://your-domain.com`（不带端口号，443 是默认 HTTPS 端口）

### 模式 B：uvicorn 直连 HTTPS

uvicorn 自己加载 SSL 证书，直接在 8102 端口提供 HTTPS 服务。不需要 Nginx。

**优点**：零额外组件、配置简单

```
本地 SyncClient ──HTTPS(8102)──→ 公网 ──→ uvicorn:8102 (自己解密)
```

**本地 `sync.remote_url` 配置**：`https://your-domain.com:8102`（必须带端口号）

### 两种模式共存

两种模式可以同时配置。本地客户端通过 `sync.remote_url` 是否带端口号来选择走哪条路径：
- 不带端口号（`https://your-domain.com`）→ 走 Nginx 443
- 带端口号（`https://your-domain.com:8102`）→ 走 uvicorn 直连

---

## 前置步骤（两种模式共用）

### 1. 获取域名

需要有一个指向服务器 IP 的域名，例如 `lifeprism.your-domain.com`。

### 2. 获取 SSL/TLS 证书

推荐使用免费的 Let's Encrypt：

```bash
# 安装 certbot（仅供参考，依发行版调整）
sudo apt install -y certbot   # Debian/Ubuntu
# 或
sudo dnf install -y certbot   # CentOS/RHEL

# 申请证书（standalone 模式，会临时占用 80 端口）
sudo certbot certonly --standalone -d your-domain.com
```

> ⚠ **注意**：如果服务器已有 Nginx 占用 80 端口，改用 `--webroot` 或 `--nginx` 模式。AI 应依据当前服务器环境选择正确的 certbot 模式。

证书路径（Let's Encrypt 默认）：
- 证书文件：`/etc/letsencrypt/live/your-domain.com/fullchain.pem`
- 私钥文件：`/etc/letsencrypt/live/your-domain.com/privkey.pem`

### 3. 防火墙 / 安全组（云服务商）

| 模式 | 需要开放的端口 | 来源限制 |
|------|--------------|---------|
| A（Nginx） | 443（HTTPS） | 通常已开放，无需额外操作 |
| B（uvicorn 直连） | 8102 | **强烈建议仅限本地客户端 IP**，在安全组中设置为 `x.x.x.x/32` |

> ⚠ **安全提醒**：模式 B 的 8102 端口直接暴露在公网。如果设置为 `0.0.0.0/0`（全开放），任何 IP 都可以访问同步 API。必须通过安全组 / iptables / ufw 限制来源 IP。

---

## 模式 A 配置：Nginx 反向代理

### A.1 安装 Nginx

```bash
# Debian/Ubuntu（仅供参考）
sudo apt install -y nginx

# CentOS/RHEL（仅供参考）
sudo dnf install -y nginx
```

### A.2 Nginx 配置

创建配置文件（路径依发行版，仅供参考）：

```nginx
# /etc/nginx/sites-available/lifeprism-sync  （Debian/Ubuntu）
# 或 /etc/nginx/conf.d/lifeprism-sync.conf   （CentOS/RHEL）

# ==================== HTTP → HTTPS 重定向 ====================
server {
    listen 80;
    server_name your-domain.com;

    # 所有 HTTP 请求重定向到 HTTPS
    return 301 https://$host$request_uri;
}

# ==================== 同步 API（HTTPS）====================
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    # SSL 证书（路径依 certbot 输出为准）
    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # TLS 安全配置（截止 2026 年推荐配置）
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # 同步 API 反向代理 → uvicorn:8102
    location /api/sync/ {
        proxy_pass http://127.0.0.1:8102;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### A.3 启用配置

```bash
# Debian/Ubuntu（仅供参考）
sudo ln -s /etc/nginx/sites-available/lifeprism-sync /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# CentOS/RHEL（仅供参考）
sudo nginx -t
sudo systemctl reload nginx
```

### A.4 证书自动续期

Let's Encrypt 证书 90 天过期，需要设置自动续期：

```bash
# certbot 通常会自动添加 systemd timer（仅供参考）
sudo systemctl status certbot.timer

# 如果没有，手动添加 crontab（仅供参考）
# 0 3 * * * certbot renew --quiet --post-hook "systemctl reload nginx"
```

### A.5 本地配置

本地前端中 `sync.remote_url` 设为：

```
https://your-domain.com
```

**不带端口号**——443 是 HTTPS 默认端口，Nginx 在此监听。

---

## 模式 B 配置：uvicorn 直连 HTTPS

### B.1 设置环境变量（代码已内置支持）

`main_agent_only.py` 已内置 HTTPS 支持，通过两个环境变量控制：

```bash
# 设置 SSL 证书路径（systemd 或启动脚本中）
export LIFEPRISM_SSL_KEYFILE=/etc/letsencrypt/live/your-domain.com/privkey.pem
export LIFEPRISM_SSL_CERTFILE=/etc/letsencrypt/live/your-domain.com/fullchain.pem
```

设置后重启 uvicorn，日志会显示 `https=True`。如果证书文件不存在则自动退回 HTTP。

### B.2 证书自动续期后重启服务

uvicorn 不会自动重载证书。证书更新后需要重启 uvicorn 进程：

```bash
# 创建续期后的重启脚本（仅供参考）
# 写入 /etc/letsencrypt/renewal-hooks/deploy/restart-lifeprism.sh
# 并 chmod +x

#!/bin/bash
# 依据使用的进程管理方式选择对应命令：
systemctl restart lifeprism-agent-only
# 或
/path/to/scripts/start.sh agent-only restart
```

### B.3 防火墙/安全组

**必须限制来源 IP**——8102 端口只允许本地客户端的 IP 访问：

```bash
# iptables 示例（仅供参考，AI 应依据实际防火墙工具）
sudo iptables -A INPUT -p tcp --dport 8102 -s YOUR_LOCAL_IP/32 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8102 -j DROP

# ufw 示例（仅供参考）
sudo ufw allow from YOUR_LOCAL_IP to any port 8102 proto tcp

# 云服务商安全组（在控制台操作，非命令行）
# 入方向：TCP 8102，来源：YOUR_LOCAL_IP/32
```

> ⚠ **如果做不到 IP 限制**（如本地电脑是动态 IP），建议使用模式 A（Nginx）。直接将 8102 端口全开（0.0.0.0/0）同步 API 是不安全的。

### B.4 本地配置

本地前端中 `sync.remote_url` 设为：

```
https://your-domain.com:8102
```

**必须带端口号**:8102——uvicorn 在此端口监听 HTTPS。

---

## 前端配置说明

本地客户端通过前端界面配置同步。前端需要说明两种模式的区别：

| 配置项 | 模式 A（Nginx） | 模式 B（直连） |
|--------|----------------|---------------|
| 云端地址（remote_url） | `https://your-domain.com` | `https://your-domain.com:8102` |
| 是否需要带端口号 | 否（默认 443） | 是（:8102） |
| 服务器需要开放端口 | 443（TCP）| 8102（TCP），需限制来源 IP |
| 服务器需要安装 | Nginx + Let's Encrypt | 无额外组件 |

前端界面中应在 `sync.remote_url` 输入框旁添加说明文案，例如：

```
云端服务器地址：
- Nginx 代理模式（推荐）：填写 https://your-domain.com（不带端口号）
  服务器需配置 Nginx + Let's Encrypt 证书
- uvicorn 直连模式：填写 https://your-domain.com:8102（必须带端口号）
  服务器需在安全组中将 8102 端口限制为仅本机 IP 可访问
```

---

## 验证部署

两种模式部署完毕后，均可用以下方式验证：

```bash
# 从本地电脑执行（替换 your-domain.com 为实际域名）

# 模式 A 验证
curl -X POST https://your-domain.com/api/sync/heartbeat \
  -H "Authorization: Bearer YOUR_SYNC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event": "ping"}'

# 模式 B 验证
curl -X POST https://your-domain.com:8102/api/sync/heartbeat \
  -H "Authorization: Bearer YOUR_SYNC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event": "ping"}'

# 预期响应：{"status": "ok", "server_time": "..."}
```

---

## 进程守护（systemd）

两种模式都建议使用 systemd 管理 uvicorn 进程（参考配置，AI 应依据实际路径调整）：

```ini
# /etc/systemd/system/lifeprism-agent-only.service（仅供参考）

[Unit]
Description=LifePrism Agent Only (Sync API)
After=network.target

[Service]
Type=simple
User=lifeprism
WorkingDirectory=/opt/lifeprism
Environment="LIFEPRISM_DATA_PATH=/opt/lifeprism/localData"
Environment="LIFEPRISM_SSL_KEYFILE=/etc/letsencrypt/live/your-domain.com/privkey.pem"
Environment="LIFEPRISM_SSL_CERTFILE=/etc/letsencrypt/live/your-domain.com/fullchain.pem"
ExecStart=/opt/lifeprism/venv/bin/python -m lifeprism.server.main_agent_only
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable lifeprism-agent-only
sudo systemctl start lifeprism-agent-only
sudo systemctl status lifeprism-agent-only
```

---

## 部署检查清单

部署完成后请逐项确认：

- [ ] SSL 证书已申请并安装（Let's Encrypt 或其他）
- [ ] 证书自动续期已配置（certbot timer 或 cron）
- [ ] 防火墙/安全组端口已开放（模式 A：443；模式 B：8102）
- [ ] 模式 B 的 8102 端口已限制来源 IP
- [ ] uvicorn 已启动并监听对应端口
- [ ] `curl` 验证 HTTPS 请求可达并返回正确响应
- [ ] 本地前端 `sync.remote_url` 已配置为对应 URL
- [ ] 同步 API Key 已生成（`cloud_init.yaml` → `CloudInitializer.initialize()`）
