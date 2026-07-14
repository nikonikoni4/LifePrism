---
version: 1.1
created_at: 2026-07-08
updated_at: 2026-07-14
last_updated: v1.1——HTTPS 从可选改为默认；新增同步端口 8102 代理配置
abstract: LifePrism 的 Nginx 反向代理配置指南，覆盖前端静态文件托管、Web Demo API（8101）代理、同步 API（8102）代理、HTTPS 默认配置、SSE 流式响应支持。
---

# Nginx 配置指南

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.1  | HTTPS 从可选改为默认配置；新增同步端口 8102 代理（`/api/sync/` → `http://127.0.0.1:8102`） |
| 1.0  | 创建文档初稿 |

---

## 1. 安装 Nginx

```bash
# Ubuntu / Debian
sudo apt install -y nginx

# CentOS / RHEL
sudo dnf install -y nginx
```

## 2. 部署前端静态文件

```bash
# 创建 Web 根目录
sudo mkdir -p /var/www/lifeprism

# 复制构建产物
sudo cp -r frontend/dist/* /var/www/lifeprism/

# 设置权限
sudo chown -R www-data:www-data /var/www/lifeprism
```

## 3. Nginx 配置

创建 `/etc/nginx/sites-available/lifeprism`（或 `/etc/nginx/conf.d/lifeprism.conf`）：

```nginx
server {
    listen 80;
    server_name your-domain.com;  # 替换为你的域名或 IP

    # HTTP → HTTPS 强制跳转（首次配置时建议注释掉，等 HTTPS 证书就绪后再启用）
    # return 301 https://$host$request_uri;

    # 前端静态文件
    root /var/www/lifeprism;
    index index.html;

    # 前端路由（HashRouter，try_files 兜底）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Web Demo 后端 API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8101;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE 支持：必须关闭缓冲，否则 Chatbot 流式响应会卡顿
        proxy_buffering off;
        proxy_cache off;

        # SSE 长连接超时设置
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}

# 同步端口 HTTPS（默认配置）
server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # 本地 SyncClient 通过 HTTPS 访问同步 API
    location /api/sync/ {
        proxy_pass http://127.0.0.1:8102;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### 启用配置

```bash
# 创建符号链接（sites-available 方式）
sudo ln -s /etc/nginx/sites-available/lifeprism /etc/nginx/sites-enabled/

# 或直接使用 conf.d 方式（无需符号链接）

# 测试配置
sudo nginx -t

# 重新加载
sudo systemctl reload nginx
```

## 4. HTTPS 配置（默认，建议必须）

> ⚠ **同步 API Key 通过 HTTP Header 传输。不走 HTTPS 时，公网中间人可直接拦截 Bearer Token。** 详见已知限制 [cloud-security-limitations.md](../known-limitations/cloud-security-limitations.md) 限制 4。

使用 Let's Encrypt 获取免费 SSL 证书：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

证书自动续期已由 certbot 配置，无需手动处理。

证书就绪后，取消注释 Nginx 配置中的 HTTP→HTTPS 跳转行：

```nginx
# 取消这行的注释
return 301 https://$host$request_uri;
```

然后在本地前端将 `sync.remote_url` 设为 `https://your-domain.com`（不带端口号——443 是 HTTPS 默认端口，Nginx 会自动路由 `/api/sync/` 到 8102）。

## 5. SSE 流式响应验证

部署后，必须验证 Chatbot 的 SSE 流式响应是否正常工作。

### 验证方法

```bash
# 发起一个 chatbot 请求，观察响应是否逐步返回
curl -N -X POST http://your-domain.com/api/v2/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
```

### 判断标准

| 现象 | 说明 |
| ---- | ---- |
| 响应逐步打印（每个 token 依次出现） | SSE 正常，`proxy_buffering` 已正确关闭 |
| 等待很久后一次性返回全部内容 | SSE 被缓冲，需检查 `proxy_buffering off` 是否生效 |

### 常见 SSE 问题排查

1. **检查 Nginx 配置生效**：`sudo nginx -t && sudo systemctl reload nginx`
2. **检查 `proxy_buffering`**：确保 `location /api/` 块中有 `proxy_buffering off;`
3. **检查后端直连**：`curl -N http://localhost:8101/api/v2/chatbot/chat -H "Content-Type: application/json" -d '{"message":"你好"}'` — 如果直连正常但经 Nginx 卡顿，确认是 Nginx 缓冲问题
4. **检查超时设置**：SSE 长连接需要足够大的 `proxy_read_timeout`

## 6. 性能优化（可选）

```nginx
# 在 http 块中添加
gzip on;
gzip_types text/css application/javascript application/json;

# 静态文件缓存
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2)$ {
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```
