---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated: 初始版本
abstract: LLM 通信与会话模块核心契约 — Channel 消息平台接入、ChatBot 对话入口、Session 生命周期管理、内容分类管线、LLM Functions 功能集
module: llm-communication
---

# LLM 通信与会话模块核心契约

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

**业务问题**：LifeWatch-AI 需要一套完整的外部消息接入、用户对话管理、会话持久化、内容智能分类和定时 LLM 任务执行体系。这些子系统共同构成 LLM 模块的"感官"和"记忆"——接收外部输入（微信）、管理对话上下文（Session）、调度 LLM 执行具体任务（分类/总结/分析）。

**核心职责**：
- **Channel 体系**：基于 BaseChannel 抽象的统一消息平台接入框架，WeChat Channel 作为首个实现，提供微信扫码认证、消息收发、媒体下载等完整能力
- **Chat Bot**：用户对话入口，封装消息总线交互和会话生命周期，对外提供简洁的 `chat()` 接口
- **Session 管理**：Session 的创建/加载/保存/删除全生命周期管理，JSONL 文件持久化 + 内存缓存双层架构，ChatHistoryManager 管理聊天历史提取结果
- **内容分类**：基于 LLM 的用户行为自动分类管线，支持 ClassifyGraph（多步推理）和 ClassifySimple（一步直出）两种模式
- **LLM Functions**：定时任务（dreaming、process_session_message）、日记总结、截图语义分析、LLM/VLM 连接测试、数据修复工具

## Scope

### 范围内

- BaseChannel 抽象接口定义（start/stop/send/is_allowed）及 WeChatChannel 完整实现（认证、消息轮询、媒体处理、用户数据管理）
- ChatBot 的无状态对话 API 及 Session 管理委托
- Session 数据结构、SessionManager 的 CRUD 与缓存策略、JSONL 文件格式契约
- ChatHistoryManager 的聊天历史记录管理与提取
- LLMClassify 分类入口 + ClassifyGraph / ClassifySimple 两套分类器
- agent_schedule_job 中的 dreaming（每日总结）和 process_session_message（会话消息提取）
- diary_summary 中的 ai_diary_summary（日记总结）
- screenshot_analysis 中的截图语义分析和行为总结
- fix_behavior_md / migrate_ai_summary 数据修复工具
- test_connect / test_vlm LLM 能力测试
- MessageQueue（bus）的消息发送/接收/限速机制（作为通信基础设施）

### 范围外

- **Agent Loop 细节**：AgentLoop 的调度循环、工具调用链、prompt 组装逻辑 — 属于 agent-spec
- **Provider/LLM Client 细节**：create_llm_client、LLMResponse、token 统计 — 属于 infrastructure-spec
- **Prompt 管理**：Prompts 枚举、prompt_loader、Prompt 版本管理 — 见 `docs/specs/2026-05-13-prompt-management-system.md`
- **WeChat Channel 与 LifePrism 对接契约**：Channel 接口定义、配置数据流、消息总线契约、session_id 规范 — 见 `docs/specs/2026-05-01-wechat-channel-integration-spec.md`
- **截图分析详细规格**：高密度时间段识别、chunk 切分、token 消耗控制 — 见 `docs/specs/2026-04-26-screenshot-analysis-spec.md`
- **分类流程完整调用链**：数据清洗管道、三级分类优先级（缓存命中→Goal 匹配→AI 纯分类）— 见 `docs/specs/2026-04-16-classify-spec.md`
- **弃用模块**：`lifeprism/llm/summary_context/`（已弃用）、`lifeprism/llm/tools/`（__init__.py 全部注释）、`lifeprism/llm/utils/llm_factory.py`（已弃用）

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### WeChat Channel

- [ ] 微信扫码登录：调用 `ilink/bot/get_bot_qrcode` 获取二维码，用户在微信端确认后 token 自动保存到 keyring
- [ ] 启动时自动恢复：已有有效 token 时跳过扫码，直接使用 token 初始化并调用 `getupdates` 验证
- [ ] Token 自动迁移：文件中旧 token 首次加载时自动迁移到 keyring，迁移后从文件清除
- [ ] 接收微信文本消息：长轮询 `ilink/bot/getupdates` 持续拉取新消息，解析文本内容
- [ ] 发送文本消息到微信：通过 `ilink/bot/sendmessage` 发送消息，自动附带 context_token 维持微信上下文
- [ ] 下载微信图片/语音/文件/视频：从微信 CDN 下载加密媒体文件，使用 AES-ECB 解密后保存本地
- [ ] 用户权限控制：config.allow_from 白名单检查，支持 "*" 通配符允许所有用户；未授权用户消息被静默丢弃
- [ ] 用户数据持久化：每个微信用户的 context_token 和 last_session_id 保存到 account.json，支持新旧格式兼容迁移
- [ ] 长轮询容错：网络错误或数据解析错误时等待 5 秒后自动重试，不退出轮询循环
- [ ] 停止时状态保存：channel.stop() 将最新的 token 和 user_data 写入文件（兜底保障）

### Chat Bot

- [ ] 创建对话：ChatBot.chat(content) 发送消息到 bus，返回 LLM 响应
- [ ] 自动会话管理：未传入 session_id 时自动创建新 Session，传入已有 session_id 时恢复上下文
- [ ] 会话操作委托：get_or_create_session、save_session、delete_session、list_sessions、get_session、update_session_name 统一通过 session_manager 执行
- [ ] LLM 调用日志自动记录：每次 chat() 调用自动记录 LLM 调用的输入输出和 system_prompt

### Session 管理

- [ ] 创建新 Session：自动生成 UUID，name 默认格式 `session_YYYYMMDDHHMM`
- [ ] 从 JSONL 文件加载 Session：解析 metadata 行获取 created_at/updated_at/last_compacted_loc/last_processed_loc/name，解析各消息行恢复 messages 列表
- [ ] 保存 Session 到 JSONL：metadata 行（_type="metadata"）+ 各消息行（仅保存 user/assistant/tool 角色），user 消息自动移除图片 base64 内容
- [ ] 内存缓存：已加载的 Session 缓存在 _cache dict 中，后续请求直接返回缓存
- [ ] 删除 Session：删除 JSONL 文件 + 从内存缓存移除
- [ ] 列出所有 Session：扫描 session_path 下所有 .jsonl 文件，返回 session_id 列表（不带后缀）
- [ ] Session 内容列表：扫描所有 session 文件，返回 session_id + 最新 user 消息预览（前 20 字符），支持日期筛选
- [ ] Metadata 快速读取：get_session_metadata() 只读第一行 metadata，不加载完整 messages
- [ ] 缓存清理：remove_from_cache() 从内存移除指定 session（用于定时任务处理后释放内存）
- [ ] ChatHistoryManager 聊天历史管理：添加总结内容、获取未处理记录、保存处理时间戳，支持 JSONL 和旧数组格式兼容

### 内容分类

- [ ] ClassifyGraph 多步分类：按用途（单用途/多用途）和时长（短/长）分流，三条分支并发执行
- [ ] App 描述自动获取：对无描述的 app 并发调用 LLM 获取 50 字以内简短描述，最多重试 3 次
- [ ] Title 语义分析：长时长多用途条目并发搜索分析 title，输出 30 字以内用户活动描述
- [ ] 分类结果关联 Goal：与用户目标高度相关的条目自动关联对应的 goal（link_to_goal 字段）
- [ ] ClassifySimple 一步分类：单次 LLM 调用完成所有条目的分类，无需 app 描述获取和 title 分析
- [ ] 批量并发分类：单批次最多 10-15 条记录，多批次通过 asyncio.gather 并发执行
- [ ] 分类器注册机制：LLMClassify 通过 CLASSIFIER_REGISTRY 根据 classify_mode 名称创建对应分类器实例

### 定时任务

- [ ] dreaming 每日执行：按日期 04:00:00 到次日 04:00:00 的时间窗口，依次执行活动总结 → 心情总结 → 写入 behavior.md → 更新记忆文档
- [ ] 活动总结（summary_activities）：查询 high_usage_segments + user_behavior_notes + ai_behavior_notes，LLM 生成"今日概览/电脑使用总览/高频使用时段"三段式总结
- [ ] 心情总结（summary_moods）：查询用户心情记录，LLM 生成心情变化总结；无心情记录时返回"无心情记录"
- [ ] 记忆文档更新（update_memory）：基于近 7 天 behavior.md + 电脑使用总览 + 当前 recent_state.md，LLM 更新 recent_state.md 和 user.md
- [ ] process_session_message 每 2 小时执行：扫描所有 session 的 metadata，提取 last_processed_loc 之后的新消息，LLM 提取有效信息写入 chat_history.json，再更新到 behavior.md
- [ ] 聊天历史格式化：多条 LLM 提取结果用空行分隔拼接，保留原始"一、二、"层级结构
- [ ] Session 批处理：每次最多处理 10 个 session 为一批，处理完成后清理缓存释放内存

### LLM Functions

- [ ] 日记总结（ai_diary_summary）：读取指定日期日记内容 + 心情/重要程度/自定义标签，LLM 生成总结写入 behavior.md；有旧总结时进入更新模式
- [ ] 截图语义分析（screenshot_analysis）：查询高密度时间段 → 按频率等级动态切分 chunk → 查询 active 截图 → LLM 分析每个 chunk 的行为语义
- [ ] 截图分类过滤：根据 screen_analysis_ignore 配置忽略指定分类的截图，被忽略的截图用文字描述替代图片内容以减少 token 消耗
- [ ] 行为总结（screenshot_behavior_summary）：合并连续的 chunk 分析结果 → LLM 生成 behavior_summary（150 字）+ title（30 字）存入 behavior_analysis 表
- [ ] LLM 连接测试（test_connect）：向当前配置的 LLM 发送测试请求，判定是否返回"连接成功"，解析错误码提供友好提示
- [ ] VLM 测试（test_vlm）：发送测试图片要求模型描述，判定是否识别出猫，验证模型的视觉理解能力
- [ ] behavior.md 格式修复（fix_behavior_md）：CLI 工具，将 LLM 错误输出的 markdown 标题格式替换为序号格式，支持 dry-run 预览
- [ ] AI 总结迁移（migrate_ai_summary）：CLI 工具，将 diary 表中的 ai_summary 字段内容迁移到 behavior.md 对应日期的"日记总结"子标题下

## Technical Contract

### BaseChannel 抽象接口

<key_function>
- lifeprism/llm/channel/base.py
  - base.BaseChannel.__init__:34
  - base.BaseChannel.start:46
  - base.BaseChannel.stop:50
  - base.BaseChannel.send:55
  - base.BaseChannel.is_allowed:64
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(config, bus)` | 初始化 Channel，接收 ChannelConfig 和 MessageQueue | config 必须实现 ChannelConfig Protocol（包含 allow_from: list[str]） |
| `start()` | 异步启动 channel，开始接收消息 | 子类必须实现；幂等：已运行时直接返回 |
| `stop()` | 异步停止 channel，释放资源 | 子类必须实现；需处理 poll_task 取消和客户端关闭 |
| `send(msg: OutboundMessage)` | 发送消息到平台 | 子类必须实现；msg.extra 中传递平台特定参数 |
| `is_allowed(sender_id)` | 检查发送者是否在白名单中 | allow_from 包含 "*" 时允许所有；allow_from 为空时拒绝所有并记录 WARNING |

### WeChatChannel

<key_function>
- lifeprism/llm/channel/wechat/channel.py
  - channel.WechatChannel.__init__:52
  - channel.WechatChannel.start:77
  - channel.WechatChannel.stop:145
  - channel.WechatChannel.send:169
  - channel.WechatChannel._poll_loop:210
  - channel.WechatChannel._handle_wechat_message:254
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(config, bus)` | 初始化微信 Channel | 创建 wechat_dir/media_dir，初始化 client/auth/media 为 None |
| `start()` | 启动 channel：初始化 client → 加载 token → 测试 token → 初始化 media → 启动轮询 | 无 token 时放弃启动并返回；token 测试失败仅记录日志不阻止启动 |
| `stop()` | 停止 channel：保存用户数据 → 取消轮询任务 → 关闭 HTTP 客户端 | 保存失败不阻止停止流程 |
| `send(msg)` | 从 msg.extra 获取 wechat_user_id → 获取 context_token → 构建文本消息 → 发送 | msg.response.content 为空时跳过发送 |
| `_poll_loop()` | 持续调用 getupdates 拉取新消息 → 逐个处理 → 更新 get_updates_buf 游标 | 网络/解析错误等待 5 秒后重试 |
| `_handle_wechat_message(msg)` | 解析消息 → 权限检查 → 保存 context_token → 下载媒体 → 发送到 bus → LLM 调用日志记录 → 更新 session_id → 发送回复 | 单个消息失败不影响其他消息；LLM 调用日志记录失败仅 WARNING |

**认证流程（WechatAuth）**：

<key_function>
- lifeprism/llm/channel/wechat/auth.py
  - auth.WechatAuth.load_state:129
  - auth.WechatAuth.save_state:218
  - auth.WechatAuth.qr_login:246
  - auth.WechatAuth.delete_token:96
</key_function>

| 接口 | 说明 | 约束 |
|------|------|------|
| `load_state()` | 加载保存的状态 | 优先级：keyring token > 文件 token（自动迁移）> 空状态；支持 user_data（新格式）和 context_tokens（旧格式）兼容 |
| `save_state(state)` | 保存状态：token 优先写 keyring，user_data 写文件 | keyring 失败时 fallback 到文件保存整个 state |
| `qr_login(timeout)` | QR 码登录：获取二维码 → 终端打印 ASCII QR → 轮询状态 | 默认超时 300 秒；状态：confirmed（成功）/expired（过期）/scanning（等待） |
| `delete_token()` | 删除 token：清理 keyring + 文件 | 任一失败不影响另一操作 |

**消息处理（WechatMessage）**：

<key_function>
- lifeprism/llm/channel/wechat/message.py
  - message.WechatMessage.parse_message:38
  - message.WechatMessage.build_text_message:71
</key_function>

| 接口 | 说明 | 约束 |
|------|------|------|
| `parse_message(msg)` | 解析微信原始消息，提取 from_user_id、content、media、context_token | 支持 ITEM_TEXT/IMAGE/VOICE/FILE/VIDEO 五种 item 类型 |
| `build_text_message(to_user_id, text, context_token)` | 构建文本消息字典 | client_id 格式 `lifeprism-{uuid.hex[:12]}`；有 context_token 时附带 |

**媒体处理（WechatMedia）**：

<key_function>
- lifeprism/llm/channel/wechat/media.py
  - media.WechatMedia.download_media:59
</key_function>

| 接口 | 说明 | 约束 |
|------|------|------|
| `download_media(media_info, media_type)` | 下载并解密媒体文件，保存到 media_dir | 有 aes_key 时使用 AES-ECB 解密；文件命名格式 `{type}_{uuid.hex[:12]}{ext}` |

**微信配置（WechatConfig）**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `enabled` | `bool` | `False` | 是否启用微信 channel |
| `base_url` | `str` | `"https://ilinkai.weixin.qq.com"` | 微信 API 基础 URL |
| `cdn_base_url` | `str` | `"https://novac2c.cdn.weixin.qq.com/c2c"` | 微信 CDN 基础 URL |
| `poll_timeout` | `int` | `35` | 长轮询超时时间（秒） |
| `allow_from` | `list[str]` | `[]` | 允许接收消息的用户列表（微信 ID） |

**微信异常体系**：

```
ExternalServiceError (lifeprism.utils.exceptions)
└── WechatError
    ├── WechatAuthError       — 认证异常（qr_login 网络/解析错误）
    ├── WechatAPIError        — API 调用异常（send 失败）
    ├── WechatMessageError    — 消息处理异常（解析/媒体下载失败）
    └── WechatMediaError      — 媒体处理异常（下载/解密/保存失败）
```

### ChatBot

<key_function>
- lifeprism/llm/chat/chat_bot.py
  - chat_bot.ChatBot.chat:17
  - chat_bot.ChatBot.get_or_create_session:66
  - chat_bot.ChatBot.save_session:70
  - chat_bot.ChatBot.delete_session:74
  - chat_bot.ChatBot.list_sessions:78
  - chat_bot.ChatBot.get_session:82
  - chat_bot.ChatBot.update_session_name:89
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `chat(content, session_id, **extra)` | 发送聊天消息，返回 LLMResponse | 自动创建/获取 session；AgentLoop 负责消息的接收、存储和回复存储 |
| `get_or_create_session(session_id)` | 获取或创建会话 | 委托 session_manager |
| `save_session(session)` | 保存会话 | 委托 session_manager |
| `delete_session(session_id)` | 删除会话 | 委托 session_manager |
| `list_sessions()` | 获取所有会话 ID 列表 | 委托 session_manager |
| `get_session(session_id)` | 获取现有会话，不存在返回 None | 异常时返回 None（safe-getter 语义） |
| `update_session_name(session_id, name)` | 更新会话名称 | session 不存在时静默忽略 |

### Session 管理

<key_function>
- lifeprism/llm/session/manager.py
  - manager.Session:21
  - manager.Session.add_message:47
  - manager.Session.get_history_message:55
  - manager.SessionManager.get_or_create_session:125
  - manager.SessionManager.save_session:192
  - manager.SessionManager.delete_session:148
  - manager.SessionManager.show_session_list:261
  - manager.SessionManager.show_session_content_list:268
  - manager.SessionManager.get_session_metadata:214
  - manager.SessionManager.remove_from_cache:242
</key_function>

**Session 数据结构**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `str` | `uuid.uuid4()` | Session 唯一标识 |
| `name` | `str` | `session_YYYYMMDDHHMM` | Session 名称 |
| `messages` | `list[dict]` | `[]` | 消息列表，每项包含 role/content/timestamp |
| `created_at` | `datetime` | `datetime.now()` | 创建时间 |
| `updated_at` | `datetime` | `datetime.now()` | 最后更新时间 |
| `last_compacted_loc` | `int` | `0` | 上一次 compact 的消息位置（用于对话压缩） |
| `auto_compact` | `bool` | `True` | 是否启用自动压缩 |
| `last_processed_loc` | `int` | `0` | 上次提取会话信息的位置（用于 process_session_message） |

**消息角色约束**：`user`、`assistant`、`tool`、`system`，非允许角色时 `add_message()` 抛出 ValueError。

**SessionManager 接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `get_or_create_session(session_id)` | 获取或创建 session | 优先从 _cache 返回；缓存未命中时从文件加载；session_id 为空时创建新 session |
| `save_session(session)` | 保存 session 到 JSONL 文件 | 第一行为 metadata（_type="metadata"）；消息仅保存 user/assistant/tool 角色；user 消息自动移除图片 base64 |
| `delete_session(session_id)` | 删除 session | 删除 JSONL 文件 + 从 _cache 移除 |
| `show_session_list(path)` | 扫描目录返回 session_id 列表 | 返回不带 .jsonl 后缀的文件名列表 |
| `show_session_content_list(date_filter, path)` | 返回 session 列表及最新 user 消息预览 | 支持按日期筛选；msg_preview 取前 20 字符 |
| `get_session_metadata(session_id)` | 只读 session 的 metadata | 不加载 messages；文件不存在或格式错误返回 None |
| `remove_from_cache(session_id)` | 从内存缓存移除 | 成功返回 True，不存在返回 False |

**JSONL 文件格式**：

```jsonl
{"_type": "metadata", "name": "session_202604281200", "created_at": "2026-04-28T12:00:00", "updated_at": "2026-04-28T12:05:00", "last_compacted_loc": 0, "last_processed_loc": 0, "message_len": 2}
{"role": "user", "content": "你好", "timestamp": "2026-04-28T12:00:00"}
{"role": "assistant", "content": "你好，有什么可以帮助你的？", "timestamp": "2026-04-28T12:00:05"}
```

**ChatHistoryManager 接口**：

<key_function>
- lifeprism/llm/session/manager.py
  - manager.ChatHistoryManager.load_histories:340
  - manager.ChatHistoryManager.get_histories_to_dream:373
  - manager.ChatHistoryManager.add_content:384
  - manager.ChatHistoryManager.save_history:411
</key_function>

| 接口 | 说明 | 约束 |
|------|------|------|
| `add_content(content, session_id)` | 添加聊天历史记录 | content 为空时跳过并 WARNING；session_id 为 None 时不关联会话 |
| `get_histories_to_dream()` | 获取所有 timestamp > last_processed_time 的未处理记录 | 每项需包含 timestamp 字段 |
| `save_history(last_processed_time)` | 保存历史到文件 | 传入 last_processed_time 时更新处理时间戳；只保留最近 1000 条记录 |
| `load_histories()` | 从文件加载历史 | 兼容 JSONL 格式（正确）和旧数组格式（bug：第二行为整个 JSON 数组） |

### 内容分类

<key_function>
- lifeprism/llm/classify/main_classify.py
  - main_classify.LLMClassify.__init__:21
  - main_classify.LLMClassify.classify:44
- lifeprism/llm/classify/classify_graph.py
  - classify_graph.ClassifyGraph.classify:43
  - classify_graph.ClassifyGraph.get_app_description:103
  - classify_graph.ClassifyGraph.single_classify:159
  - classify_graph.ClassifyGraph.multi_classify_short:214
  - classify_graph.ClassifyGraph.multi_classify_long:294
  - classify_graph.ClassifyGraph.get_titles:260
- lifeprism/llm/classify/classify_simple.py
  - classify_simple.ClassifySimple.classify:62
</key_function>

**LLMClassify 接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(classify_mode, goal, category_tree)` | 初始化分类器 | classify_mode 必须为 "classify_graph" 或 "classify_simple"，无效时 classifier 为 None |
| `classify(state)` | 执行分类，返回 {"result_items": [...]} | classifier 为 None 时返回 None；log_items 为空时跳过 |

**ClassifyGraph 多步分类流程**：

1. **get_app_description**：并发为无描述的 app 获取 50 字以内描述（最多重试 3 次）
2. **split_by_purpose**：按用途分为单用途/多用途
3. **split_by_duration**：多用途按时长分为短时长/长时长
4. **三条分支并发执行**：
   - 单用途分支：`single_classify` — 基于 app_description 分类，每批 10 条
   - 短时长多用途分支：`multi_classify_short` — 基于 title 分类，每批 10 条
   - 长时长多用途分支：`get_titles` → `multi_classify_long` — 先搜索分析 title（30 字），再基于 title_analysis 分类

**ClassifySimple 一步分类**：

- 单次 LLM 调用完成所有条目的分类
- 数据格式：`[id, app_name, app_description, title, is_multipurpose]`
- 每批最多 15 条记录并发处理

**分类器注册表（CLASSIFIER_REGISTRY）**：

| 名称 | 类 | 特点 |
|------|-----|------|
| `classify_graph` | `ClassifyGraph` | 多步推理：用途分流 → 时长分流 → 描述获取 → title 分析 → 分类 |
| `classify_simple` | `ClassifySimple` | 一步直出：单次 LLM 调用完成所有分类 |

**分类输出契约**：

分类结果为 JSON，key 为记录 id，value 为 `[category, sub_category, link_to_goal]` 三元组：
- `category`：主分类名，无法分类时为 null
- `sub_category`：子分类名，无法分类时为 null
- `link_to_goal`：关联的 goal 名称，与 goal 不高度相关时为 null

### MessageQueue（消息总线）

<key_function>
- lifeprism/llm/bus/queue.py
  - queue.MessageQueue.send:105
  - queue.MessageQueue.publish_inbound:45
  - queue.MessageQueue.consume_inbound:48
  - queue.MessageQueue.publish_outbound:51
  - queue.MessageQueue.consume_outbound:53
  - queue.MessageQueue.close:69
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `send(msg: InboundMessage)` | 发送消息并等待结果 | 懒启动接收循环；限速等待（滑动窗口 60 RPM，安全系数 0.7）；超时 1000 秒；自动保存 token usage |
| `publish_inbound(msg)` | 发布入站消息到队列 | — |
| `consume_inbound()` | 消费入站消息 | — |
| `publish_outbound(msg)` | 发布出站消息到队列 | — |
| `consume_outbound()` | 消费出站消息 | — |
| `close()` | 停止接收循环 | 取消所有 pending futures |

**限速机制**：滑动窗口 60 秒内最多 60 次请求，安全系数 0.7（实际约 42 次/分钟），超出时等待最早请求滑出窗口。

**InboundMessage 结构**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `type` | `str` | — | 功能类型：classify / chat / general_task / dream_task |
| `id` | `str` | `uuid4()[:4]` | 消息唯一标识 |
| `channel` | `str` | `"local"` | 来源渠道：wechat / local |
| `content` | `MessageContentInput` | `""` | 消息内容，自动归一化为 MessageContent |
| `session_id` | `str \| None` | `None` | 关联的会话 ID |
| `token_type` | `str \| None` | `None` | token 统计类型，为空时使用 type |
| `extra` | `dict \| None` | `None` | 额外数据（classify 传 system_prompt，chat 传 skill_list，channel 传 wechat_user_id） |

**MessageType 说明**：

| 类型 | 值 | 用途 |
|------|-----|------|
| `CLASSIFY` | `"classify"` | 分类任务，从 extra 提供分类提示词 |
| `CHAT` | `"chat"` | 聊天对话，自动添加聊天系统提示词 |
| `GENERAL_TASK` | `"general_task"` | 通用任务，不自动添加系统提示词 |
| `DREAM_TASK` | `"dream_task"` | 记忆提取任务（聊天数据提取→behavior.md→recent_state.md） |

**OutboundMessage 结构**：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `str` | `""` | 对应 InboundMessage 的 id |
| `response` | `LLMResponse \| None` | `None` | LLM 返回消息 |
| `session_id` | `str \| None` | `None` | 首次创建 session 时返回 id |
| `extra` | `dict \| None` | `None` | 额外数据（channel 特定信息如 wechat_user_id） |

### 定时任务

<key_function>
- lifeprism/llm/function/agent_schedule_job.py
  - agent_schedule_job.dreaming:282
  - agent_schedule_job.summary_activities:65
  - agent_schedule_job.summary_moods:143
  - agent_schedule_job.update_memory:196
  - agent_schedule_job.process_session_message:428
  - agent_schedule_job.extract_from_chat_messages:360
- lifeprism/llm/function/diary_summary.py
  - diary_summary.ai_diary_summary:26
- lifeprism/llm/function/screenshot_analysis.py
  - screenshot_analysis.screenshot_analysis:433
  - screenshot_analysis.analyze_chunk_screenshots:273
  - screenshot_analysis.screenshot_behavior_summary:675
</key_function>

**dreaming(date) 执行流程**：

| 阶段 | 操作 | 说明 |
|------|------|------|
| 阶段1 | 活动数据获取 + 总结 | 查询 high_usage_segments / user_behavior_notes / ai_behavior_notes → LLM 生成三段式总结 |
| 阶段2 | 心情数据获取 + 总结 | 查询心情记录 → LLM 生成心情变化总结 |
| 阶段3 | 写入 behavior.md | 行为总结 + 心情总结写入对应日期的子标题下 |
| 阶段4 | 更新记忆文档 | 基于近 7 天 behavior.md 更新 recent_state.md 和 user.md |

时间窗口：`date 04:00:00` ~ `date+1 04:00:00`

**process_session_message(days_offset) 执行流程**：

| 阶段 | 操作 | 说明 |
|------|------|------|
| 扫描 | 遍历所有 session metadata | 筛选 message_len > last_processed_loc 且 update_at 在 days_offset 内的 session |
| 提取 | 每 10 个 session 一批，并发调用 extract_from_chat_messages | LLM 提取有效信息，更新 last_processed_loc |
| 保存 | 提取结果写入 chat_history.json | 关联 session_id |
| 更新 | 未处理的 history 写入 behavior.md | 更新 last_processed_time |

**日记总结（ai_diary_summary）参数**：

| 参数 | 类型 | 说明 |
|------|------|------|
| `date` | `str` | 日记日期 "YYYY-MM-DD" |
| `mood` | `str` | 写日记时的心情 |
| `importence` | `str` | 日记重要程度 |
| `custom_label` | `list[str]` | 自定义标签列表 |
| `outdate_summary` | `str \| None` | 旧总结（非 None 时进入更新模式） |

字数上限：`min(max(日记长度 * 0.3, 100), 500)`

**截图分析（screenshot_analysis）参数**：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `start_time` | `str` | — | 开始时间（YYYY-MM-DD HH:MM:SS） |
| `end_time` | `str` | — | 结束时间（YYYY-MM-DD HH:MM:SS） |
| `todolist` | `str` | — | 用户今日目标文本 |
| `density_threshold` | `float` | `0.6` | 密度阈值 |
| `min_duration_minutes` | `int` | `6` | 最小高密度时长（分钟） |
| `frequency_level` | `int` | `2` | 截图频率等级（1=低频 2=中频 3=高频） |

### LLM 连接测试

<key_function>
- lifeprism/llm/function/test_connect.py
  - test_connect.test_connect:11
- lifeprism/llm/function/test_vlm.py
  - test_vlm.test_vlm:32
</key_function>

**test_connect 返回结构**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `success` | `bool` | 连接是否成功 |
| `message` | `str` | 结果信息 |
| `model_response` | `str` | 模型回复内容 |
| `provider` | `str` | 使用的服务商 |
| `model` | `str` | 使用的模型 |

**test_vlm 返回结构**：与 test_connect 相同，额外包含 `image_path` 字段。

**判定逻辑**：

| 测试 | 成功条件 | 失败条件 |
|------|----------|----------|
| test_connect | 回复包含"连接成功" | 包含 error / 未返回预期内容 / 异常 |
| test_vlm | 回复包含"猫"或"cat" | 包含 error / 回复"未收到图片" / 未识别出猫 / 文件不存在 |

### 数据修复工具

<key_function>
- lifeprism/llm/function/fix_behavior_md.py
  - fix_behavior_md.fix_behavior_md:29
- lifeprism/llm/function/migrate_ai_summary.py
  - migrate_ai_summary.migrate:18
</key_function>

**fix_behavior_md(path, dry_run)**：将 behavior.md 中的 markdown 标题格式（`### 今日概览` 等）替换为 prompt 要求的序号格式（`1. 今日概览` 等），支持 dry-run 预览模式。

**migrate_ai_summary(dry_run)**：遍历 diary 表中所有记录，将 `ai_summary` 字段内容写入 behavior.md 对应日期的"日记总结"子标题下，写入模式为 overwrite。

### Channel 实例契约

`lifeprism/llm/channel/__init__.py` 模块加载时创建全局 LazySingleton：

| 实例名 | 类 | 初始化参数 |
|--------|-----|-----------|
| `wechat_channel` | `WechatChannel` | `WechatConfig(enabled=True, allow_from=["*"])`, `bus` |

使用 `LazySingleton` 包装，首次属性/方法访问时才实例化，避免模块导入时的启动延迟。

## Design Rationale

**为什么用 LazySingleton 管理 wechat_channel？**
- WeChat Channel 的初始化涉及 HTTP 客户端创建、状态文件路径解析等操作，不应在模块导入时立即执行
- LazySingleton 在首次访问时才实例化，实现延迟加载，避免阻塞应用启动
- 双重检查锁定（DCL）保证线程安全

**为什么 WeChat 认证使用扫码方式而非帐密？**
- 微信 iLink Bot API 仅支持 QR 码登录方式（`get_bot_qrcode` → `get_qrcode_status`）
- 扫码登录避免了明文存储密码的安全风险
- Token 通过 keyring + 文件双层持久化，支持重启后自动恢复

**为什么 Token 存储使用 keyring + 文件双层策略？**
- keyring 是操作系统级安全存储（Windows Credential Manager / macOS Keychain），优先使用
- 文件存储作为 fallback，当 keyring 不可用时（如无桌面环境）退回文件存储
- 旧格式数据自动迁移到 keyring，保证向后兼容

**为什么 WeChat Channel 的消息处理链路中 session_id 由 AgentLoop 管理？**
- Channel 只负责消息的接收、解析和发送，不关心对话逻辑
- Session 的创建、消息存储、上下文管理由 AgentLoop 在 `bus.send()` 处理链中完成
- Channel 转发 AgentLoop 返回的最新 session_id 给下一次请求，实现微信会话延续

**为什么 Session 同时有内存缓存和数据库持久化？**
- 内存缓存（`_cache: dict[str, Session]`）：高频读取场景下避免反复解析 JSONL 文件
- JSONL 文件持久化：保证重启后数据不丢失，支持跨进程读取
- 两者互补：缓存加速读取，文件保证持久化；写入时同时更新缓存和文件

**为什么 Session 使用 JSONL 而非 SQLite 存储？**
- Session 的读写模式是"整存整取"——大部分操作加载完整 session 或保存完整 session
- JSONL 格式更适合这种场景：按行追加便于扩展，人类可读便于调试
- 第一行为 metadata 的设计使得 `get_session_metadata()` 可以只读首行，避免加载完整消息列表

**为什么有 ClassifyGraph 和 ClassifySimple 两套分类器？**
- ClassifyGraph 是多步推理方案：按用途分流 → 时长分流 → app 描述获取 → title 语义分析 → 分类。精度高但 token 消耗大
- ClassifySimple 是一步直出方案：单次 LLM 调用完成所有分类。速度快但精度较低
- 两套方案通过 CLASSIFIER_REGISTRY 注册，用户可根据场景（精度优先 vs 速度优先）选择
- ClassifyGraph 内部通过 `asyncio.gather` 并发执行三条分支，在保证精度的同时最大化并发性能

**为什么 dreaming 任务按 04:00:00 到次日 04:00:00 划分一天？**
- 避免在午夜的活跃期（用户可能还在使用电脑）执行总结
- 04:00 是一天中用户活动最少的时段，适合执行后台任务
- 这个时间窗口使得"今天"的总结涵盖从昨天早晨到今早凌晨的完整活动周期

**为什么 process_session_message 每 2 小时执行一次？**
- 聊天消息的提取不需要实时性——用户对话后稍作延迟再提取不会影响体验
- 2 小时间隔既能及时将对话内容纳入记忆系统，又不会频繁调用 LLM 造成浪费
- 处理时批量 10 个 session 并发，最大化吞吐量

**为什么 user 消息保存时自动移除图片 base64？**
- 图片 base64 数据通常非常大（单张几 MB），直接写入 JSONL 会严重膨胀文件体积
- 图片在 session 恢复时不需要（VLM 分析已在上次请求中完成）
- `_remove_image_content()` 在保存时过滤 image/image_url 类型的 content block

**有哪些约束？**
- WeChat Channel 依赖 iLink Bot API，API 稳定性取决于微信平台
- MessageQueue 的限速机制（60 RPM, 安全系数 0.7）对所有 LLM 调用生效，包括分类、聊天、定时任务
- Session JSONL 文件格式依赖首行 metadata 约定，修改 metadata 字段可能影响旧文件的兼容性
- ClassifyGraph 中的 app 描述获取和 title 分析依赖 LLM 搜索能力（非 VLM），对不支持搜索的模型可能精度下降
- dreaming 任务中的 update_memory 使用 DREAM_TASK 类型（带工具调用），依赖 AgentLoop 的工具执行能力

**有哪些已知限制？**
- WeChat Channel 无 token 时直接放弃启动（qr_login 代码被注释），当前需要预先配置 token 才能使用
- WeChat Channel 仅支持单用户数据管理（_user_data dict 在内存），不支持分布式部署
- Session 的 `auto_compact` 功能仅标记为 True，但 compact 逻辑未实现（在 LifeWatch-AI 场景中暂无长对话需求）
- ChatHistoryManager 不是单例，每次创建独立实例，多个调用方可能产生并发写入问题
- ClassifyGraph 和 ClassifySimple 的 LLM 调用通过 bus.send 走统一的消息总线，分类任务与其他任务共享限速配额

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **WeChat Channel 对接契约**：[`docs/specs/2026-05-01-wechat-channel-integration-spec.md`](../specs/2026-05-01-wechat-channel-integration-spec.md) — Channel 接口定义、配置数据流、消息总线契约、session_id 规范
- **截图分析详细规格**：[`docs/specs/2026-04-26-screenshot-analysis-spec.md`](../specs/2026-04-26-screenshot-analysis-spec.md) — 高密度时间段识别、chunk 切分逻辑、token 消耗控制、screen_analysis_ignore 配置
- **分类流程完整规格**：[`docs/specs/2026-04-16-classify-spec.md`](../specs/2026-04-16-classify-spec.md) — 数据清洗管道（EventTransformer→CacheMatcher→ClassifyCollector）、三级分类优先级、同步 API 契约
- **Prompt 管理系统**：[`docs/specs/2026-05-13-prompt-management-system.md`](../specs/2026-05-13-prompt-management-system.md) — Prompt 文件组织、加载接口、版本管理、使用统计
- **Agent Loop**：AgentLoop 的调度循环、工具调用链、prompt 组装逻辑 — 属于 agent-spec
- **Provider/LLM Client**：create_llm_client、LLMResponse、token 统计基础设施 — 属于 infrastructure-spec
- **Config 模块**：settings 路径解析、keyring 配置、Provider 管理 — 见 [`docs/specs/2026-07-06-config-path-spec.md`](../specs/2026-07-06-config-path-spec.md) 和 [`docs/specs/2026-07-06-config-settings-spec.md`](../specs/2026-07-06-config-settings-spec.md)
- **弃用模块**：`lifeprism/llm/summary_context/`、`lifeprism/llm/tools/`、`lifeprism/llm/utils/llm_factory.py`
