使用 tdd skill 完成任务

# Issue #10: LLM 模块时间处理迁移

## Parent

`.scratch/utc-timezone-migration/prd.md`

## What to build

迁移 LLM 模块的时间处理逻辑。

**修改范围**：
- `lifeprism/llm/` - 所有涉及时间处理的子模块
- `lifeprism/llm/session/manager.py` - Session 管理的时间戳
- `lifeprism/llm/utils/llm_call_logger.py` - LLM 调用日志的时间戳
- `lifeprism/llm/agent/context.py` - 如果涉及时间处理
- `lifeprism/llm/prompts/prompt_loader.py` - 如果涉及时间戳

**修改模式**：
- 所有 `datetime.now()` 改为 `datetime.now(timezone.utc)`
- 所有 `.strftime()` 改为 `.isoformat()`
- 所有时间戳记录使用 UTC

**注意事项**（参考 `docs/guides/utc-migration-hidden-dependencies.md`）：
- LLM 调用日志的时间戳需要与系统其他日志一致
- Session 管理的时间戳影响会话过期判断
- 检查是否有时间相关的 Prompt 生成逻辑

## Acceptance criteria

- [ ] 所有 `datetime.now()` 已改为 `datetime.now(timezone.utc)`
- [ ] 所有 `.strftime()` 已改为 `.isoformat()`
- [ ] LLM 调用日志的时间戳格式已统一
- [ ] Session 管理的时间戳逻辑已验证
- [ ] 已新增单元测试验证时间字段格式
- [ ] 所有现有 LLM 模块测试仍然通过

## Blocked by

- Issue #2 - Repository 层基础迁移
