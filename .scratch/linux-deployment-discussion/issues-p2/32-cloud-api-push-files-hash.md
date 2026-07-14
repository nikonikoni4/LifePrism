# 云端 API: push-files 改造

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

改造现有 `/push-files` 端点（issue 22），新增 parent_hash + current_hash 字段，云端写入文件后立即更新 file_sync_state。

**ADR 参考**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.1 决策 5

**改造内容**：

### `POST /api/sync/push-files`（改造现有）

请求新增 parent_hash + current_hash 字段：

```python
class FilePushItem(BaseModel):
    path: str
    content: str        # gzip 压缩 + base64 编码
    parent_hash: str | None = None   # 新增：推送方的 parent_hash
    current_hash: str              # 新增：推送方的 current_hash
    # mtime 字段移除——不再用 mtime 做 LWW
```

云端逻辑：
1. base64 解码 + gzip 解压 → 写入文件
2. 写入后**立即**计算 current_hash（调用 compute_file_hash）→ 更新 file_sync_state 表
3. 如果 file_sync_state 中无此文件记录 → 插入新记录（parent_hash = NULL, current_hash = 计算值）
4. 如果已有记录 → 只更新 current_hash（**parent_hash 不修改**，保持云端原值）

**关键约束**：push-files **不修改 parent_hash**。推送方传来的 parent_hash 仅用于云端记录是否需要插入新记录的判断（无记录时插入），不用于覆盖云端已有的 parent_hash。parent_hash 的推进由 `/pull-files/commit` 端点负责（见 issue 31），在 Phase 3 verify 校验通过后执行。

Response 新增 results 字段：

```python
{
    "results": [{"path": "...", "action": "accepted"}],
    "sync_time": "..."
}
```

**原 mtime LWW 逻辑废弃**：不再比较 mtime，不再设置 os.utime。冲突检测由 hash 矩阵判定（在 SyncClient 侧执行，见 issue 33）。

**parent_hash 推进不在本端点**：push-files 只负责写入文件 + 更新 current_hash。parent_hash 的推进由 `/pull-files/commit` 端点负责（见 issue 31），在 Phase 3 verify 校验通过后执行。如果 verify/commit 失败，parent_hash 保持原值（NULL 或上一次同步的值），下次同步会重新触发 PUSH，安全重试。

## Acceptance criteria

- [ ] FilePushItem 新增 parent_hash + current_hash 字段
- [ ] FilePushItem 移除 mtime 字段
- [ ] 云端写入文件后立即调用 compute_file_hash 计算 current_hash
- [ ] 云端写入后立即更新 file_sync_state 表（upsert current_hash）
- [ ] push-files 不推进 parent_hash（由 commit 端点负责）
- [ ] 不再比较 mtime 做 LWW
- [ ] 不再调用 os.utime 设置 mtime
- [ ] Response 包含 results 字段（每文件的 action）
- [ ] 路径安全检查（防路径遍历攻击）
- [ ] API Key 认证生效
- [ ] 日志记录：INFO 级别记录写入文件数
- [ ] 集成测试：文件写入 + file_sync_state 更新正确
- [ ] 集成测试：parent_hash 为 None 时正确处理（新文件）

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/30-file-sync-state-table-and-provider.md` - file_sync_state 表和 compute_file_hash() 必须先就绪
