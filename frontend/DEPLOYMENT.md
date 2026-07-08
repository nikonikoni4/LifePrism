# 前端部署说明

本文档说明如何将 LifePrism 前端构建为静态文件并部署到 Linux 服务器（Web Demo 模式）。

---

## 1. 构建静态文件

### 前置要求

- Node.js >= 18
- npm（或兼容包管理器）

### 构建命令

```bash
cd frontend
npm install        # 首次或依赖变更时执行
npm run build
```

### 构建产物

- 输出目录：`frontend/dist/`
- 包含内容：`index.html`、`assets/`（JS、CSS、字体、图片等）
- `vite.config.ts` 中 `base: './'`，所有资源引用使用相对路径，可直接托管在 Nginx 任意子路径下

---

## 2. 部署到服务器

将 `dist/` 目录复制到服务器，例如 `/var/www/lifeprism`：

```bash
scp -r dist/ user@server:/var/www/lifeprism/
```

---

## 3. 后端 API 代理配置

前端在**非 Electron 环境**（浏览器访问）下，API 请求使用**相对路径**（见 `core/services/apiConfig.ts` 的 `getApiBaseUrlSync()`）。
因此无需在前端配置后端地址，只需在 Nginx 中将 `/api/*` 反向代理到后端服务即可。

### Nginx 关键配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    root /var/www/lifeprism;
    index index.html;

    # 前端路由（HashRouter，无需 history fallback，但建议保留以防万一）
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 反向代理
    location /api/ {
        proxy_pass http://127.0.0.1:8101;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # SSE 支持：必须关闭缓冲，否则 Chatbot 流式响应会卡顿
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
    }
}
```

### SSE 验证方法

部署后，可通过以下方式验证 SSE 流式响应是否正常：

```bash
# 发起一个 chatbot 请求，观察是否逐步返回（而非一次性返回）
curl -N -X POST http://your-domain.com/api/v2/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"你好"}'
```

如果响应逐步打印（streaming），说明 SSE 正常；如果等待很久后一次性返回，说明 `proxy_buffering` 未关闭。

---

## 4. 注意事项

- **路由模式**：前端使用 HashRouter（URL 带 `#`），Nginx 无需特殊处理前端路由
- **端口**：后端 Web Demo 固定监听 `8101`，详见后端部署文档
- **环境变量**：前端构建无需任何环境变量；`GEMINI_API_KEY`（如有）仅在开发模式使用，部署时由后端处理 LLM 调用
- **资源路径**：`base: './'` 确保资源引用为相对路径，可部署在域名根路径或子路径下
