---
version: 1.4
created_at: 2026-04-10
updated_at: 2026-06-30
last_updated: 新增工具调用链完整记录功能决策文档索引
abstract: 架构决策目录索引，用于导航 ADR 文档并说明长期设计取舍。
---

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
