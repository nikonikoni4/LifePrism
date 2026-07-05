# Issue 4: Goal + Diary + Todos 模块端到端错误处理

Status: ready-for-agent

## 必读文档

1. **PRD**: `.scratch/backend-error-handling/PRD.md`
2. **编码规范**: `docs/coding-rules/backend-error-handling.md`
3. **日志规则**: `lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）

## Parent

`.scratch/backend-error-handling/PRD.md`

## What to build

端到端修复 Goal、Diary、Todos 三个模块的错误处理路径。这三个模块当前端点基本没有 try/except，依赖全局 handler 兜底，但 Provider 层大量使用 `return None` 而非抛异常。

### Goal 模块
- `goal_api.py`：当前端点无 try/except，让 LWBaseError 自然冒泡是正确的。但需要确认端点中 `if not result: raise HTTPException(404)` 是否应改为让 Provider 抛 `EntityNotFoundError`
- `goal_providers.py`：已验证部分方法已正确使用 `ConflictError`（sqlite3.IntegrityError），需确认其他 `return None` 是否应改为抛异常
- `goal_aggregator.py`：`return None` → ERROR 日志 + `raise DataAccessError`

### Diary 模块
- `diary_api.py`：当前端点无 try/except，确认是否需要补充（如果 service 层正确抛 LWBaseError 子类，无需改动）
- `diary_api.py` 中 `if not result: raise HTTPException(404)` 模式确认

### Todos 模块
- `todos_api.py`：当前端点无 try/except，确认 `return None` 处理模式
- `todo_provider.py`：大量 `except Exception` 需要检查是否应窄化为 `except sqlite3.Error`

### 日志要求
- Provider 首次发现点 → ERROR 日志
- 聚合器数据库故障 → ERROR 日志 + 抛异常（不再静默返回空值）
- 对已是正确模式的代码（如 `goal_providers.py` 的 `ConflictError`）不做无谓修改

## Acceptance criteria

- [ ] Goal/Diary/Todos 端点中 NotFoundError 等能正确映射（404 而非 500）
- [ ] `goal_aggregator.py` 数据库故障不再静默返回 `None`
- [ ] `todo_provider.py` 中过宽的 `except Exception` 窄化为 `except sqlite3.Error`
- [ ] Provider 首次发现点有 ERROR 日志（含 entity 标识 + 上下文）
- [ ] 已是正确模式的代码不被无谓修改
- [ ] 不引入新的 linter 错误

## Blocked by

- Issue 1（基础设施修复）
