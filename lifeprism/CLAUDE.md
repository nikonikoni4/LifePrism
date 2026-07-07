# 后端通用规则

错误处理详见 `docs/coding-rules/backend-error-handling.md`

## 类型注解规范

**禁止使用 `Any` 作为返回类型**：

```python
# ❌ 错误：返回类型使用 Any
async def execute(self, **kwargs: Any) -> Any:
    return {"key": "value"}  # 调用方无法知道返回什么类型

# ✅ 正确：明确返回类型
async def execute(self, **kwargs: Any) -> dict[str, str]:
    return {"key": "value"}

# ✅ 正确：多种返回类型使用 Union
async def execute(self, **kwargs: Any) -> dict[str, Any] | str:
    if error:
        return "ERROR: ..."
    return {"data": [...]}
```

**为什么禁止 `Any`**：
1. 丧失类型检查能力，IDE 无法提供自动补全
2. 调用方无法知道返回什么类型，容易出错
3. 违反"明确优于隐式"的 Python 设计原则

**例外情况**：
- 参数类型可以使用 `**kwargs: Any`（kwargs 本身就是动态的）
- 处理真正动态的 JSON 数据时，可以用 `dict[str, Any]`（但应注明具体结构）

## 错误处理

**分层规则**：

| 层级 | 规则 |
|------|------|
| 底层（Provider/Repository） | 抛出领域异常（如 NotFoundError、DataAccessError），不 catch，让错误冒泡 |
| 中间层（Service） | 捕获外部服务错误（LLM/IO/网络/数据库），转换为领域异常后抛出；不做兜底 |
| 顶层（API） | **禁止 try/except**，让异常自然冒泡到全局异常处理器统一映射 |

**⚠️ 技术债警告**：当前 `lifeprism/server/api/*.py` 中存在大量冗余的 try/except 代码（约 74 处），违反了上述规则。**新代码禁止使用这种模式**，现有代码将逐步清理。详见 `docs/technical-debt/api-redundant-exception-handling.md`

**API 层正确做法**：

```python
# ✅ 正确：API 层不需要 try/except，让异常自然冒泡
@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str):
    return goal_service.get_goal(goal_id)  # 直接调用，不捕获
    # NotFoundError → 全局处理器 → HTTP 404
    # DataAccessError → 全局处理器 → HTTP 500

# ❌ 错误：API 层手动捕获并转换（冗余）
@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str):
    try:
        return goal_service.get_goal(goal_id)
    except LWBaseError:  # ← 冗余，全局处理器会处理
        raise
    except Exception as e:  # ← 冗余，全局兜底处理器会处理
        raise HTTPException(status_code=500, detail="...")
```

**外部接口层必须捕获并转换**：

```python
# ✅ 正确：捕获 sqlite3.Error，转换为 DataAccessError
try:
    cursor.execute(sql, (todo_id,))
except sqlite3.Error as e:
    raise DataAccessError(
        message="获取任务失败",
        details={"todo_id": todo_id, "error": str(e)}
    ) from e

# ✅ 正确：捕获 LLM 返回异常，转换为 ExternalServiceError
if result.response is None or not result.response.content:
    raise ExternalServiceError(
        message="心情总结 LLM 返回数据错误",
        details={"result": str(result)}
    )

# ❌ 错误：中间层 catch Exception 并吞掉
def _refresh_cache(self):
    try:
        items, _ = self.goal_repository.get_goals(page=1, page_size=1000)
    except Exception as e:  # 禁止
        logger.error(f"刷新目标缓存失败: {e}")
        # 异常被吞掉，调用方无法感知缓存刷新失败
```

## 日志记录

**触发场景**：数据流处理、生命周期管理、跨边界调用、异常处理（raise 前）

**核心原则**：生产环境 DEBUG 不可见，关键流程必须用 INFO，异常抛出前必须用 ERROR

### INFO：关键流程必须可追踪

**判断标准**：主流程 / 操作失败用户可感知 / 流程出问题必须在日志看到 → INFO

**必须 INFO 的场景**：

```python
logger.info("目标创建: goal_id=%s, name=%s", goal_id, name)
logger.info("LLM 定时任务启动/完成: task=%s, date=%s", task_name, date)
logger.info("Session 创建/销毁: session_id=%s, ...", session_id)
logger.info("跨边界调用: LLM 提供商=%s, 模型=%s, ...", provider, model)
logger.info("Repository 写操作: 创建/更新/删除, entity=%s, id=%s", entity_type, entity_id)
```

### ERROR：异常抛出前必须记录完整上下文

**规则**：在错误首次发现点必须有 ERROR 日志，包含：操作标识 + 失败原因 + 当前状态

**判断流程**：

```
异常即将 raise
    ↓
问：这是错误的首次发现点吗？
    ├─ 是 → 问：调用方能从异常消息获得足够调试信息吗？
    │         ├─ 否 → ✅ 必须记录 ERROR + 完整上下文
    │         └─ 是 → ❌ 不需要（简单参数错误、业务规则）
    └─ 否 → ❌ 不需要（底层已记录，避免重复）
              ⚠️ 建议：加注释说明底层已记录
```

**示例**：

```python
# ✅ 正确：首次发现点，记录完整上下文
def delete_todo(self, todo_id: str) -> bool:
    existing = self.get_todo_by_id(todo_id)
    if not existing:
        logger.error(
            "删除任务失败: todo_id=%s, 任务不存在, 当前任务总数=%d",
            todo_id,
            self._count_todos(),  # ← 关键：当前状态
        )
        raise NotFoundError(
            message=f"任务 {todo_id} 不存在",
            code="TODO_NOT_FOUND",
            details={"todo_id": todo_id}
        )

# ✅ 正确：Provider 层首次发现点，转换外部错误
def query_todos(self, options: QueryOptions) -> tuple:
    try:
        cursor.execute(sql, params)
    except sqlite3.Error as e:
        logger.error(
            "查询任务失败: date=%s, filters=%s, error=%s",
            options.date_range, options.filters, e
        )
        raise DataAccessError(
            message="查询任务失败",
            details={"options": str(options), "error": str(e)}
        ) from e

# ✅ 正确：中间层转发，不重复记录
async def dreaming_task(self, date: str):
    try:
        mood_summary = await self._summarize_moods(date)  # ← 底层已记录
        ...
    except ExternalServiceError:
        # 直接向上传递，_summarize_moods() 已在首次发现点记录了 ERROR
        raise

# ✅ 正确：简单参数校验，异常消息已足够
def create_goal(self, name: str, category_id: str):
    if not name or not name.strip():
        raise ValidationError("目标名称不能为空")  # 不需要 log

# ❌ 错误：首次发现点但缺少上下文
logger.debug("任务不存在")  # 级别错误
raise NotFoundError(message=f"任务 {todo_id} 不存在")

# ❌ 错误：中间层重复记录
async def dreaming_task(self, date: str):
    try:
        mood_summary = await self._summarize_moods(date)
        ...
    except ExternalServiceError as e:
        logger.error("定时任务失败: %s", str(e))  # ← 重复记录，污染日志
        raise
```

**记录内容要求**：
- 操作标识：entity_id、session_id、task_name 等唯一标识
- 失败原因：具体是什么错误
- 当前状态：已有数据量、配置值、缓存大小等调试关键信息

### WARN vs DEBUG

- **WARN**：批量操作部分失败、降级方案、可疑状态但不影响当前操作
- **DEBUG**：幂等性检查、辅助函数、详细参数、内部状态

## 消息内容格式

**硬约束：Session 消息 content 是 `str | list | None`，读取时必须归一化**

`Session.add_message()` 接受 `content: str | list | None`，存到 JSONL 的消息 content 可能是三种格式之一：

- `str`: 纯文本（如 assistant 回复）
- `list[dict]`: 多模态结构（如 user 消息，`[{"type":"text","text":"..."}]`）
- `None`: 空内容

**规则**：任何从 `session.messages` 读取 content 并传给 Pydantic 模型或前端的地方，**必须先归一化为字符串**。

```python
# ❌ 错误：直接传 msg["content"]，list 类型会触发 Pydantic ValidationError
ChatMessage(role=msg["role"], content=msg["content"], ...)

# ✅ 正确：先归一化再传
ChatMessage(role=msg["role"], content=_normalize_content(msg.get("content")), ...)

def _normalize_content(content: str | list | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    return str(content)
```

**为什么 user 消息是 list**：`InboundMessage.__post_init__` 将 content 统一归一化为 `MessageContent`（list 子类），`context.py::_build_user_message()` 构建多模态列表返回。历史 bug 见 `docs/history-bugs/2026-05-26-message-content-type-mismatch.md`。

**必须检查的位置**：任何读取 `session.messages[n]["content"]` 并对外输出的地方（API、UI、日志预览等）。

## 禁止事项

- ❌ 关键流程（数据持久化、LLM 调用、状态变化、跨边界）使用 DEBUG
- ❌ 异常抛出前使用 DEBUG 或不记录日志
- ❌ ERROR 日志缺少上下文（只有错误消息）
- ❌ 循环内使用 INFO（应该汇总后记录）
- ❌ 辅助函数使用 INFO（应该用 DEBUG）
- ❌ `except Exception` 吞掉异常（除非满足合法场景：API 边界兜底 / 辅助操作兜底 / 第三方未知错误）
- ❌ 不捕获外部错误，让原始异常直接冒泡

## `except Exception` 合法场景

**默认禁止**，仅在以下场景合法：

1. **API 边界兜底**：全局异常处理器
2. **辅助操作兜底**：日志记录、指标上报等失败不应影响主流程
3. **第三方未知错误**：外部服务 API（微信、支付等）可能抛出未知异常且影响系统稳定性

详细规则见 `docs/coding-rules/backend-error-handling.md#4-except-exception-禁止规则`
