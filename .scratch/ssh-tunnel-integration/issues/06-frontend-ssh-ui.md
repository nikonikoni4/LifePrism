---
issue: 06
title: 前端 SSH 配置 UI + 公钥展示 + 配置命令
triage: ready-for-agent
slice: 6
---

# 前端 SSH 配置 UI + 公钥展示 + 配置命令

## Parent

PRD: [.scratch/ssh-tunnel-integration/prd.md](../prd.md)

## What to build

在设置页"数据同步"区域新增连接方式切换 UI（参考已有"极简/复杂模式"切换风格），并提供 SSH 隧道配置选项卡。

**两个选项卡**：
1. HTTP/HTTPS（保留现有云端地址输入 + 生成云端配置按钮）
2. SSH 隧道（新增 SSH 参数表单 + 公钥展示区 + 配置命令展示区 + 测试连接按钮）

**注**：隧道状态实时显示（已连接/重连中/已断开）不在本切片范围，由未来 PRD 增强。前端通过"测试连接"按钮手动验证隧道当前是否可用（一次性结果展示）。

**SSH 选项卡 UI 元素清单**：

| 元素 | 类型 | 说明 |
|------|------|------|
| SSH 主机 | 输入框 | 服务器 IP |
| SSH 端口 | 输入框 | 默认 22 |
| SSH 用户名 | 输入框 | 如 "lifeprism" |
| 本地监听端口 | 输入框 | 默认 8102 |
| 远程目标端口 | 输入框 | 默认 8102 |
| 公钥展示区 | 只读文本框 | 进入页面时调 GET /public-key 加载 |
| 复制公钥 | 按钮 | 一键复制公钥到剪贴板 |
| 配置命令展示区 | 只读文本框 | 模板含实际公钥值，前端动态拼接 |
| 复制命令 | 按钮 | 一键复制完整命令到剪贴板 |
| 测试连接 | 按钮 | 调 POST /test 验证隧道 + 远程可达，显示一次性结果（成功/失败 + 原因） |

**配置命令模板**（前端动态拼接，公钥值从 GET /public-key 响应中获取）：

```bash
# 在云端服务器执行以下命令（追加 SSH 公钥）
mkdir -p ~/.ssh
chmod 700 ~/.ssh
echo '<public_key>' >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

**切换交互逻辑**：
- 用户切换到 SSH 模式 → 先调 POST /enable 触发密钥准备（如已存在则保留）→ 加载公钥展示 → 拼接配置命令 → 调 PATCH /api/v2/settings 保存 connection_mode
- 切换回 HTTP/HTTPS 模式 → SSH 配置保留（不删除）→ 调 PATCH /api/v2/settings 保存 connection_mode
- 切换时自动保存，无需额外点击保存按钮

## Acceptance criteria

- [ ] 修改 `frontend/apps/settings/components/SyncConfigSection.tsx` 新增连接方式切换 UI
- [ ] 选项卡 1（HTTP/HTTPS）保留现有云端地址输入 + 生成云端配置按钮，行为不变
- [ ] 选项卡 2（SSH 隧道）新增 10 个 UI 元素（参考元素清单）
- [ ] 切换到 SSH 模式时自动调 POST /api/v2/settings/ssh-tunnel/enable
- [ ] 切换到 SSH 模式后自动调 GET /api/v2/settings/ssh-tunnel/public-key 加载公钥
- [ ] 公钥展示区显示完整公钥（以 `ssh-ed25519 ` 开头）
- [ ] 配置命令展示区动态拼接实际公钥值到模板
- [ ] "复制公钥"按钮一键复制公钥到剪贴板（使用 navigator.clipboard）
- [ ] "复制命令"按钮一键复制完整命令到剪贴板
- [ ] "测试连接"按钮调 POST /api/v2/settings/ssh-tunnel/test 并显示一次性结果（成功/失败 + 原因）
- [ ] 测试连接中显示 loading 状态，避免重复点击
- [ ] 切换模式时自动保存 connection_mode 到后端
- [ ] 切换回 HTTP 模式时 SSH 配置保留（不删除输入值）
- [ ] 修改 `frontend/apps/settings/syncApi.ts` 新增 3 个 API 调用函数（enableSshTunnel / getPublicKey / testConnection）
- [ ] 修改 `frontend/apps/settings/syncTypes.ts` 新增相关 TypeScript 接口
- [ ] 扩展 `frontend/apps/settings/components/SyncConfigSection.test.tsx` 新增 UI 测试
- [ ] 遵循 [coding-rules/frontend-core-rule.md](../../../docs/coding-rules/frontend-core-rule.md) 规范
- [ ] 所有现有前端测试通过（无回归）

## Blocked by

- Issue 04: SSH 隧道管理 API（前端需调用 enable/public-key/test 端点）
- Issue 05: SyncClient SSH 隧道编排（隧道运行时已就绪，前端"测试连接"按钮可验证真实隧道）

## User stories covered

- 1, 2, 3, 4, 5（连接方式选择 + 选项卡）
- 9, 10, 11, 12（公钥展示/复制 + 配置命令展示/复制）
- 22（通过测试连接按钮手动验证隧道可用性）

注：原 User Story 18（隧道状态实时显示）已从 PRD v1.2 移除，由未来 PRD 增强。
