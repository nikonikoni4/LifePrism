# 后端错误处理规范化 — Subagent 上下文约束

## 核心原则

错误处理路径：**底层抛领域异常 → 中间层透传 → 全局 handler 统一映射为 HTTP 响应**

## 必须遵守的错误处理模式

### 模式 1：Repository/Provider 层 — 捕获特定异常，转为领域异常

```python
import sqlite3
from lifeprism.utils.exceptions import DataAccessError

# ❌ 禁止
try:
    cursor.execute(sql, params)
except Exception as e:
    logger.error(f"操作失败: {e}")
    raise

# ✅ 正确
try:
    cursor.execute(sql, params)
except sqlite3.Error as e:
    logger.error(
        "查询用户数据失败: user_id=%s, table=%s, error=%s",
        user_id, table_name, e
    )
    raise DataAccessError(
        message="查询用户数据失败",
        details={"user_id": user_id, "table": table_name, "error": str(e)},
        cause=e,
    ) from e
```

### 模式 2：API 路由层 — 分层捕获

```python
from lifeprism.utils.exceptions import LWBaseError
from fastapi import HTTPException

# ✅ 正确（在路由端点中）
try:
    result = some_service.do_something()
except LWBaseError:
    raise  # 让全局 handler 映射为正确 HTTP 状态码
except HTTPException:
    raise
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
except Exception as e:
    logger.error(f"<操作描述>失败: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="服务器内部错误")
```

### 模式 3：`return None` → 抛异常

```python
# ❌ 禁止 — 调用方无法区分"不存在"和"数据库故障"
def get_entity(self, entity_id):
    try:
        ...
    except Exception:
        return None

# ✅ 正确
from lifeprism.repository.exceptions import EntityNotFoundError

def get_entity(self, entity_id):
    try:
        ...
    except sqlite3.Error as e:
        raise DataAccessError(...) from e

    if result is None:
        raise EntityNotFoundError(
            entity_type="EntityName",
            entity_id=entity_id,
        )
```

### 模式 4：使用模块专属异常

| 模块 | 基础异常 | 具体异常 |
|------|----------|----------|
| Config | `ConfigError` | `ConfigFileNotFoundError`, `InvalidConfigError` |
| LLM | `LLMError(ExternalServiceError)` | `LLMResponseError`, `LLMOutputParseError` |
| Processors | `ProcessorError(DataAccessError)` | `ClassificationError`, `CacheUpdateError` |
| Repository | `RepositoryError(DataAccessError)` | `EntityNotFoundError`, `DuplicateEntityError` |

## 日志记录规则（来自 lifeprism/CLAUDE.md）

### INFO：关键流程必须可追踪

必须 INFO 的场景：
- 数据持久化操作（创建/更新/删除）
- 跨边界调用（LLM 调用、外部 API）
- 状态变化

### ERROR：异常首次发现点必须记录完整上下文

**规则**：在错误首次发现点必须有 ERROR 日志，包含：操作标识 + 失败原因 + 当前状态

```python
# ✅ 正确：首次发现点，完整上下文
logger.error(
    "删除任务失败: todo_id=%s, 任务不存在, 当前任务总数=%d",
    todo_id, current_count
)

# ❌ 错误：重复记录（底层已记录）
# 如果 provider 层已记录 ERROR，service 层不需要再记录
```

**记录内容要求**：
- 操作标识：entity_id、session_id、task_name 等
- 失败原因：具体错误信息
- 当前状态：数据量、配置值等

### 禁止事项
- ❌ 首次发现点使用 DEBUG 或不记录日志
- ❌ 中间层重复记录（底层已记录的情况下）
- ❌ 循环内使用 INFO
- ❌ 辅助函数使用 INFO
- ❌ `except Exception` 吞掉异常（除合法场景外）
- ❌ ERROR 日志缺少上下文

### `except Exception` 合法场景（需加注释 `# LEGITIMATE:`）
1. **API 边界兜底**：全局异常处理器
2. **辅助操作兜底**：日志记录、指标上报失败不影响主流程
3. **第三方未知错误**：外部服务 API（微信、Windows API 等）

## 不要做的事

1. **不要创建新的异常类** — 当前异常层级已完整覆盖
2. **不要修改异常继承链** — 所有异常应继承自 LWBaseError 子树
3. **不要在 API 路由层手动构造 HTTPException 响应**（LWBaseError 子类使用 `raise` 透传）
4. **不要删除现有的正确错误处理** — 只修复有问题的部分
5. **不要修改已正确使用 `sqlite3.Error` + `DataAccessError` 的代码**

## 验证标准

完成修复后：
- [ ] `NotFoundError` 及其子类 → API 返回 404
- [ ] `ConflictError` 及其子类 → API 返回 409
- [ ] `ValidationError` → API 返回 422
- [ ] `DataAccessError` → API 返回 500
- [ ] `ExternalServiceError` → API 返回 503
- [ ] `ConfigError` → API 返回 500
- [ ] 每个异常首次发现点有 ERROR 日志（含完整上下文）
- [ ] 使用 `raise ... from e` 保留异常链
