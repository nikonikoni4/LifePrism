---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated: 初始版本
abstract: LLM 基础设施模块核心契约 — Provider 抽象与多服务商适配、Client 工厂统一创建、Token 用量追踪、Prompt 模板管理、Schema 定义、工具函数集
module: llm-infrastructure
---

# LLM 基础设施核心契约

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

**业务问题**：LifeWatch-AI 需要调用多种 LLM 服务（OpenAI、Anthropic、DeepSeek、MiniMax、DashScope 等）完成行为分类、截图分析、心情总结、聊天机器人等任务。不同服务商的 API 接口、认证方式、模型命名约定各不相同，上层业务代码不应该关心这些差异。同时，所有 LLM 调用需要统一的 Token 用量追踪、Prompt 模板管理和调用日志记录能力。

**核心职责**：
- **Provider 体系**：提供统一的 `LLMProvider` 抽象层，通过 LiteLLM 适配 18+ 个 LLM 服务商，支持直接 OpenAI SDK 的自定义端点；通过 `ProviderSpec` 注册表驱动 Provider 发现与路由
- **Client 工厂**：`create_llm_client()` 从 `settings` 读取当前配置的 provider/model/api_key，自动创建对应的 Provider 实例
- **用量追踪**：`LLMUsageDataProvider` 持久化记录每次 LLM 调用的 Token 消耗（prompt/completion/total），按 session 维度聚合
- **支持设施**：Prompt 模板管理与变量替换、Schema 定义（分类状态、摘要上下文、聊天状态、用户指南）、工具函数（调用日志、Token 估算、数据密度计算、格式化与解析、Markdown 文件读写）

## Scope

### 范围内

- `LLMProvider` 抽象基类 — `chat()`/`chat_with_retry()`/`get_default_model()` 接口、消息清理（`_sanitize_empty_content`/`_sanitize_request_messages`/`_validate_last_user_content_is_multimodal`）、瞬态错误重试机制
- `LiteLLMProvider` — 基于 LiteLLM 的多服务商适配，gateway/provider 自动检测、模型名解析与前缀注入、Prompt Caching 支持、XML 工具调用解析
- `CustomProvider` — 基于 OpenAI SDK 的直连实现，用于 Custom 端点、Xiaomi MIMO 等不经过 LiteLLM 的服务商
- `ProviderSpec` — 注册项结构定义，`PROVIDERS` 注册表从 `providers.yaml` 动态构建
- `create_llm_client()` — 统一的 Client 创建入口，通过 `is_direct` 标志路由到 `LiteLLMProvider` 或 `CustomProvider`
- `LLMUsageDataProvider` — Token 用量的单条/批量持久化，继承 `LWBaseDataProvider`
- `PromptLoader` / `PromptRef` / `Prompts` — Markdown 文件驱动的 Prompt 模板加载、多版本管理、参数注入与校验、使用统计
- Schema 定义 — `LLMResponse`/`ToolCallRequest`/`GenerationSettings`（Provider 层）、`classifyState`/`LogItem`/`AppInFo`/`Goal`（分类）、`SummaryContext`（摘要）、`ChatBotSchemas`（聊天）、`UserGuide`/`GuideSection`（用户指南）
- 工具函数 — 调用日志记录（`LLMCallLogger`）、Token 估算（`estimate_prompt_tokens`）、密度计算（`compute_bucket_density`/`build_time_segments`）、分类格式化与解析（`format_goals_for_prompt`/`parse_classification_result`）、Markdown 读写（`read_md`/`write_date_md`/`extract_date_md`/`prompts_md_load`）、数据拆分（`split_by_purpose`/`split_by_duration`）
- 异常体系 — `LLMError`/`LLMResponseError`/`LLMOutputParseError`/`PromptNotFoundError`
- `LLMResponse` / `ToolCallRequest` / `GenerationSettings` 数据结构 — Provider 层跨模块通用返回类型和生成参数

### 范围外

- Agent 循环逻辑 — 见 Agent 相关 spec（`lifeprism/llm/agent/`）
- Channel 消息总线集成 — 见 WeChat Channel Integration spec
- 具体分类图（classify_graph/classify_simple）的实现 — 见 Classify spec
- 截图分析与行为总结的具体 Prompt 内容 — 见 Screenshot Analysis spec
- 弃用模块：`lifeprism/llm/utils/llm_factory.py`（被 `build_llm_client.py:create_llm_client()` 替代）、`lifeprism/llm/summary_context/`（整个目录）、`lifeprism/llm/tools/`（整个目录，`__init__.py` 全部注释）、`lifeprism/llm/tools/summary_tools.py`
- 前端 UI 如何配置 provider/model/api_key — 见 Config spec

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### Provider 体系

- [ ] `LLMProvider` 作为抽象基类，定义 `chat()` 和 `get_default_model()` 抽象方法，子类必须实现
- [ ] `chat_with_retry()` 在瞬态错误（429/500/502/503/504/timeout/overloaded/rate limit）时自动重试，最多重试 3 次（延迟 1s/2s/4s）
- [ ] `chat_with_retry()` 遇到非瞬态错误但消息包含图片时，自动移除图片以纯文本重试一次
- [ ] `chat_with_retry()` 的参数（max_tokens/temperature/reasoning_effort）未显式传入时，自动从 `self.generation` 读取默认值
- [ ] `_sanitize_empty_content()` 修复消息中的空内容块：空字符串 content 转为 None（如有 tool_calls）或 `"(empty)"`；list 内容中移除空 text 块和 `_meta` 字段
- [ ] `_validate_last_user_content_is_multimodal()` 确保最后一条 user 消息的 content 是多模态列表而非普通字符串，防止图片 base64 被 stringify 丢失
- [ ] `LiteLLMProvider` 通过 LiteLLM 库调用 18+ 个 LLM 服务商，统一接口
- [ ] `LiteLLMProvider` 支持 streaming 和 non-streaming 两种模式（通过 `acompletion` 底层支持）
- [ ] `LiteLLMProvider._resolve_model()` 根据 Gateway 或 Provider Spec 自动为模型名添加前缀（如 `deepseek/`、`anthropic/`）
- [ ] `LiteLLMProvider` 检测到 gateway 时，注入 gateway 专属的 `litellm_kwargs`
- [ ] `LiteLLMProvider` 支持 Anthropic-style Prompt Caching（`_apply_cache_control`，为 system 消息末尾和最后一个 tool 注入 `cache_control: {type: ephemeral}`）
- [ ] `LiteLLMProvider._apply_model_overrides()` 对特定模型应用参数覆盖（如 `kimi-k2.5` 强制 `temperature=1.0`）
- [ ] `LiteLLMProvider._sanitize_messages()` 过滤非标准消息字段，同时保留 Anthropic 专属的 `thinking_blocks`
- [ ] `LiteLLMProvider._sanitize_messages()` 规范化 tool_call_id（统一为 9 字符 alphanumeric，兼容 Mistral 限制），并保持 tool_calls 和 tool_call_id 的引用一致性
- [ ] `LiteLLMProvider` 支持 XML 格式工具调用解析（`_parse_xml_tool_calls`），处理 MIMO/MiniMax 等模型的 `<tool_call>` XML 输出
- [ ] `LiteLLMProvider` 的 `chat()` 异常时返回 `LLMResponse(content="Error calling LLM: ...", finish_reason="error")`，不向上抛异常
- [ ] `CustomProvider` 使用 `openai.AsyncOpenAI` 客户端直连 OpenAI 兼容 API，不经过 LiteLLM
- [ ] `CustomProvider` 同样支持 XML 格式工具调用解析和 native tool_calls 解析
- [ ] `CustomProvider` 自动生成 `x-session-affinity` header 提升后端缓存命中率
- [ ] `CustomProvider` 异常时返回包含错误详情的 `LLMResponse`（优先使用 API 返回的 body 而非通用异常消息）
- [ ] `ProviderSpec` 是 frozen dataclass，包含 20 个字段（name/keywords/env_key/litellm_prefix/skip_prefixes/is_gateway/is_local/is_oauth/is_direct/supports_prompt_caching 等）
- [ ] `PROVIDERS` 注册表从 `providers.yaml`（通过 `provider_manager.get_raw_specs()`）动态构建，非硬编码
- [ ] `find_by_model(model)` 按模型名关键词匹配标准 Provider（跳过 gateway/local），优先匹配显式 provider 前缀
- [ ] `find_gateway(provider_name, api_key, api_base)` 三级检测：provider_name 直接匹配 → api_key 前缀（如 `sk-or-` → OpenRouter）→ api_base 关键词（如 `aihubmix` → AiHubMix）
- [ ] `find_by_name(name)` 按 config field name 精确查找 ProviderSpec

### Client 工厂

- [ ] `create_llm_client()` 从 `settings.provider` 读取当前选择的服务商
- [ ] `create_llm_client()` 从 `settings.model` 读取当前选择的模型
- [ ] `create_llm_client()` 从 `settings.api_base` 读取 API 端点
- [ ] `create_llm_client()` 通过 `provider_manager.get_api_key(provider)` 从 keyring 读取 API key
- [ ] `create_llm_client()` 通过 `find_by_name(provider)` 获取 ProviderSpec，根据 `is_direct` 标志路由：`True` → `CustomProvider`，`False` → `LiteLLMProvider`
- [ ] `create_llm_client()` 在 provider 为空或无效时抛出 `ValueError` 并给出明确的错误消息

### 用量追踪

- [ ] `LLMUsageDataProvider.save_usage(session_id, usage, mode)` 持久化单次调用的 Token 用量（prompt_tokens/completion_tokens/total_tokens）
- [ ] `save_usage()` 通过 `upsert_session_tokens_usage()` 实现，同一 session 多次调用自动合并更新
- [ ] `save_usage()` 在 session_id 或 usage 为空时返回 0，不执行写入操作
- [ ] `LLMUsageDataProvider.batch_save_usage(usage_list)` 批量保存多条 Token 记录
- [ ] Token 用量保存失败时以 WARNING 级别记录日志，不向上抛异常（辅助操作兜底）
- [ ] `llm_usage_db_provider` 通过 `LazySingleton` 实现全局单例，懒加载

### Prompt 管理

- [ ] `PromptLoader` 从 `lifeprism_data_path/prompts/` 目录加载 `{module}_prompts.md` 格式的 Prompt 文件
- [ ] 开发环境下自动从 `templates/prompts` 同步 `.md` 文件到数据目录
- [ ] `load_prompt(prompt, module, version, **params)` 支持两种调用方式：`PromptRef` 对象（推荐）或字符串 + module 参数（向后兼容）
- [ ] `load_prompt()` 自动选择 `active_version`（当 version 参数为 None 时）
- [ ] `load_prompt()` 支持通过 `**params` 进行 Python `str.format()` 风格的参数注入
- [ ] `load_prompt()` 在版本声明了 params 时自动校验：检测未知参数和缺少必需参数
- [ ] `load_prompt()` 每次调用后自动更新使用统计（total_count/version_stats/last_used）
- [ ] `get_prompt_metadata(module, prompt_name)` 返回 active_version 和 version_history
- [ ] `get_available_versions(module, prompt_name)` 返回所有可用版本列表
- [ ] `get_usage_stats(prompt_name)` 返回指定或全部 Prompt 的使用统计
- [ ] `clear_cache()` 清空内存缓存，强制下次访问时重新从磁盘加载
- [ ] `Prompts.Schedule.*` 提供所有定时任务 Prompt 的类型安全引用（`ACTIVITY_SUMMARY`/`MOOD_SUMMARY`/`UPDATE_MEMORY`/`SCREENSHOT_ANALYSIS` 等 8 个 PromptRef）
- [ ] Prompt 文件缺失时抛出 `PromptNotFoundError`（HTTP 404）
- [ ] Prompt 文件缺少 frontmatter 或 metadata 时抛出 `ValueError`

### Schema 定义

- [ ] `LLMResponse` 包含 `content`（文本或 None）、`tool_calls`（`list[ToolCallRequest]`）、`finish_reason`（默认 `"stop"`）、`usage`（Token 用量 dict）、`reasoning_content`（Kimi/DeepSeek-R1 思考内容）、`thinking_blocks`（Anthropic extended thinking）
- [ ] `LLMResponse.has_tool_calls` 属性判断响应是否包含工具调用
- [ ] `ToolCallRequest` 包含 `id`/`name`/`arguments`/`provider_specific_fields`/`function_provider_specific_fields`，提供 `to_openai_tool_call()` 序列化方法
- [ ] `GenerationSettings` 是 frozen dataclass，包含 `temperature`（默认 0.7）、`max_tokens`（默认 4096）、`reasoning_effort`（默认 None）
- [ ] `classifyState` 包含 `app_registry`/`log_items`/`result_items` 三个字段
- [ ] `LogItem` 包含 `id`/`app`/`duration`（秒）/`title`/`title_analysis`/`category`/`sub_category`/`link_to_goal`
- [ ] `SummaryContext` 包含 `summary_type`/`range`/`coverage`/`activity`/`execution`/`authored`/`uncertainty` 七个子上下文，所有子类继承 `StrictBaseModel`（`extra="forbid"`）
- [ ] `ChatBotSchemas` 使用 LangGraph 的 `TypedDict` + `Annotated` 定义状态（`messages`/`intent`/`guide_content`/`current_human_message`/`tools_result`）
- [ ] `UserGuide` 支持嵌套 `GuideSection` 结构、ID 缓存、关键词收集、Markdown 转换、层级深度计算

### 工具函数

- [ ] `LLMCallLogger.log_call()` 记录 InboundMessage/OutboundMessage 的完整信息（文本、图片、Token、System Prompt、调用位置、工具调用链）
- [ ] `LLMCallLogger` 通过 `settings.llm_call_logger_enabled` 配置项控制记录开关，关闭时 `log_call()` 返回 None
- [ ] `LLMCallLogger` 的日志按日期分文件存储（`llm_calls_YYYY-MM-DD.json`），图片单独存储在 `images/` 子目录
- [ ] `LLMCallLogger.export_by_prompt()` 按 prompt/module 导出数据集，支持版本和日期范围过滤
- [ ] `LLMCallLogger.export_by_workflow()` 按 workflow_id 导出完整调用链数据
- [ ] `estimate_prompt_tokens()` 使用 tiktoken `cl100k_base` 编码估算 Token 数（包括 content/tool_calls/reasoning_content/name/tool_call_id/tools + 每条消息 4 token overhead），失败返回 0
- [ ] `detect_image_mime()` 通过 magic bytes 检测图片 MIME 类型（支持 PNG/JPEG/GIF/WEBP）
- [ ] `build_assistant_message()` 构建兼容多种 Provider 的 assistant 消息（自动处理 reasoning_content/thinking_blocks）
- [ ] `compute_bucket_density()` 计算时间桶内的活动覆盖密度，返回 [0.0, 1.0] 范围值
- [ ] `build_time_segments()` 使用滑动窗口算法识别高密度时间段，支持桥接桶（bridge buckets）合并相邻段，过滤短时段
- [ ] `format_goals_for_prompt()` / `format_category_tree_for_prompt()` / `format_log_items_table()` 将结构化数据格式化为 LLM 可读文本
- [ ] `parse_classification_result()` 将 LLM 返回的分类结果字典解析并回填到 `LogItem` 对象
- [ ] `extract_json_from_response()` 从 LLM 响应中剥离 Markdown 代码块标记，提取纯 JSON
- [ ] `parse_token_usage()` 兼容阿里云（input_tokens/output_tokens）、火山/OpenAI（prompt_tokens/completion_tokens）、MiniMax（仅 total_tokens）三种 Token 格式
- [ ] `read_md()` 读取 Markdown 文件，文件不存在时自动创建
- [ ] `write_date_md()` 向按日期组织的 Markdown 文件写入内容，支持 append/overwrite 模式，自动按日期升序排列
- [ ] `extract_date_md()` / `extract_date_logs_from_file()` 从按日期组织的 Markdown 文本/文件中提取指定日期范围的内容
- [ ] `prompts_md_load()` 解析 Prompt Markdown 文件（frontmatter + `# prompt_name` + `## metadata` + `## v1/v2` 版本块）
- [ ] `split_by_purpose()` 将 `classifyState` 按应用单用途/多用途分离
- [ ] `split_by_duration()` 将多用途 log_items 按时长阈值（`settings.long_log_threshold`）分离为短/长两组

### 异常体系

- [ ] `LLMError` 继承 `ExternalServiceError`，由全局异常处理器映射为 HTTP 503
- [ ] `LLMResponseError` 在 LLM 返回无效响应时抛出，携带 model 和 raw_response
- [ ] `LLMOutputParseError` 在 JSON 解析/Schema 校验失败时抛出，携带 expected_fields/actual_keys/raw
- [ ] `PromptNotFoundError` 继承 `NotFoundError`（而非 `LLMError`），映射为 HTTP 404（配置问题非临时故障）

## Technical Contract

### LLMProvider 抽象基类

<key_function>
- lifeprism/llm/providers/llm_providers/base.py
  - base.LLMProvider.chat:184
  - base.LLMProvider.chat_with_retry:246
  - base.LLMProvider.get_default_model:306
  - base.LLMProvider._sanitize_empty_content:102
  - base.LLMProvider._sanitize_request_messages:155
  - base.LLMProvider._validate_last_user_content_is_multimodal:170
  - base.LLMProvider._is_transient_error:211
  - base.LLMProvider._strip_image_content:216
  - base.LLMProvider._safe_chat:237
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `chat(messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice)` | 发送一次聊天补全请求，返回 `LLMResponse` | 抽象方法，子类必须实现 |
| `chat_with_retry(messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice)` | 带重试的聊天补全，自动处理瞬态错误 | 参数未传时从 `self.generation` 读取默认值；最多重试 3 次；非瞬态错误但含图片时自动纯文本重试 |
| `get_default_model()` | 获取 Provider 的默认模型名 | 抽象方法，子类必须实现 |

**重试行为**：

- 瞬态错误标记：`429`/`rate limit`/`500`/`502`/`503`/`504`/`overloaded`/`timeout`/`timed out`/`connection`/`server error`/`temporarily unavailable`
- 重试延迟：第 1 次 1s、第 2 次 2s、第 3 次 4s
- 非瞬态错误 + 消息含图片 → 自动 `_strip_image_content()` 替换为 `[image: path]` 文本占位符后重试

**消息清理**：

- `_sanitize_empty_content()`：空字符串 → `None`（有 tool_calls 时）或 `"(empty)"`；移除 list 中的空 text 块和 `_meta` 字段
- `_sanitize_request_messages()`：按 `allowed_keys` 过滤消息字段，确保 assistant 消息有 content key
- `_validate_last_user_content_is_multimodal()`：最后一条 user 消息的 content 为 str 时抛出 `ValueError`

### LiteLLMProvider

<key_function>
- lifeprism/llm/providers/llm_providers/litellm_provider.py
  - litellm_provider.LiteLLMProvider.__init__:45
  - litellm_provider.LiteLLMProvider.chat:232
  - litellm_provider.LiteLLMProvider._resolve_model:105
  - litellm_provider.LiteLLMProvider._sanitize_messages:201
  - litellm_provider.LiteLLMProvider._parse_response:371
  - litellm_provider.LiteLLMProvider._parse_xml_tool_calls:316
  - litellm_provider.LiteLLMProvider._apply_cache_control:141
  - litellm_provider.LiteLLMProvider._apply_model_overrides:169
  - litellm_provider.LiteLLMProvider.get_default_model:453
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(api_key, api_base, default_model, provider_name, extra_headers)` | 初始化 LiteLLMProvider | api_key/api_base/default_model 均为非空必填；provider_name 用于 gateway 检测和模型名解析 |
| `chat(messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice)` | 通过 LiteLLM `acompletion` 发送请求 | model 为 None 时使用 `self.default_model`；异常时返回 error LLMResponse 不抛异常 |
| `get_default_model()` | 返回 `self.default_model` | — |

**模型名解析流程**（`_resolve_model`）：

1. 如有 gateway：应用 `gateway.litellm_prefix`，若 `gateway.strip_model_prefix` 则先剥离已有前缀
2. 无 gateway：通过 `find_by_model()` 查找标准 Provider，自动注入 `spec.litellm_prefix`（跳过已在 `skip_prefixes` 中的前缀）

**Prompt Caching**（`_apply_cache_control`）：

- 仅在 `_supports_cache_control(model)` 返回 True 时执行
- system 消息末尾注入 `cache_control: {type: "ephemeral"}`
- 最后一个 tool 定义注入相同标记

### CustomProvider

<key_function>
- lifeprism/llm/providers/llm_providers/custom_provider.py
  - custom_provider.CustomProvider.__init__:19
  - custom_provider.CustomProvider.chat:41
  - custom_provider.CustomProvider._parse:122
  - custom_provider.CustomProvider._parse_xml_tool_calls:74
  - custom_provider.CustomProvider.get_default_model:173
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(api_key, api_base, default_model, extra_headers)` | 初始化 CustomProvider，创建 `AsyncOpenAI` 客户端 | api_key 默认 `"no-key"`；自动注入 `x-session-affinity` header |
| `chat(messages, tools, model, max_tokens, temperature, reasoning_effort, tool_choice)` | 通过 OpenAI SDK 直连发送请求 | 异常时优先返回 API body 内容（截断到 500 字符） |
| `get_default_model()` | 返回 `self.default_model` | — |

### Provider Registry

<key_function>
- lifeprism/llm/providers/llm_providers/registry.py
  - registry.PROVIDERS:107
  - registry.find_by_model:115
  - registry.find_gateway:137
  - registry.find_by_name:168
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `PROVIDERS` | 全局 ProviderSpec 元组，从 `providers.yaml` 动态构建 | 模块加载时构建；`_build_providers()` 自动将 list 转为 tuple 字段 |
| `find_by_model(model)` | 按模型名关键词匹配标准 Provider | 跳过 gateway/local；优先匹配显式 provider 前缀；大小写不敏感 |
| `find_gateway(provider_name, api_key, api_base)` | 三级检测 gateway/local Provider | 1) provider_name 直接匹配 → 2) api_key 前缀 → 3) api_base 关键词 |
| `find_by_name(name)` | 按 config field name 精确查找 | — |

### ProviderSpec 字段契约

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | `str` | — | config field name，如 `"dashscope"` |
| `keywords` | `tuple[str, ...]` | — | 模型名关键词，用于 `find_by_model` 匹配 |
| `env_key` | `str` | `""` | keyring 存储键名；为空则不使用 keyring |
| `display_name` | `str` | `""` | 前端展示名称 |
| `litellm_prefix` | `str` | `""` | LiteLLM 模型名前缀 |
| `skip_prefixes` | `tuple[str, ...]` | `()` | 已有此前缀的模型名不重复添加 |
| `env_extras` | `tuple[tuple[str, str], ...]` | `()` | 额外环境变量 |
| `is_gateway` | `bool` | `False` | 是否为 Gateway（路由任意模型） |
| `is_local` | `bool` | `False` | 是否为本地部署（vLLM/Ollama） |
| `detect_by_key_prefix` | `str` | `""` | 通过 api_key 前缀自动检测 |
| `detect_by_base_keyword` | `str` | `""` | 通过 api_base 关键词自动检测 |
| `default_api_base` | `str` | `""` | 默认 API 端点 |
| `strip_model_prefix` | `bool` | `False` | 解析模型名时先剥离已有前缀 |
| `litellm_kwargs` | `dict[str, Any]` | `{}` | 传递给 LiteLLM 的额外参数 |
| `model_overrides` | `tuple[tuple[str, dict], ...]` | `()` | 模型级参数覆盖 |
| `is_oauth` | `bool` | `False` | 是否使用 OAuth 而非 API key |
| `is_direct` | `bool` | `False` | 是否绕过 LiteLLM 直连（route to CustomProvider） |
| `supports_prompt_caching` | `bool` | `False` | 是否支持 cache_control |
| `default_model` | `str` | `""` | Provider 默认模型 |

### create_llm_client()

<key_function>
- lifeprism/llm/providers/llm_providers/build_llm_client.py
  - build_llm_client.create_llm_client:14
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `create_llm_client()` | 从 settings 读取配置并创建 LLMProvider 实例 | 无参数；provider 为空或无效时抛 ValueError；返回 `LiteLLMProvider` 或 `CustomProvider` |

**行为契约**：

1. 从 `settings.provider` 读取当前选择的 provider 显示名
2. 通过 `provider_manager.get_provider_id()` 将显示名转为 provider id（name）
3. 通过 `find_by_name(provider_id)` 获取 `ProviderSpec`
4. 若 `spec.is_direct == True` → 返回 `CustomProvider(api_key, api_base, default_model)`
5. 若 `spec.is_direct == False` → 返回 `LiteLLMProvider(api_key, api_base, default_model, provider_name=provider_id)`
6. API key 通过 `provider_manager.get_api_key(provider_id)` 从 keyring 获取
7. API base 和 model 从 `settings.api_base` 和 `settings.model` 读取

### LLMUsageDataProvider

<key_function>
- lifeprism/llm/providers/llm_providers/llm_usage_db_provider.py
  - llm_usage_db_provider.LLMUsageDataProvider.save_usage:26
  - llm_usage_db_provider.LLMUsageDataProvider.batch_save_usage:55
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `save_usage(session_id, usage, mode)` | 保存或更新单个会话的 Token 用量 | session_id 或 usage 为空时返回 0；内部调用 `upsert_session_tokens_usage()` |
| `batch_save_usage(usage_list)` | 批量保存 Token 用量记录 | 空列表返回 0 |

**全局单例**：`llm_usage_db_provider = LazySingleton(LLMUsageDataProvider)`

### PromptLoader

<key_function>
- lifeprism/llm/prompts/prompt_loader.py
  - prompt_loader.PromptLoader.__init__:72
  - prompt_loader.PromptLoader.load_prompt:269
  - prompt_loader.PromptLoader.get_prompt_metadata:357
  - prompt_loader.PromptLoader.get_available_versions:379
  - prompt_loader.PromptLoader.get_usage_stats:401
  - prompt_loader.PromptLoader.clear_cache:418
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(prompts_dir, usage_stats_file)` | 初始化加载器，同步开发环境 Prompt 文件 | prompts_dir 默认为 `settings.lifeprism_data_path / "prompts"` |
| `load_prompt(prompt, module, version, **params)` | 加载指定 Prompt 内容 | 支持 `PromptRef` 对象或字符串；自动使用 active_version；自动参数注入和校验 |
| `get_prompt_metadata(module, prompt_name)` | 获取 Prompt 元数据 | — |
| `get_available_versions(module, prompt_name)` | 获取所有可用版本列表 | — |
| `get_usage_stats(prompt_name)` | 获取使用统计数据 | prompt_name 为 None 时返回全部 |
| `clear_cache()` | 清空内存缓存 | — |

**PromptRef 数据结构**：`frozen dataclass`，包含 `module: str` 和 `name: str`。

**Prompts 类层次**：命名空间类，当前包含 `Prompts.Schedule`（8 个定时任务 PromptRef 常量）。

**Prompt Markdown 文件格式契约**：

```markdown
---
module: schedule
description: ...
author: ...
---

# activity_summary

## metadata
```yaml
active_version: v2
version_history:
  v1:
    created: 2026-01-01
    params: [goals, activities]
  v2:
    created: 2026-03-01
    params: [goals, activities, mood]
```

## v1
...prompt content...

## v2
...prompt content...
```

### Schema 核心数据结构

#### LLMResponse

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `content` | `str \| None` | — | LLM 返回的文本内容 |
| `tool_calls` | `list[ToolCallRequest]` | `[]` | 工具调用列表 |
| `finish_reason` | `str` | `"stop"` | 结束原因（stop/tool_calls/error） |
| `usage` | `dict[str, int]` | `{}` | Token 用量（prompt_tokens/completion_tokens/total_tokens） |
| `reasoning_content` | `str \| None` | `None` | 思考过程（Kimi/DeepSeek-R1） |
| `thinking_blocks` | `list[dict] \| None` | `None` | Anthropic extended thinking |

#### ToolCallRequest

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `id` | `str` | — | 工具调用 ID |
| `name` | `str` | — | 函数名 |
| `arguments` | `dict[str, Any]` | — | 函数参数 |
| `provider_specific_fields` | `dict[str, Any] \| None` | `None` | Provider 专属字段 |
| `function_provider_specific_fields` | `dict[str, Any] \| None` | `None` | 函数级 Provider 专属字段 |

`to_openai_tool_call()` 序列化为 OpenAI 兼容格式。

#### GenerationSettings

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `temperature` | `float` | `0.7` | 采样温度 |
| `max_tokens` | `int` | `4096` | 最大输出 Token |
| `reasoning_effort` | `str \| None` | `None` | 深度思考强度 |

#### classifyState

| 字段 | 类型 | 说明 |
|------|------|------|
| `app_registry` | `dict[str, AppInFo]` | 应用注册表，key 为应用名 |
| `log_items` | `list[LogItem]` | 原始待分类数据 |
| `result_items` | `list[LogItem] \| None` | 分类结果输出 |

#### SummaryContext

包含 7 个子上下文：`SummaryRange`（时间范围）、`CoverageContext`（数据覆盖度）、`ActivityContext`（活动详情）、`ExecutionContext`（TODO/Habit 执行）、`AuthoredContext`（自定义块/日记/心情）、`UncertaintyContext`（置信度与警告）。

所有子类继承 `StrictBaseModel`（`extra="forbid"`），保证 Schema 严格性。

### 异常体系

<key_function>
- lifeprism/llm/exceptions.py
  - exceptions.LLMError:13
  - exceptions.LLMResponseError:19
  - exceptions.LLMOutputParseError:34
  - exceptions.PromptNotFoundError:49
</key_function>

**继承链**：

```
LWBaseError (lifeprism.utils.exceptions)
├── ExternalServiceError
│   └── LLMError                    — LLM 模块基础异常 → HTTP 503
│       ├── LLMResponseError        — LLM 返回无效响应
│       └── LLMOutputParseError     — JSON/Schema 解析失败
└── NotFoundError
    └── PromptNotFoundError         — Prompt 文件缺失 → HTTP 404
```

**异常类契约**：

| 异常类 | 父类 | code | HTTP 映射 | 构造参数 |
|--------|------|------|-----------|----------|
| `LLMError` | `ExternalServiceError` | — | 503 | 继承自 LWBaseError |
| `LLMResponseError` | `LLMError` | `LLM_RESPONSE_ERROR` | 503 | `model: str, raw_response: str, cause: Exception` |
| `LLMOutputParseError` | `LLMError` | `LLM_OUTPUT_PARSE_ERROR` | 503 | `expected_fields: list, actual_keys: list, raw_output: str` |
| `PromptNotFoundError` | `NotFoundError` | `PROMPT_NOT_FOUND` | 404 | `prompt_name: str, module: str` |

### 模块导出清单

`lifeprism/llm/providers/__init__.py` 对外导出：

| 符号 | 类型 | 说明 |
|------|------|------|
| `LLMProvider` | 抽象类 | Provider 基类 |
| `LLMResponse` | dataclass | LLM 响应结构 |
| `ToolCallRequest` | dataclass | 工具调用请求 |
| `GenerationSettings` | dataclass | 生成参数 |
| `LiteLLMProvider` | 类 | LiteLLM 实现 |
| `CustomProvider` | 类 | 直连实现 |
| `ProviderSpec` | frozen dataclass | Provider 注册项 |
| `PROVIDERS` | tuple | 全局注册表 |
| `find_by_model` | 函数 | 按模型名查找 |
| `find_gateway` | 函数 | Gateway 检测 |
| `find_by_name` | 函数 | 按名称查找 |
| `create_llm_client` | 函数 | Client 工厂 |

## Design Rationale

**为什么用 ProviderRegistry 而非硬编码？**

- 18+ 个 LLM 服务商各有不同的认证方式、模型命名规则、API 端点格式。硬编码 if-elif 链会导致 `LiteLLMProvider` 内部充斥服务商专属逻辑，难以扩展
- `ProviderSpec` frozen dataclass 将每个服务商的元信息（前缀、跳过前缀、Gateway 检测规则、参数覆盖、Caching 支持）声明为数据而非代码
- 新增 Provider 只需在 `providers.yaml` 中添加一行配置，无需修改任何 Python 代码
- Gateway 和标准 Provider、本地部署（vLLM/Ollama）通过同一套数据结构统一管理，检测逻辑集中在 `find_gateway()` 的五级优先级中

**为什么 create_llm_client() 替代了旧的 create_llm()？**

- 旧的 `llm_factory.py:create_llm()` 基于 LangChain 封装，耦合了 ChatTongyiModel 等具体实现，且需要手动传入所有参数
- `create_llm_client()` 从 `settings` 和 `provider_manager` 自动读取配置，实现零参数调用，调用方只需 `client = create_llm_client()` 即可获得可用的 LLM 客户端
- `is_direct` 路由机制让 CustomProvider（OpenAI SDK 直连）和 LiteLLMProvider（多服务商适配）共享统一入口，对调用方透明

**为什么 LiteLLM 作为主要适配层？**

- 优势：LiteLLM 统一了 100+ 个 LLM 服务商的 API 差异，无需为每个服务商编写独立的 HTTP 调用代码
- 优势：自动处理 streaming/non-streaming 模式切换、Token 计数、错误重试等通用逻辑
- 代价：LiteLLM 增加了依赖体积和启动延迟；对于 OpenAI 兼容的自定义端点（如 Xiaomi MIMO），多一层 LiteLLM 代理是不必要的开销，因此通过 `is_direct` 标志直接使用 OpenAI SDK

**为什么 ChatBotSchemas 使用 TypedDict 而非 Pydantic BaseModel？**

- LangGraph 官方推荐使用 `TypedDict` 定义状态类型
- Pydantic BaseModel 的验证器与 LangChain 的 `ToolMessage` 等消息类型存在兼容性问题（自动类型转换和序列化冲突）
- TypedDict 更轻量，不触发不必要的类型验证，同时通过 `Annotated` + `operator.add` 实现状态累加语义

**为什么 LLMCallLogger 使用配置开关（llm_call_logger_enabled）？**

- 调用日志记录涉及大量文件 I/O（每条 LLM 调用写一次 JSON 文件 + 可能的图片保存），对生产环境性能有显著影响
- 通过配置项控制，用户可以在需要调试或收集测试数据时开启，日常使用时关闭
- `LazySingleton` 确保日志目录只在首次访问时创建

**为什么 Prompt 使用 Markdown 文件而非代码常量？**

- Markdown 文件便于非技术人员（产品经理、领域专家）直接编辑和版本管理
- 支持多版本共存和 `active_version` 切换，实现 A/B 测试和渐进式 Prompt 优化
- 通过 `usage_stats.yaml` 追踪每个 Prompt/版本的使用频率，为优化提供数据支撑
- 详见 `docs/specs/2026-05-13-prompt-management-system.md`

**有哪些约束？**

- 所有 LLMProvider 调用必须是 async（`async def chat()`），调用方需在异步上下文中使用
- `LiteLLMProvider` 的 `chat()` 在异常时不抛出，而是返回 content 为错误消息的 `LLMResponse`，调用方需要检查 `finish_reason != "error"` 来判断是否成功
- `CustomProvider` 同理返回 error LLMResponse，不抛异常
- `LLMUsageDataProvider` 的 `save_usage()` 和 `batch_save_usage()` 失败时只记录 WARNING 日志，不向上抛异常（辅助操作兜底）
- `ProviderSpec` 从 `providers.yaml` 动态构建，依赖于 `provider_manager` 单例已正确初始化
- `PromptLoader` 使用文件系统缓存，`clear_cache()` 后才能加载外部修改的 Prompt 文件

**有哪些已知限制？**

- `LiteLLMProvider` 不支持 `generate()` 和 `embed()` 方法（`LLMProvider` 抽象基类中未定义这些抽象方法）
- `LLMUsageDataProvider` 的 Token 记录依赖于上层调用方主动调用 `save_usage()`，没有自动拦截机制
- `estimate_prompt_tokens()` 使用 `cl100k_base` 编码器做近似估算，可能与实际 Token 数存在偏差
- `LLMCallLogger` 的按日期分文件存储可能导致单文件过大（高频率调用场景），不自动轮转或压缩
- `ProviderSpec` 的 `env_extras` 字段在当前代码中未被使用（继承自 Nanobot，保留以兼容未来需求）

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **Agent 循环与工具调用**：`lifeprism/llm/agent/` — Agent 的消息循环、工具执行、上下文管理。LLM 基础设施只提供 `chat()` 接口，Agent 如何编排多次调用属于 Agent spec 范畴
- **Channel 消息总线**：见 [`docs/specs/2026-05-01-wechat-channel-integration-spec.md`](2026-05-01-wechat-channel-integration-spec.md) — Channel 如何将用户消息转换为 LLM 调用并返回结果
- **Prompt 管理系统**：见 [`docs/specs/2026-05-13-prompt-management-system.md`](2026-05-13-prompt-management-system.md) — Prompt 文件的组织规范、格式定义、版本管理详细规则
- **LLM 测试框架**：见 [`docs/specs/2026-05-13-llm-test-spec.md`](2026-05-13-llm-test-spec.md) — LLM 测试数据管理、测试执行、评估表生成
- **分类系统**：见 [`docs/specs/2026-04-16-classify-spec.md`](2026-04-16-classify-spec.md) — AI 数据分类流程、LangGraph 分类图实现
- **截图分析**：见 [`docs/specs/2026-04-26-screenshot-analysis-spec.md`](2026-04-26-screenshot-analysis-spec.md) — 截图语义分析的具体 Prompt 和流程
- **Config 模块**：见 [`docs/specs/2026-07-06-config-path-spec.md`](2026-07-06-config-path-spec.md)（路径体系）和 [`docs/specs/2026-07-06-config-settings-spec.md`](2026-07-06-config-settings-spec.md)（配置管理）— provider_manager、settings_manager 的完整实现和数据流
- **弃用模块**：`lifeprism/llm/utils/llm_factory.py`、`lifeprism/llm/summary_context/`、`lifeprism/llm/tools/`、`lifeprism/llm/tools/summary_tools.py` — 已有替代方案，不在本 spec 覆盖范围内
