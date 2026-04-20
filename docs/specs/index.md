
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
