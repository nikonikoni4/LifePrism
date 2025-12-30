# ChatBot 流程图

## 概述

ChatBot 使用 LangGraph 构建对话流程，支持意图识别、功能介绍、工具调用等功能。

## 整体流程 V2(实现工具调用)

```
START
  │
  ▼
┌─────────────────┐
│  intent_router  │ ◀── 意图识别
└────────┬────────┘
         │
         ├──────────────────────────────────────┐
         │                                      │
         ▼                                      ▼
┌──────────────────┐                   ┌─────────────┐
│ feat_intro_router│                   │  norm_chat  │ ◀── 绑定工具
└────────┬─────────┘                   └──────┬──────┘
         │                                    │
         ▼                                    │
┌──────────────────┐                    验证 tool_calls
│feature_introduce │                          │
└────────┬─────────┘                          │
         │                       ┌────────────┴────────────┐
         ▼                       │                         │
        END              工具存在且有调用             工具不存在
                                 │                         │
                                 ▼                         ▼
                         ┌─────────────┐         抛出 LLMParseError
                         │  tool_node  │              (重试2次)
                         └──────┬──────┘                  │
                                │                         ▼
                                ▼                   重试失败 → 异常
                     ┌──────────────────────┐             │
                     │ tool_result_handler  │             ▼
                     └──────────┬───────────┘      chat入口捕获
                                │                         │
                                ▼                         ▼
                               END                  返回错误信息
                                              
         无 tool_calls ──────────────────────▶ END
```

## 节点说明

| 节点 | 功能 | 状态描述 |
|------|------|----------|
| `intent_router` | 意图识别 | "正在识别意图..." |
| `feat_intro_router` | 功能介绍路由 | "正在检索相关文档..." |
| `feature_introduce` | 功能介绍生成 | "正在生成回答..." |
| `norm_chat` | 普通对话（绑定工具） | "正在生成回答..." |
| `tool_node` | 执行工具调用 | "正在查询数据..." |
| `tool_result_handler` | 整合工具结果生成回答 | "正在整合数据生成回答..." |

## 条件路由

### 1. `route_by_intent` (intent_router → ?)

```python
if intent == "lifeprism软件使用和讲解":
    return "feat_intro_router"
else:
    return "norm_chat"
```

### 2. `route_after_norm_chat` (norm_chat → ?)

```python
if last_message.tool_calls:
    return "tool_node"
else:
    return END
```

## 工具验证

在 `norm_chat` 节点中验证工具调用：

```python
VALID_TOOLS = {"get_user_behavior_stats"}

if tool_name not in VALID_TOOLS:
    raise LLMParseError(f"未知工具: {tool_name}")
```

- 未知工具会触发 `LLMParseError`
- `RetryPolicy(max_attempts=2)` 会重试最多 2 次
- 重试失败后异常被 chat 入口捕获，返回友好错误信息

## State Schema

```python
class ChatBotSchemas(BaseModel):
    messages: Annotated[list[HumanMessage | AIMessage | ToolMessage], operator.add]
    intent: Annotated[list[str], operator.add]
    guide_content: Annotated[list[str], operator.add]
    current_human_message: Optional[str] = None  # 当前用户问题
    tools_result: Annotated[list[str], operator.add] = None  # 工具调用结果
```

## 可用工具

| 工具名 | 功能 |
|--------|------|
| `get_user_behavior_stats` | 获取用户行为统计数据 |

## 相关文件

- [`chat_bot_graph.py`](lifewatch/llm/llm_classify/chat/chat_bot_graph.py) - ChatBot 主类
- [`chatbot_schemas.py`](lifewatch/llm/llm_classify/schemas/chatbot_schemas.py) - State Schema
- [`database_tools.py`](lifewatch/llm/llm_classify/tools/database_tools.py) - 工具定义
- [`common_prompt.py`](lifewatch/llm/custom_prompt/common_prompt.py) - Prompt 模板
