
本文档说明 `lifeprism/llm/channel/wechat/channel.py` 中 session 的构造、使用，以及发送微信消息所需内容。

## 1. 接收：微信消息原始结构

微信服务器通过 `ilink/bot/getupdates` API 返回消息，原始数据结构如下：

```python
msg = {
    "from_user_id": "微信用户的唯一标识",  # 发送消息的用户ID
    "context_token": "上下文令牌",         # 微信提供的会话上下文token
    "item_list": [                          # 消息内容列表
        {
            "type": 1,                      # 文本类型
            "text_item": {"text": "消息内容"}
        },
        {
            "type": 2,                      # 图片类型
            "image_item": {...}
        }
    ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `from_user_id` | str | 发送消息的微信用户唯一ID |
| `context_token` | str | 微信提供的上下文令牌，用于回复时保持会话连续性 |
| `item_list` | list | 消息内容项，支持文本、图片、语音等 |

---

## 2. 改造：接收后的字段转换

### 2.1 `WechatMessage.parse_message()` 解析

`WechatMessage.parse_message(msg)` 将原始微信消息解析为：

```python
parsed = {
    "from_user_id": "微信用户ID",
    "content": "消息文本内容",
    "media": [
        {"type": "image", "info": {...}},
        {"type": "voice", "info": {...}}
    ],
    "context_token": "上下文令牌"
}
```

| 原始字段 | 解析后字段 | 变化说明 |
|----------|-----------|---------|
| `from_user_id` | `parsed["from_user_id"]` | 保持不变 |
| `item_list` 中 `text_item.text` | `parsed["content"]` | 提取文本内容 |
| `item_list` 中媒体项 | `parsed["media"]` | 提取媒体列表 |
| `context_token` | `parsed["context_token"]` | 保持不变 |

### 2.2 `InboundMessage` 构造

```python
inbound_msg = InboundMessage(
    type="chat",
    content=parsed["content"],
    session_id=f"wechat:{from_user_id}",   # 构造带前缀的session_id
    extra={
        "media": media_paths,              # 下载后的本地媒体路径
        "sender_id": from_user_id,         # 原始发送者ID
        "chat_id": from_user_id             # 用于标识对话
    }
)
```

**关键改造：`session_id = f"wechat:{from_user_id}"`**

这是 LifePrism 内部使用的会话标识符格式：
- 前缀 `wechat:` 用于区分不同的 Channel（渠道）
- 后跟 `from_user_id` 是微信用户ID

```python
# 示例
from_user_id = "用户123"
session_id = "wechat:用户123"
```

### 2.3 `_context_tokens` 存储

接收消息后，`context_token` 被存储到实例变量中：

```python
# 存储
self._context_tokens[from_user_id] = context_token
```

`_context_tokens` 是一个字典，key 是微信用户ID，value 是该用户的 context_token。

```python
# 示例
_context_tokens = {
    "用户123": "token_abc",
    "用户456": "token_def"
}
```

---

## 3. 发送：发送时的字段使用

当 AgentLoop 处理完消息，需要通过 `WechatChannel.send()` 发送回复时：

### 3.1 从 OutboundMessage 提取

```python
session_id = msg.session_id  # 例如: "wechat:用户123"
content = msg.response.content  # LLM 回复内容
```

### 3.2 提取用户ID

```python
to_user_id = session_id.replace("wechat:", "")  # "用户123"
```

**注意**：`to_user_id` 和接收时的 `from_user_id` 是相同的值。

### 3.3 获取 context_token

```python
context_token = self._context_tokens.get(to_user_id, "")
```

从 `_context_tokens` 字典中获取该用户之前存储的 context_token。

### 3.4 构造并发送

```python
message_body = WechatMessage.build_text_message(
    to_user_id,      # 发送目标用户ID
    content,        # LLM 回复内容
    context_token   # 上下文令牌
)
await self.client.api_post("ilink/bot/sendmessage", message_body)
```

`WechatMessage.build_text_message()` 构造的最终消息结构：

```python
{
    "msg": {
        "from_user_id": "",           # 发送者留空，由微信服务端填充
        "to_user_id": "用户123",       # 接收者ID（对应接收时的 from_user_id）
        "client_id": "lifeprism-xxx",
        "message_type": 1,
        "message_state": 2,
        "context_token": "token_abc", # 上下文令牌
        "item_list": [
            {"type": 1, "text_item": {"text": "LLM回复内容"}}
        ]
    }
}
```

---

## 4. 字段对照表

### 接收 → 发送字段映射

| 接收阶段 | 字段名 | 发送阶段 | 字段名 | 说明 |
|---------|--------|---------|--------|------|
| 微信原始 | `from_user_id` | 发送目标 | `to_user_id` | 同一个微信用户ID |
| 微信原始 | `context_token` | 发送携带 | `context_token` | 保持会话上下文 |
| 微信原始 | `item_list[].text_item.text` | 发送内容 | `item_list[].text_item.text` | 用户消息 ↔ 回复内容 |

### Session ID 格式

| 场景 | 格式 | 示例 |
|------|------|------|
| 接收时 | `wechat:{from_user_id}` | `wechat:用户123` |
| 发送时提取 | `session_id.replace("wechat:", "")` | `用户123` |

---

## 5. `_context_tokens` 详细说明

### 用途
`context_token` 是微信提供的会话上下文令牌，用于在多轮对话中保持会话连续性。每次回复时需要在请求中携带该 token。

### 生命周期

```
接收消息 → 保存 token
    ↓
_in_context_tokens[from_user_id] = context_token
    ↓
发送消息时取出 → 使用后仍保留（微信会更新）
```

### 持久化
`_context_tokens` 在 `start()` 时从 `account.json` 加载：
```python
state = self.auth.load_state()
self._context_tokens = state.get("context_tokens", {})
```

并在认证状态变更时自动保存回文件。

---

## 6. 完整数据流

```
┌─────────────────────────────────────────────────────────────────┐
│                          微信服务器                               │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    get_updates 返回消息
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  原始 msg:                                                     │
│    from_user_id: "用户123"                                      │
│    context_token: "token_abc"                                   │
│    item_list: [{"type":1, "text_item":{"text":"你好"}}]         │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    WechatMessage.parse_message()
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  parsed:                                                       │
│    from_user_id: "用户123"                                      │
│    content: "你好"                                             │
│    context_token: "token_abc"                                   │
│    media: []                                                   │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    存储 + 构造 InboundMessage
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  存储: _context_tokens["用户123"] = "token_abc"                  │
│                                                                │
│  InboundMessage:                                               │
│    session_id: "wechat:用户123"                                 │
│    content: "你好"                                             │
│    extra.sender_id: "用户123"                                  │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                         Bus → AgentLoop
                                ↓
                        LLM 处理 + 回复
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  OutboundMessage:                                              │
│    session_id: "wechat:用户123"                                 │
│    response.content: "你好！有什么可以帮你？"                    │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    WechatChannel.send()
                                ↓
                    提取 + 查找 token
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  to_user_id: "用户123"                                          │
│  context_token: "_context_tokens["用户123"]" = "token_abc"      │
│  content: "你好！有什么可以帮你？"                               │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                    build_text_message()
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  API 请求 body:                                                 │
│    msg: {                                                      │
│      to_user_id: "用户123",                                      │
│      context_token: "token_abc",                                 │
│      item_list: [{"type":1, "text_item":{"text":"你好！..."}}]  │
│    }                                                           │
└─────────────────────────────────────────────────────────────────┘
                                ↓
                         发送成功
```