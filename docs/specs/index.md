
## data-sync-overview
- updated_at: 2026-07-16
- path: `docs/specs/2026-07-16-data-sync-overview.md`
- 触发规则：首次接触数据同步模块、需要理解子模块划分和依赖关系、或新增同步相关功能需要定位哪个 spec 时阅读
- 内容摘要：数据同步模块总览，定义子模块分层架构（数据库同步 + 动态表 + 心跳 / 文件同步 / 配置桥接）、依赖规则和子 spec 索引。原 `2026-07-11-data-sync-spec.md` 因超过 500 行拆分为 core 和 files 两个子 spec

## data-sync-core-spec
- updated_at: 2026-07-23
- path: `docs/specs/2026-07-16-data-sync-core-spec.md`
- 触发规则：开发、修改或查询数据库同步、动态表同步、墓碑同步（删除传播）、心跳管理、消息路由、云端配置初始化相关功能时阅读
- 内容摘要：数据同步模块核心规格，定义 29 张静态表增量同步（updated_at + 分批拉取）、动态表 slug 集合对比双向建表、墓碑专用端点跨端传播 DELETE（3 个专用端点 + HTTP 外事务内 + INSERT OR IGNORE 跳过 LWW）、LWW 冲突解决策略、心跳状态管理（纯内存 15 分钟超时）、消息路由、云端配置生成与初始化（CloudConfigGenerator → CloudInitializer）、API Key 认证安全

## data-sync-files-spec
- updated_at: 2026-07-16
- path: `docs/specs/2026-07-16-data-sync-files-spec.md`
- 触发规则：开发、修改或查询文件同步、per-file version tracking、三阶段 API 协议、CONFLICT_RESOLVE 冲突合并相关功能时阅读
- 内容摘要：文件双向同步规格，定义 per-file version tracking（parent_hash + current_hash + 11 状态决策矩阵）、三阶段 API 协议（check → fetch/push → verify/commit）、按文件类型分流冲突解决（MD 由 AI 合并、JSONL 走 LWW）、同步白名单（对齐 Agent 工具白名单）和认证安全

## category-spec
- updated_at: 2026-04-16
- path: `docs/specs/2026-04-16-category-spec.md`
- 触发规则：开发、修改或查询分类管理模块相关功能时阅读（分类CRUD、Map Cache管理、分类状态切换、Goal绑定）
- 内容摘要：分类管理模块规格，定义分类层级结构（主分类/子分类）、Map Cache映射管理、分类启用/禁用状态及级联影响（禁用分类→Map Cache禁用→Goal排除）、Goal分类绑定规则（track_time_automatically=1且分类启用才参与分类）、冲突处理机制

## classify-spec
- updated_at: 2026-04-16
- path: `docs/specs/2026-04-16-classify-spec.md`
- 触发规则：开发、修改或查询 AI 数据分类流程相关功能时阅读（数据清洗管道、Map Cache、LLM 分类逻辑、同步 API）
- 内容摘要：AI 数据分类流程规格，定义数据清洗管道（EventTransformer→CacheMatcher→ClassifyCollector）、三级分类优先级（缓存命中→Goal 匹配→AI 纯分类）、两种分类模式（classify_graph/classify_simple）及同步 API 契约

## habit-system
- updated_at: 2026-04-19
- path: `docs/specs/2026-04-15-habit-system.md`
- 触发规则：开发、修改或查询习惯系统相关功能时阅读
- 内容摘要：习惯系统规格文档，定义基于习惯堆叠心理学的习惯养成系统，包含锚点机制、等级制挑战系统（0-4级）、打卡与补签（滚动7天窗口）、Streak连续天数计算（daily逐天判定/非daily按周结算）、状态流转、统计规则、链条Timeline时间计算等核心功能的业务规则和技术契约

## monitor-screenshot
- updated_at: 2026-04-02
- path: `docs/specs/2026-04-02-monitor-screenshot-spec.md`
- 触发规则：开发、修改或查询 monitor 模块截图功能时阅读（scheduled/active/enter 三类截图、AFK 与 engaged 状态机、engaged_segment_id、截图清理）
- 内容摘要：monitor 截图功能规格，定义三类截图触发逻辑（固定间隔、engaged 持续时长、Enter 独立直拍）、AFK 与 engaged 分层状态机、主动截图频率等级（L1/L2/L3）、截图元数据表 screen_captures、文件按天分目录与过期清理策略

## mind-space-diary
- updated_at: 2026-04-15
- path: `docs/specs/2026-04-15-mind-space-diary.md`
- 触发规则：开发、修改或查询 Mind Space 日记界面相关功能时阅读
- 内容摘要：Mind Space 日记界面功能规格，定义日记的存储机制（文件+数据库混合）、日记 CRUD API、模板管理 API、心情标签（5级）和重要程度标签（3级）的枚举值与颜色方案、前端交互设计原则（极简禅意风格）

## config-spec
- updated_at: 2026-04-20
- path: `docs/specs/2026-04-20-config-spec.md`
- 触发规则：开发、修改或查询配置管理模块相关功能时阅读（配置读写、路径解析、API Key 存储、Provider 管理、配置迁移、前后端配置交互）
- 内容摘要：配置管理模块规格，定义配置读写流程（环境变量>keyring>yaml>默认值）、路径解析规则（config_base_path 固定/lifeprism_data_path 可迁移）及打包环境前后端路径配置详细流程图、API Key 安全存储（keyring）、Provider 管理（白名单/模型历史/VLM 缓存）、配置迁移机制及前后端交互契约（REST API），包含前端路径配置已知问题说明

## wechat-channel-integration-spec
- updated_at: 2026-05-01
- path: `docs/specs/2026-05-01-wechat-channel-integration-spec.md`
- 触发规则：开发、修改或查询 WeChat Channel 与 LifePrism 对接相关功能时阅读（Channel 接口、配置数据流、消息总线集成）
- 内容摘要：WeChat Channel 与 LifePrism 对接规格，定义 Channel 暴露给 LifePrism 的接口、配置数据流（WechatConfig、allow_from 白名单）、消息总线契约（InboundMessage/OutboundMessage）、Channel 生命周期管理（启动/停止）、session_id 规范

## screenshot-analysis-spec
- updated_at: 2026-04-26
- path: `docs/specs/2026-04-26-screenshot-analysis-spec.md`
- 触发规则：开发、修改或查询截图语义分析功能时阅读（高密度时间段识别、chunk 切分、LLM 分析、行为总结、tokens 消耗控制）
- 内容摘要：截图语义分析功能规格，定义基于 LLM 的截图语义分析流程（高密度时间段识别→chunk 切分→截图查询→LLM 分析→行为总结），包括 ANALYSIS_SYSTEM_PROMPT 核心原则（精确度优先、基于截图内容、独立判断）、三种语义推断情况、输出契约、数据持久化规则，以及新增的 tokens 消耗控制机制（基于分类的截图过滤、配置项 screen_analysis_ignore、前端多选界面）

## prompt-management-system
- updated_at: 2026-05-13
- path: `docs/specs/2026-05-13-prompt-management-system.md`
- 触发规则：开发、修改或查询 Prompt 集中管理系统时阅读（文件组织、格式规范、加载接口、版本管理、使用统计）
- 内容摘要：Prompt 集中管理系统规格，定义使用 Markdown 文件管理所有 LLM prompts 的技术契约，包括文件命名规范（{模块名}_prompts.md）、Prompt 命名规范（snake_case）、Markdown 文件格式（frontmatter + metadata + 多版本）、导出接口（get_{prompt_name}_prompt）、使用统计机制（usage_stats.yaml）。支持版本管理、A/B 测试、代码解耦。Prompt 测试机制待后续补充。

## llm-test-spec
- updated_at: 2026-05-13
- path: `docs/specs/2026-05-13-llm-test-spec.md`
- 触发规则：开发、修改或查询 LLM 测试框架相关功能时阅读（测试数据管理、测试执行、评估表生成、元数据追踪）
- 内容摘要：LLM 测试框架规格，定义测试数据目录结构、输出目录结构、meta_data.json 文件结构（包含 version、round、pass_ratio、temperature、create_at、input_file 字段）、评估表结构（6 列：llm_input、llm_output、pass、score、reason、other）、LLMTestBase 抽象函数规范（data_input、run_test、generate_eval_sheet、read_eval_result）

## mood-module-spec
- updated_at: 2026-05-20
- path: `docs/specs/2026-05-20-mood-module-spec.md`
- 触发规则：开发、修改或查询心情模块相关功能时阅读（心情类型管理、心情记录 CRUD、影响因素管理）
- 内容摘要：心情模块规格文档，定义 Mind Space 心情追踪系统，包含心情类型（mood_types）的 CRUD 与删除约束、心情记录（mood_entries）的创建与评分自动获取规则、影响因素（mood_impacts）的唯一性约束与管理、按日期范围查询能力

## config-path-spec
- updated_at: 2026-07-06
- path: `docs/specs/2026-07-06-config-path-spec.md`
- 触发规则：开发、修改或查询路径解析体系相关功能时阅读（config_base_path 固定路径 vs lifeprism_data_path 可迁移路径、打包/开发环境路径差异、数据迁移流程）
- 内容摘要：Config 路径体系规格，定义 config_base_path（固定不变，配置文件根目录）和 lifeprism_data_path（可迁移，数据根目录）的解析规则、三级优先级（yaml > env var > default）、6 种环境组合、派生路径自动推算、安全检查机制

## config-settings-spec
- updated_at: 2026-07-06
- path: `docs/specs/2026-07-06-config-settings-spec.md`
- 触发规则：开发、修改或查询配置管理相关功能时阅读（SettingsManager 初始化流程、配置读写、API Key 安全存储、ProviderManager、配置优先级状态机）
- 内容摘要：Config 配置管理规格，定义 SettingsManager 7 步初始化流程、config.yaml/providers.yaml schema、ProviderManager 3 步并行初始化、配置优先级状态机（env > keyring > yaml > default）、API Key 安全存储（keyring）

## llm-agent-spec
- updated_at: 2026-07-06
- path: `docs/specs/2026-07-06-llm-agent-spec.md`
- 触发规则：开发、修改或查询 Agent 执行引擎相关功能时阅读（AgentLoop 主循环、Context 构建、Skill 系统、Tool 注册与安全沙箱、Event Bus、Session 自动压缩）
- 内容摘要：Agent 执行引擎核心规格，定义 AgentLoop 生命周期（消息处理→上下文构建→LLM 调用→工具执行循环）、30 项功能检查点、7 类 17 个工具实现、文件系统安全沙箱（allowed_dir_path 白名单 + 命令黑名单）、Event Bus 消息队列（asyncio.Queue）、Skill 可插拔加载系统

## llm-communication-spec
- updated_at: 2026-07-06
- path: `docs/specs/2026-07-06-llm-communication-spec.md`
- 触发规则：开发、修改或查询 LLM 通信与会话模块相关功能时阅读（Channel 消息平台接入、ChatBot 对话入口、Session 生命周期管理、内容分类管线、LLM Functions 功能集）
- 内容摘要：LLM 通信与会话模块核心规格，定义 Channel 体系（BaseChannel 抽象 + WeChatChannel 完整实现）、ChatBot 无状态对话 API、Session 管理（JSONL 持久化 + 内存缓存双层架构）、内容分类（ClassifyGraph 多步推理 vs ClassifySimple 一步直出）、定时任务（dreaming/process_session_message）、LLM Functions（日记总结/截图分析/连接测试/数据修复工具）

## llm-infrastructure-spec
- updated_at: 2026-07-06
- path: `docs/specs/2026-07-06-llm-infrastructure-spec.md`
- 触发规则：开发、修改或查询 LLM 基础设施相关功能时阅读（Provider 体系、LLM Client 工厂、Token 用量追踪、Prompt 模板加载、Schema 定义、工具函数集）
- 内容摘要：LLM 基础设施核心规格，定义 Provider 抽象与多服务商适配（LiteLLM/Custom）、create_llm_client 工厂、ProviderSpec 注册表（18+ 服务商）、68 项功能检查点、LLMResponse/ToolCallRequest 数据结构、PromptLoader Markdown 模板管理、异常体系（LLMError→503/PromptNotFoundError→404）

## repository-core-spec
- updated_at: 2026-07-06
- path: `docs/specs/2026-07-06-repository-core-spec.md`
- 触发规则：开发、修改或查询数据访问层相关功能时阅读（DatabaseManager、LWTableManager、BaseDataProvider、迁移系统、QueryOptions）
- 内容摘要：Repository 数据访问层核心规格，定义 DatabaseManager 15 个对外接口、LWBaseDataProvider 元数据驱动 CRUD（_TABLE_NAME/_PRIMARY_KEY 白名单防注入）、AWBaseDataProvider 只读查询、3 个数据库实例（lw/aw/chat_history）连接池契约、迁移系统（版本检测→备份→执行）、QueryOptions 不可变查询对象

## waid-window-spec
- updated_at: 2026-05-20
- path: `docs/specs/2026-05-20-waid-window-spec.md`
- 触发规则：开发、修改或查询 WAID 浮窗相关功能时阅读（任务管理、计时功能、拖拽排序、状态同步）
- 内容摘要：WAID 浮窗功能规格，定义浮窗的任务显示逻辑、计时功能规则、拖拽排序机制、状态同步机制，以及相关的 API 契约和 Electron IPC 通信规范。包含创建任务时的字段映射（关联每日目标 goal-daily 和计划文档 每日目标-docs）和计时结束时 CustomBlock 的完整字段结构

## custom-records-module
- updated_at: 2026-07-11
- path: `docs/specs/custom-records-module.md`
- 触发规则：开发、修改或查询自定义记录模块相关功能时阅读（类型管理、记录CRUD、展示配置、布局引擎、AI工具、ChatPanel集成）
- 内容摘要：自定义记录模块规格（v1.1），定义顶级独立模块允许用户通过 AI 或表单创建任意结构化数据类型。采用 SQLite 动态建表 + meta 表元数据驱动方案（custom_record_types + custom_record_fields + custom_<slug> 动态表），9 个 API 端点覆盖类型CRUD + 记录CRUD + PATCH配置 + PATCH字段角色，L1/L2/L3 三层布局引擎（启发式自动布局 + 用户角色覆盖 + 5套视觉模板预设），支持多正文叠加渲染和空字段自动过滤，4 个 LLM Tool（列出/创建类型、录入/查询记录），前端集成 ChatPanel AI 侧边栏（卡片/表格/模板对比三视图）

## data-backup-spec
- updated_at: 2026-07-17
- path: `docs/specs/2026-07-17-data-backup-spec.md`
- 触发规则：开发、修改或查询数据备份模块相关功能时阅读（定时全量备份、数据库在线备份、备份保留策略、完整性校验、恢复 API、sync_conflict 清理）
- 内容摘要：数据备份模块规格（v1.0），触发于 2026-07-16 CONFLICT_RESOLVE LLM 合并破坏 behavior.md 的生产级 bug。定义三道防线中的第三道（定时全量备份），覆盖文档目录（user/diary/agent/session/expand_dir）与 SQLite 数据库（lifewatch_ai.db）的定时全量备份（默认每天 03:00 + 每周日 03:00 周备份），SQLite 使用 Online Backup API 保证一致性，备份后立即完整性校验（manifest + 抽样 SHA-256），日保留 7 个周保留 4 个，sync_conflict/ 30 天清理。提供 8 个恢复 API 端点（列出/manifest/单文件提取/下载/整包恢复/单文件恢复/手动触发/重载配置），恢复前强制创建 pre_restore 快照
