# Agent 内核迁移执行报告

更新日期：2026-10-03

## 结果与范围

P0 bootstrap 清理、P1 原生 Runtime/工具/提示词及聊天事件、P2 后台 bus 桥接与生产引用替换已实施。原目录保留为 `lifeprism/llm/deprecated_agent/`，新运行不依赖旧 Context/SessionManager/ToolRegister。完整冻结构建成功；可执行文件启动与真实渠道/供应商仍未联调，不能宣称桌面安装包已可发布。

本地与微信共用 Runtime 事件订阅，后台保留 bus。关联字段来自 myagent 已存在的 `session/event`，本轮未修改 sibling 源码。原生 UUID 新会话可继续；旧会话不迁移，会话业务 API 返回 501，前端历史入口禁用，微信历史命令提示暂不可用。

P3（熔断配置、IoC、人在回路、重试、provider 错误树）与 P4（Session 业务、查询、提取、独立处理进度）没有提前实施。基础失败传播、取消和关闭属于此次生命周期保障。

## 职责归属

| 职责 | 迁移后归属 |
| ---- | ---------- |
| ReAct、工具执行、原生记录 | myagent |
| 事件关联、终态收集、取消、同会话串行 | Runtime |
| 提示词 | myagent SystemPrompt 动态注册 |
| 工具业务、安全目录权限 | runtime_tools，继承原生 Tool |
| 模型路由、鉴权、请求参数 | 现有生产 Provider |
| 实际模型调用限速 | Runtime 共享 ModelCallLimiter |
| 全步骤 token 累加持久化 | Runtime |
| 成功聊天调用日志 | Runtime，一轮一条，原生 request/header 快照 |
| 后台调用日志 | 原任务调用方，Runtime 不重复记 |
| 后台请求响应 | AgentBusWorker 与原 bus |

## 验证证据

- 综合限定回归：`workspace/final-tests.log`，111 项通过（覆盖 Runtime、ProviderAdapter、SSE、共享限速、新工具业务、明确 501 API、资源初始化、agent-only/monitor/cloud CLI 及配置回归）。
- 新 Runtime 测试使用真实 myagent loop 与确定性假模型，不产生线上费用；验证工具中间结果不提前完成、用量累加、同会话串行、失败、断开、取消、重启和初始化失败清理。
- 核心 Runtime/工具/bus/ProviderAdapter/SSE 测试的 scoped Ruff check 与 format 通过；全部 32 个活跃迁移 Python 文件格式通过，check 剩余 3 条既有字符串 Enum 升级建议（UP042），未改变类型行为；`git diff --check` 无空白错误（只有仓库 CRLF 提示）。
- LifePrism 与 myagent wheel 构建通过，输出在 `workspace/artifacts/`。检查 LifePrism wheel 包含 runtime/runtime_tools，排除 deprecated_agent。分发需安装对应 myagent wheel；uv 本地路径源为 `../agent`。两个 wheel 在独立目录安装后，真实原生工具循环成功返回最终答复与 14 tokens 总量，确认导入来自 wheel 而非 editable 源码（`workspace/wheel-smoke.log`）。
- 前端 tsc 检查：Chatbot 范围无错误；全量检查存在 9 条其他区域错误，未扩展范围修改。
- 完整 PyInstaller：日志 `workspace/pyinstaller-build.log`。首次因环境同时收集 PyQt5/PyQt6 失败，确认后端无 Qt 使用后在 spec 中排除无关绑定，重跑成功。输出 `workspace/dist/lifeprism-backend/`，PYZ 验证包含 runtime 和 30 个实际使用的 myagent 模块、排除弃用目录，包含历史用量 501 修复。最后格式清理后未重做冻结，产物用于模块收集验证，未作正式发布包。
- 启动测试出现 Windows `0xc0000139` 原生库加载诊断（asyncssh.agent_win32 导入堆栈），进程退出码为 0、pytest 汇总通过；不能据此声称原生环境完全健康。

## 审查与修复

Claude CLI 承担限定机械任务，审查记录见 `workspace/claude-final-review.md`。Codex 审查核心执行/生命周期设计并修复：

- worker 重启时 Runtime 保持关闭状态：先复现，再增加显式 start。
- 工具注册失败留下新 context：先复现，再增加准备阶段清理。
- 聊天绕开旧入口后生产日志漏记：Runtime 补回，测试验证后台不双计。
- 原 bus 限速测试改测共享模型调用限速器。
- 历史用量路由调用旧方法：先复现，再接入新服务的 501 延后接口。
- 两个生产 Provider 的 SDK stream 在消费者断开时关闭，测试均通过。

## 当前限制与后续风险

- 尚未在线验证真实供应商、微信收发和桌面安装包启动。
- myagent 当前消息契约没有承载 Anthropic thinking blocks/供应商签名字段；依赖这些字段的模型需要专项兼容实现和验证。这是消息契约兼容问题，不能仅以 P3 错误策略解决。
- 聊天 context 当前保留至应用关闭，长期大量新建会话可能增加内存；空闲淘汰策略待后续设计。
- 未注册的 web 图片工具保留历史实现，启用前须适配多模态工具返回；本轮不扩大工具集。
- 旧历史不可用是明确阶段边界，已有用户文件未删除。P4 决定新历史管理和渠道恢复。

## 文档与交付

总体计划：`workspace/task_plan.md`。正式运行契约：`docs/specs/2026-10-03-myagent-runtime-spec.md`。架构决策：`docs/adr/2026-10-03-myagent-runtime.md`。架构地图已同步。

本地提交已尝试，但 pre-commit 的全仓库 lint 检查阻挡：除迁移文件基线问题外还有 100 条来自 32 个未改文件的既有错误。已修迁移活跃代码可安全修复项；保留归档及无关代码，未绕过 hook、未产生 commit、未推送或部署。迁移更改已暂存，原始 CLI 日志与指令未暂存。
