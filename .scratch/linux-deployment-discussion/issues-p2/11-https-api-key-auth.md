# HTTPS + API Key 认证

**Status**: ready-for-agent  
**Type**: HITL  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

配置云端 HTTPS 证书和生成同步 API Key，完成安全认证配置。

**需要人工操作的部分（HITL）**：
1. 生成同步 API Key：
   - 使用脚本生成 32 字节随机字符串
   - 保存到云端 keyring 或配置文件
2. 配置 Let's Encrypt SSL 证书：
   - 需要域名和云服务器访问权限
   - 使用 `certbot` 申请证书
3. 配置 Nginx：
   - HTTPS 监听（443 端口）
   - 反向代理到后端（8101 端口）
   - 证书路径配置

**实现端到端**：
1. 新增 `scripts/generate_sync_api_key.py`（生成 32 字节随机 API Key）
2. 文档化 HTTPS 配置流程（`docs/deployment/https-setup.md`）
3. 提供 Nginx 配置模板
4. 验证 HTTPS 连接（使用 `curl` 测试）
5. 验证 API Key 认证（测试 Pull/Push 接口）

---

## Acceptance criteria

- [ ] 同步 API Key 生成脚本已创建（`scripts/generate_sync_api_key.py`）
- [ ] HTTPS 配置文档已完成（`docs/deployment/https-setup.md`）
- [ ] Nginx 配置模板已提供
- [ ] HTTPS 证书配置完成（Let's Encrypt）
- [ ] HTTPS 连接验证通过（`curl https://your-server.com/api/sync/pull`）
- [ ] API Key 认证验证通过：
  - 正确的 Key 返回 200
  - 错误的 Key 返回 422（`ValidationError(code="INVALID_SYNC_API_KEY")`，与 Issue #03/#04 一致）

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/03-sync-api-pull.md`
- `.scratch/linux-deployment-discussion/issues-p2/04-sync-api-push.md`
