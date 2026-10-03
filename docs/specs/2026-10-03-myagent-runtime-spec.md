---
version: 1.0
created_at: 2026-10-03
updated_at: 2026-10-03
last_updated: 定义 myagent Runtime 聊天与后台执行契约
abstract: 原生 Agent 执行、事件关联、最终答复、工具和提示词注册、共享用量统计，以及暂不可用的会话业务边界。
---

# myagent Runtime

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建迁移后运行契约 |

## 业务意图

聊天和后台 Agent 任务使用同一个 myagent 内核，避免维护两套 ReAct、工具注册和上下文系统。用户可创建原生新会话并在当前会话继续聊天；本地流式输出与微信最终答复采用同一个订阅结果来源。

## 执行契约

Runtime 接收现有 InboundMessage（内容块、场景、渠道、可选 session_id、extra 和用量类别）。新会话创建原生 UUID；已有会话只接受可加载的原生 Session，旧 ID/旧文件明确拒绝。同会话串行，不同会话可并行，共享实际模型调用限速。

`stream` 返回 RuntimeEvent：`type/run_id/session_id` 必填；`turn/step/seq` 可为空；`text` 默认空字符串，`data` 默认空对象；`result` 仅用于完成事件，包含现有 OutboundMessage。原生 chunk 投影为 content/reasoning 等事件，工具调用与结果携带原生记录数据。

`done` 必须满足执行任务结束且本轮终态成功；结果文本使用最后一次 assistant message，用量累加本轮所有完成的模型步骤。失败输出 error，不输出 done。取消结束 turn，不生成成功结果。用量持久化保留已完成步骤，即使后续失败或取消。成功聊天在 Runtime 记录一次生产调用日志，提示词及模型取原生 request/header；后台日志由现有任务调用方记录，避免重复。

`execute` 收集上述事件得到 OutboundMessage；错误抛出 RuntimeError。后台 worker 将异常转为 OutboundMessage.error，bus 等待者立即失败。请求取消/超时取消对应后台执行。

## 本地 SSE 契约

`POST /chatbot/chat/stream` 保留已有请求结构。ChatStreamEvent 字段：`type` 必填（session/status/content/done/error）；`node/message/session_id/session_name/is_new_session/error/run_id/turn/step/seq/data/usage` 可为空。session 提供原生会话 ID；content 为真实文本增量；status 表示 tool/call 或 tool/result；done.message 为最终答复，覆盖中间累积文本，usage 为 input_tokens/output_tokens/total_tokens 的本轮总量。

客户端断开通过关闭事件生成器取消模型任务。会话列表、历史、改名、删除和历史用量接口返回 HTTP 501；前端历史入口禁用。微信 `/new` 清空渠道会话引用，下次创建原生会话；`/continue` 与 `/session-list` 提示暂不可用。

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
- [ ] 真实微信收发与在线供应商联调。
- [ ] 供应商专属 thinking blocks/signature 消息兼容验证。

## 后续范围

P3 错误策略及 P4 会话业务另行设计。当前不提供旧会话迁移、会话查询工具、会话信息提取或 `process_session_message` 进度管理。

设计依据：[myagent 内核 ADR](../adr/2026-10-03-myagent-runtime.md)。


<key_function>
- lifeprism/llm/runtime/service.py
  - service.AgentRuntime.start:117
  - service.AgentRuntime.stream:161
  - service.AgentRuntime.execute:270
  - service.AgentRuntime.close:315
- lifeprism/llm/runtime/worker.py
  - worker.AgentBusWorker.loop:27
- lifeprism/server/api/chatbot_api.py
  - chatbot_api.chat_stream:152
</key_function>
