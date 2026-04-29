---
version: 1.0
created_at: 2026-04-29
updated_at: 2026-04-29
last_updated: 创建微信 channel 设计文档
abstract: 在 lifeprism 中实现微信 channel，通过 ilinkai.weixin.qq.com API 实现与微信的消息互通，支持文本、图片、语音、文件的收发
id: wechat-channel
title: 微信 Channel 实现
status: draft
module: lifeprism.llm.channel.wechat
sourc_spec: docs/superpowers/specs/2026-04-29-wechat-channel-design.md
related_plan: 待创建
code_scope: lifeprism/llm/channel/wechat/, lifeprism/llm/channel/base.py
contract_refs: lifeprism/llm/bus/events.py
---

# 微信 Channel 实现

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建设计文档初稿 |

## Overview

在 lifeprism 中实现微信 channel，参考 nanoboat 的微信实现，通过 ilinkai.weixin.qq.com API 实现与微信平台的消息互通。

核心功能：
1. QR 码扫描登录认证
2. 接收微信消息（文本、图片、文件、语音）
3. 发送微信消息（文本、图片、文件）
4. 通过 MessageQueue (bus) 与 agent 通信
5. 模块化设计，便于后续优化

## Scope

**包含：**
- 微信平台接入（基于 ilinkai.weixin.qq.com API）
- QR 码登录流程
- 长轮询消息接收
- 文本、图片、语音、文件的接收和发送
- 媒体文件下载和上传
- 与 MessageQueue (bus) 的集成
- BaseChannel 基类定义

**不包含：**
- 语音转文字功能（后续添加）
- 消息加密传输（依赖微信 API）
- 群聊功能（当前只支持单聊）
- 消息撤回、编辑等高级功能

## Core Behavior

### 模块结构

系统按功能拆分为 7 个模块：

1. **BaseChannel** - 定义所有 channel 的通用接口
2. **WechatConfig** - 配置定义
3. **WechatClient** - HTTP 客户端和 API 调用封装
4. **WechatAuth** - QR 码登录认证
5. **WechatMedia** - 媒体文件下载、上传、解密
6. **WechatMessage** - 消息解析和构造
7. **WechatChannel** - 主类，整合所有模块

### 核心流程

#### 启动流程
1. 加载本地保存的状态（token、context_tokens）
2. 如果没有有效 token，执行 QR 码登录
3. 启动长轮询任务，持续接收消息

#### 消息接收流程
1. 通过长轮询 API 获取新消息
2. 解析消息类型（文本/图片/语音/文件）
3. 如果包含媒体，下载到本地并解密
4. 构造 InboundMessage 对象
5. 通过 bus.publish_inbound() 发送给 agent

#### 消息发送流程
1. Agent 处理完成后，通过 bus.publish_outbound() 发送 OutboundMessage
2. WechatChannel 接收 OutboundMessage
3. 根据内容类型发送文本或媒体消息到微信
4. 处理发送失败的降级逻辑

### 认证机制

使用 QR 码扫描登录：
1. 请求获取 QR 码
2. 在终端打印 QR 码（ASCII 艺术）
3. 轮询 QR 码状态，等待用户扫码确认
4. 获取 token 并保存到本地
5. 后续请求使用 token 认证

### 媒体处理

**下载流程：**
1. 从消息中提取媒体 URL 和加密参数
2. 通过 CDN 下载加密的媒体文件
3. 使用 AES-ECB 解密
4. 保存到本地媒体目录

**上传流程：**
1. 获取上传 URL
2. 上传媒体文件到 CDN
3. 获取媒体 ID
4. 在消息中引用媒体 ID

### 状态管理

状态保存到 `state_dir/account.json`：
- `token` - 认证令牌
- `get_updates_buf` - 长轮询缓冲标记
- `context_tokens` - 每个用户的上下文 token（用于回复）
- `typing_tickets` - typing 状态的 ticket 缓存
- `base_url` - API 服务器地址

### 错误处理

- **Session 过期**：清除本地 token，重新 QR 登录
- **网络错误**：重试最多 3 次，使用指数退避
- **媒体下载失败**：降级为文本提示用户
- **长轮询超时**：正常行为，继续下一次轮询

## Technical Contract

### 配置结构

**WechatConfig 配置项：**
- `enabled` (bool): 是否启用微信 channel
- `base_url` (str): 微信 API 地址，默认 "https://ilinkai.weixin.qq.com"
- `cdn_base_url` (str): CDN 地址，默认 "https://novac2c.cdn.weixin.qq.com/c2c"
- `state_dir` (str): 状态保存目录路径
- `poll_timeout` (int): 长轮询超时时间（秒），默认 35
- `allow_from` (list[str]): 允许的用户 ID 白名单，空列表拒绝所有，"*" 允许所有

### 消息事件结构

**InboundMessage（微信 → Agent）：**
- `type` (str): 消息类型，固定为 "chat"
- `content` (str): 文本内容
- `session_id` (str): 会话 ID，格式为 "wechat:{user_id}"
- `extra` (dict): 额外信息
  - `media` (list[str]): 媒体文件本地路径列表
  - `sender_id` (str): 发送者微信 ID
  - `chat_id` (str): 聊天 ID

**OutboundMessage（Agent → 微信）：**
- `id` (str): 消息 ID
- `response` (LLMResponse): 回复内容对象
  - `content` (str): 文本内容
- `session_id` (str): 会话 ID

### API 端点

**认证相关：**
- `GET /ilink/bot/get_bot_qrcode?bot_type=3` - 获取 QR 码
- `GET /ilink/bot/get_qrcode_status?qrcode={id}` - 查询 QR 码状态

**消息相关：**
- `POST /ilink/bot/getupdates` - 长轮询获取新消息
- `POST /ilink/bot/sendmessage` - 发送消息
- `POST /ilink/bot/getconfig` - 获取配置（typing ticket）

**媒体相关：**
- `POST /ilink/bot/getuploadurl` - 获取媒体上传 URL
- `GET {cdn_url}/download?encrypted_query_param={param}` - 下载媒体

### 消息类型常量

- `ITEM_TEXT = 1` - 文本消息
- `ITEM_IMAGE = 2` - 图片消息
- `ITEM_VOICE = 3` - 语音消息
- `ITEM_FILE = 4` - 文件消息
- `ITEM_VIDEO = 5` - 视频消息

### HTTP 请求头

所有 API 请求必须包含：
- `X-WECHAT-UIN`: 随机生成的 UIN（每次请求重新生成）
- `Authorization`: "Bearer {token}"（认证后）
- `iLink-App-Id`: "bot"
- `iLink-App-ClientVersion`: 版本号（整数）
- `Content-Type`: "application/json"

### 状态持久化

保存到 `{state_dir}/account.json`：
```json
{
  "token": "认证令牌",
  "get_updates_buf": "长轮询缓冲标记",
  "context_tokens": {
    "user_id": "context_token"
  },
  "typing_tickets": {
    "user_id": {
      "ticket": "typing_ticket",
      "next_fetch_at": 1234567890.0
    }
  },
  "base_url": "API 服务器地址"
}
```

### 媒体文件存储

- 保存路径：`{media_dir}/weixin/{filename}`
- 文件命名：`{type}_{timestamp}_{hash}{ext}`
- 支持的扩展名：
  - 图片：.jpg, .png, .gif, .bmp, .webp
  - 语音：.mp3, .wav, .amr, .silk, .ogg, .m4a
  - 视频：.mp4, .avi, .mov, .mkv

## Acceptance Notes

**核心功能验收：**
1. QR 码登录成功，获取并保存 token
2. 能够接收微信文本消息并转发给 agent
3. 能够接收微信图片消息，下载到本地并转发
4. 能够接收微信语音消息，下载到本地并转发
5. 能够发送文本消息到微信
6. 能够发送图片消息到微信
7. 长轮询稳定运行，不会异常退出
8. Session 过期后能够重新登录

**安全验收：**
1. `allow_from` 白名单生效，拒绝未授权用户
2. Token 安全保存到本地文件
3. 媒体文件保存到独立目录

## Out of Spec

以下内容不在本 spec 范围内：
1. 语音转文字功能（后续单独实现）
2. 群聊支持
3. 消息撤回、编辑功能
4. 消息加密传输（依赖微信 API）
5. 具体的函数实现细节
6. 具体的类名、变量名
7. 错误日志的具体格式
8. 性能优化细节
