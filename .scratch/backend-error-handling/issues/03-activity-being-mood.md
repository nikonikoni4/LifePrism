# Issue 3: Activity + Being + Mood 模块端到端错误处理

Status: ready-for-agent

## 必读文档

1. **PRD**: `.scratch/backend-error-handling/PRD.md`
2. **编码规范**: `docs/coding-rules/backend-error-handling.md`
3. **日志规则**: `lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）

## Parent

`.scratch/backend-error-handling/PRD.md`

## What to build

端到端修复 Activity、Being、Mood 三个模块的错误处理路径。

### Activity 模块
- `activity_api.py`：8+ 处 `except Exception → HTTPException(500)` 改为分层捕获模式（同 Issue 2 模式）
- 当前 `except ValueError as e: raise HTTPException(400)` 保留

### Being 模块
- `being_api.py`：`except Exception → HTTPException(500)` 改为分层捕获模式
- `being_api.py` 第 107、127、151 行：尝试调用 `to_http_exception` 替代手动 `HTTPException`
- `computer_usage_provider.py` 第 127 行：`return None` → `raise EntityNotFoundError("ComputerUsage", ...)`

### Mood 模块
- `mood_api.py`：补充异常处理（当前端点没有 try/except，让 LWBaseError 自然冒泡到全局 handler 是正确的，但需要确认）
- `mood_api.py` 中如有 `except Exception` 一并修复
- `mood_aggregator.py`：在数据库错误首次发现点记录 ERROR 日志并 `raise DataAccessError`（而非 `return None`/`[]`）

### 日志要求
- Provider 层首次发现点 → ERROR 日志（含 entity 标识 + 失败原因）
- 聚合器层：数据库故障不再静默返回空值，必须 ERROR 日志 + 抛异常
- 遵循底层记录、上层透传原则

## Acceptance criteria

- [ ] `activity_api.py` 所有 `except Exception` 改为分层捕获模式
- [ ] `being_api.py` 所有 `except Exception` 改为分层捕获模式
- [ ] `mood_api.py` 中如有 `except Exception` 一并修复
- [ ] `computer_usage_provider.py` 的 `return None` 改为 `raise EntityNotFoundError`
- [ ] `mood_aggregator.py` 中 `return None`/`[]` 改为抛异常 + ERROR 日志
- [ ] Activity/Being/Mood 端点：NotFoundError → 404、ValidationError → 422
- [ ] 首次发现点有 ERROR 日志（含上下文），上层不重复记录
- [ ] 不引入新的 linter 错误

## Blocked by

- Issue 1（基础设施修复）
