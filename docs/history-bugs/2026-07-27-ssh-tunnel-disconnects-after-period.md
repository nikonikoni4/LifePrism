---
version: 1.0
created_at: 2026-07-27
updated_at: 2026-07-27
last_updated: 创建初稿，记录 SSH 隧道运行一段时间后无法连接的问题及可能根因（云端 sshd ClientAliveInterval=0 + 阿里云 DDoS 防护）
abstract: SSH 隧道启动后能正常同步一次，但运行 10 分钟以上后所有 sync_once 调用均超时（WinError 121）或报 502 Bad Gateway，本地隧道重连机制虽能重建 SSH 连接但仍无法访问云端 8102 服务。根因未最终确定，可能为云端 sshd 死连接累积触发阿里云 DDoS 防护 IP 暂封
status: open
---

# SSH 隧道运行一段时间后无法访问云端服务

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建初稿，记录现象、排查过程和可能的根因 |

## 现象

**触发场景**：本地 LifePrism 启动后 SSH 隧道建立成功，第一次 sync_once 正常完成（约 35 秒）。但运行 10 分钟以上后，所有定时 sync_once 调用均失败。

**错误表现**：
1. 本地日志显示 `[WinError 121] 信号灯超时时间已到` — SSH 隧道的 TCP 连接超时
2. 本地日志显示 `502 Bad Gateway for url 'http://localhost:8102/api/sync/dynamic-tables-definitions'` — httpx 在 TCP 连接超时后错误地报 502
3. SSH keep-alive 检测到断开，自动重连成功，但重连后仍无法访问云端 8102 服务
4. 重启云端服务后，本地又能正常同步一次，但过段时间后再次失败

**日志时间线**：
```
08:32:21 SSH 隧道 connected（启动）
08:32:21 定时同步开始 → 08:32:56 sync_once 完成（35s，成功）
08:42:56 定时同步开始 → 08:43:19 失败（WinError 121 + 502）
08:43:26 SSH 隧道连接已断开，进入 reconnecting
08:43:31 SSH 隧道 reconnect 成功
08:53:19 定时同步开始 → 08:53:41 失败（WinError 121 + 502）
... （后续每 10 分钟定时同步均失败）
12:14:06 重启云端服务后，sync_once 成功一次
12:21:12 定时同步开始 → 失败
... （再次进入失败循环）
```

## 影响范围

- **功能影响**：sync_once 完全失效，本地与云端数据无法同步
- **数据影响**：无数据丢失（sync_once 失败不更新 last_sync_time，下次重试从同一时间点）
- **用户体验**：用户看到"上一次同步时间是 1 小时前"（实际是首次同步时间），且无法恢复

## 可能根因（未最终确定）

### 假设 1：云端 sshd ClientAliveInterval=0 + 阿里云 DDoS 防护

**推测链路**：
1. 云端 sshd 配置 `ClientAliveInterval=0`（默认值）— 死连接永不清理
2. 每次本地隧道断开重连（如网络抖动、keep-alive 超时）都留下一个僵尸 SSH 连接
3. 僵尸连接累积到一定数量（推测 17 个左右）→ 阿里云 DDoS 防护触发 → IP 被暂封
4. IP 暂封期间，本地能建立 SSH 连接（22 端口未被封），但通过 SSH 隧道访问的 8102 服务请求被丢弃
5. TCP 连接超时 → `[WinError 121] 信号灯超时时间已到`
6. httpx 在超时后错误地报 `502 Bad Gateway`（误导性错误信息）

**支持证据**：
- 本地日志显示 SSH 连接能成功建立（22 端口可达）
- 但通过隧道访问 8102 端口超时（请求未到达云端服务）
- 云端日志在失败时段完全没有任何请求记录（请求根本没到达云端 8102 服务）
- 重启云端服务后能短暂工作（可能 IP 暂封有时间窗口，重启时间刚好错开）

**待验证项**：
- [ ] 云端 sshd 配置是否真的是 `ClientAliveInterval=0`
- [ ] 阿里云控制台是否有 DDoS 防护触发记录
- [ ] 失败时段 `ss -tnp | grep :22` 是否显示大量僵尸 SSH 连接
- [ ] 失败时段本地 IP 是否能 ping 通云端

### 假设 2：云端 8102 服务崩溃

**推测链路**：
1. 云端 uvicorn 服务因内存泄漏/资源耗尽在运行一段时间后崩溃
2. 8102 端口无进程监听
3. SSH 隧道 forwarder 尝试转发到 127.0.0.1:8102 但连接被拒绝
4. TCP 连接超时 → `[WinError 121]`

**支持证据**：
- 云端日志在失败时段确实没有任何记录
- 重启云端服务后能短暂工作

**反驳证据**：
- 如果是服务崩溃，`ss -tlnp | grep 8102` 应该显示无监听，但用户未验证
- 服务崩溃通常会有 systemd 日志或 uvicorn 错误输出

### 假设 3：本地测试连接按钮创建独立隧道导致端口冲突

**推测链路**：
1. 用户点击"测试连接"按钮 → 新建 SSHTunnel 实例 → 新建 forwarder 监听 8102 端口
2. 两个 forwarder（SyncClient 的 + 测试连接的）同时监听 8102，互相冲突
3. 测试连接关闭后，原 SyncClient 隧道的 forwarder 已损坏
4. 后续 sync_once 通过损坏的 forwarder 访问失败

**支持证据**：
- 本地日志 13:30:04 显示测试连接新建 forwarder，13:30:24 原隧道报 `WinError 121`
- 测试连接和原隧道使用相同的 `local_port=8102`

**反驳证据**：
- 用户反馈即使不点"测试连接"按钮，sync 也会在 10 分钟后失败
- 第一次 sync 成功，10 分钟后的定时 sync 失败 — 与测试连接无关

## 排查过程

### 已确认

1. **本地 SSH 隧道工作正常** — SSH 连接能成功建立，认证通过，forwarder 创建成功
2. **本地代码无 bug** — `ssh_tunnel.py` 和 `sync_client.py` 逻辑正确
3. **云端服务在启动时正常** — 首次 sync_once 能成功完成
4. **问题出在云端** — 失败时段云端日志无任何请求记录，说明请求未到达云端 8102 服务

### 待排查

1. **云端 sshd 配置**：`cat /etc/ssh/sshd_config | grep ClientAlive`
2. **云端连接状态**：`ss -tnp | grep :22 | wc -l`（僵尸连接数）
3. **阿里云 DDoS 防护**：登录阿里云控制台查看是否有 IP 暂封记录
4. **云端 8102 服务状态**：`systemctl status lifeprism` 或 `ps aux | grep uvicorn`
5. **云端系统日志**：`journalctl -u sshd --since "1 hour ago" | grep -i "disconnect\|timeout"`

## 排查方向（按优先级）

### 优先级 1：验证假设 1（云端 sshd 死连接）

```bash
# 云端执行
cat /etc/ssh/sshd_config | grep -i "ClientAlive"
ss -tnp | grep :22 | wc -l
# 阿里云控制台查看 DDoS 防护日志
```

如果确认 `ClientAliveInterval=0`，修复方案：
```bash
# 云端 /etc/ssh/sshd_config 添加
ClientAliveInterval 60
ClientAliveCountMax 3
# 重启 sshd
systemctl restart sshd
```

### 优先级 2：验证假设 2（云端服务崩溃）

```bash
# 云端执行
systemctl status lifeprism  # 或对应的服务名
ss -tlnp | grep 8102
journalctl -u lifeprism --since "1 hour ago"
```

### 优先级 3：假设 3 的修复（测试连接端口冲突）

即使假设 3 不是本次 bug 的根因，测试连接按钮的端口冲突问题仍需修复：

**方案 A（推荐）**：测试连接复用已运行的隧道
- 前端检测 SyncClient 隧道状态
- 若隧道已运行，直接测试 `/api/sync/health`
- 若未运行，才新建测试隧道

**方案 B**：测试连接使用不同的本地端口
- `local_port=0`（系统分配随机端口）
- 避免与已运行隧道冲突

## 修复方案

待根因确定后补充。

## 相关文档

- SSH 隧道 ADR：[2026-07-27-ssh-tunnel-encryption.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-27-ssh-tunnel-encryption.md)
- SSH 隧道 Spec：[2026-07-26-data-sync-ssh-tunnel-spec.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-26-data-sync-ssh-tunnel-spec.md)
- SSH 隧道 Flow：[2026-07-26-ssh-tunnel-flow.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/flows/2026-07-26-ssh-tunnel-flow.md)
- 打包环境 GSSAPI Bug：[2026-07-27-packaged-win32timezone-gssapi.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-27-packaged-win32timezone-gssapi.md)

## 教训

1. **误导性错误信息**：httpx 在 TCP 连接超时后报 `502 Bad Gateway` 而非 `ConnectionError`，导致排查方向错误。本地代码应在 sync 失败时额外记录 `WinError` 详情。
2. **跨层排查思维**：当本地日志显示"502 Bad Gateway"时，容易误判为云端 HTTP 服务问题。实际上 502 是 httpx 对 TCP 超时的错误包装，真正的问题在网络层或云端服务层。
3. **云端服务监控缺失**：云端服务无健康检查和自动重启机制，崩溃后无法自动恢复。建议配置 systemd `Restart=always`。
