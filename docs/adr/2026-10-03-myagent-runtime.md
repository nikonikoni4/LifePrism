---
version: 1.4
created_at: 2026-10-03
updated_at: 2026-10-08
last_updated: 默认会话根目录收敛为 session
abstract: 使用外部 myagent 执行所有 Agent 轮次，聊天订阅原生 session 事件，后台保留 bus 请求响应桥接，旧会话业务与错误策略分别延后。
status: decided
---

# myagent 内核与消息入口

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 记录内核迁移决策 |
| 1.1 | Session 先按归属隔离目录，再实施会话管理 |
| 1.2 | 聊天目录统一为 chat/<session_id>，channel 不参与归属 |
| 1.3 | 恢复前端聊天管理，工作流仍作为独立 API 请求记录 |
| 1.4 | 默认会话根目录收敛为 session |

## 问题与约束

旧 AgentLoop、Context、ToolRegister 与 myagent 重复。myagent 的 ReAct turn 不返回业务答复，最终结果必须从原生 Session 事件获取。用户授权 P1/P2 迁移，保留原 agent 源码供追溯，不兼容旧会话，不提前设计错误策略。

## 决策

- 直接依赖 `myagent==0.1.0`；本地开发由 uv 路径源指向 `../agent`。Python 最低版本对齐为 3.12。分发需先提供对应 myagent 包，wheel 不包含 sibling 源码。
- `lifeprism/llm/runtime` 是业务适配层。Runtime 负责事件关联、同会话串行、最终答复投影、共享模型限速、用量统计及生命周期；ReAct、原生 Session、ToolRegister 和提示词组装由 myagent 负责。
- 本地聊天与微信直接调用 Runtime 事件路径。后台任务继续通过 bus 提交，由 AgentBusWorker 消费并收集同一事件路径的最终结果。bus 不参与聊天、工具调度或模型限速。
- 订阅 `session/event` 的完整记录，以 `run_id/session_id/turn/step/seq` 关联事件。只有执行任务完成且本轮 `turn/end` 成功才输出 `done`；中间 assistant 消息不代表完成。已存在所需事件字段，因此本阶段不修改 myagent 事件源码。
- 工具继承原生 Tool，业务返回值转为 ToolResult，全部保留默认熔断配置。提示词通过 SystemPrompt section/context/reminder 注册；自定义规则仍由 reminder 以 user role 注入，承接既有 custom prompt ADR。
- 原目录归档为 `deprecated_agent`，不进入生产执行或打包。旧 SessionManager 留存但新运行不引用它。bootstrap 从模板、提示词和工具注册中移除，用户已有文件不删除。
- 应用拥有 Runtime 启停；取消订阅或 bus 请求会取消对应 turn，并完成原生记录持久化。后台一次性 context 结束后释放，聊天 context 继续保留。

## 取舍

保留 bus 有利于维持后台请求响应契约；让聊天继续走 bus 则需要额外流式桥接并重复关联事件。双入口共享一个 Runtime，可保留后台解耦并让聊天直接消费真实增量。

原生会话与旧历史结构不同。前端管理已恢复原生聊天的列表、历史、改名、删除和继续；旧历史、会话查询工具与提取仍暂不可用。原生记录承担运行 trace；Runtime 为成功聊天保留一次生产调用日志，后台调用方保留原有日志，避免双计。

## 后续边界

P3 单独决定工具熔断配置、loop IoC、人在回路、重试、退避与生产 provider 错误树；当前只传播失败和执行取消。P4 决定会话业务、旧历史与 `process_session_message` 独立处理进度字段。

供应商专属消息字段（如 Anthropic thinking blocks）不在当前 myagent 核心消息契约中，须另行完成兼容验证；不应将通用 OpenAI stream 测试视为全部模型验证。

## Session 归属决策（2026-10-07）

用户授权先建立类别与工作流目录归属，再实现 Session 管理。新增可选 workflow_id，只负责稳定的工作流归属；type 保留工具及提示词选择职责，token_type 保留统计职责。工作流每次执行仍有独立 run_id，一个 workflow_id 可包含多个 session_id。

业务 Runtime 使用 myagent 的 SessionStore(flat=True)，指定最终目录；提供 workflow_id 时使用 workflows/<workflow_id>，普通聊天统一使用 chat/<session_id>.jsonl。未指定归属的后台请求保留 tasks 兼容目录，生产工作流显式传入 ID。类别从是否指定工作流及聊天入口推导，不新增需要调用方同时维护的冗余类别字段。

聊天目录不按 local/wechat 渠道细分（2026-10-07 调整）：同一用户通过不同渠道进入的是同一段聊天，渠道只决定消息收发路由与事件字段；业务存储归属只按 chat/workflow/task 分类。因此本地与微信可以在同一 session 内继续同一段对话，channel 不参与目录归属校验。

采用原生 JSONL 文件直接置于归属目录，而不是为每个 Session 再建一层文件夹；这与 myagent 已有持久化接口一致。目录归属由业务层控制，不扩展目前无法恢复自定义字段的原生 metadata。拒绝跨归属恢复和缓存复用，不扫描全目录寻找同名 ID。

默认存储根目录定在数据目录下的 session，避免重复 localData，并消除项目路径编码对会话定位的影响。Runtime 以 `session_root` 属性集中解析该根，聊天与工作流两条路径共用，防止默认根表达式分散后漂移；注入替代根目录的规则不变。旧目录与已有数据不自动移动；提取进度仍作为后续任务。

## 前端聊天管理决策（2026-10-07）

Session 管理器仅面向前端聊天，限定 chat 目录。workflow 每次视为独立 API 请求，不进入前端列表或通用续执行接口；不扫描其他目录判断 Session 去向。

用户选择永久删除，无回收站和恢复。执行或排队中的 Session 禁止删除，前端禁用按钮且后端独立返回 409；空闲缓存必须先关闭 context 和持久化 worker 再删除文件。管理期间阻止该 Session 开始新轮次，避免已删除文件被 worker 重建。改名沿用空闲限制并原子替换文件头，防止旧缓存名称覆盖新名称。

聊天历史投影用户消息与每轮最终 assistant 答复，工具中间步骤保留在原生账本，不作为重复答复显示。

## 契约

见 [myagent Runtime 规格](../specs/2026-10-03-myagent-runtime-spec.md)。实施记录位于仓库 `workspace/`。
