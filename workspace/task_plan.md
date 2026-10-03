# Agent 内核迁移总体计划

更新日期：2026-10-03

## 当前状态

P0/P1/P2 代码迁移与限定验证完成。Windows 冻结构建成功，在线供应商、真实微信和可执行文件启动尚未联调；本地提交被既有全仓库 lint 阻挡。用户已明确授权整个执行过程无需审批，并要求简单机械任务优先使用 Claude CLI，复杂架构与函数改造由 Codex 完成。超过 3 个文件的修改先拆分为小任务。

## 目标

将 LifePrism 原 Agent 执行内核全部替换为外部 `myagent` 包，保留原 agent 目录并改名标记为已弃用。本地聊天与微信通过事件注册和订阅获取输出，后台任务保留 bus，并由统一 Runtime 接入 myagent。

迁移工作资料统一放在项目根目录 `workspace/`。本文件维护总体范围、优先级、阶段验收与进度；具体实施方案、接口约定和验证记录后续按阶段写入此目录。

## 已确认的架构与范围

1. myagent 项目根目录为 `D:/desktop/软件开发/agent`，包源码位于 `src/myagent`。直接以包依赖引入，不复制一份内核到 LifePrism。
2. 原 `lifeprism/llm/agent/` 保留为弃用目录，具体目录名在实施方案中确定；正式运行链路不再依赖旧内核。
3. 本地聊天和微信的输入、输出不经过 bus，统一通过 Runtime 提交和事件订阅消费输出。
4. 后台任务保留现有 bus 的提交与最终结果通道，由 Runtime 桥接 myagent 事件到最终回复。
5. 旧 Session 与 SessionManager 不再作为新内核依赖。不做旧会话格式适配或数据迁移；P1 仅使用 myagent 原生 Session 支撑执行与事件记录。
6. 移除旧 Tool 基类和 ToolRegistry 的运行依赖；业务工具继承 myagent Tool，并使用其 ToolRegister。
7. 工具的熔断配置当前全部使用 myagent 默认值，不迁移旧配置、不定制策略。
8. 移除旧 Context 组装机制，全部使用 myagent SystemPrompt 注册机制。装配方式参考 lifeprismevalue，不直接引入评测环境的业务依赖。
9. bootstrap 机制全部移除，优先级 P0。用户数据中的 bootstrap 文件不因代码清理自动删除。
10. 错误策略统一留到 P3，包括工具熔断配置、loop IoC、人在回路、重试、退避，以及现有 provider 独特错误树的衔接。
11. Session 专项留到 P4，尤其是 `process_session_message` 的独立处理进度字段及提取流程。
12. P1/P2 需要保证异常、取消和运行结束能够让订阅者或等待者收尾并释放资源；这不包括错误认领和重试策略设计。

## 阶段与进度

- [x] 确认总体架构、优先级与延后范围。
- [x] 建立 workspace 总体计划。
- [x] P0：移除 bootstrap 机制。
- [x] P1：替换执行内核、工具与提示词装配，打通聊天事件链路。
- [x] P2：接通后台 bus，完成正式运行切换与旧内核归档。
- [ ] P3：统一错误策略。
- [ ] P4：处理 Session 业务与会话信息提取。

### P0：移除 bootstrap

任务：

- 清理 bootstrap 提示词加载分支和回退逻辑中的 bootstrap 判断。
- 移除 DeleteBootstrapTool 的正式注册与使用，以及对应配置引用。
- 调整相关测试和行为说明，保留正常 identity/soul/agent/tool 等提示词能力。
- 检查 myagent 新装配方案，确保不重新引入 bootstrap。

验收：正式运行链路不再加载、注册或执行 bootstrap 机制；不删除用户数据文件。

### P1：新内核与聊天事件

拆分任务：

1. 依赖与基础装配：引入 myagent 包，检查 Python 版本与运行环境，建立 AgentContext 工厂及 Runtime。
2. 工具迁移：迁移生产业务实现的继承和构造初始化，按场景注册工具集合；失败结果转换为 myagent ToolResult，所有熔断参数保持默认。
3. 提示词注册：用 section、system reminder 和适合的运行时注册能力替代 Context；迁移技能发现、动态文件读取和参数注入。
4. Provider 最小衔接：满足 myagent 模型接口与流式消息契约，保留所需生产 provider 能力；错误树、重试职责和 IoC 策略设计留 P3。
5. 事件输出：补足必要 payload 和运行关联，统一文本增量、工具过程、终态及最终结果的投影。
6. 聊天渠道：本地聊天和微信改为调用 Runtime 并订阅事件；本地 SSE 输出真实增量，微信按渠道能力消费事件并发送回复。

验收：

- 聊天与工具循环实际由 myagent 执行，不调用旧 loop、Context 或 ToolRegistry。
- 本地聊天与微信不使用 bus 收发聊天内容。
- 同会话运行与不同会话事件能够正确关联，终态依据本轮完成记录判断，中间 assistant 消息不被误当最终结果。
- 完成、异常和取消均能收尾；事件订阅和异步资源有明确生命周期。
- 新执行只使用 myagent 原生 Session，不读取旧会话文件。

明确延后：旧会话兼容、会话管理 API 的完整迁移、会话查询工具、会话信息提取、错误策略定制。具体切换方案应列明这些旧入口的暂不可用处理，避免静默回退到旧内核。

### P2：后台与正式运行切换

拆分任务：

1. bus 消费者：用 Runtime 替换旧 AgentLoop 消费执行，保持后台调用所需最终结果契约。
2. 后台入口：迁移分类、总结、截图分析、记忆更新、同步合并等 bus 执行路径；`process_session_message` 及依赖旧 session 的信息提取不在本阶段迁移。
3. 公共运行职责：落实共享限速、usage 统计和调用日志的归属，避免聊天绕过 bus 后漏计、后台重复计；不扩展为 P3 错误策略设计。
4. 生命周期：替换主服务、agent-only、bootstrap 启动模块、独立脚本等旧 loop 启停引用，关闭时结束执行并完成必要持久化收尾。
5. 正式归档：将原 agent 目录改名为弃用目录，正式工具放入独立目录，清理运行导入，检查依赖及 PyInstaller 打包。
6. 更新相应测试与正式架构文档；进入 docs 前按项目文档规则读取导航和写入规则。

验收：所有正式 Agent 执行入口使用新内核；后台 bus 的正常结果和失败收尾可用；正式运行链路不导入弃用 agent；启动、关闭和打包链路完成验证。P4 范围内的入口明确延后，不冒充已迁移完成。

### P3：错误策略专项

在 P1/P2 完成后，基于实际集成结果重新提出方案：

- 工具熔断阈值、模式、触发行为及配置归属。
- myagent loop IoC 控制反转：人在回路、错误认领、重试、退避、预算处置等。
- 现有 provider 独特错误树与 myagent 错误分类的映射。
- provider 与 loop 的重试职责，避免叠加重试和错误信息损失。
- 相应策略测试与可观测性。

验收：错误类别、处理责任与终态行为有明确契约，关键策略有针对性验证。当前不预设最终策略。

### P4：Session 专项

在前述阶段完成后单独设计：

- 新会话列表、历史展示、改名、删除与渠道恢复命令。
- 新会话查询工具与持久化查询接口。
- `process_session_message` 的独立处理进度字段、存放位置及更新规则；不修改 myagent 核心记录来混入未经讨论的业务字段。
- 基于新 session 记录的对话提取、增量处理及与 ChatHistory/记忆任务的衔接。
- 旧 session 数据是否需要展示或迁移，届时再讨论；当前没有迁移承诺。

验收：会话业务及提取进度设计完成并验证，不依赖旧 SessionManager。

## 实施纪律与验证

- 2026-10-02 用户授权执行 P1–P2，无需逐步审批；P0 bootstrap 清理作为迁移前置工作，P3/P4 不提前实施。
- 修改超过 3 个文件先分解小任务；实施前按需加载编码规则、规格与相关目录导航。
- 修改 myagent 项目源码前读取该项目的 AGENTS.md 与适用规则。
- 每个阶段保留具体修改范围、验证结果、风险与未完成项；有代码变化后列明实际风险。
- 测试重点是事件关联与终态、工具失败语义、提示词动态更新、bus 结果桥接、启动关闭和打包；按阶段运行相关检查。
- 不改动与迁移无关的已有工作区修改。

## 已落实的设计

- 旧目录 `deprecated_agent`；生产工具 `runtime_tools`；执行适配 `runtime`。
- 依赖固定 `myagent==0.1.0`，uv 开发源 `../agent`，Python >=3.12；独立 wheel 分发已验证。
- 同会话 context/锁串行执行，后台一次性 context 结束即释放；聊天 context 保留到应用关闭。
- `session/event` 已包含完整记录，无需再修改事件源码；Runtime 增加 run_id，保留原生 session_id/turn/step/seq。
- 提示词 section/context/reminder 每次模型调用动态读取文件；配置在 turn 开始刷新。
- ProviderAdapter 消费生产 provider 原始 stream，保留生产路由与鉴权；不复制评测 provider。
- P4 旧业务明确 501/渠道命令提示，不静默回退；供应商专属消息字段兼容仍需专项实现与验证。

## 工作记录

- 2026-10-02：完成初步源码检查与范围讨论，建立总体计划；未实施代码修改，未运行测试。

## 已知调查差异

- myagent 包不在项目根目录下的 `myagent/`，实际位于 `src/myagent/`。
- LifePrism 当前 `docs/design-decisions/index.md` 不存在；后续写正式架构决策前需按实际文档导航确定目录。

## 执行记录（2026-10-03）

- Claude CLI 分别完成工具迁移、provider 请求参数抽取与 stream 接口、生产引用切换、旧目录归档、前端与测试机械适配、限定范围 lint 和复审；Codex 完成 Runtime、终态/取消、提示词注册、ProviderAdapter、bus 桥接与生命周期编排。
- 原内核正式归档为 `lifeprism/llm/deprecated_agent/`，生产执行不导入该目录。新工具位于 `runtime_tools/`。
- 复用 myagent 现有 `session/event` 完整记录，不需为字段再次修改 sibling 源码。
- 聊天和微信直接消费 Runtime 事件路径；后台 bus worker 保留请求响应。旧会话业务接口明确 501；`process_session_message` 不注册。
- 已修复 worker 重启、新 context 初始化失败资源残留、聊天调用日志漏记；日志只在成功聊天 Runtime 记录一次，后台保留调用方日志。
- 最新限定回归 111 项通过；共享限速器、原生 loop、工具终态、SSE 断开、取消、资源初始化与启动覆盖在内。完整验证结果及限制见 `workspace/execution_report.md`。
- LifePrism 与 myagent wheel 均成功构建，检查前者包含 runtime/runtime_tools 且不含 deprecated_agent。第一次冻结构建因 Anaconda 环境 Qt 多绑定失败；后端无 Qt 源码依赖，排除四种绑定后重新验证。
- P3/P4 未实施；供应商专属 thinking blocks/signature、在线供应商和真实微信联调尚未验证。

- 冻结构建最终成功；PYZ 检查包含 runtime 和 30 个实际使用的 myagent 模块、排除 deprecated_agent，历史用量 501 修复已包含。最后格式清理后未再次冻结，构建产物用于本轮模块收集验证，未作为正式发布包交付。
- 本地提交尝试被 pre-commit 的全仓库 lint 阻挡；已修迁移活跃文件可安全修复项，保留旧 Enum 升级建议、弃用代码和其他模块既有债务；未绕过 hook、未推送。

## Provider 分类基础（2026-10-03）

- 按用户批准实现最小结构化错误分类，接入两个生产 provider 和 ProviderAdapter。
- Claude CLI 完成两个生产 provider 的机械接线；Codex 完成分类器、共享边界与生命周期修正。
- 禁用 SDK 自动重试与旧 chat_with_retry 的恢复行为，严格保留无效工具参数原文。
- P3 恢复策略仍未实现。具体契约、验证和兼容风险见 workspace/provider-errors-implementation.md。

## 重试 IoC（2026-10-03）

- 按用户指定参考实现接入 context.register_policy / request/error waterfall。
- LLMRetry 只裁决，myagent loop 管理每轮 3 次重试、退避和记录；撤回 provider 内重试。
- 相关测试 63 项通过，覆盖真实 loop 恢复/耗尽及 llm/retry 记录；限定文件 Ruff 通过。
- 详情及边界见 workspace/llm-retry-implementation.md。

## Agent 配置（2026-10-03）

- 新增 AgentSettings 并挂到 settings.agent；config.yaml 存 agent 嵌套节点，保存前验证。
- context 初始化从配置加载步数、重试预算、LLMRetry 和 myagent ToolUseGuard。
- 相对护栏路径基于数据目录解析；支持本平台绝对路径并拒绝外平台路径。
- 当前本地 config.yaml 补入默认 agent 节点，保持 LLMRetry 开启、ToolGuard 关闭。
- 76 项相关测试通过，限定 Ruff 通过。示例与边界见 workspace/agent-config-example.yaml 和 workspace/agent-config-implementation.md。
