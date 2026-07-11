使用 tdd skill 完成任务

# Issue #5: 定时任务服务迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移定时任务服务的时间处理逻辑，确保 Cron 表达式、相对时间计算、任务触发时间判断都使用 UTC。

**修改范围**：
- `lifeprism/server/services/schedule_service.py` - Cron 表达式、时间判断逻辑
- `lifeprism/llm/function/agent_schedule_job.py` - 如果涉及时间计算

**核心修改**：
- `_SYSTEM_CRON_JOB_TIME` 从 `"0 10 * * *"` 改为 `"0 2 * * *"`（保持本地时间 10:00 触发）
- `_dreaming()` 中的"昨天"计算改为 `datetime.now(timezone.utc) - timedelta(days=1)`
- `_should_execute_cron_today()` 中的"今天"判断改为 `datetime.now(timezone.utc).strftime("%Y-%m-%d")`
- APScheduler 时区设置（如果需要）

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- Cron 表达式需要调整以保持用户预期的触发时间（本地时间 10:00）
- 相对时间概念（"昨天"、"今天"）需要明确基于 UTC
- 需要测试验证任务在预期时间触发

## Acceptance criteria

- [ ] Cron 表达式已调整为 UTC 时区下对应本地时间 10:00
- [ ] 所有相对时间计算（"昨天"、"今天"）已改为 UTC
- [ ] 所有 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 已新增单元测试验证时间判断逻辑
- [ ] 已新增集成测试：模拟不同时区下任务触发时间
- [ ] 所有现有定时任务测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
