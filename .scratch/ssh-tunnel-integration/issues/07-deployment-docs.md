---
issue: 07
title: 部署文档更新（cloud-https-setup + known-limitations）
triage: ready-for-agent
slice: 7
---

# 部署文档更新（cloud-https-setup + known-limitations）

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

更新部署文档和已知限制文档，反映 SSH 隧道方案引入后的部署变更。这是非代码任务（文档维护）。

**文档更新清单**：

1. **修改 `docs/deployment/cloud-https-setup.md`**：
   - 新增"模式 C：SSH 隧道（无域名场景）"章节，与模式 A（Nginx）和模式 B（uvicorn 直连）并列
   - 模式 C 章节内容：
     - 适用场景：本地无备案域名 + 动态 IP
     - 服务器端配置：8102 默认绑定 127.0.0.1 + 关闭防火墙 8102 公网规则 + SSH 服务加固建议（fail2ban、禁用密码认证、禁止 root 登录）
     - 本地配置：切换到 SSH 模式 + 自动生成密钥 + 复制公钥 + 在云端执行配置命令 + 测试连接
     - 完整配置流程示例（含命令）
   - 标注模式 B（uvicorn 直连）为"不推荐，仅测试用"（因 8102 默认绑定 127.0.0.1 后已无法公网访问）

2. **修改 `docs/known-limitations/cloud-security-limitations.md`**：
   - 限制 4（HTTP 明文传输 API Key）增加备注：SSH 隧道模式可作为替代方案，无需域名和证书

3. **新增 `docs/known-limitations/ssh-tunnel-limitations.md`**：
   - 记录 SSH 隧道方案的已知限制：
     1. 本地需要保持 SSH 隧道进程（LifePrism 内置自动管理，关闭后隧道也关闭）
     2. SSH 服务必须可用（服务器 SSH 服务故障会导致同步中断）
     3. 私钥丢失后无法恢复（需重新生成密钥对并配置云端 authorized_keys）
     4. 不支持私钥导入（仅支持前端生成密钥对）
     5. 密钥保留不覆盖（切换到 SSH 模式时如已有私钥则保留，可能导致前端公钥与云端不一致）
     6. 无私钥轮换 UI（不提供"重新生成密钥对"按钮）

4. **修改 `docs/known-limitations/index.md`**：
   - 注册新增的 ssh-tunnel-limitations.md 索引

## Acceptance criteria

- [ ] 修改 `docs/deployment/cloud-https-setup.md` 新增"模式 C：SSH 隧道"章节
- [ ] 模式 C 章节包含完整配置流程（服务器端 + 本地端）
- [ ] 模式 C 章节包含 SSH 服务加固建议（fail2ban、禁用密码认证、禁止 root 登录）
- [ ] 标注模式 B 为"不推荐，仅测试用"
- [ ] 修改 `docs/known-limitations/cloud-security-limitations.md` 限制 4 增加 SSH 隧道备注
- [ ] 新增 `docs/known-limitations/ssh-tunnel-limitations.md` 记录 6 项已知限制
- [ ] 修改 `docs/known-limitations/index.md` 注册新文档索引
- [ ] 遵循 [docs/docs-rules/docs-write-rules.md](../../../docs/docs-rules/docs-write-rules.md) 文档编写规范
- [ ] 遵循 [docs/docs-rules/known-limitations-and-debt-rules.md](../../../docs/docs-rules/known-limitations-and-debt-rules.md) 已知限制文档规范
- [ ] 文档中所有代码引用使用正确的相对路径
- [ ] 文档审阅通过（用户确认）

## Blocked by

- Issue 01: 8102 端口默认绑定 127.0.0.1（部署文档需反映此变更）
- Issue 05: SyncClient SSH 隧道编排（文档需描述运行时行为）
