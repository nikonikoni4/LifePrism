
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
