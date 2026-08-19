---
version: 1.0
created_at: 2026-05-01
updated_at: 2026-05-01
last_updated: 创建 WeChat Channel 与 LifePrism 对接规格文档
abstract: >
  WeChat Channel 与 LifePrism 对接规格文档。定义 WeChat 模块暴露给 LifePrism 的接口、
  配置数据流、以及与消息总线（MessageQueue）的集成方式。WeChat 内部协议实现细节不在本文档范围内。
id: wechat-channel-integration-spec
title: WeChat Channel 与 LifePrism 对接规格
status: draft
module: lifeprism/llm/channel
sourc_spec:
related_plan:
code_scope:
  - lifeprism/llm/channel/__init__.py
  - lifeprism/llm/channel/wechat/channel.py
  - lifeprism/llm/channel/wechat/config.py
  - lifeprism/llm/channel/wechat/message.py
  - lifeprism/llm/bus/queue.py
  - lifeprism/llm/bus/events.py
  - lifeprism/server/main.py
contract_refs:
  - lifeprism/llm/channel/wechat/config.py
  - lifeprism/llm/bus/events.py
---

# WeChat Channel 与 LifePrism 对接规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 WeChat Channel 与 LifePrism 对接规格初稿 |

## Overview

WeChat Channel 是 LifePrism 的外部消息接入模块，通过微信平台实现用户与系统的交互。Channel 模块遵循统一接口设计，消息通过 MessageQueue 总线与 AgentLoop 交互，形成完整的消息处理链路。

核心价值：
1. 提供微信平台的消息接入能力，用户可通过微信与应用交互
2. 统一的消息处理架构，微信消息与其他渠道共享处理逻辑
3. 支持长轮询模式接收消息，主动推送模式发送消息

## Scope

**在范围内：**

- WeChat Channel 与 LifePrism 的接口定义
- WeChat 配置数据流（配置读取 → WechatConfig → Channel 初始化）
- 消息总线集成（InboundMessage / OutboundMessage 契约）
- Channel 生命周期管理（启动/停止）
- 消息发送流程（session_id 规范、消息构建）
- `allow_from` 白名单机制

**不在范围内：**

- WeChat 内部协议实现（HTTP API 调用、Token 管理、媒体处理）
- 二维码登录流程
- 消息编解码细节
- AgentLoop 内部处理逻辑

## Core Behavior

### 1. 整体架构

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────┐
│   微信用户   │ ←──→ │  WechatChannel   │ ←──→ │MessageQueue│
└─────────────┘      └──────────────────┘      └──────┬──────┘
                              ↑                         │
                              │                         ▼
                       WechatConfig              ┌─────────────┐
                       (配置注入)                │  AgentLoop  │
                                                  └─────────────┘
```

### 2. Channel 模块层级

| 模块 | 职责 |
| ---- | ---- |
| `wechat_channel` | WechatChannel 单例，全局唯一实例 |
| `WechatChannel` | Channel 实现类，负责消息收发和轮询 |
| `WechatConfig` | 微信配置数据类 |
| `WechatClient` | HTTP API 客户端（内部实现） |
| `WechatAuth` | 认证模块（内部实现） |
| `WechatMessage` | 消息解析和构建（内部实现） |


### 4. Channel 生命周期

#### 启动流程

1. 初始化时的启动
```
1. 应用启动 (lifespan)
   ↓
2. 导入 wechat_channel 单例
   ↓
3. 调用 wechat_channel.start()
   ↓
4. WechatChannel.start():
   - 初始化 WechatClient
   - 加载或创建认证状态
   - 初始化 WechatMedia
   - 启动消息轮询任务 (_poll_loop)
```

**启动条件：**
- Token 存在（有效性由 _poll_loop 首次调用 getupdates 暴露并自动 5s 重试，2026-08-19 移除启动时 token 预测试段以避免 lifespan 阻塞，详见 [ADR 2026-08-19-startup-optimization-phased-strategy](../adr/2026-08-19-startup-optimization-phased-strategy.md)）
- `enabled = True`（隐含于 Token 检查）

2. 注册成功之后的启动

这里是为了绑定之后立即启动/重新启动 Channel。

```
1. 前端设置界面配置QR码
   ↓
2. 前端轮询QR码状态
   ↓
3. 状态为'confirm'
   ↓
4. WechatChannel.start():
```

#### 停止流程

```
1. 应用关闭 (lifespan)
   ↓
2. 检查 wechat_channel._running
   ↓
3. 调用 wechat_channel.stop()
   ↓
4. WechatChannel.stop():
   - 设置 _running = False
   - 取消轮询任务
   - 关闭 HTTP 客户端
```

### 5. 消息接收流程（长轮询）

```
微信服务器
    ↓ (长轮询 getupdates)
WechatClient.api_post()
    ↓ (解析消息)
WechatMessage.parse_message()
    ↓ (权限检查)
WechatChannel.is_allowed()
    ↓ (发布到总线)
MessageQueue.send(InboundMessage)
    ↓ (AgentLoop 处理)
等待回复
```

**接收的 InboundMessage 格式：**

| 字段 | 值 |
| ---- | --- |
| `type` | `"chat"` |
| `channel` | `"wechat"` |
| `content` | 消息文本内容 |
| `session_id` | `"wechat:{from_user_id}"` |
| `extra` | `None` |

### 6. 消息发送流程

```
1. AgentLoop 处理消息
   ↓ 
2. 返回给 MessageQueue.send
   ↓ 
3. session_id更新（来自OutboundMessage.session_id）
   ↓
4. 状态持久化（结构为 {"token":token,"wechat_user_id": {"last_session_id": session_id,"context_token": context_token}}）
```

### 7. session_id

1. WechatChannel.session_id 被初始化为None，默认首次信息是一个新的会话（系统启动以来）
2. 后续对话：WechatChannel.session_id = outbound_msg.session_id，内部会自动处理会话保持
3. 每次处理消息都会保存当前会话的last_session_id和context_token，用于后续继续对话


### 7. WeChat 内部实现简述

**长轮询机制：**
- 客户端持续调用 `getupdates` API
- 服务器保持连接直至有新消息或超时
- 返回 `get_updates_buf` 用于下次请求的断点续传
- 网络错误时等待 5 秒后重试

**消息类型支持：**
- 文本消息（ITEM_TEXT）
- 图片消息（ITEM_IMAGE）
- 语音消息（ITEM_VOICE）
- 文件消息（ITEM_FILE）
- 视频消息（ITEM_VIDEO）

**当前实现仅处理文本消息**，媒体消息暂不处理。

## Technical Contract

### 1. Channel 基础接口

WeChat Channel 继承 `BaseChannel`，实现以下接口：

```python
class BaseChannel(ABC):
    name: str                          # Channel 名称标识
    config: ChannelConfig              # 配置对象
    bus: MessageQueue                 # 消息总线

    async def start(self) -> None:    # 启动 Channel
    async def stop(self) -> None:     # 停止 Channel
    async def send(self, msg: OutboundMessage) -> None:  # 发送消息
    def is_allowed(self, sender_id: str) -> bool:  # 权限检查
```

### 2. 消息总线契约

**InboundMessage（接收消息）：**

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `type` | str | 消息类型，目前为 `"chat"` |
| `channel` | str | 渠道标识 `"wechat"` |
| `content` | str | 消息内容 |
| `session_id` | str | 会话 ID，格式 `"wechat:{wxid}"` |
| `extra` | dict | 扩展信息，可选 |

**OutboundMessage（发送消息）：**

| 字段 | 类型 | 说明 |
| ---- | ---- | ---- |
| `id` | str | 消息 ID |
| `response` | LLMResponse | LLM 响应对象 |
| `session_id` | str | 会话 ID，格式 `"wechat:{wxid}"` |

### 3. WeChat 配置契约

```python
@dataclass
class WechatConfig:
    enabled: bool = False
    base_url: str = "https://ilinkai.weixin.qq.com"
    cdn_base_url: str = "https://novac2c.cdn.weixin.qq.com/c2c"
    poll_timeout: int = 35
    allow_from: list[str] = field(default_factory=list)
```

### 4. 应用层 API 契约

WeChat Channel 通过 `setting_api.py` 提供以下 REST API：

**获取 QR 码：**

```
GET /api/settings/qrcode?channel=wechat
```

响应示例：
```json
{
    "qrcode_id": "uuid-xxx",
    "qrcode_data": "data:image/png;base64,..."
}
```

**查询 QR 码扫描状态：**

```
GET /api/settings/qrcode/status?channel=wechat&qrcode_id=uuid-xxx
```

响应示例：
```json
{
    "status": "scanned",
    "message": "已扫码，请确认登录"
}
```

状态值：`pending` | `scanned` | `confirmed` | `expired`

### 5. 状态存储契约

WeChat Channel 的认证状态存储在 `channel_path / "wechat" / "account.json"`：

说明： token 默认优先存放在keyring中，keyring失效之后才fallback到account.json中
```json
{
    "token": "...", 
    "context_tokens": {
        "wxid1": "context_token1",
        "wxid2": "context_token2"
    }
}
```

- `token`：API 认证令牌
- `context_tokens`：用户级上下文令牌映射，用于多轮对话


## Acceptance Notes

1. **Channel 启动成功**
   - Token 存在时成功启动轮询
   - Token 不存在时优雅放弃启动

2. **消息接收**
   - 微信消息正确转换为 `InboundMessage`
   - 消息内容正确提取

3. **消息发送**
   - 响应正确发送到对应用户
   - 消息内容正确提取

4. **权限控制**
   - 非白名单用户消息被拒绝

5. **生命周期**
   - 正常停止时清理所有资源
   - 重启时正确恢复状态

## Out of Spec

以下内容不在本规格范围内：

1. **WeChat 内部协议实现**
   - HTTP API 调用细节
   - Token 管理策略
   - 媒体文件处理
   - 二维码登录流程

2. **AgentLoop 内部逻辑**
   - LLM 调用细节
   - Skill 加载机制
   - Prompt 构建规则

3. **前端微信绑定界面**
   - 微信登录/登出界面
   - 白名单配置界面

4. **媒体消息处理**
   - 图片、语音、视频消息的接收和发送
   - 文件消息处理
