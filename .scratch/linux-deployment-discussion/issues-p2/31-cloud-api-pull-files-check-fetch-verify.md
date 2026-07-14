# 云端 API: pull-files/check + fetch + verify + commit 四端点

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

在云端 sync_cloud_api.py 中新增四个文件同步端点，替换原有的 `/pull-files` 端点（issue 21）。实现三阶段协议的云端侧：check（快照交换）→ fetch（内容拉取）→ verify（一致性校验）→ commit（parent_hash 推进）。

**ADR 参考**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.1 决策 5

**四个端点**：

### 1. `POST /api/sync/pull-files/check`

云端按 mtime 过滤，返回变更文件的 hash 状态（轻量，不传内容）。

- Request: `{last_sync_time, directories}`
- Response: `{files: [{path, parent_hash, current_hash}], sync_time}`
- 云端逻辑：遍历 directories（排除 chat_history.json），找到 mtime > last_sync_time 的文件 → 实时计算 current_hash（调用 compute_file_hash）→ 从 file_sync_state 表读 parent_hash → 返回
- check 端点返回空列表时（无变更文件），客户端应正常跳过后续 Phase

### 2. `POST /api/sync/pull-files/fetch`

云端按路径返回文件内容（仅 PULL + CONFLICT 文件）。

- Request: `{paths: ["user/user.md", ...]}`
- Response: `{files: [{path, content, parent_hash, current_hash}]}`
- content 为 gzip 压缩 + base64 编码
- 返回的 parent_hash 供客户端初始化本地 file_sync_state（如新文件首次 PULL 时本地无记录）
- current_hash 供客户端校验传输完整性，但客户端写入文件后应**重新计算** current_hash（不直接使用 fetch 返回的值）
- 请求路径不存在时跳过（不报错，不返回该文件）

### 3. `POST /api/sync/pull-files/verify`

云端实时计算 hash，用于 Phase 3 一致性校验。**纯只读，不修改任何状态**。

- Request: `{paths: ["user/user.md", ...]}`
- Response: `{files: [{path, current_hash}]}`
- 云端对 paths 中的文件**实时计算** current_hash（再次读取文件内容 → 规范化 → SHA-256）

### 4. `POST /api/sync/pull-files/commit`（新增）

本地 verify 校验通过后，通知云端推进 parent_hash。职责明确：verify 只读校验，commit 负责推进。

- Request: `{paths: ["user/user.md", ...]}`
- Response: `{committed: [{path, parent_hash}]}`
- 云端逻辑：对 paths 中的每个文件，将 file_sync_state 的 `parent_hash = current_hash`
- 本地在 verify 通过后同时推进本地 parent_hash 和调用此端点推进云端 parent_hash

**核心原则**：发送 hash 或对比 hash 时，必须确保 hash 是最新的。不能用缓存值、不能用历史值。

**原 `/pull-files` 端点处理**：替换为以上四个端点，原 mtime + LWW 逻辑废弃。确认无其他调用方后删除原端点（原调用方 `sync_client.py:pull_files_from_remote` 会被 issue 33 改造）。

## Acceptance criteria

- [ ] `POST /api/sync/pull-files/check` 已实现：按 mtime 过滤返回 {path, parent_hash, current_hash}
- [ ] `POST /api/sync/pull-files/fetch` 已实现：按路径返回文件内容 + hash
- [ ] `POST /api/sync/pull-files/verify` 已实现：实时计算 hash 返回（纯只读）
- [ ] `POST /api/sync/pull-files/commit` 已实现：推进云端 parent_hash = current_hash
- [ ] check 端点排除 chat_history.json
- [ ] check 端点实时计算 current_hash（调用 compute_file_hash）
- [ ] check 端点无变更文件时返回空列表
- [ ] fetch 端点 content 为 gzip 压缩 + base64 编码
- [ ] fetch 端点请求路径不存在时跳过（不报错）
- [ ] verify 端点实时计算 hash（不使用缓存，不修改任何状态）
- [ ] commit 端点推进 parent_hash = current_hash
- [ ] 路径安全检查（防路径遍历攻击）
- [ ] API Key 认证生效
- [ ] 日志记录：INFO 级别记录各端点请求参数和返回文件数
- [ ] 集成测试：check 增量过滤正确
- [ ] 集成测试：check 无变更时返回空列表
- [ ] 集成测试：fetch 内容编解码正确
- [ ] 集成测试：fetch 路径不存在时跳过
- [ ] 集成测试：verify 实时 hash 正确
- [ ] 集成测试：commit 推进 parent_hash 正确

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/30-file-sync-state-table-and-provider.md` - file_sync_state 表和 compute_file_hash() 必须先就绪
