# 微信 Channel 设计文档

## 概述

在 lifeprism 中实现微信 channel，参考 nanoboat 的微信实现，通过 ilinkai.weixin.qq.com API 实现与微信的消息互通。

## 目标

1. 支持 QR 码扫描登录
2. 接收微信消息（文本、图片、文件、语音）
3. 发送微信消息（文本、图片、文件）
4. 通过 MessageQueue (bus) 与 agent 通信
5. 模块化设计，便于后续优化

## 非目标

- 暂不接入 agent loop（只实现消息互通）
- 暂不实现语音转文字（只下载语音文件）

## 架构设计

### 目录结构

```
lifeprism/llm/channel/wechat/
├── __init__.py          # 导出 WechatChannel
├── config.py            # 配置类定义
├── client.py            # HTTP 客户端和 API 调用
├── auth.py              # QR 码登录认证
├── message.py           # 消息接收和发送逻辑
├── media.py             # 媒体文件处理
└── channel.py           # WechatChannel 主类
```

### 核心流程

#### 1. 启动流程
```
WechatChannel.start()
  → 加载状态（token、context_tokens）
  → 如无 token，执行 QR 登录
  → 启动长轮询任务
```

#### 2. 消息接收流程
```
长轮询获取消息
  → 解析消息类型（文本/图片/语音/文件）
  → 下载媒体文件（如有）
  → 调用 _handle_message()
  → 构造 InboundMessage
  → bus.publish_inbound()
```

#### 3. 消息发送流程
```
Agent 处理完成
  → bus.publish_outbound()
  → WechatChannel.send()
  → 发送文本/媒体到微信
```

## 模块设计

### 1. BaseChannel 基类

定义所有 channel 的通用接口：

```python
class BaseChannel:
    name: str = "base"
    
    def __init__(self, config: Any, bus: MessageQueue)
    async def start() -> None
    async def stop() -> None
    async def send(msg: OutboundMessage) -> None
    async def _handle_message(sender_id, chat_id, content, media, metadata) -> None
```

### 2. WechatConfig (config.py)

配置项：
- `enabled`: 是否启用
- `base_url`: API 地址
- `cdn_base_url`: CDN 地址
- `state_dir`: 状态保存目录
- `poll_timeout`: 长轮询超时时间
- `allow_from`: 允许的用户 ID 列表

### 3. WechatClient (client.py)

HTTP 客户端封装：
- 构建请求头（随机 UIN、Authorization）
- `_api_get()`: GET 请求
- `_api_post()`: POST 请求
- 错误处理和重试

### 4. WechatAuth (auth.py)

认证模块：
- `login()`: QR 码登录流程
- `_fetch_qr_code()`: 获取 QR 码
- `_print_qr_code()`: 打印 QR 码到终端
- `_poll_qr_status()`: 轮询 QR 码状态
- `_load_state()`: 加载保存的 token
- `_save_state()`: 保存 token

### 5. WechatMedia (media.py)

媒体处理：
- `download_media()`: 下载媒体文件（图片、语音、文件、视频）
- `upload_media()`: 上传媒体文件
- `_decrypt_aes()`: AES 解密
- 支持的媒体类型：
  - 图片：jpg, png, gif 等
  - 语音：mp3, wav, amr, silk 等
  - 文件：任意类型
  - 视频：mp4, avi 等

### 6. WechatMessage (message.py)

消息处理：
- `parse_message()`: 解析接收到的消息
- `build_text_message()`: 构造文本消息
- `build_media_message()`: 构造媒体消息
- `handle_typing()`: 处理 typing 状态

### 7. WechatChannel (channel.py)

主类，整合所有模块：
- 继承 `BaseChannel`
- 使用 `WechatClient` 进行 API 调用
- 使用 `WechatAuth` 进行认证
- 使用 `WechatMedia` 处理媒体
- 使用 `WechatMessage` 处理消息
- 实现长轮询循环
- 与 MessageQueue (bus) 通信

## 数据流

### InboundMessage（微信 → Agent）

```python
InboundMessage(
    type="chat",  # 消息类型
    content="消息内容",  # 文本内容
    session_id="wechat:user_id",  # 会话 ID
    extra={
        "media": ["path/to/image.jpg"],  # 媒体文件路径
        "sender_id": "user_id",  # 发送者 ID
        "chat_id": "user_id"  # 聊天 ID
    }
)
```

### OutboundMessage（Agent → 微信）

```python
OutboundMessage(
    id="msg_id",  # 消息 ID
    response=LLMResponse(content="回复内容"),  # 回复内容
    session_id="wechat:user_id"  # 会话 ID
)
```

## 协议细节

### API 端点

- `GET /ilink/bot/get_bot_qrcode`: 获取 QR 码
- `GET /ilink/bot/get_qrcode_status`: 查询 QR 码状态
- `POST /ilink/bot/getupdates`: 长轮询获取消息
- `POST /ilink/bot/sendmessage`: 发送消息
- `POST /ilink/bot/getuploadurl`: 获取上传 URL
- `POST /ilink/bot/getconfig`: 获取 typing ticket

### 消息类型

- `ITEM_TEXT = 1`: 文本
- `ITEM_IMAGE = 2`: 图片
- `ITEM_VOICE = 3`: 语音
- `ITEM_FILE = 4`: 文件
- `ITEM_VIDEO = 5`: 视频

### 认证

- 请求头包含：
  - `X-WECHAT-UIN`: 随机生成的 UIN
  - `Authorization`: Bearer token
  - `iLink-App-Id`: "bot"
  - `iLink-App-ClientVersion`: 版本号

## 状态管理

保存到 `state_dir/account.json`：
- `token`: 认证 token
- `get_updates_buf`: 长轮询缓冲
- `context_tokens`: 用户上下文 token（用于回复）
- `typing_tickets`: typing ticket 缓存
- `base_url`: API 地址

## 错误处理

- Session 过期：重新 QR 登录
- 网络错误：重试（最多 3 次）
- 媒体下载失败：降级为文本提示
- 长轮询超时：正常，继续下一次轮询

## 安全考虑

- `allow_from` 白名单控制访问
- 空列表拒绝所有访问
- `"*"` 允许所有用户
- 媒体文件保存到独立目录
- Token 保存到本地文件

## 测试计划

1. QR 码登录测试
2. 接收文本消息测试
3. 接收图片消息测试
4. 接收语音消息测试
5. 发送文本消息测试
6. 发送图片消息测试
7. 长轮询稳定性测试
8. 错误恢复测试

## 实现优先级

1. 基础框架（BaseChannel、WechatConfig、WechatClient）
2. 认证模块（QR 登录）
3. 消息接收（文本、图片）
4. 消息发送（文本、图片）
5. 媒体处理（语音、文件、视频）
6. 错误处理和重试
7. 状态持久化

## 参考

- nanobot 微信 channel 实现：`D:/desktop/软件开发/nanobot/nanobot/channels/weixin.py`
- lifeprism MessageQueue：`lifeprism/llm/bus/queue.py`
- lifeprism 事件定义：`lifeprism/llm/bus/events.py`
