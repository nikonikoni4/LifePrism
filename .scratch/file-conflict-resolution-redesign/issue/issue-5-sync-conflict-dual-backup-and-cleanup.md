# Issue 5: sync_conflict/ 双向备份修复 + 30 天清理机制

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 9, 19）

## What to build

修复 sync_conflict/ 仅备份本地的 bug，并新增 30 天自动清理机制。

**Bug 描述**（[sync_client.py:1610-1614](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1610-L1614)）：

当前冲突前只备份本地版本，云端版本在降级 keep_ours 后永久丢失。用户无法对比本地与云端差异，无法判断 keep_ours 是否正确，如果发现 keep_ours 选错了，没有云端版本可恢复。

**改造**：

```python
# 当前（有 bug）：
backup_path = (data_path / "sync_conflict" / timestamp_str / file_path).resolve()
backup_path.parent.mkdir(parents=True, exist_ok=True)
backup_path.write_text(local_content, encoding="utf-8")  # 只备份本地
```

改为同时备份本地和云端：

```python
# 改造后（同时备份本地和云端）：
conflict_dir = (data_path / "sync_conflict" / timestamp_str).resolve()
conflict_dir.mkdir(parents=True, exist_ok=True)

# 备份本地版本
(conflict_dir / f"{file_path_str}.local.md").write_text(local_content, encoding="utf-8")

# 备份云端版本
(conflict_dir / f"{file_path_str}.remote.md").write_text(remote_content, encoding="utf-8")
```

**备份目录结构**（扁平化，路径用 `__` 分隔避免嵌套）：

```
sync_conflict/
└── 20260717_154500/
    ├── agent__behavior.md.local.md    ← 本地版本
    └── agent__behavior.md.remote.md   ← 云端版本
```

**清理机制**：

- 沿用数据备份 spec 的清理策略
- 30 天保留期，超期自动删除子目录
- 每次冲突备份时顺带检查并清理过期目录

**关键约束**：

- 本 issue 只修复备份完整性和清理机制，不涉及冲突处理流程改造（在 Issue 4 中实现）
- 与现有 sync_conflict/ 路径保持兼容（向后兼容旧的单文件备份结构）

## Acceptance criteria

- [ ] 修改 `sync_client.py` 冲突备份逻辑，同时备份本地和云端两个版本
- [ ] 本地版本文件名后缀：`.local.md`
- [ ] 云端版本文件名后缀：`.remote.md`
- [ ] 文件路径用 `__` 分隔避免嵌套（如 `agent__behavior.md.local.md`）
- [ ] sync_conflict/ 30 天保留期，超期自动清理
- [ ] 清理时机：每次冲突备份时顺带检查并清理过期目录
- [ ] 单元测试覆盖双向备份
- [ ] 单元测试覆盖 30 天清理机制
- [ ] 向后兼容：旧的单文件备份结构仍可读取（不强制迁移）
- [ ] 验证：触发冲突后 sync_conflict/{ts}/ 同时包含 `.local.md` 和 `.remote.md`

## Blocked by

None - can start immediately

## User stories covered

PRD 用户故事：30, 31（sync_conflict 双向备份 + 30 天清理）

## Related ADRs

- [docs/adr/2026-07-17-conflict-failure-policy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-failure-policy.md) - 冲突失败处理策略，明确要求 sync_conflict/ 必须同时备份本地和云端版本（本 issue 的核心 ADR）
- [docs/adr/2026-07-17-data-backup-strategy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md) - 数据备份策略（30 天清理机制沿用）
