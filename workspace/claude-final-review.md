# myagent P1/P2 迁移 — 只读终审

日期：2026-10-03
范围：`lifeprism/llm/runtime/`、`lifeprism/llm/runtime_tools/`、`lifeprism/llm/bus/`、
`lifeprism/server/`、`lifeprism/llm/providers/llm_providers/`、
`frontend/core/components/Chatbot/`、`pyproject.toml`、`lifeprism.spec`
架构依据：`workspace/task_plan.md`
方式：只读审查，未修改任何被发现的问题，未提交，未启动子代理。

## 结论

P1/P2 的五条主链路通过审查：生产代码已无旧内核导入，聊天/微信不走 bus，
取消与关闭有收尾路径，provider 流式契约有真实增量与终态，前端 SSE 能消费增量。

发现 **1 个应修缺陷（P2 验收范围内）**、**3 个低风险观察**。
另有 1 项属 P3 明确延后范围，按约定不计为遗漏。

> **第二轮收尾复审见 §五**：D1 已闭环（聊天日志取自 myagent 原生 `request/header`），
> 附录的限速孤儿测试已迁移为 `ModelCallLimiter` 测试。当前无遗留红灯项。

---

## 一、应修缺陷

### D1 聊天链路的 LLM 调用日志不再落盘（P2 任务 3 漏项）

**严重度**：中（数据资产静默缺失，不报错）
**状态**：已修复并于第二轮复审闭环，见 §5.1。

**证据**

- 旧路径记录调用日志：
  - `git show HEAD:lifeprism/llm/chat/chat_bot.py` 中 `ChatBot.chat` 调用
    `llm_call_logger.log_call(...)`。
  - `git show HEAD:lifeprism/llm/channel/wechat/channel.py` 中微信聊天分支调用
    `llm_call_logger.log_call(...)`。
- 新路径无任何记录点：
  - `lifeprism/llm/chat/chat_bot.py:12-25` 全文件无 `llm_call_logger`。
  - `lifeprism/llm/channel/wechat/channel.py:530` 改为 `await agent_runtime.execute(inbound_msg)`，
    其后不再记录。
  - `lifeprism/llm/runtime/service.py` 全文件无 `log_call`（唯一相关的持久化是
    `_save_usage`，见 261-277 行）。
- 仍在使用 `log_call` 的只剩后台任务：
  `lifeprism/llm/function/agent_schedule_job.py:99,176,275`、
  `lifeprism/llm/function/diary_summary.py:113`。
- 开关默认开启：`lifeprism/config/settings_manager.py:88`
  `"llm_call_logger_enabled": True`。

**触发条件**

1. 用户在本地聊天或微信发一条消息（走 `agent_runtime.stream/execute`）。
2. 检查 `llm_call_logger` 落盘目录 —— 本地/微信聊天轮次不出现。
   后台 dreaming/diary/screenshot 轮次正常出现。

**与计划的关系**

`workspace/task_plan.md` P2 拆分任务 3 明确要求
“落实共享限速、usage 统计和调用日志的归属，避免聊天绕过 bus 后漏计、后台重复计”。
限速（`ModelCallLimiter`，`lifeprism/llm/runtime/limiter.py`，在
`lifeprism/llm/runtime/provider.py:61-62` 对聊天与后台统一生效）与 usage 统计
（`service.py:238-241` + `_save_usage`）已落实；**调用日志未落实**。

**备注**：聊天绕过 bus 后，原 `Context.build_system_prompt(inbound_msg)` 的
`system_prompt` 参数在新链路也没有等价来源。若恢复记录，需要决定
`system_prompt` 取自 `register_prompts` 注册的 sections，还是允许该字段为空。

---

## 二、低风险观察

### O1 聊天 Session 槽位无淘汰，长期运行内存单调增长

**证据**

- `lifeprism/llm/runtime/service.py:129-130`：同 `session_id` 命中缓存直接返回。
- `lifeprism/llm/runtime/service.py:244-246`：仅 `message.type != MessageType.CHAT`
  时才 `self._slots.pop(sid, None)` 并关闭上下文。
- 因此每个聊天会话在 `self._slots` 中常驻一个 `AgentContext`
  （含 `EventService`、`Session`（含完整消息历史）、持久化 worker、`ProviderAdapter`）。
- 全量释放只在 `AgentRuntime.close()`（`service.py:279-297`），而它由
  `AgentBusWorker.loop()` 的 finally 在应用关闭时调用
  （`lifeprism/llm/runtime/worker.py:48-51`）。

**触发条件**

桌面端长时间不重启，用户反复“新建对话”或与大量不同会话交互：
`len(runtime._slots)` 只增不减，每个槽位持有该会话的全部消息历史于内存。

**说明**：聊天会话需要跨轮复用上下文，保留槽位本身是设计意图；缺失的是上限或
空闲淘汰策略。当前无任何证据表明它已造成故障，故列为观察而非缺陷。

### O2 `ProviderAdapter` 绕过 myagent 规定的唯一解析入口（当前无害）

**证据**

- myagent 契约：`D:/desktop/软件开发/agent/src/myagent/agent/core/provider.py:39-48`
  规定 `from_wire` 是唯一构造路径，理由写明“否则会出现某条路径没解析的漏网”。
- 实际实现：`lifeprism/llm/runtime/provider.py:130-138` 直接构造 `RawToolCall`，
  `arguments` 传拼接后的原始 JSON 字符串；`provider.py:141-148` 的 XML 回退路径同样直接构造。
- 兼容原因：`ToolRegister.parse_call`（myagent `.../core/tool/register.py:258-295`）
  对 `str` 形态会自行 `json.loads`，失败时回喂 PARSE_* hint，因此链路可用。
- 现有测试把该行为固化为期望：
  `test/core/unit/llm/test_myagent_provider.py:75`
  `assert final.tool_call_requests[0].arguments == '{"text":"hello"}'`。

**风险**：一旦工具层或护栏按文档假设“非 str 必然是 dict”，此路径会静默退化。
当前无触发场景，列为观察。

### O3 前端：首个 token 到达前中止会留下永久“输入中”气泡

**证据**

- `frontend/core/components/Chatbot/components/ChatPanel.tsx:171`
  创建占位消息时 `{ isLoading: true }`。
- 只有三条分支会清掉它：`content`（197 行）、`done`（209 行）、`error`（229 行）。
- 停止按钮 `handleStop`（250-256 行）只调用 `abortController.abort()`，不清 `isLoading`。

**触发条件**

提交消息后、任何 `content` 事件到达前点击“停止生成”：
该 AI 气泡保持 `isLoading=true` 且 `text===''`，渲染分支（613-618 行）持续显示跳动点。
后端此时已正确取消本轮（`runtime/service.py:228-231`），只是前端没有终态。

**说明**：此行为在迁移前已存在（`done` 分支改动只新增了覆盖最终文本），
迁移未引入也未修复，列入观察供后续决定。

---

## 三、明确延后，不计为遗漏

按 `workspace/task_plan.md`，以下范围本次不评审为缺口：

- P3（`task_plan.md:85-95`）：工具熔断阈值与模式、loop IoC、重试与退避、
  现有 provider 错误树到 myagent 错误分类的映射。
  审查侧确认现状与计划一致：`lifeprism/llm/runtime_tools/` 全部工具使用
  `Tool.__init__` 默认值（`max_consecutive_failures=None`，即不熔断，
  见 `test/core/integration/test_myagent_runtime.py:229-238` 的断言），
  与旧 `loop.py` 硬编码 `MAX_TOOL_ERROR_COUNT = 5` 不同 —— 这是计划第 7、10 条的
  有意选择，非缺陷。
- P4（`task_plan.md:97-107`）：会话列表/历史/改名/删除、会话查询工具、
  `process_session_message` 独立进度字段。
  现状与计划一致：`lifeprism/server/services/chatbot_service.py:27-41` 四个会话接口
  统一返回 HTTP 501，消息文案明确指向 P4；
  `lifeprism/llm/function/agent_schedule_job.py` 的 `extract_from_chat_messages`
  改为 `NotImplementedError`，`schedule_service` 不再注册该 interval 任务，
  并在 `lifeprism/server/services/schedule_service.py:136-143` 留下恢复注释。

---

## 四、已核验通过项（含证据）

### 1. 生产导入不再指向旧内核

- `grep -rn "lifeprism\.llm\.agent" --include=*.py lifeprism/` 命中仅 2 处，
  且都在 `runtime_tools/` 的文档字符串里说明迁移来源
  （`lifeprism/llm/runtime_tools/__init__.py:1`、
  `lifeprism/llm/runtime_tools/base.py:3`），非导入语句。
- `grep -rn "deprecated_agent" --include=*.py lifeprism/`（排除该目录自身）无命中。
- 生产侧对 `lifeprism.llm.session` 的导入为 0。
- 运行入口已切换：`lifeprism/server/main.py:515` 与
  `lifeprism/server/bootstrap.py:90` 均导入
  `lifeprism.llm.runtime.worker.agent_loop`。
- 聊天/微信改为直连 Runtime：`lifeprism/llm/chat/chat_bot.py:15,22`、
  `lifeprism/llm/channel/wechat/channel.py:530`。
- 残留仅为注释/文档字符串，无功能影响：
  `lifeprism/server/api/system_api.py:31,89`（仍写“取消 AgentLoop”）、
  `lifeprism/llm/bus/events.py:17`、`lifeprism/llm/channel/wechat/channel.py:490`、
  `lifeprism/server/services/sync_service.py:258`、`lifeprism/sync/sync_client.py:436`。
  建议顺手改掉 `system_api.py` 的两处表述，避免误导排障。

### 2. 取消与关闭

- `AgentRuntime.close()` 先取消消费者再取槽位锁（`service.py:282-295`），
  顺序正确，不会与持有 `slot.lock` 的运行中 `_stream` 死锁；
  已有测试覆盖：`test_myagent_runtime.py:241-260`（关闭取消活跃订阅者、无死锁）。
- 消费者中止会取消内部 turn 任务并落 `interrupted` 终态：
  `service.py:228-233`，测试 `test_myagent_runtime.py:157-173`。
- 后台等待者取消会连带取消执行：`AgentBusWorker._dispatch` +
  `lifeprism/llm/bus/queue.py:49-56` 的 `bind_execution`，
  测试 `test_myagent_runtime.py:263-291`。
- 关闭时即使本轮失败/取消也补写持久化与 usage：
  `service.py:234-243`（异常被降级为 warning，不吞主流程）。
- 订阅注册/注销成对：`service.py:158-165`（`finally` 中 `discard`）。
- worker 可重启：`worker.py:27-51` + `service.py:112-118`（`start()` 重建 limiter），
  测试 `test_myagent_runtime.py:294-311`。
- provider 流在取消时确保关闭：
  `lifeprism/llm/runtime/provider.py:124-125`（`finally: await stream.aclose()`），
  底层 `litellm_provider.py:375-381`、`custom_provider.py:130-136` 同样有 finally 关闭。

### 3. 工具失败契约

- 边界归一化集中在 `lifeprism/llm/runtime_tools/base.py:39-77`：
  `"Error: "` 前缀 → `ToolResult.error(..., TOOL_EXECUTION)`；其余 str 视为成功；
  dict/list 序列化为 JSON 字符串。
- 与旧实现语义一致：旧 `loop.py:173` 的
  `is_error = isinstance(result, str) and result.startswith(ERROR)`，
  即旧实现同样不把 `{"error": ...}` 字典计为失败。
  `runtime_tools/filesystem.py` 中返回 `{"error": ...}` 的位置
  （360/369/401/404/407/832/834/858/860/870/1023/1029/1130 行）
  与旧文件逐条对应，属**保留行为而非回归**；代价是这类业务级失败不参与熔断计数。
- 熔断参数全部保持默认：`test_myagent_runtime.py:229-238` 断言
  `max_consecutive_failures is None` / `schema_hide` / `raise_on_break is False`。
- 异常路径由 `ToolRegister._execute` 兜底为 `TOOL_EXECUTION`
  （myagent `register.py:375-382`），不会把工具异常抛穿到 loop。

**已知潜伏项（当前不可达）**：`lifeprism/llm/runtime_tools/web.py:288-317`
的 `WebFetchTool.execute` 在命中图片时返回 `list[dict]`（多模态块），
不套 `normalize_tool_result`；一旦被注册，`ToolRegister._execute`
（myagent `register.py:367`）会走 `ToolResult(content=str(raw))`，
图片结构被字符串化。当前
`lifeprism/llm/runtime_tools/__init__.py:139-148` 的 `build_tools` 不注册任何 web 工具，
故不可达。恢复 web 工具注册前必须修此路径。

### 4. 前端 SSE

- 后端只发真实增量：`lifeprism/server/services/chatbot_service.py:63-64`
  把 `event.text` 映射为 `content` 事件的 `message`。
- `done` 事件带最终正文与 usage：`chatbot_service.py:68-74`；
  前端据此覆盖整轮文本、避免把工具中间内容拼进终稿
  （`ChatPanel.tsx:201-223`）。
- 关联字段完整透传：`run_id/turn/step/seq/data` 在
  `lifeprism/server/schemas/chatbot_schemas.py:127-132` 定义、
  `frontend/core/components/Chatbot/api.ts:236-241` 解析、
  `types.ts:67-76` 声明，三处一致。
- 会话相关接口已显式降级为 501 而非静默回退旧内核
  （`chatbot_service.py:27-41`），前端禁用历史入口并注明
  （`ChatPanel.tsx:483-490`），与 P1 验收“避免静默回退”一致。

### 5. provider 原始流

- 契约一致：`ProviderAdapter.stream_chat` 在正常耗尽时恰好产出一个
  `LLMResponse`（`lifeprism/llm/runtime/provider.py:149-155`），
  与 myagent `provider.py:245-261` 的契约文字一致。
- 未正常结束不谎报成功：无 `finish_reason` 抛错
  （`provider.py:126-127`），测试 `test_myagent_provider.py:90-97`。
- 双通道（正文/推理）分别产出增量块：
  `provider.py:93-100`，测试 `test_myagent_provider.py:78-83`。
- 截断标记按 `finish_reason == "length"` 设置，且原始参数串保留：
  `provider.py:130-138`，测试 `test_myagent_provider.py:100-122`。
- 底层 provider 只出原始 chunk、不做重试（符合 P1 任务 4 的分工）：
  `custom_provider.py:116-136`、`litellm_provider.py:361-381`。
- 限速在流式入口统一生效，聊天与后台共用同一 limiter 实例：
  `provider.py:61-62` + `service.py:105`。

### 6. 打包与依赖

- `pyproject.toml`：`requires-python` 升到 `>=3.12`（与 myagent 的
  `class AgentPolicySpec[T]` PEP 695 语法一致），ruff/mypy target 同步为 3.12。
- 打包排除弃用目录：`[tool.setuptools.packages.find] exclude = ["lifeprism.llm.deprecated_agent*"]`；
  `lifeprism.spec:127` 也把 `lifeprism.llm.deprecated_agent` 加入 excludes，
  同时把 myagent 子模块加入 hiddenimports（`lifeprism.spec:103-109`）。
- **待验证项**：`[tool.uv.sources] myagent = { path = '../agent', editable = true }`
  指向仓库外的相对路径。PyInstaller 打包机上该路径必须存在，否则冻结流程会失败。
  本次未运行打包，无法确认；建议在正式归档前跑一次冷冻验证。

### 7. 本轮附带清理

- `lifeprism/llm/bus/queue.py` 中 `_wait_for_rate_limit`、
  `_rate_timestamps` / `_rate_lock` / `_last_request_at`、
  `RATE_LIMIT` / `RATE_WINDOW` / `RATE_SAFETY_FACTOR` 及 `time` / `deque` 导入已删除；
  删除前确认这些符号在 `lifeprism/` 内仅自引用（无外部调用方）。
- 对指定路径运行 `ruff check --fix`（修 14 项）与 `ruff format`（重排 10 个文件），
  两者最终均为 clean；未触碰 `deprecated_agent`。

---

## 五、收尾复审（第二轮，2026-10-03）

范围：`lifeprism/llm/runtime/{service,worker,limiter,provider}.py`、
`test/core/integration/test_myagent_runtime.py`、
`test/core/unit/llm/test_message_queue_rate_limit.py`。
依据：`docs/adr/2026-10-03-myagent-runtime.md`、`docs/specs/2026-10-03-myagent-runtime-spec.md`。
方式：只读复审，未修改 runtime 源码。

### 5.1 D1 已闭环：聊天调用日志

D1 遗留的取值问题（`system_prompt` 从哪来）已确定：直接取 myagent 原生
`request/header` 快照，不再从旧 `Context` 反推。

- 采集：`service.py:57-70`，`_AgentSlot.on_record` 在 `record.type == "request/header"`
  时把 `record.data` 存入 `slot.header`。
- 落盘：`service.py:284-295`，`_log_chat` 用 `header.system_prompt` / `header.model_name`
  填充 `log_call` 的 `system_prompt` / `model`。
- 快照字段真实存在：myagent `agent/core/session/types.py:46-50` 定义
  `RequestHeaderData.model_name` / `.system_prompt`，由 `agent/core/agent/loop.py:552-553`
  写入，经 `agent/core/session/session.py:211` 的 `SESSION_EVENT` 广播到订阅方。

**聊天只记录一次**：记录点 `service.py:243-249` 位于 `_stream` 的 `finally`，
单个 turn 只经过一次，门槛为 `message.type == MessageType.CHAT and result is not None`。
`result` 仅在成功产出 `done` 时赋值（`service.py:219-222`），
所以失败/取消（`result is None`）与客户端中断（生成器关闭时 `finally` 提前执行）
都不写日志，不存在半条记录。

**后台不重复**：后台走 `bus.send` → `AgentBusWorker._dispatch` → `runtime.execute`
（`worker.py:19-25`），消息类型为 `GENERAL_TASK` / `DREAM_TASK`，
被 `service.py:243` 的类型判断挡下；`llm_call_logger.log_call` 仅由
`lifeprism/llm/function/agent_schedule_job.py:99,176,275` 与 `diary_summary.py:113`
在拿到结果后各调一次。全仓 `log_call` 调用点已 grep 核对，聊天侧只有
`service.py:288` 一处，无第二写入点。

本地聊天与微信同属 CHAT：`lifeprism/llm/chat/chat_bot.py:15,22`、
`lifeprism/llm/channel/wechat/channel.py:516-530`，两条入口命中同一条记录路径。

回归覆盖：`test_myagent_runtime.py:336-356` —— 聊天后 `len(logged) == 1`，
再跑一轮后台仍为 1，并断言 `system_prompt` 非空、`model == "fake"`、
`inbound_msg.session_id` 已替换为新会话 ID。

### 5.2 `_prepare_slot` 失败清理

`service.py:181-187`：准备阶段抛错时，`is_new` 或非 CHAT 的槽位执行
`_slots.pop` + `_close_slot`，其余（既有聊天会话）保留。判断合理：
新建槽位准备失败等于未建立，必须回收；既有聊天会话保留才能跨轮复用上下文。
且下一轮 `_prepare_slot` 先 `unregister(tool_list())` 再 `register(...)`
（`service.py:265-268`），上次注册即使只完成一半也会被纠正，可自愈。

覆盖：`test_myagent_runtime.py:318-333` 断言 `GENERAL_TASK` 准备失败后 `not runtime._slots`。

**观察（非缺陷）**：既有 CHAT 会话的准备失败分支无测试覆盖。该分支不回收槽位，
符合 ADR「聊天 context 继续保留」的取舍，但缺一条回归。

### 5.3 worker 启动与 Runtime 重启

- `AgentBusWorker.loop()` 在置位 `_running` 之前调用 `self._runtime.start()`
  （`worker.py:31`），启动失败不会留下半启动状态。
- `AgentRuntime.start()`（`service.py:117-123`）仅在 `_closing` 为真时动作：
  先确认 `_slots` / `_tasks` / `_consumers` 均已清空，否则抛
  `RuntimeError("Agent Runtime 尚未完成关闭")`；通过后重建 `ModelCallLimiter` 并复位 `_closing`。
  首次启动 `_closing` 为假，属无操作，limiter 已在 `__init__`（`service.py:110`）建立。
- 覆盖：`test_myagent_runtime.py:298-315` 连跑两轮 loop/停机，第二轮仍能拿到结果。

**观察（非缺陷）**：`close()`（`service.py:315-333`）未显式清空 `self._consumers`，
依赖被取消消费者在 `stream()` 的 `finally`（`service.py:169-170`）里自行 `discard`。
`close()` 用 `gather` 等它们结束，实际会被清空；但当 `close()` 由某个消费者任务自身调用时，
`service.py:318` 会把它排除在外，条目残留并会让后续 `start()` 抛错。
当前唯一调用方是 `worker.py:48-51` 的 loop 收尾，不在此列，风险不可达。

### 5.4 共享限速器

- 单一实例：`AgentRuntime.__init__` 创建 `self._limiter = ModelCallLimiter()`（`service.py:110`），
  `_get_slot` 用它构造 `ProviderAdapter(create_llm_client(), self._limiter)`（`service.py:148`）。
- 单一入口：`ProviderAdapter.stream_chat` 首行 `await self.limiter.acquire()`（`provider.py:61-62`），
  聊天与后台的每次模型调用都经此路径，故共享同一配额。
- 重启后重建：`start()` 换新 limiter；此时槽位已清空，新槽位使用新实例，无悬挂引用。
- 归属正确：bus 侧限速代码已删净，`lifeprism/llm/bus/queue.py` 中
  `RATE_LIMIT` / `_rate_timestamps` / `_wait_for_rate_limit` 等 grep 无命中。

**此前限速孤儿测试已迁移**：`test/core/unit/llm/test_message_queue_rate_limit.py`
已改写为针对 `ModelCallLimiter` 的测试（文件头注释 “Shared admission replaces the
former bus-only limiter.”，第 7 行导入 `lifeprism.llm.runtime.limiter.ModelCallLimiter`），
实测通过。原附录记录的「测试套件红灯」阻塞项已消除。

**观察（非缺陷）**：现有限速测试只覆盖 `ModelCallLimiter.acquire()` 的等待语义（1 个用例），
未断言「聊天与后台共用同一实例」这一接线事实；`test_myagent_runtime.py` 的 `make_runtime`
传了 `client_factory`，会绕过限速器，所以该接线目前只能靠读码确认。
建议后续补一条断言 `ProviderAdapter` 持有 `runtime._limiter` 的用例。

### 5.5 取消与错误路径资源收尾

- 消费者取消：`stream()` 的 `finally` 注销自身（`service.py:169-170`）；
  内层 `_stream` 的 `finally` 取消 turn 任务、`gather` 收尾、从 `_tasks` 摘除、
  清空 `slot.queue`（`service.py:227-232`）。
- 关键点：`service.py:223` 是 `except Exception`；Python 3.12 中
  `asyncio.CancelledError` 属 `BaseException`，不会被吞，取消照常向上传播，
  同时 `finally` 仍执行 —— 取消路径不漏收尾。
- 错误路径：`service.py:223-226` 产出 `error` 事件而非 `done`；
  `finally` 仍补写原生持久化与用量（`service.py:234-242`，异常降级为 warning）。
- 后台槽位：非 CHAT 无条件 `pop` + `_close_slot`（`service.py:250-252`）；
  `_close_slot` 先关 context 再关 client（`service.py:336-342`）。
- 应用关闭：`close()` 先取消消费者、再取消任务、最后在槽位锁内逐个关闭
  （`service.py:315-333`），顺序避免与持有锁的运行中 `_stream` 死锁。
- 覆盖：`test_myagent_runtime.py:161-177`（消费者中止落 `interrupted` 终态）、
  `245-264`（关闭取消活跃订阅且不死锁）、`267-295`（后台等待者取消连带停模型）、
  `180-198`（后台结束释放槽位）。

**观察（非缺陷）**：`slot.header` 只在收到 `request/header` 记录时更新，
而 `_stream` 每轮重置队列/用量/终态时未重置它（`service.py:188-192`）。
myagent 仅在首次与配置变更时写该记录（`agent/core/agent/loop.py:561-565`），
因此多轮会话中 `slot.header` 保留最近一次快照 —— 对 `_log_chat` 而言这正是
「本轮实际使用的配置」，语义正确；且记录点只在成功轮触发，首轮必已写入，不会取空值。
若后续把记录点扩展到失败轮，需重新评估该快照的时效性。

### 5.6 本轮附带：测试适配（任务 1）

`test/core/unit/llm/test_custom_records_tool.py` 由旧内核路径迁移到 runtime_tools：

- 导入改为 `lifeprism.llm.runtime_tools.base` / `.custom_records_tool`（第 19-20 行）。
- 7 处 patch 目标改为 `lifeprism.llm.runtime_tools.custom_records_tool.custom_record_repository`。
- 5 处失败断言改为 `ToolResult.is_error` + `result.content`
  （契约见 myagent `agent/core/tool/tool.py:44-67`；`normalize_tool_result` 把
  `Error: ` 前缀串转成 `ToolResult.error`，错误 JSON 位于 `content[len(ERROR):]`）。
- 成功断言保持原样（成功路径仍返回带 `Success: ` 前缀的 `str`），全部业务回归内容保留。

结果：`python -m pytest test/core/unit/llm/test_custom_records_tool.py -q` → **10 passed**。
未改动任何业务实现。同时 `test_myagent_runtime.py` + `test_message_queue_rate_limit.py`
合计 **14 passed**。

---

## 附录：queue.py 清理留下的阻塞项（已解决）

原记录：`test/core/unit/llm/test_message_queue_rate_limit.py` 是仅测试已删 bus 限速代码的
孤儿测试，删函数后必然失败（`AttributeError: ... has no attribute 'RATE_LIMIT'`），
使测试套件处于红灯状态。

**状态：已迁移。** 该文件现已改写为针对
`lifeprism/llm/runtime/limiter.py` 的 `ModelCallLimiter` 测试（见 5.4），实测通过。
无遗留红灯项。

## Codex 最后检查补充

历史用量 API 残留 get_last_token_usage 调用已通过失败测试复现，改为 await get_tokens_usage，明确返回 501。SDK stream 关闭用例覆盖两个生产 Provider，均通过。最后综合限定回归 111 项通过。

## 最终交付状态

完整 PyInstaller 构建成功，PYZ 包含 runtime 和 30 个实际使用的 myagent 模块、无弃用目录，501 修复已包含。最后格式清理后未重做冻结，仅作为模块收集验证。迁移活跃文件安全 lint 修复完成，保留原有 3 个 UP042 Enum 升级建议。pre-commit 全仓库既有 lint 债务阻挡本地提交，未绕过 hook。
