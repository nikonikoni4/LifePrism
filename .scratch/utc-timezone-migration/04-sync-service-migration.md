使用 tdd skill 完成任务

# Issue #4: 数据同步服务迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移数据同步服务的时间处理逻辑，确保 LWW 冲突解决使用 UTC 时间戳，本地和云端时间比较正确。

**修改范围**：
- `lifeprism/server/services/sync_service.py` - 所有时间生成、比较、序列化
- `lifeprism/server/services/plandoc_sync_service.py` - 如果涉及时间处理

**核心修改**：
- `incremental_sync()` 中的时间范围查询改为 UTC
- `last_sync_time` 的读取和更新改为 UTC
- LWW 冲突解决的时间戳比较确保使用 ISO 8601 格式字符串

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- 这是 P0 问题的核心修复点（LWW 冲突解决失败）
- 需要特别注意时间戳字符串比较的正确性
- 需要集成测试模拟跨时区同步场景

## Acceptance criteria

- [ ] `sync_service.py` 中所有 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] `last_sync_time` 的读取和更新使用 UTC
- [ ] LWW 冲突解决逻辑已验证使用 ISO 8601 格式比较
- [ ] 已新增集成测试：模拟本地 UTC+8、云端 UTC 的数据同步场景
- [ ] 已新增集成测试：验证 LWW 冲突解决在跨时区下正确
- [ ] 所有现有同步测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
