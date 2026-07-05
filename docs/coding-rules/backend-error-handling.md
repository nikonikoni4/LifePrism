---
version: 1.1
created_at: 2026-07-05
updated_at: 2026-07-06
last_updated: 细化 except Exception 合法场景（API 边界/辅助操作/第三方未知错误）；修复 ConfigError 映射缺失；修正 PromptNotFoundError 继承关系
abstract: 后端错误处理规范，包含异常继承体系、分层捕获规则、异常定义规范、except Exception 禁止规则（含合法场景判断标准）、API 层处理器规范和错误码管理
---

# 后端错误处理规范

## 1. 异常继承体系

### 1.1 层级结构

所有业务异常必须继承自 `LWBaseError`。异常按**谁应该处理**分类：

```
Exception
  └── LWBaseError                   # 基类，携带 code / message / details / cause
        ├── NotFoundError           # → HTTP 404
        ├── ConflictError           # → HTTP 409
        ├── ValidationError         # → HTTP 422
        ├── DataAccessError         # → HTTP 500
        │     ├── RepositoryError   # repository 模块基类
        │     ├── ProcessorError    # processors 模块基类
        │     └── MonitorError      # monitor 模块基类（已迁入）
        ├── ExternalServiceError    # → HTTP 503
        │     ├── LLMError          # llm 模块基类
        │     └── WechatError       # wechat 模块基类（已迁入）
        └── ConfigError             # config 模块基类（直接继承 LWBaseError）
```

### 1.2 各基类使用场景

| 基类 | 使用场景 | API 状态码 |
|------|---------|-----------|
| `NotFoundError` | 资源（目标、习惯、日记等）不存在 | 404 |
| `ConflictError` | UNIQUE 约束冲突、重复操作 | 409 |
| `ValidationError` | 业务规则校验失败（非 Pydantic 校验） | 422 |
| `DataAccessError` | 数据库操作失败（连接、查询、写入） | 500 |
| `ExternalServiceError` | 外部服务失败（LLM API、网络请求） | 503 |
| `ConfigError` | 配置加载/校验失败 | 500 |

---

## 2. 分层捕获规则

### 2.1 分层总览

| 层级 | 职责 | 可以做的 | 禁止做的 |
|------|------|---------|---------|
| **外部接口层**（Provider / Repository / LLM 调用 / Monitor） | 捕获外部异常，转换为领域异常后抛出 | `catch sqlite3.Error` → `DataAccessError`；`catch httpx.HTTPError` → `ExternalServiceError` | ❌ `except Exception`；❌ 返回 None/默认值代替抛异常 |
| **Service 层** | 让异常自然冒泡 | 无需 try/except | ❌ 捕获异常并吞掉；❌ 捕获后只记日志不重新抛出 |
| **API 层** | 全局异常处理器统一转换 | 使用 `to_http_exception()` 映射 | ❌ 在每个路由里单独 try/except |

### 2.2 外部接口层 — 正确示例

```python
# ✅ 正确：catch 具体异常 → 转换 → 抛出
import sqlite3
from lifeprism.utils.exceptions import DataAccessError

def query_todos(self, options: QueryOptions) -> tuple:
    try:
        cursor.execute(sql, params)
        ...
    except sqlite3.Error as e:
        logger.error("查询任务失败: date=%s, filters=%s, error=%s", options.date_range, options.filters, e)
        raise DataAccessError(
            message="查询任务失败",
            details={"options": str(options), "error": str(e)},
            cause=e,
        ) from e
```

```python
# ✅ 正确：LLM 返回异常 → ExternalServiceError
from lifeprism.utils.exceptions import ExternalServiceError

if result.response is None or not result.response.content:
    logger.error("LLM 返回无效响应: model=%s, result=%s", model, result)
    raise ExternalServiceError(
        message=f"LLM ({model}) 返回无效响应",
        details={"model": model, "raw": str(result)},
    )
```

### 2.3 外部接口层 — 错误示例

```python
# ❌ 错误：catch Exception 并返回 None，吞掉异常
def get_todo_by_id(self, todo_id: str):
    try:
        cursor.execute(sql, (todo_id,))
        return cursor.fetchone()
    except Exception as e:
        logger.error(f"获取任务失败: {e}")
        return None  # ← 调用方无法区分"不存在"和"数据库故障"
```

```python
# ❌ 错误：catch Exception 后只记日志不重新抛出
def _refresh_cache(self):
    try:
        items, _ = self.goal_repository.get_goals(page=1, page_size=1000)
    except Exception as e:
        logger.error(f"刷新缓存失败: {e}")
        # ← 异常被吞掉，调用方不知道缓存已过期
```

### 2.4 Service 层 — 正确示例

```python
# ✅ 正确：让异常自然冒泡
class GoalService:
    def delete_goal(self, goal_id: str) -> None:
        self.goal_repository.delete_goal(goal_id)  # 可能抛出 NotFoundError，不做捕获
```

### 2.5 Service 层 — 错误示例

```python
# ❌ 错误：捕获异常后不重新抛出
class GoalService:
    def delete_goal(self, goal_id: str) -> None:
        try:
            self.goal_repository.delete_goal(goal_id)
        except Exception as e:
            logger.error(f"删除目标失败: {e}")
            # ← 吞掉异常，API 层返回 200 但实际没有删除
```

---

## 3. 异常定义规范

### 3.1 LWBaseError 基类

所有异常通过以下字段携带上下文：

| 字段 | 类型 | 说明 |
|------|------|------|
| `message` | `Optional[str]` | 人类可读的错误描述 |
| `code` | `Optional[str]` | 错误码（如 `"HABIT_NOT_FOUND"`），API 层用于映射 HTTP 状态码 |
| `details` | `Dict[str, Any]` | 结构化调试信息（实体 ID、当前状态等） |
| `cause` | `Optional[Exception]` | 原始异常（用于异常链追溯） |

### 3.2 何时创建子异常

满足以下**任一**条件时应创建子异常：

1. 需要类型化构造器强制调用方提供领域上下文（如 `EntityNotFoundError(entity_type, entity_id)`）
2. 需要区别于父类的特定错误码
3. 调用方需要针对该异常做特殊处理（如重试逻辑）

不需要创建子异常的情况：
- 简单的参数校验：直接使用 `raise LWBaseError` 或 `raise ValidationError`
- 一次性的错误场景：使用通用基类 + `code` 字符串即可

### 3.3 子异常定义规范

```python
# ✅ 正确：类型化构造器，强制携带上下文
from lifeprism.utils.exceptions import NotFoundError

class EntityNotFoundError(NotFoundError):
    """通用实体未找到（数据库返回空结果）。"""
    def __init__(self, entity_type: str, entity_id: str, **extra_details):
        super().__init__(
            message=f"{entity_type} 未找到: {entity_id}",
            code=f"{entity_type.upper()}_NOT_FOUND",
            details={"entity_type": entity_type, "entity_id": entity_id, **extra_details},
        )

# 使用
raise EntityNotFoundError(entity_type="goal", entity_id="goal-abc12345")
```

```python
# ❌ 错误：只接受 message 字符串，丢失领域上下文
from lifeprism.utils.exceptions import NotFoundError

class EntityNotFoundError(NotFoundError):
    pass

# 使用
raise EntityNotFoundError(message="目标 goal-abc12345 未找到")  # code/detail 全靠调用方自觉
```

### 3.4 模块异常文件位置

| 模块 | 文件路径 | 基础异常类 |
|------|---------|-----------|
| LLM | `lifeprism/llm/exceptions.py` | `LLMError(ExternalServiceError)` |
| Repository | `lifeprism/repository/exceptions.py` | `RepositoryError(DataAccessError)` |
| Processors | `lifeprism/processors/exceptions.py` | `ProcessorError(DataAccessError)` |
| Config | `lifeprism/config/exceptions.py` | `ConfigError(LWBaseError)` |

**规则**：每个模块的异常定义在模块自己的 `exceptions.py` 中，不跨模块引用（如 repository 不应引用 llm 的异常类）。

---

## 4. `except Exception` 禁止规则

### 4.1 基本原则

**默认禁止** `except Exception`，除非满足以下**合法场景**之一。

### 4.2 三种禁止模式

```python
# ❌ 模式一：吞掉异常，返回默认值
def get_data(self, id: str):
    try:
        return self._query(id)
    except Exception:
        return None  # ← 数据库挂了也返回 None，调用方以为"不存在"


# ❌ 模式二：只记日志，不重新抛出
def _refresh_cache(self):
    try:
        self._load_data()
    except Exception as e:
        logger.error(f"刷新失败: {e}")
        # ← 吞掉异常，后续代码继续用过期缓存


# ❌ 模式三：捕获所有异常再做判断
def process(self, data):
    try:
        self._validate(data)
        self._save(data)
    except Exception as e:
        if isinstance(e, ValidationError):
            raise
        logger.error(f"处理失败: {e}")
        # ← 如果 _save 抛出的是编程错误（NameError），也被吞掉了
```

### 4.3 合法场景一：API 边界的最外层兜底

仅允许在 **API 边界的最外层**（即全局异常处理器）使用 `except Exception` 作为兜底：

```python
# main.py — API 全局异常处理器
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局兜底 — 捕获所有未被 LWBaseError 处理器捕获的未知异常。"""
    logger.error("未处理的异常: %s (路径: %s)", str(exc), request.url.path, exc_info=True)
    return JSONResponse(status_code=500, content={"error_code": "INTERNAL_ERROR", "message": "服务器内部错误"})
```

### 4.4 合法场景二：辅助操作的兜底（不影响主流程）

**判断标准**：操作失败不应导致主流程中断（日志记录、指标上报、缓存预热等）

```python
# ✅ 正确：日志记录失败不应影响消息处理
try:
    llm_call_logger.log_call(...)
except Exception as log_e:
    logger.warning(f"记录 LLM 调用日志失败: {log_e}")
    # ← 日志失败不影响消息正常发送

# ✅ 正确：指标上报失败不应影响业务
try:
    metrics.record_duration(duration)
except Exception as e:
    logger.warning(f"上报指标失败: {e}")
```

**禁止场景**：主流程操作（数据持久化、API 调用、状态变更）不得使用 `except Exception`

```python
# ❌ 错误：保存用户数据是主流程，不应吞掉异常
try:
    self.user_repository.save(user)
except Exception as e:
    logger.error(f"保存用户失败: {e}")
    # ← 数据没保存，后续逻辑基于错误假设
```

### 4.5 合法场景三：第三方库未知错误（可能影响系统稳定性）

**判断标准**：第三方库可能抛出**未知类型**的异常，且失败会导致系统不可用

**适用范围**：
- 外部服务 API 调用（微信 API、支付接口、推送服务）
- 第三方 SDK（日志上报、监控 SDK）
- 用户自定义扩展插件

**不适用范围**：
- 标准库（`os`、`json`、`sqlite3` 等有明确异常类型）
- 知名框架（FastAPI、SQLAlchemy 等有文档化的异常）

```python
# ✅ 正确：微信 API 可能抛出未知异常，需要兜底
try:
    await wechat_client.send_message(msg)
except Exception as e:
    logger.error(f"微信消息发送失败: {e}", exc_info=True)
    raise ExternalServiceError(
        message="微信消息发送失败",
        details={"error": str(e)},
        cause=e,
    ) from e

# ✅ 正确：发送错误消息失败时，避免无限循环
try:
    await self.send(error_response)
except Exception as send_error:
    logger.error(f"发送错误消息也失败: {send_error}", exc_info=True)
    # ← 不再重试，防止递归错误

# ❌ 错误：os 模块异常类型明确（OSError、IOError），应捕获具体类型
try:
    with open(path, "w") as f:
        f.write(data)
except Exception as e:  # ← 应改为 except OSError
    logger.error(f"写文件失败: {e}")
```

**使用要求**：
1. 必须记录 `exc_info=True`（保留完整异常栈）
2. 必须转换为领域异常后抛出（不得吞掉）
3. 必须在注释中说明为何使用 `except Exception`

### 4.6 推荐的捕获策略

### 4.6 推荐的捕获策略

```python
# ✅ 正确：catch 具体的异常类型 → 转换 → 抛出
import sqlite3

def save_data(self, data: dict):
    try:
        self._execute_insert(data)
    except sqlite3.IntegrityError as e:
        raise ConflictError(
            message=f"数据已存在: {data.get('id')}",
            code="ENTITY_ALREADY_EXISTS",
            details={"id": data.get("id")},
            cause=e,
        ) from e
    except sqlite3.Error as e:
        raise DataAccessError(
            message="数据写入失败",
            details={"error": str(e)},
            cause=e,
        ) from e
```

---

## 5. API 层异常处理器规范

### 5.1 处理器结构

API 层使用 **2 个** 全局异常处理器：

| 处理器 | 捕获类型 | 行为 |
|--------|---------|------|
| `lw_base_error_handler` | `LWBaseError` 及其所有子类 | 调用 `to_http_exception()` 映射到 HTTP 状态码和标准响应体 |
| `global_exception_handler` | `Exception`（兜底） | 记录异常栈，返回 500 |

**关键要求**：
- 所有 `LWBaseError` 子类的响应体必须包含 `error_code`、`message`、`details` 三个字段
- 4xx 异常使用 `logger.warning`，5xx 异常使用 `logger.error` + `exc_info=True`
- 不得在每个路由里单独 try/except 处理业务异常

```python
# ✅ 正确：使用 to_http_exception() 统一映射
from lifeprism.server.errors import to_http_exception

@app.exception_handler(LWBaseError)
async def lw_base_error_handler(request: Request, exc: LWBaseError):
    http_exc = to_http_exception(exc)
    if http_exc.status_code < 500:
        logger.warning("%s: %s (code=%s, path=%s)", type(exc).__name__, exc.message, exc.code, request.url.path)
    else:
        logger.error("%s: %s (code=%s, path=%s)", type(exc).__name__, exc.message, exc.code, request.url.path, exc_info=True)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)
```

### 5.2 响应体格式

```json
// 4xx 响应
{
  "error_code": "HABIT_NOT_FOUND",
  "message": "习惯 habit-abc12345 未找到",
  "details": {"entity_type": "habit", "entity_id": "habit-abc12345"}
}

// 5xx 响应
{
  "error_code": "INTERNAL_ERROR",
  "message": "服务器内部错误",
  "details": {}
}
```

---

## 6. 错误码管理

### 6.1 错误码定义位置

所有错误码统一定义在 `lifeprism/server/errors/error_codes.py`，按模块分组：

```python
# ===== 通用错误码 =====
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
VALIDATION_FAILED = "VALIDATION_FAILED"
INTERNAL_ERROR = "INTERNAL_ERROR"
EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"

# ===== Habit 模块 =====
HABIT_NOT_FOUND = "HABIT_NOT_FOUND"
...

# ===== LLM 模块 =====
LLM_RESPONSE_ERROR = "LLM_RESPONSE_ERROR"
LLM_OUTPUT_PARSE_ERROR = "LLM_OUTPUT_PARSE_ERROR"
PROMPT_NOT_FOUND = "PROMPT_NOT_FOUND"

# ===== Repository 模块 =====
ENTITY_NOT_FOUND = "ENTITY_NOT_FOUND"
ENTITY_ALREADY_EXISTS = "ENTITY_ALREADY_EXISTS"
```

### 6.2 错误码到 HTTP 状态码的映射

在 `api_error_mapping.py` 的 `ERROR_CODE_TO_STATUS` 字典中维护：

```python
ERROR_CODE_TO_STATUS: Dict[str, int] = {
    # 通用
    NOT_FOUND: 404,
    CONFLICT: 409,
    VALIDATION_FAILED: 422,
    INTERNAL_ERROR: 500,
    EXTERNAL_SERVICE_ERROR: 503,
    # 按模块追加...
}
```

### 6.3 fallback 映射规则

当异常实例未设置 `code` 字段时，`_fallback_code()` 根据异常类型决定错误码：

```python
def _fallback_code(error: LWBaseError) -> str:
    if isinstance(error, NotFoundError):
        return NOT_FOUND
    if isinstance(error, ConflictError):
        return CONFLICT
    if isinstance(error, ValidationError):
        return VALIDATION_FAILED
    if isinstance(error, ExternalServiceError):
        return EXTERNAL_SERVICE_ERROR
    if isinstance(error, DataAccessError):
        return INTERNAL_ERROR
    return INTERNAL_ERROR
```

---

## 7. 禁止事项总览

| 禁止项 | 说明 |
|--------|------|
| ❌ `except Exception` 在非合法场景使用 | 仅允许：API 边界兜底、辅助操作兜底、第三方未知错误（详见 4.3~4.5） |
| ❌ 吞掉异常（`except: pass` 或 `return None`） | 异常必须向上传播（辅助操作除外） |
| ❌ 丢失异常链（`raise XxxError(...)` 不用 `from e`） | 必须保留原始异常链以便追溯 |
| ❌ 只传 message 字符串不带上下文 | 必须传 `code` + `details`（至少 `message`） |
| ❌ 不继承 `LWBaseError` 的孤立异常 | 所有领域异常必须纳入 `LWBaseError` 体系 |
| ❌ API 路由内单独 try/except 处理业务异常 | 统一由全局异常处理器处理 |
| ❌ 跨模块引用异常类 | 如 repository 不应引用 `llm.exceptions` |
| ❌ 标准库使用 `except Exception` | 标准库（os、json、sqlite3）异常类型明确，应捕获具体类型 |
