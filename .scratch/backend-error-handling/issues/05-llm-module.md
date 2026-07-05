# Issue 5: LLM 模块端到端错误处理

Status: ready-for-agent

## 必读文档

1. **PRD**: `.scratch/backend-error-handling/PRD.md`
2. **编码规范**: `docs/coding-rules/backend-error-handling.md`
3. **日志规则**: `lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）
4. **LLM 异常定义**: `lifeprism/llm/exceptions.py`

## Parent

`.scratch/backend-error-handling/PRD.md`

## What to build

让 LLM 模块真正使用已定义的 `LLMResponseError`、`LLMOutputParseError` 和 `PromptNotFoundError`，替代当前的"静默吞错误"和"Python 内置异常"模式。

### classify_graph.py
- 第 90 行：`except Exception` 获取描述异常 → 窄化为具体异常
- 第 130、173、241 行：LLM 返回空内容时 `logger.warning` + 跳过 → `raise LLMResponseError`（模型 + 原始响应作为 details）
- 分类失败应在首次发现点记录 ERROR 日志（含 batch_num + model + 原始响应片段）

### screenshot_analysis.py
- 第 392-397 行：LLM 调用失败 `except ValueError` + `except Exception → return None` → 使用 `LLMResponseError` + `LLMOutputParseError`
- LLM 故障不再静默返回 None，让调用方能感知并降级

### diary_summary.py
- 当前没有任何 LLM 调用错误处理 → 补充 `try/except`，捕获 LLM 故障并转为 `LLMResponseError`
- 在首次发现点记录 ERROR 日志

### agent_schedule_job.py
- 当前已使用 `ExternalServiceError`，改为更具体的 `LLMResponseError` / `LLMOutputParseError`（如果语义匹配）

### prompt_loader.py
- 第 195 行：`raise FileNotFoundError`（Python 内置异常 → 全局 handler → 500）
- → 改为 `raise PromptNotFoundError(prompt_name, module)`（继承自 NotFoundError → 404）

### 日志要求
- LLM 返回空/无效时 → ERROR 日志（含 model + prompt 标识 + 原始响应片段）
- LLM 输出解析失败 → ERROR 日志（含预期字段 + 实际字段 + 原始输出片段）
- Prompt 文件缺失 → ERROR 日志（含 prompt_name + module）

## Acceptance criteria

- [ ] LLM 返回空内容时抛出 `LLMResponseError`（非静默跳过）
- [ ] LLM 输出解析失败时抛出 `LLMOutputParseError`（非 `return None`）
- [ ] `prompt_loader.py` 抛出 `PromptNotFoundError`（非 `FileNotFoundError`）
- [ ] `PromptNotFoundError` → API 返回 404（非 500）
- [ ] `LLMResponseError` → API 返回 503
- [ ] 调试 LLM 故障时能从 ERROR 日志找到：哪个模型、哪个 prompt、返回了什么
- [ ] 不引入新的 linter 错误

## Blocked by

- Issue 1（基础设施修复）
