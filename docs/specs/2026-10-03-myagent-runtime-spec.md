---
version: 1.8
created_at: 2026-10-03
updated_at: 2026-10-08
last_updated: 微信会话服务消费事件流，按运行注入原生人在回路客户端
abstract: 原生 Agent 执行、事件关联、最终答复、工具和提示词注册、共享用量统计，以及暂不可用的会话业务边界。
---

# myagent Runtime

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建迁移后运行契约 |
| 1.1 | 工作流与聊天渠道的会话目录归属 |
| 1.2 | 聊天统一 chat/<session_id>.jsonl，channel 不参与目录归属 |
| 1.3 | 前端聊天列表、历史、改名、删除及继续聊天 |
| 1.4 | 原生 turn 增量提取及独立业务进度 |
| 1.5 | 微信聊天会话分页列表及渠道引用切换 |
| 1.6 | 默认会话根目录收敛为 session，Runtime 以 session_root 集中解析 |
| 1.7 | 微信命令恢复即时新建、历史回顾、日期筛选与消息摘要 |
| 1.8 | 微信纯收发、独立会话服务与原生 HITL 的运行级注入 |

## 业务意图

聊天和后台 Agent 任务使用同一个 myagent 内核，避免维护两套 ReAct、工具注册和上下文系统。用户可创建原生新会话并在当前会话继续聊天；本地流式输出与微信最终答复采用同一个订阅结果来源。

## 执行契约

Runtime 接收现有 InboundMessage（内容块、场景、渠道、可选 session_id、extra 和用量类别）。新会话创建原生 UUID；已有会话只接受可加载的原生 Session，旧 ID/旧文件明确拒绝。同会话串行，不同会话可并行，共享实际模型调用限速。

`stream` 返回 RuntimeEvent：`type/run_id/session_id` 必填；`turn/step/seq` 可为空；`text` 默认空字符串，`data` 默认空对象；`result` 仅用于完成事件，包含现有 OutboundMessage。原生 chunk 投影为 content/reasoning 等事件，工具调用与结果携带原生记录数据。

`done` 必须满足执行任务结束且本轮终态成功；结果文本使用最后一次 assistant message，用量累加本轮所有完成的模型步骤。失败输出 error，不输出 done。取消结束 turn，不生成成功结果。用量持久化保留已完成步骤，即使后续失败或取消。成功聊天在 Runtime 记录一次生产调用日志，提示词及模型取原生 request/header；后台日志由现有任务调用方记录，避免重复。

`execute` 收集上述事件得到 OutboundMessage；错误抛出 RuntimeError。后台 worker 将异常转为 OutboundMessage.error，bus 等待者立即失败。请求取消/超时取消对应后台执行。

## 会话交互契约

微信不等待 execute 的最终返回，输入提交到 ConversationService 后及时返回。服务拥有原 stream 的消费任务，人工提示、命令答复与最终结果共用 ConversationClient.send。具体输入、忙状态及会话命令契约见 [微信接入 Spec](2026-05-01-wechat-channel-integration-spec.md)。

`stream` 增加可选 `interaction_client`、`hitl_timeout=60`、`hitl_grant_steps=5`。客户端提供 `bind(run_id, session_id)` 与原生 `ask_human(HITLMessage) -> HumanReturn`；在 Session 执行锁内、本轮 turn 启动前绑定，清理时解除匹配绑定。无客户端的本地 SSE 与后台路径保持原等待契约，不启用人工等待。

原生 HITL 通过 context 注册 REQUEST_ERROR waterfall，提供最大步数及工具熔断回调；每缓存 Session 只注册一次，回调目标按本轮绑定。人工答案完成原 Future，不追加 user turn，不取得原 Session 执行锁。最大步数继续由 loop 留存 grant；取消产生 interrupted，工具熔断取消产生 error。Runtime 的 error.data 保留原生终态记录（无终态时 reason_type=error）。会话服务耗尽并关闭流、等待 Runtime 清理后才发送一次终态。

默认工具配置仍不变；工具熔断回调只有在工具配置实际抛出熔断异常时介入。人工等待超时由原生策略管理，Runtime 的 1000 秒总超时包含等待。服务关闭取消并等待自有任务；共享 Runtime 由应用生命周期关闭。

## Session 存储归属

`InboundMessage.workflow_id: str | None` 标识稳定的工作流归属，不是一次执行的 run_id。一个工作流可包含多个原生 session_id，归属不决定工具或提示词，也不决定用量类别；这些仍分别由 type 与 token_type 控制。

默认存储根目录为 `<lifeprism_data_path>/session`；Runtime 可注入替代根目录，两者共用 `session_root` 属性集中解析，避免聊天与工作流两条路径各自维护默认根而漂移。提供 workflow_id 时优先存到 `workflows/<workflow_id>/<session_id>.jsonl`，包括使用 CHAT 工具配置的工作流。未提供 workflow_id 的 CHAT 统一存到 `chat/<session_id>.jsonl`，不按 local/wechat 渠道细分目录；未指定归属的后台调用兼容存到 `tasks/<session_id>.jsonl`，不根据 type/token_type 猜测所属工作流。

workflow_id 是 1–64 位小写 ASCII 字母、数字、下划线或连字符，首位必须为字母或数字，禁止 Windows 设备保留名。目录解析拒绝符号链接逃出存储根目录。已有 Session 只能在原归属目录恢复，内存缓存同样检查归属；聊天可在同一 slot 内跨渠道继续，但不扫描其他归属目录兜底。

会话头 RuntimeEvent.data 保留 name/is_new，并增加 workflow_id（可为空）、channel、session_category（workflow/chat/task）。channel 仅用于收发与事件，不参与目录归属；业务存储归属只按 chat/workflow/task 分类。目录是当前持久化归属依据，不向 myagent 原生 metadata 塞入其加载器无法恢复的自定义键。原项目编码目录及旧业务 Session 数据保留，不自动迁移。

生产工作流 ID：classify-graph、classify-simple、daily-memory（活动/心情总结及记忆更新）、chat-extraction（聊天增量提取）、diary-summary、screenshot-analysis、behavior-summary、file-conflict-resolve。

## 本地 SSE 契约

`POST /chatbot/chat/stream` 保留已有请求结构。ChatStreamEvent 字段：`type` 必填（session/status/content/done/error）；`node/message/session_id/session_name/is_new_session/error/run_id/turn/step/seq/data/usage` 可为空。session 提供原生会话 ID；content 为真实文本增量；status 表示 tool/call 或 tool/result；done.message 为最终答复，覆盖中间累积文本，usage 为 input_tokens/output_tokens/total_tokens 的本轮总量。

客户端断开通过关闭事件生成器取消模型任务。前端会话列表、历史、改名、删除仅管理 `chat/` 中的原生会话，可选择后继续聊天；不扫描 workflows/tasks，也不适配旧目录。历史显示用户消息及每轮最终 assistant 答复，工具步骤不作为重复答复显示。

列表包含 `is_running`，执行或等待同会话锁的请求均为运行中。前端禁用运行会话的删除，后端独立拒绝，返回 HTTP 409。删除永久移除文件，无回收站或恢复入口；释放空闲执行缓存与持久化 worker 后才删除，管理期间拒绝同 Session 新请求。改名同样限空闲会话，名称为 1–200 个非空白字符。缺失资源返回 404，非法 Session ID 返回 400。

历史用量接口仍返回 HTTP 501。

微信会话命令在既有白名单及本地/云端路由检查后执行，不调用模型或后台 bus：

- `/session-list [页码]` 或 `/session-list YYYY-MM-DD [页码]`：统一聊天目录按更新时间降序分页，每页 10 条；展示名称、完整 UUID、最近用户消息的 20 字摘要、当前会话及运行状态。日期严格校验，并按用户配置时区的最后更新时间筛选；页码为正整数，缺省 1。空列表和超出页数均明确提示。
- `/continue <Session ID>`：验证原生 UUID，且目标存在于统一聊天目录后，持久化当前微信用户的会话引用；回复成功信息、会话 ID、最近各一条用户消息及最终助手答复（沿用历史文案“最后两轮对话”）。空历史不展示回顾章节。下一条普通消息继续该会话，切换命令本身不执行历史任务。允许选择本地创建的聊天，会话执行仍遵守 Runtime 串行规则。
- `/new`：立即创建并保存原生空会话，切换当前微信用户引用；回复新 ID，并在存在上一会话时附上可复制的 `/continue <旧ID>`。不删除上一会话，不启动模型、执行 context 或持久化 worker，也不写入虚构用户轮次。

新建和切换在状态保存失败时恢复内存引用；新建后的引用保存失败还会清理未绑定的空会话。无效或缺失目标保持原引用。命令成功回复带 `[SUCCESS]`，参数及执行错误带 `[ERROR]`；成功新建/继续的出站消息携带相应 session_id。只匹配完整命令名，参数错误回复用法。旧会话、workflow/task 不提供微信恢复入口；统一聊天目录是应用级共享列表，不增加按微信用户的存储归属。

## 工具与提示词

工具使用 myagent Tool/ToolRegister，保留业务目录权限；字符串 `Error: ` 转为失败 ToolResult，普通字符串为成功结果，结构数据序列化为 JSON。熔断阈值、模式与抛错行为使用原生默认值。

CHAT 注册文件、系统查询、习惯及自定义记录工具；DREAM_TASK 注册文件及指定系统查询；其他场景不注册工具。会话查询和 bootstrap 工具不注册。

SystemPrompt 注册动态文件 section、技能、运行时 context 和自定义规则 reminder。每次模型调用重读文件，已识别占位符替换，JSON 花括号保留。生产 provider 的路由、鉴权和请求参数继续由生产系统负责，配置在每个新 turn 开始刷新。

## Functional Checklist

- [x] 工具中间答复不提前完成，最终结果与全部步骤用量正确关联。
- [x] 同会话并发请求串行，提示词文件变更生效。
- [x] 失败只有 error，原生 turn/end 留存失败原因。
- [x] SSE 断开和 bus 请求取消停止模型任务。
- [x] 关闭释放活跃订阅，worker 可重新启动。
- [x] 首次初始化不生成 bootstrap，已有用户文件保留。
- [x] 工作流与聊天目录隔离落盘，关闭 Runtime 后可恢复同归属的会话。
- [x] 聊天统一目录，可在同一 slot 内跨渠道继续会话。
- [x] 缓存不能改用工作流归属，符号链接不能绕过目录隔离。
- [x] workflow_id 不改变消息工具选择或 token_type 用量分类。
- [x] 聊天历史与名称跨重启恢复，删除后缓存不会重建文件。
- [x] 执行及排队会话拒绝删除，工作流记录不进入聊天管理。
- [x] 原生 turn 增量提取、失败不推进、重启恢复及历史保存后的去重重试。
- [x] 崩溃轮次缺口不会被游标越过，日期章节隔离且落盘失败保留原文件。
- [x] 微信列表、切换及即时空会话创建不调用模型；非法目标及保存失败不改变引用。
- [x] 微信新会话可跨重启继续；返回旧会话恢复指令，继续命令展示最近对话，列表支持本地日期及摘要。
- [x] 人工继续恢复原 turn；取消/超时保留原因，服务关闭清理 pending 和 turn。
- [x] 微信两批协议输入可在人工等待期间收取；使用新凭据输出最终结果（离线协议替身验证）。
- [ ] 真实微信收发与在线供应商联调。
- [ ] 供应商专属 thinking blocks/signature 消息兼容验证。

## 会话增量提取

记忆更新请求明确给出 `user/user.md` 和 `user/daily_data/recent_state.md` 的绝对路径；前者与聊天提示词读取的用户文件一致，不能以其他目录的同名文件代替。真实模型工具参数异常及步骤超时的恢复仍属于 P3。

`process_session_message` 仅扫描统一 `chat/`，不扫描工作流或旧会话。`meta.extra.last_processed_turn` 为独立业务处理进度，缺省 0；原生轮次从 1 开始。以最后一个 `turn/end` 为增量边界，提取上次进度之后至该边界的用户消息及最终答复；中间因崩溃缺少结束事件的轮次也纳入，防止游标越过后遗漏。边界之后未结束的尾部轮次等待后续处理。其他 extra 键保持原值。

输入包含用户消息及每轮最后的非工具调用助手消息，不包含工具轨迹、思考片段或图片原文。提取请求使用后台 bus，归属 `chat-extraction` 工作流，用量归入 DREAM_TASK。

执行和排队中的会话本次跳过；空闲会话在处理期间预留，拒绝新轮次、删除及改名。历史成功保存后才原子提交游标；模型错误、空响应及历史保存失败不推进，明确的“无可提取内容”仍提交。ChatHistory 记录 session_id/start_turn/end_turn，允许游标提交失败后去重重试。

保存到 ChatHistory 后更新 behavior.md 的当天聊天章节，再提交历史处理时间；当天多次执行重建完整章节。默认只处理近 3 天更新的会话，每批最多 10 个并发；auto_summary_session 开启时每 4 小时调度，TEST_MODE 使用测试分钟间隔。历史文件与 Session 元信息采用原子替换，跨文件写入以可重试顺序处理，不提供跨进程事务。

## 后续范围

P3 错误策略及剩余 P4 会话业务另行设计。当前不提供旧会话迁移、workflow 管理或会话查询工具。

设计依据：[myagent 内核 ADR](../adr/2026-10-03-myagent-runtime.md)。


<key_function>
- lifeprism/llm/runtime/service.py
  - service.AgentRuntime.start:244
  - service.AgentRuntime.stream:338
  - service.AgentRuntime.execute:535
  - service.AgentRuntime.close:610
- lifeprism/llm/conversation/service.py
  - service.ConversationService.submit:110
  - service.ConversationService.close:280
- lifeprism/llm/conversation/client.py
  - client.RunClient.ask_human:81
  - client.RunClient.answer:109
- lifeprism/llm/runtime/worker.py
  - worker.AgentBusWorker.loop:52
- lifeprism/server/api/chatbot_api.py
  - chatbot_api.chat_stream:151
- lifeprism/llm/function/agent_schedule_job.py
  - agent_schedule_job.extract_from_chat_messages:382
  - agent_schedule_job.process_session_message:438
</key_function>
