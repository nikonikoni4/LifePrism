# Bug: InboundMessage.content 类型不统一导致图片丢失和上下文爆炸

- **date**: 2026-05-26
- **updated_at**: 2026-07-07
- **status**: fixed
- **scope**: lifeprism/llm, lifeprism/server

## 问题描述

`InboundMessage.content` 字段原本可以是 `str`、`list` 或 `None` 三种类型。在 `context.py` 构建用户消息时，使用 f-string 直接拼接 `msg.content`：

```python
return f"{Context._build_run_context(msg)}## user's message \n {msg.content}"
```

当 `content` 是包含图片信息的 `list`（多模态格式）时：

1. **图片无法识别**：f-string 将 list 转为字符串表示（如 `[{'type': 'image_url', ...}]`），图片 URL 变成纯文本字符串，LLM 无法解析为图片
2. **上下文爆炸**：包含 Base64 编码的图片 list 被字符串化后，token 数量急剧膨胀，导致上下文长度溢出

## 根因分析

类型不统一导致下游处理无法安全地假设 `content` 的类型：

- **events.py** 定义 `content: str | list | None = ''`
- **context.py** 的 `_build_user_message` 返回类型是 `str`，强制将所有 content 转为字符串
- 没有统一的类型校验机制，调用方可以随意传入不同类型

## 解决方案

### 1. 新增 MessageContent 类型（events.py）

创建 `MessageContent` 类继承自 `list`，专门处理多模态内容：

```python
class MessageContent(list):
    """Normalized multimodal message content blocks."""

    def __init__(self, value: MessageContentInput | MessageContent = None):
        super().__init__()
        self.add_tail(value)

    @classmethod
    def _normalize(cls, value) -> list[dict[str, Any]]:
        # 统一转换为 [{type: "text", text: ...}] 格式
        if value is None:
            return []
        if isinstance(value, str):
            return [{"type": "text", "text": value}]
        if isinstance(value, dict):
            cls._validate_block(value)
            return [value]
        if isinstance(value, list):
            for block in value:
                cls._validate_block(block)
            return value
        raise TypeError(f"content 必须是 str、dict、list、MessageContent 或 None")
```

### 2. InboundMessage 自动归一化（events.py）

在 `__post_init__` 中强制转换：

```python
def __post_init__(self):
    self.content = MessageContent(self.content)  # 统一归一化
```

### 3. context.py 返回多模态列表

`_build_user_message` 返回类型从 `str` 改为 `list[dict]`：

```python
@staticmethod
def _build_user_message(msg: InboundMessage) -> list[dict[str, Any]]:
    return [
        {"type": "text", "text": f"{Context._build_run_context(msg)}## user's message"},
        *msg.content,  # MessageContent 已是 list，可直接解包
    ]
```

### 4. llm_provider 增加强制校验（base.py）

新增 `_validate_last_user_content_is_multimodal` 方法，在调用 LLM 前校验：

```python
@staticmethod
def _validate_last_user_content_is_multimodal(messages: list[dict[str, Any]]) -> None:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            if isinstance(msg.get("content"), str):
                raise ValueError("last user message content must be a multimodal list, got str")
            return
```

## 关键教训

1. **类型契约必须明确**：公共接口（如 InboundMessage.content）不应允许多种类型，应尽早归一化
2. **不要用 f-string 拼接复杂对象**：list/dict 被 f-string 转为字符串后会丢失语义，应使用结构化数据传递
3. **防御性校验应在入口处**：MessageContent 在 InboundMessage 构造时就归一化，而不是在每个下游使用点检查

## 补充修复（2026-07-07）

### 问题

修复 `InboundMessage` 写入侧（user 消息统一用 list 存储）后，**读取侧没有同步更新**。`chatbot_service.py::get_history()` 直接从 `session.messages` 取 `msg["content"]` 传给 `ChatMessage`（Pydantic 要求 `content: str`），当 user 消息 content 为 list 时触发 `ValidationError`，导致 `GET /chatbot/sessions/{id}/history` 返回 500。

```
pydantic_core._pydantic_core.ValidationError: 1 validation error for ChatMessage
content
  Input should be a valid string [type=string_type, input_value=[{'type': 'text', 'text':...}], input_type=list]
```

### 修复

在 `ChatbotService` 新增 `_normalize_content()` 静态方法，将 `str | list | None` 统一转为 `str`：

```python
@staticmethod
def _normalize_content(content: str | list | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "".join(text_parts)
    return str(content)
```

### 硬约束

已在 `lifeprism/CLAUDE.md` 新增「消息内容格式」规则：任何从 `session.messages` 读取 content 并对外输出的地方，必须先归一化为字符串。

## 触发规则

在排查以下问题时阅读：
- 图片/多模态消息发送后 LLM 无法识别图片
- 上下文长度异常膨胀或 token 爆炸
- InboundMessage.content 相关的类型错误
- MessageContent 类的使用和扩展
- `GET /chatbot/sessions/{id}/history` 返回 500 / Pydantic ValidationError / content type string_type
- 会话历史消息加载失败
