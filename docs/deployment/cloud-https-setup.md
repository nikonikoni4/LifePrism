---
version: 1.1
created_at: 2026-07-14
updated_at: 2026-07-26
last_updated: 新增"模式 C：SSH 隧道（无域名场景）"章节；标注模式 B 为"不推荐，仅测试用"（因 8102 默认绑定 127.0.0.1 后无法公网访问）
abstract: LifePrism 云端同步 API 的部署完整配置。覆盖三种连接模式——Nginx 反向代理（推荐）、uvicorn 直连 HTTPS（不推荐，仅测试用）、SSH 隧道（无域名场景）。所有代码仅供参考，云端 AI 在部署时应依据实际环境适配。
---

# 云端同步 API 的部署配置

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.1  | 新增"模式 C：SSH 隧道（无域名场景）"章节；标注模式 B 为"不推荐，仅测试用"（因 8102 默认绑定 127.0.0.1 后无法公网访问）；更新防火墙表格、systemd 配置示例和部署检查清单 |
| 1.0  | 创建文档初稿 |

> ⚠ 本文档是**部署参考模板**。云端 AI 在部署时应依据当前服务器的实际环境（系统发行版、已有 Nginx、防火墙类型等）进行适配。所有代码仅供参考。

---

## 三种连接模式

### 模式 A：Nginx 反向代理（推荐，需要域名）

Nginx 在 443 端口接收 HTTPS 请求，解密后转发到 uvicorn 的 8102 端口（内部 HTTP）。

**优点**：证书热重载不停服、端口统一管理、生产环境标准做法

```
本地 SyncClient ──HTTPS(443)──→ 公网 ──→ Nginx:443 ──→ uvicorn:8102 (内部 HTTP)
```

**本地 `sync.remote_url` 配置**：`https://your-domain.com`（不带端口号，443 是默认 HTTPS 端口）

### 模式 B：uvicorn 直连 HTTPS（不推荐，仅测试用）

> ⚠ **不推荐生产环境使用**：自 8102 端口默认绑定 `127.0.0.1` 起（环境变量 `LIFEPRISM_API_HOST` 可覆盖），uvicorn 不再监听公网请求。若需使用本模式，必须显式设置 `LIFEPRISM_API_HOST=0.0.0.0`，且配合严格的来源 IP 限制，否则同步 API 不可达或存在安全风险。仅推荐在测试环境临时使用。

uvicorn 自己加载 SSL 证书，直接在 8102 端口提供 HTTPS 服务。不需要 Nginx。

**优点**：零额外组件、配置简单

```
本地 SyncClient ──HTTPS(8102)──→ 公网 ──→ uvicorn:8102 (自己解密，需 LIFEPRISM_API_HOST=0.0.0.0)
```

**本地 `sync.remote_url` 配置**：`https://your-domain.com:8102`（必须带端口号）

### 模式 C：SSH 隧道（无域名场景，推荐）

本地 SyncClient 通过 SSH 加密隧道把云端 `127.0.0.1:8102` 映射到本地端口，所有同步流量走 SSH 加密通道，无需域名和 TLS 证书。云端 8102 端口完全不暴露公网。

**优点**：无需域名和证书、本地动态 IP 友好、8102 完全不可见、API Key 经 SSH 加密传输

```
本地 SyncClient ──HTTP(localhost:8102)──→ SSH 隧道 ──→ 云端 SSH:22 ──→ 127.0.0.1:8102 (uvicorn)
```

**适用场景**：本地无备案域名 + 公网 IP 动态变化，无法使用模式 A 或 B

**本地配置方式**：在前端"数据同步"区域将连接方式切换为 SSH，填写 SSH 参数（host/port/username 等），无需修改 `sync.remote_url`

### 三种模式共存

模式 A 和模式 B 可以同时配置（本地客户端通过 `sync.remote_url` 是否带端口号选择路径）：
- 不带端口号（`https://your-domain.com`）→ 走 Nginx 443
- 带端口号（`https://your-domain.com:8102`）→ 走 uvicorn 直连

模式 C 与模式 A/B 互斥：在前端切换为 SSH 模式后，SyncClient 启动时建立 SSH 隧道，`remote_url` 在运行时被临时替换为 `http://localhost:{local_port}`，原配置值保留不变（参考 [`docs/coding-rules/sync-remote-url-access-rules.md`](../coding-rules/sync-remote-url-access-rules.md)）。

---

## 前置步骤（模式 A、B 共用）

> 模式 C（SSH 隧道）不需要域名和 SSL 证书，前置步骤见下文"模式 C 配置"章节。

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
| B（uvicorn 直连） | 8102（需 `LIFEPRISM_API_HOST=0.0.0.0`） | **强烈建议仅限本地客户端 IP**，在安全组中设置为 `x.x.x.x/32` |
| C（SSH 隧道） | 22（SSH） | **必须**仅限必要 IP 段或全网开放（动态 IP 场景），8102 公网规则应**关闭** |

> ⚠ **安全提醒**：
> - 模式 B 的 8102 端口直接暴露在公网。如果设置为 `0.0.0.0/0`（全开放），任何 IP 都可以访问同步 API。必须通过安全组 / iptables / ufw 限制来源 IP。
> - 模式 C 下云端 8102 端口默认绑定 `127.0.0.1`，公网规则即使存在也无法访问。建议在安全组中直接关闭 8102 公网规则，仅保留 SSH（22）端口。

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

## 模式 C 配置：SSH 隧道（无域名场景）

### C.1 适用场景

满足以下任一条件时优先选择模式 C：

- 本地无备案域名（无法申请 Let's Encrypt 证书）
- 本地公网 IP 动态变化（无法稳定配置安全组 CIDR）
- 不希望 8102 端口暴露公网（即使有域名）
- 希望在不引入 Nginx/证书运维成本的前提下获得传输加密

### C.2 服务器端配置

#### C.2.1 8102 端口绑定 127.0.0.1（默认已生效）

LifePrism `main_agent_only.py` 默认将 8102 绑定到 `127.0.0.1`（仅本机可见），无需用户额外操作。

如需覆盖（如测试场景需临时暴露公网），通过环境变量 `LIFEPRISM_API_HOST` 控制：

```bash
# 默认行为（推荐）：仅本机可见，SSH 隧道模式下必需
export LIFEPRISM_API_HOST=127.0.0.1

# 测试场景：临时监听公网（不推荐，仅在模式 B 测试时使用）
# export LIFEPRISM_API_HOST=0.0.0.0
```

#### C.2.2 关闭防火墙 8102 公网规则

确认安全组 / iptables / ufw 中**没有** 8102 端口的公网放行规则。如存在历史规则应删除：

```bash
# ufw 示例（仅供参考）
sudo ufw delete allow 8102/tcp

# iptables 示例（仅供参考，AI 应依据实际防火墙工具）
sudo iptables -D INPUT -p tcp --dport 8102 -j ACCEPT

# 云服务商安全组：删除 TCP 8102 入方向规则
```

仅保留 SSH（22）端口开放。

#### C.2.3 SSH 服务加固建议

SSH 服务直接暴露公网，必须加固。以下措施**强烈建议全部实施**：

**1. 安装 fail2ban（拦截暴力破解）**

```bash
# Debian/Ubuntu（仅供参考）
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban

# CentOS/RHEL（仅供参考）
sudo dnf install -y fail2ban
sudo systemctl enable --now fail2ban
```

默认配置 `/etc/fail2ban/jail.local`（参考）：

```ini
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
```

**2. 禁用密码认证（仅允许密钥认证）**

编辑 `/etc/ssh/sshd_config`：

```sshd_config
PasswordAuthentication no
PubkeyAuthentication yes
ChallengeResponseAuthentication no
UsePAM no
```

重启 sshd 生效：

```bash
sudo systemctl restart sshd
```

> ⚠ **风险提醒**：禁用密码认证前，请确认已通过 `ssh-copy-id` 或手工方式将本地公钥追加到云端 `~/.ssh/authorized_keys`，并验证可使用密钥登录。否则将无法登录服务器。

**3. 禁止 root 直接登录**

```sshd_config
PermitRootLogin no
```

使用普通用户登录后通过 `sudo` 提权。

**4. 可选：修改默认 SSH 端口**

将 `Port 22` 改为非标准端口（如 `Port 22022`），可减少扫描噪音。但 LifePrism 前端 SSH 配置需对应修改 `port` 字段。本项为可选项，非强制。

### C.3 本地配置流程

#### C.3.1 在前端切换到 SSH 模式

进入 LifePrism 设置页"数据同步"区域，将"连接方式"从 HTTP/HTTPS 切换为 SSH。切换时如本地 keyring 中无私钥，系统会自动生成 ed25519 密钥对，私钥存入 keyring，公钥在 UI 中展示。

#### C.3.2 复制公钥并部署到云端

前端 SSH 选项卡会展示完整的配置命令（含实际公钥值），点击"复制命令"按钮一键复制：

```bash
# 在云端服务器执行以下命令（追加 SSH 公钥，公钥值由前端动态拼接）
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '<ssh-ed25519 AAAA... user@host>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

通过其他渠道（如已有 SSH 会话或控制台）登录云端服务器，粘贴并执行上述命令。

#### C.3.3 填写 SSH 参数并测试连接

在前端 SSH 表单填写：

| 字段 | 说明 | 示例 |
|------|------|------|
| SSH 主机 | 云端服务器 IP | `123.56.49.198` |
| SSH 端口 | SSH 服务端口 | `22` |
| SSH 用户名 | 云端登录用户 | `lifeprism` |
| 本地监听端口 | 本地隧道端口 | `8102` |
| 远程目标端口 | 云端 uvicorn 端口 | `8102` |

点击"测试连接"按钮，前端调用 `POST /api/v2/settings/ssh-tunnel/test`，后端会建立临时 SSH 连接 + 本地端口转发 + 验证 `http://localhost:8102/api/sync/health` 可达，然后关闭测试连接。返回成功表示参数正确。

#### C.3.4 保存配置

测试通过后，前端会自动保存 `sync.connection_mode = "ssh"` 及 SSH 参数到 `config.yaml`，私钥保存到 keyring（不写入文件系统）。

SyncClient 下次启动时会自动建立 SSH 隧道，所有同步流量走加密通道。

### C.4 完整配置流程示例

以下是一次性从零配置的完整命令序列示例（假设云端 IP 为 `123.56.49.198`，SSH 用户为 `lifeprism`）：

```bash
# ============================================================
# 步骤 1：云端服务器——SSH 加固（一次性，可选项但强烈推荐）
# ============================================================
# 安装 fail2ban
sudo apt install -y fail2ban
sudo systemctl enable --now fail2ban

# 编辑 sshd_config（禁用密码认证、禁止 root 登录）
sudo vi /etc/ssh/sshd_config
# 设置：PasswordAuthentication no
# 设置：PermitRootLogin no
# 设置：PubkeyAuthentication yes
sudo systemctl restart sshd

# ============================================================
# 步骤 2：云端服务器——确认 8102 仅本机可见
# ============================================================
# LifePrism 默认行为，无需操作。如需验证：
# 查看进程监听地址
sudo ss -tlnp | grep 8102
# 应只看到 127.0.0.1:8102，不应有 0.0.0.0:8102

# 关闭防火墙 8102 公网规则（如存在）
sudo ufw delete allow 8102/tcp 2>/dev/null || true

# ============================================================
# 步骤 3：本地前端——切换 SSH 模式并复制公钥
# ============================================================
# 3.1 打开 LifePrism 设置页 → 数据同步 → 连接方式切换为 SSH
# 3.2 系统自动生成密钥对（首次切换时），UI 展示公钥
# 3.3 点击"复制命令"按钮，复制内容（含实际公钥）

# ============================================================
# 步骤 4：云端服务器——部署公钥（粘贴步骤 3.3 复制的命令）
# ============================================================
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '<ssh-ed25519 AAAA... user@host>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# ============================================================
# 步骤 5：本地前端——填写 SSH 参数并测试
# ============================================================
# 5.1 SSH 主机：123.56.49.198
# 5.2 SSH 端口：22
# 5.3 SSH 用户名：lifeprism
# 5.4 本地监听端口：8102
# 5.5 远程目标端口：8102
# 5.6 点击"测试连接"，预期返回成功

# ============================================================
# 步骤 6：保存配置并重启 SyncClient
# ============================================================
# 前端自动保存。SyncClient 下次启动时建立 SSH 隧道。
# 同步流量走 http://localhost:8102 → SSH 加密 → 云端 127.0.0.1:8102
```

### C.5 SSH 隧道运行时行为

以下行为由 LifePrism 内置自动管理，用户无需手动干预：

- **自动启动**：SyncClient 启动时若 `sync.connection_mode == "ssh"` 且 keyring 中存在私钥，自动建立 SSH 隧道
- **断线重连**：SSH 连接断开后自动重连，指数退避 5s → 10s → 20s → 30s（上限），重连无最大次数限制
- **故障不阻塞**：隧道建立失败不阻塞 SyncClient 启动，仅记录 ERROR 日志，其他功能（如 LLM 对话）仍可用
- **优雅关闭**：LifePrism 关闭时优雅关闭 SSH 隧道连接，不留孤儿进程
- **透明转发**：所有 httpx 同步请求透明走 `http://localhost:8102`，业务代码零改动
- **端口占用检测**：本地监听端口被占用时给出明确错误（如"端口 8102 已被其他程序占用"）

详细运行时限制见 [`docs/known-limitations/ssh-tunnel-limitations.md`](../known-limitations/ssh-tunnel-limitations.md)。

---

## 前端配置说明

本地客户端通过前端界面配置同步。前端需要说明三种模式的区别：

| 配置项 | 模式 A（Nginx） | 模式 B（直连，不推荐） | 模式 C（SSH 隧道） |
|--------|----------------|----------------------|------------------|
| 云端地址（remote_url） | `https://your-domain.com` | `https://your-domain.com:8102` | 保留原值（运行时不使用，走 `http://localhost:8102`） |
| 是否需要带端口号 | 否（默认 443） | 是（:8102） | 否（前端 SSH 表单单独填写端口） |
| 服务器需要开放端口 | 443（TCP）| 8102（TCP，需 `LIFEPRISM_API_HOST=0.0.0.0` + 限源 IP） | 22（TCP，SSH） |
| 服务器需要安装 | Nginx + Let's Encrypt | 无额外组件 | SSH 服务（默认已具备） |
| 是否需要域名/证书 | 是 | 是 | 否 |
| 是否动态 IP 友好 | 否 | 否 | 是 |
| 前端切换方式 | HTTP/HTTPS 选项卡 + 填写 remote_url | HTTP/HTTPS 选项卡 + 填写 remote_url | SSH 选项卡 + 填写 SSH 参数 + 复制公钥部署 |

前端界面中应在 `sync.remote_url` 输入框旁添加说明文案，例如：

```
云端服务器地址：
- 模式 A：Nginx 代理（推荐，需域名）——填写 https://your-domain.com（不带端口号）
  服务器需配置 Nginx + Let's Encrypt 证书
- 模式 B：uvicorn 直连（不推荐，仅测试用）——填写 https://your-domain.com:8102（必须带端口号）
  需设置 LIFEPRISM_API_HOST=0.0.0.0 并在安全组中限制 8102 端口来源 IP
- 模式 C：SSH 隧道（推荐，无域名场景）——切换到 SSH 选项卡，填写 SSH 参数并部署公钥
  云端 8102 默认绑定 127.0.0.1，无需公网暴露
```

---

## 验证部署

三种模式部署完毕后，均可用以下方式验证：

```bash
# 从本地电脑执行（替换 your-domain.com 为实际域名）

# 模式 A 验证
curl -X POST https://your-domain.com/api/sync/heartbeat \
  -H "Authorization: Bearer YOUR_SYNC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event": "ping"}'

# 模式 B 验证（需云端 LIFEPRISM_API_HOST=0.0.0.0）
curl -X POST https://your-domain.com:8102/api/sync/heartbeat \
  -H "Authorization: Bearer YOUR_SYNC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event": "ping"}'

# 模式 C 验证：直接使用前端"测试连接"按钮即可
# 后端会自动执行 SSH 连接 + 本地端口转发 + 验证 http://localhost:8102/api/sync/health
# 如需手动验证（隧道已建立时）：
curl -X POST http://localhost:8102/api/sync/heartbeat \
  -H "Authorization: Bearer YOUR_SYNC_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"event": "ping"}'

# 预期响应：{"status": "ok", "server_time": "..."}
```

---

## 进程守护（systemd）

三种模式都建议使用 systemd 管理 uvicorn 进程（参考配置，AI 应依据实际路径调整）：

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
# 8102 端口绑定地址：默认 127.0.0.1（仅本机，模式 C 必需）
# 模式 A：可保持 127.0.0.1（Nginx 转发到本机）
# 模式 B：需设为 0.0.0.0（不推荐，仅测试用）
# 模式 C：保持默认 127.0.0.1
Environment="LIFEPRISM_API_HOST=127.0.0.1"
# 模式 B 专用 SSL 配置（模式 A/C 不需要）
# Environment="LIFEPRISM_SSL_KEYFILE=/etc/letsencrypt/live/your-domain.com/privkey.pem"
# Environment="LIFEPRISM_SSL_CERTFILE=/etc/letsencrypt/live/your-domain.com/fullchain.pem"
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

### 通用项（三种模式共用）

- [ ] uvicorn 已启动并监听对应端口（模式 A/C 默认 127.0.0.1:8102，模式 B 需 0.0.0.0:8102）
- [ ] `curl` 验证同步 API 可达并返回正确响应
- [ ] 本地前端 `sync.remote_url` 已配置为对应 URL（模式 C 下保留原值，仅作标识）
- [ ] 同步 API Key 已生成（`cloud_init.yaml` → `CloudInitializer.initialize()`）

### 模式 A 专属

- [ ] SSL 证书已申请并安装（Let's Encrypt 或其他）
- [ ] 证书自动续期已配置（certbot timer 或 cron）
- [ ] 防火墙/安全组已开放 443 端口

### 模式 B 专属（不推荐，仅测试用）

- [ ] 已显式设置 `LIFEPRISM_API_HOST=0.0.0.0`
- [ ] SSL 证书已申请并安装（Let's Encrypt 或其他）
- [ ] 证书自动续期后已配置 uvicorn 重启 hook
- [ ] 防火墙/安全组 8102 端口已**严格限制来源 IP**

### 模式 C 专属

- [ ] 云端 8102 端口绑定 `127.0.0.1`（默认行为，无需操作）
- [ ] 防火墙/安全组 8102 公网规则已**关闭**（仅保留 22 端口）
- [ ] SSH 服务加固已实施：fail2ban 已安装、密码认证已禁用、root 登录已禁止
- [ ] 本地前端已切换到 SSH 模式，密钥对已自动生成
- [ ] 公钥已复制到云端 `~/.ssh/authorized_keys`
- [ ] 前端"测试连接"按钮验证通过
