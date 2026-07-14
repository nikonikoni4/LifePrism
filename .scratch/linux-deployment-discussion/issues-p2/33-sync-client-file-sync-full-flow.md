# SyncClient 文件同步全流程

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

在 SyncClient 中实现完整的文件同步流程：更新白名单（11→4 目录）+ Phase 1-3 完整流程 + hash 时效性保证 + parent_hash 推进。替换原 issue 23 的 mtime + LWW 逻辑。

**ADR 参考**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.1 决策 1 + 5

**白名单更新**：

SYNC_DIRECTORIES 从 11 个目录缩减为 4 个：
- `session/` — 会话记录
- `diary/` — 日记
- `agent/` — Agent 配置
- `user/` — 用户数据（behavior.md 等）

移除的目录（已改为数据库同步或排除）：
- `channel/wechat/account.json` → wechat_account_state 表（issue 35）
- `config/` → 走 storage.yaml（issue 26）
- `memory/`, `llm/` 等非同步目录

**排除文件**：`chat_history.json`（仅由 dreaming task 定时任务改写，云端不启动 dreaming，明确排除）

**完整流程**：

### Phase 1: 快照交换
- 调用 `POST /pull-files/check` 发送 last_sync_time + directories
- 云端返回变更文件的 {path, parent_hash, current_hash}
- 本地对相同文件实时计算 current_hash（调用 compute_file_hash）

### Phase 2a: 本地 11 状态矩阵判定
- 对每个文件比较 4 个变量：本地 parent_hash、本地 current_hash、云端 parent_hash、云端 current_hash
- 决策矩阵输出：PULL / PUSH / CONFLICT / SKIP

### Phase 2b: 拉取内容（PULL + CONFLICT）
- 调用 `POST /pull-files/fetch` 拉取云端内容
- 解压解码 → 写入本地文件
- **写入后立即**计算 current_hash → 更新本地 file_sync_state 表

### Phase 2c: 推送内容（PUSH 文件）
- 调用 `POST /push-files` 推送文件内容 + hash 状态
- 云端写入后更新云端 file_sync_state
- **CONFLICT 文件**：本 issue 暂不处理，记录日志（文件路径 + CONFLICT 标记），跳过推送。CONFLICT 的 AI 合并由 issue 34 实现，届时在 Phase 2c 中补充合并结果推送

### Phase 3: 一致性校验 + parent_hash 推进
- 调用 `POST /pull-files/verify` 对所有变更文件（PULL + PUSH）实时获取云端 hash
- 比对本地 current_hash == 云端 current_hash
- 一致 → 本地推进 parent_hash = current_hash + 调用 `POST /pull-files/commit` 通知云端推进 parent_hash
- 不一致 → 不推进 parent_hash，下次同步重试

**同步前全量扫描**：Phase 1 前需扫描 SYNC_DIRECTORIES 下所有文件，刷新本地 file_sync_state 的 current_hash（调用 compute_file_hash）。因为 11 状态矩阵需要比较本地 parent_hash 和 current_hash，必须确保 current_hash 是最新的。

**hash 时效性原则**（核心约束）：
- Phase 1 快照时的 hash 必须是此刻实时计算的
- Phase 2b 写入后立即计算 hash 更新 DB
- Phase 2c 云端写入后立即计算 hash 更新 DB
- Phase 3 verify 时两端都实时计算 hash
- **任何时刻发送或对比 hash 时，hash 必须是最新的**

**与 issue 35 的协作**：本 issue 在 35 已移除 account.json 的基础上，进一步缩减其他目录（config/、memory/、llm/ 等），最终 SYNC_DIRECTORIES 为 4 个目录（session/、diary/、agent/、user/）。

**sync_once() 改造方式**：替换现有的 `pull_files_from_remote()` + `push_files_to_remote()` 为新的 `_sync_files_full_flow()` 方法，包含 Phase 1-3 完整流程。原方法废弃删除。

## Acceptance criteria

- [ ] SYNC_DIRECTORIES 更新为 4 个目录（session/、diary/、agent/、user/）
- [ ] chat_history.json 在文件扫描时被排除
- [ ] 同步前全量扫描：刷新 SYNC_DIRECTORIES 下所有文件的 current_hash
- [ ] Phase 1: 调用 /pull-files/check 获取云端 hash 快照
- [ ] Phase 2a: 11 状态矩阵判定正确（PULL/PUSH/CONFLICT/SKIP）
- [ ] Phase 2b: 拉取 PULL 文件 → 写入 → 立即更新 current_hash
- [ ] Phase 2c: 推送 PUSH 文件 → 云端写入 → 云端更新 current_hash
- [ ] Phase 2c: CONFLICT 文件被检测到并跳过（记录日志，标记未处理）
- [ ] Phase 3: 调用 /pull-files/verify 校验一致性
- [ ] Phase 3: 一致时本地推进 parent_hash + 调用 /pull-files/commit 推进云端 parent_hash
- [ ] Phase 3: 不一致时不推进 parent_hash
- [ ] hash 时效性：Phase 1/2b/2c/3 均使用实时计算的 hash
- [ ] 日志记录：每个 Phase 的开始/结束、处理的文件数、PULL/PUSH/CONFLICT/SKIP 计数
- [ ] 集成测试：PULL 场景（仅云端改）
- [ ] 集成测试：PUSH 场景（仅本地改）
- [ ] 集成测试：SKIP 场景（双方都没改）
- [ ] 集成测试：CONFLICT 场景（双方都改 → 检测到并跳过，记录日志）
- [ ] 集成测试：换电脑场景（本地 parent=NULL，云端 parent=A → PULL）
- [ ] 集成测试：空文档覆盖 Bug 场景（云端新部署空文档，本地有内容 → 矩阵判定为 PUSH 而非覆盖）
- [ ] 集成测试：Phase 3 校验通过 → 本地+云端 parent_hash 推进
- [ ] 集成测试：Phase 3 校验失败 → parent_hash 不推进

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/30-file-sync-state-table-and-provider.md` - file_sync_state 表和 compute_file_hash() 必须先就绪
- `.scratch/linux-deployment-discussion/issues-p2/31-cloud-api-pull-files-check-fetch-verify.md` - 云端 check/fetch/verify/commit 端点必须先就绪
- `.scratch/linux-deployment-discussion/issues-p2/32-cloud-api-push-files-hash.md` - 云端 push-files 改造必须先就绪
- `.scratch/linux-deployment-discussion/issues-p2/35-wechat-account-state-table-and-migration.md` - account.json 从 SYNC_DIRECTORIES 移除由 35 负责
