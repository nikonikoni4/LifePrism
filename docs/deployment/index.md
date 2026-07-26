## cloud-https-setup
- updated_at: 2026-07-26
- path: `docs/deployment/cloud-https-setup.md`
- 触发规则：云端部署同步 API 时阅读
- 内容摘要：三种连接模式（Nginx 反向代理 + uvicorn 直连 HTTPS + SSH 隧道）的完整部署配置。覆盖 SSL 证书申请、Nginx 配置（443 → 8102）、uvicorn SSL 参数、SSH 隧道流程、SSH 服务加固（fail2ban、禁用密码认证、禁止 root 登录）、防火墙 / 安全组设置、systemd 进程守护、证书自动续期、前端 remote_url 配置说明。所有代码仅供参考，AI 应依据实际环境适配。

## linux-deployment-guide
- updated_at: 2026-07-08
- path: `docs/deployment/linux-deployment-guide.md`
- 触发规则：Linux 服务器部署 LifePrism 时阅读
- 内容摘要：Linux 部署完整指南，覆盖系统要求、依赖安装、Web Demo / Agent Only 两种模式的启动命令、环境变量配置、systemd 进程管理和常见问题

## nginx-setup
- updated_at: 2026-07-08
- path: `docs/deployment/nginx-setup.md`
- 触发规则：配置 Nginx 反向代理时阅读
- 内容摘要：Nginx 配置指南，包含静态文件托管、API 反向代理、SSE 流式响应支持（proxy_buffering off）、HTTPS 配置和 SSE 验证方法
