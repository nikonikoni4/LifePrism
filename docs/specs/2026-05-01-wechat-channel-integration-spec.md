---
version: 2.0
created_at: 2026-05-01
updated_at: 2026-10-08
last_updated: 微信纯收发，独立会话服务管理命令、执行与原生人工交互
abstract: 微信 transport 的输入/输出、应用装配、准入与生命周期契约；独立会话服务消费 Runtime 事件，原生 HITL 通过客户端发问，聊天不走 bus。
---

# WeChat Channel 与 LifePrism 对接规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 初始 Channel 与消息总线接入契约（已替换） |
| 2.0 | 纯收发、独立会话路由与原生 HITL；保留现有微信命令反馈 |

## Overview

微信收发期间不能等待 Agent 的最终结果，否则人工问题发出后，下一批回答无法进入。WechatChannel 只负责认证、协议转换、媒体与回复凭据；ConversationService 负责准入、会话命令、Session 引用、执行任务及输出，原生 HITL 独立负责错误事件裁决。

## Scope

范围内：微信与会话服务的装配，输入/输出数据，用户权限与本地/云端处理归属，命令和人工答案路由，运行拥有权，凭据/会话引用隔离保存及关闭清理。

范围外：微信平台回复额度、在线模型兼容性、前端人工交互 UI、workflow 管理、旧 Session 迁移，以及其他 P3 恢复策略。执行与存储契约见 [myagent Runtime Spec](2026-10-03-myagent-runtime-spec.md)，数据流见 [会话与 HITL Flow](../flows/2026-10-08-wechat-conversation-hitl-flow.md)。

## Functional Checklist

- [x] 微信把命令原文交给服务，服务及时返回接收结果；长执行不阻塞下一批收取。
- [x] 白名单和本地在线归属检查在媒体下载、凭据更新和业务提交之前完成。
- [x] 原生最大步数问题可通过微信提示和下一条答案恢复原 turn；答案不成为第二条 user 消息。
- [x] 无效/过期结构化回答保持当前等待，跨用户输入不唤醒他人的请求。
- [x] 同一用户的命令、提示及终态经同一个发送入口串行发送。
- [x] 只读会话列表允许在普通执行期间查询，切换命令拒绝改变活跃运行。
- [x] 终态在流与 Runtime 清理之后输出一次；发送失败不重跑 Agent 或重复执行命令。
- [x] 人工超时、取消、关闭清理 Future/任务；缓存 Session 的后续本地调用不向旧微信用户发问。
- [x] 凭据和 Session 引用各自单字段保存，停止时不覆盖新状态。
- [x] 部分启动失败、轮询失败后的停止均关闭自有资源；迁移失败保留源文件。
- [ ] 真实微信多次发送及回复额度联调。

## Technical Contract

### 装配与收发接口

`wire_wechat_channel(channel, runtime, references) -> ConversationService` 是应用装配入口。默认单例沿用现有 start/stop 调用位置；注入 `on_message=service.submit`、`allow_input=service.can_receive` 及业务 start/close 回调。

| 接口 | 契约 |
| ---- | ---- |
| `WechatChannel.start()` | 打开客户端、读取认证及旧用户状态，有 token 且接收入口已注入后开始轮询；缺 token 关闭连接并返回 |
| `WechatChannel.stop()` | 停止接收，取消并等待轮询，关闭会话服务自有任务，关闭 HTTP；共享 Runtime 由应用关闭 |
| `WechatChannel.send(OutboundMessage)` | 读取最新回复凭据后发送完整文本；未运行、目标缺失或发送失败抛错 |
| `ConversationService.submit(ConversationInput)` | 原子准入与操作预留，启动自有任务后及时返回 operation_id；答案/重复/拒绝输入返回 None |
| `ConversationService.close()` | 拒绝新输入，取消并 await 自有任务，清理 pending/路由/发送锁；start 可重开接入 |
| `ConversationClient.send(OutboundMessage)` | 固定路由接收人并串行输出；不在等待人工答案时持有发送锁 |
| `RunClient.ask_human(HITLMessage)` | 在发送之前登记 pending/Future，等待原生 HumanReturn；finally 按身份清理 |
| `RunClient.answer(text, request_id=None)` | 同步校验并完成当前 Future；无效/过期回答不改变原等待 |

Channel 构造仍接收 bus 参数用于兼容 BaseChannel；聊天、命令和人工交互不使用 bus。后台任务继续使用 Runtime.execute/bus worker，微信消费 Runtime.stream。

### 输入数据

| 类型/字段 | 契约 |
| ---- | ---- |
| `ConversationRoute.channel` | 渠道标识，微信为 wechat |
| `ConversationRoute.recipient_id` | 非空微信用户 ID；不是 Session ID |
| `ConversationRoute.transport_id` | 收发实例标识，当前默认 wechat |
| `ConversationInput.route` | 不可变路由 |
| `ConversationInput.content` | MessageContent 内容块；文本输入归一化；text 属性用于命令/回答解析 |
| `ConversationInput.input_id` | 优先平台 message_id/client_id，否则随机标识；服务按 route+input_id 去重 |
| `ConversationInput.extra` | 默认空对象；微信提供 media 路径及 wechat_user_id，不保存旧回复 token |
| `ConversationInput.request_id` | 可选人工请求关联；微信当前纯文本不携带此字段 |

稳定 input_id 的去重窗口为最多 4096 个已接收输入，活跃任务另保护其原始输入 ID；进程重启或平台缺少稳定 ID 不保证重复投递去重。

### 输出数据

沿用 OutboundMessage 的 id/response/session_id/extra/error。业务消息以 response.content 为发送文本，Session 使用原生 UUID，与收件人分离。ConversationClient 将 extra 的 channel/transport_id/recipient_id/wechat_user_id 固定为本路由；kind 区分 command/interaction/notice/terminal，相关操作增加 operation_id、run_id，人工提示增加 request_id。

同一路由所有输出共用发送锁；不同路由独立。微信不发送模型 token 分块。程序每轮最多尝试一次终态发送；网络结果未知时仅记录失败，不承诺端到端恰好一次送达。

### 准入、人工答案与忙状态

`allow_from=[]` 拒绝全部输入，`["*"]` 允许全部，其他列表按用户匹配。agent_only 模式下本地心跳在线则拒绝云端处理，离线/超时才处理；本地模式不受心跳在线影响。拒绝输入不得更新凭据、下载媒体或进入交互。处理归属变化时旧运行在下一次准入检查被取消；不迁移悬挂 Future。

一个 route 仅有一个活跃操作。已接收任务在服务的后台任务集合中有明确拥有者，输入处理不等待模型/命令查询/发送。下一条输入先去重，再优先匹配 pending；有效答案唤醒原执行，命令文本或无效选项提示重输。无 pending 时，携带旧 request_id 的回答明确拒绝。

无 pending 的执行/准备/收尾期间，普通聊天及 /new、/continue 返回忙提示；/session-list 可启动独立只读任务，不替换原运行。空闲时处理命令或启动新 turn。Runtime 对相同 Session 继续串行，包括不同 route 共用 Session；答案路径不取得此锁。

纯文本迟到答案无法可靠关联旧请求，空闲时作为普通聊天；当前不提供进程重启后继续旧等待协程。原生人工等待默认 60 秒，最大步数继续授予 5 步；工具默认配置保持，工具熔断人工回调只有实际抛出熔断错误时触发。

### Session 命令

/new 即时创建并保存原生空会话，返回新 ID；有上一会话时包含 /continue <旧ID> 指令。引用保存失败清理未绑定空会话。/continue <UUID> 仅切换后续聊天引用，并展示最近 user/assistant 回顾。/session-list [页码] 或 /session-list YYYY-MM-DD [页码] 每页 10 条，展示统一 chat 记录的名称、摘要、当前及运行标记。不区分微信和本地，不查询 workflow/task 或旧 Session，不调用模型或 bus。

### 配置与状态

WechatConfig 沿用 enabled=False、base_url=https://ilinkai.weixin.qq.com、cdn_base_url=https://novac2c.cdn.weixin.qq.com/c2c、poll_timeout=35、allow_from=[]；应用单例构造使用 enabled=True 和 allow_from=["*"]。本次不调整设置 API 与登录界面。

认证仍由 WechatAuth 读取配置存储，兼容旧 account.json。WechatReplyStore 持有最新 context_token 缓存并调用 save_context_token；即使持久化失败，内存新凭据仍可用于本轮答复。WechatSessionReferences 每次从 wechat_account_state 读 last_session_id，调用 save_session_reference 只更新引用。两侧均不可用全量旧缓存覆盖另一字段。

旧 account.json 支持 user_data/context_tokens，逐用户迁移缺失记录，已有记录保留。保存全部成功后才重命名 .json.bak；保存失败保留源文件供重试。停止不再批量保存账户缓存。

## Design Rationale

原生错误策略只依赖 HITLChannel，会话服务负责回答与任务拥有权，transport 只承担收发。保留 Runtime.execute 避免后台契约变化；通过本轮注入的 relay 避免持久 context 累计旧用户 client。人工提示与最终结果共用发送入口，输入读取独立于原 turn 的等待。

真实微信回复额度尚未核实：程序在提示后收到新输入会更新 token，离线协议测试验证最终回复使用新 token；多次提示、无效回答和只读命令是否受平台额度约束仍需真实联调。

## 对外接口位置

<key_function>
- lifeprism/llm/channel/__init__.py
  - __init__.wire_wechat_channel:20
- lifeprism/llm/channel/wechat/channel.py
  - channel.WechatChannel.start:66
  - channel.WechatChannel.stop:102
  - channel.WechatChannel.send:125
- lifeprism/llm/conversation/service.py
  - service.ConversationService.submit:110
  - service.ConversationService.can_receive:70
  - service.ConversationService.close:280
- lifeprism/llm/conversation/client.py
  - client.ConversationClient.send:26
  - client.RunClient.ask_human:81
  - client.RunClient.answer:109
- lifeprism/llm/conversation/commands.py
  - commands.SessionCommandService.handle:74
</key_function>
