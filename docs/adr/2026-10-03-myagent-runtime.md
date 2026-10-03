---
version: 1.0
created_at: 2026-10-03
updated_at: 2026-10-03
last_updated: 记录已授权的 myagent 内核替换与双入口边界
abstract: 使用外部 myagent 执行所有 Agent 轮次，聊天订阅原生 session 事件，后台保留 bus 请求响应桥接，旧会话业务与错误策略分别延后。
status: decided
---

# myagent 内核与消息入口

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 记录内核迁移决策 |

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

原生会话与旧历史结构不同。当前历史列表、改名、删除、查询、提取等入口明确暂不可用；不以旧内核回退掩盖迁移边界。原生记录承担运行 trace；Runtime 为成功聊天保留一次生产调用日志，后台调用方保留原有日志，避免双计。

## 后续边界

P3 单独决定工具熔断配置、loop IoC、人在回路、重试、退避与生产 provider 错误树；当前只传播失败和执行取消。P4 决定会话业务、旧历史与 `process_session_message` 独立处理进度字段。

供应商专属消息字段（如 Anthropic thinking blocks）不在当前 myagent 核心消息契约中，须另行完成兼容验证；不应将通用 OpenAI stream 测试视为全部模型验证。

## 契约

见 [myagent Runtime 规格](../specs/2026-10-03-myagent-runtime-spec.md)。实施记录位于仓库 `workspace/`。
