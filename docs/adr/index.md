---
version: 2.0
created_at: 2026-04-10
updated_at: 2026-07-13
last_updated: 新增日期到 UTC 转换边界与查询参数传递策略决策
abstract: 架构决策目录索引，用于导航 ADR 文档并说明长期设计取舍。
---

## date-to-utc-conversion-boundary
- updated_at: 2026-07-13
- path: `docs/adr/2026-07-13-date-to-utc-conversion-boundary.md`
- 触发规则：当需要理解前端日期查询的转换位置、单表/聚合查询的参数传递策略、或新增日期查询 API 时读取
- 内容摘要：确立日期到 UTC 时间范围的转换边界为"组件内转换"（组件 onChange 回调），系统内部保持 UTC ISO 8601 纯净格式。单表查询：有 date 字段传 date，只有 datetime 传 start_time/end_time（UTC）。聚合查询（混合表）传 date + start_time/end_time，后端根据表结构选择使用哪个参数。决策基于：工程复用性不存在（只有 2 处转换）、架构清晰性优先、前端日期来源可靠（input[type="date"] 保证格式）。决策前提：转换需求量 <= 5 个 API、无统一 DatePicker 组件、14 行代码重复可接受。

## time-conversion-layering
- updated_at: 2026-07-12
- path: `docs/adr/2026-07-12-time-conversion-layering.md`
- 触发规则：当需要理解时间转换在哪个层级进行、为什么不用装饰器自动转换、或新增 LLM 工具时参考转换模式时读取
- 内容摘要：确立时间转换职责分层——数据层只返回 UTC ISO，LLM 工具 execute 层负责输入转换，工具函数内部显式转换输出。否决装饰器方案（字段用途差异、静默失败、返回类型多样）和 Repository 增加 return_local_time 参数方案（违反数据层职责单一）。决策经历 4 次迭代：v1 工具内部转换 → v2 考虑 Repository 参数（动摇）→ v3 考虑装饰器（审查后否决）→ v4 回到工具内部显式转换（职责更清晰）。

## migrate-to-utc-timezone
- updated_at: 2026-07-12
- path: `docs/adr/2026-07-12-migrate-to-utc-timezone.md`
- 触发规则：当需要理解时区策略、修改时间相关代码、处理时间格式问题、或考虑跨时区部署时读取
- 内容摘要：时间处理从本地时区迁移到 UTC + ISO 8601 格式。核心原因：解决旧表 UTC 和新表本地时区不一致导致的数据同步失败（LWW 比较错误）、前后端时区不一致、格式混乱、未来云端部署风险。符合业界最佳实践（Laravel/ActivityWatch 等都强制 UTC）。即使是桌面应用也需要 UTC 以避免夏令时、服务器迁移、跨时区用户等问题。


## key-fallback-strategy
- updated_at: 2026-07-09
- path: `docs/ADR/2026-07-09-key-fallback-strategy.md`
- 触发规则：当需要理解密钥存储方式、考虑改用 .env 环境变量、或新增密钥类型时读取
- 内容摘要：密钥存储采用 keyring 优先 + config.yaml fallback，否决 .env 和 systemd 环境变量方案。核心原因：.env 本质也是文件，而 config.yaml 已被 settings_manager 加载，无需引入 python-dotenv 依赖。.env 扁平格式不适合多 Provider 的嵌套 Key 结构。

## lww-conflict-resolution
- updated_at: 2026-07-09
- path: `docs/ADR/2026-07-09-lww-conflict-resolution.md`
- 触发规则：当需要理解同步冲突解决策略、三类表写入分类、或考虑引入 CRDT/版本号时读取
- 内容摘要：冲突解决采用 LWW + 三类表写入分类，否决 CRDT 和版本号方案。核心原因：主备模式下同步频率低、时间差大，冲突概率 < 0.1%。版本号方案需改 30+ 张表 schema，CRDT 过度设计。三类表分类：TEXT 主键（INSERT OR REPLACE）/ AUTOINCREMENT+UNIQUE（剥离远程 id）/ 补充 UNIQUE 约束。

## rest-polling-communication
- updated_at: 2026-07-09
- path: `docs/ADR/2026-07-09-rest-polling-communication.md`
- 触发规则：当需要理解同步通信架构、考虑改用 WebSocket、或调整同步频率时读取
- 内容摘要：通信采用 HTTP REST + 本地主动轮询（10 分钟），否决 WebSocket 和云端推送。核心原因：使用模式为电脑开机用本地、出门用手机，同步频率低无需实时性。本地在 NAT 后面，本地主动发起避免 NAT 穿透问题。REST 最简单可靠，调试方便。

## cloud-init-atomic-strategy
- updated_at: 2026-07-09
- path: `docs/ADR/2026-07-09-cloud-init-atomic-strategy.md`
- 触发规则：当需要理解 cloud_init.yaml 初始化流程、验证失败处理、或 monitor_type 强制覆盖逻辑时读取
- 内容摘要：cloud_init.yaml 初始化采用验证失败不删除策略。核心原因：密钥由本地 keyring 生成，删除文件后如果本地程序已关闭则密钥不可恢复。只有 config.yaml 和 providers.yaml 都写入成功才删除 cloud_init.yaml。monitor_type 强制覆盖为 none（云端禁用 Monitor）。

## sync-atomicity-strategy
- updated_at: 2026-07-09
- path: `docs/ADR/2026-07-09-sync-atomicity-strategy.md`
- 触发规则：当需要理解同步系统的错误处理粒度、last_sync_time 更新策略、或考虑改为 row-level best-effort 时读取
- 内容摘要：同步系统采用全局 last_sync_time 整体原子性策略（Pull+Push 全部成功才更新时间戳），否决 row-level best-effort 方案。核心原因：row-level 方案推进时间戳后，失败行 updated_at <= last_sync_time，下次 query_incremental 查询不到，数据永久丢失。整体原子性下成功表重复同步是幂等操作，代价可接受。

## linux-deployment-multiple-entrypoints
- updated_at: 2026-07-08
- path: `docs/adr/2026-07-08-linux-deployment-multiple-entrypoints.md`
- 触发规则：当需要理解为什么采用多入口架构（三个独立启动文件）而非单文件配置控制、或新增运行模式时读取
- 内容摘要：Linux 跨平台部署采用多入口架构（main.py、main_web_demo.py、main_agent_only.py），而非单文件配置控制。核心原因：避免 Python import 机制导致的平台依赖问题（顶部 import 无论如何都会执行），三种运行形态是不同的产品形态而非模式切换。优势：职责单一、依赖按需加载、易于测试和维护。劣势：代码分散、新增模式需创建新文件。

## custom-records-storage
- updated_at: 2026-07-06
- path: `docs/adr/2026-07-06-custom-records-storage.md`
- 触发规则：当需要理解自定义记录模块的存储设计、动态建表机制、meta 表元数据驱动方案、或扩展该模块功能时读取
- 内容摘要：决定自定义记录模块采用 SQLite 动态建表 + meta 表元数据驱动方案，否决 JSON 文件方案。核心决策：AI 负责 schema 生成与持续录入，P1 仅支持文本字段且字段定义后不可变，记录类型硬删且 slug 可复用，AI 无删除工具。记录了两个误区纠正：JSON 无法部分读取（无索引）、xxx-01 编号命名是反模式（meta 表已提供类型发现）。

## tool-call-chain-logging
- updated_at: 2026-06-30
- path: `docs/design-decisions/2026-06-30-tool-call-chain-logging.md`
- 触发规则：当需要理解工具调用链的记录机制、调试多轮工具调用问题、或扩展 llm_call_logger 功能时读取
- 内容摘要：在 llm_call_logger 中实现完整的工具调用链记录功能。在 `_run_agent_loop` 中记录每一轮的工具调用（包括工具名、参数、结果），通过 `OutboundMessage.extra` 传递，最终保存到日志文件的 `tool_call_chain` 字段。解决了只记录最后一轮工具调用导致的调试困难问题，工具结果全量保存便于问题排查。

## diary-component-refactoring
- updated_at: 2026-06-29
- path: `docs/design-decisions/2026-06-29-diary-component-refactoring.md`
- 触发规则：当需要理解日记组件架构设计、滚动控制方案、自定义 hooks 分离逻辑、或排查日记界面相关问题时读取
- 内容摘要：日记组件架构重构，采用关注点分离原则将 700+ 行单文件重构为主组件 + 3 个自定义 hooks（useDiaryData、useCalendarScroll、useBackgroundColor）。彻底解决了反复出现的日历点击滚动 bug：通过简化滚动逻辑（只在初始化时滚动，用户点击不触发）从根本上消除竞态条件。记录了防抖保存、编辑器水合处理、跨日期保存保护等关键实现细节。

## repository-interface-encapsulation
- updated_at: 2026-04-24
- path: `docs/design-decisions/2026-04-24-repository-interface-encapsulation.md`
- 触发规则：当需要统一 repository 上层调用边界，并明确禁止业务层穿透 `.provider` 时读取
- 内容摘要：确立 `repository` 强封装策略，采用受控透传替代上层直连 provider，降低混用与误用风险。

## llm-tool-separation-for-detail-query
- updated_at: 2026-05-03
- path: `docs/design-decisions/2026-05-03-llm-tool-separation-for-detail-query.md`
- 触发规则：当设计 LLM Agent 工具时，需要决策是否合并功能相似但信息密度差异大的工具
- 内容摘要：电脑使用详细日志查询工具设计决策，选择独立工具而非合并到聚合查询工具，基于信息密度差异（30-60倍）、使用场景差异和 LLM 工具调用可理解性考虑。核心原则：职责清晰 > 工具数量少，避免误触发 > 统一接口。

## chat-history-memory-positioning
- updated_at: 2026-05-08
- path: `docs/design-decisions/2026-05-08-chat-history-memory-positioning.md`
- 触发规则：当设计记忆系统文档结构、需要理解 chat_history.md 与 behavior.md 的职责划分时读取
- 内容摘要：确立 chat_history.md 作为记忆系统「短期跨会话上下文层」的定位，采用间隔任务更新，按天组织内容，并作为 behavior.md 聊天总结部分的上游数据源。解决了聊天记录的跨会话连贯性需求与行为/心情总结的按天总结需求之间的时间粒度冲突。

## memory-system-compact-dream-separation
- updated_at: 2026-05-11
- path: `docs/design-decisions/2026-05-11-memory-system-compact-dream-separation.md`
- 触发规则：当需要理解 lifeprism 记忆系统的 compact 与 dream 机制、游标设计、触发时机时读取
- 内容摘要：将 nanobot 记忆系统的 compact 机制与 dream 记忆提取机制分离，以适配 lifeprism 的短对话情感捕捉场景。Compact 专注于 token 管理（写入 session.jsonl），Dream 专注于记忆提取（写入 history.jsonl），两个游标完全独立。解决了短对话记忆丢失问题和职责混淆问题。

## prompt-centralized-management
- updated_at: 2026-05-13
- path: `docs/design-decisions/2026-05-13-prompt-centralized-management.md`
- 触发规则：当需要理解为什么采用 Markdown 文件管理 Prompt、为什么不用纯代码方式、如何进行方案决策时读取
- 内容摘要：决定采用 Markdown + YAML 文件管理 Prompt，而非纯代码方式。解决了版本管理、A/B 测试、代码耦合、元数据记录、使用统计等问题。按大模块分组组织文件，一个文件包含多个相关 prompts。记录了 AI 辅助决策的经验教训：需要主动追问缺点，避免片面决策。
