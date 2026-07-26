## sync-friendly-table-design.md

- updated_at: 2026-07-23
- path: `docs/coding-rules/sync-friendly-table-design.md`
- 触发规则：创建新数据库表、将现有表加入 SYNC_TABLES、修改同步表的主键/UNIQUE/时间戳约束、涉及 hash_id 或 HASH_ID_PREFIXES 的改动时阅读
- 内容摘要：同步友好建表规则，要求新同步表优先使用 TEXT PRIMARY KEY；AUTOINCREMENT 同步表必须注册 HASH_ID_PREFIXES、增加 hash_id TEXT NOT NULL UNIQUE，并将所有业务 UNIQUE（包括单列）显式声明在 table_constraints，确保 get_unique_fields 的 LWW 查找键与 INSERT OR REPLACE 的业务冲突键一致；包含 SYNC_TABLES 接入检查清单和 mood_impacts 数据覆盖案例

## tombstone-prevention-rules.md

- updated_at: 2026-07-24
- path: `docs/coding-rules/tombstone-prevention-rules.md`
- 触发规则：创建新同步表、为已有 SYNC_TABLES 新增删除方法、修改删除逻辑实现、编写 Service/Aggregator 层级联或隐蔽删除时阅读
- 内容摘要：墓碑同步预防性规则，要求新同步表必须提供走墓碑通道（_generic_delete/_generic_batch_delete）的删除方法，旧表修改删除逻辑必须验证墓碑写入，禁止绕过墓碑通道的删除模式（原生 DELETE FROM、db.delete、软删除伪装），包含级联删除、软删除、同步触发删除的规则和测试覆盖要求

## sync-remote-url-access-rules.md

- updated_at: 2026-07-26
- path: `docs/coding-rules/sync-remote-url-access-rules.md`
- 触发规则：新增 SyncClient 同步方法、修改已有方法的 remote_url 获取方式、在 SyncClient 之外新增发起 HTTP 请求到云端的代码、修改 _read_remote_url() 方法本身、修改 sync.connection_mode 或 SSH 隧道配置 schema 时阅读
- 内容摘要：remote_url 访问预防性规则，要求所有发起 HTTP 请求的代码路径必须通过 SyncClient._read_remote_url() 获取 remote_url，禁止直接调用 get_setting("sync.remote_url")，防止 SSH 隧道启用时同步请求绕过隧道导致连接失败或泄露真实服务器 IP；包含例外清单（前端展示、配置完整性检查、日志记录）、新增同步方法的检查清单、违反约束的后果说明

## backend-core-rules.md

- updated_at: 2026-04-15
- path: `docs/coding-rules/backend-core-rules.md`
- 触发规则：编写任何后端代码时阅读（高频）
- 内容摘要：后端开发核心规范，包含类型注解、文档字符串、日志记录、数据库操作、Service层职责、ID生成规范和命名约定，数据库操作规范

## backend-api-rules.md

- updated_at: 2026-04-15
- path: `docs/coding-rules/backend-api-rules.md`
- 触发规则：开发或修改 API 端点、路由时阅读
- 内容摘要：API 设计规范，包括路由定义、HTTP 方法、参数验证、错误响应、增量更新（PATCH）三态语义等

## time-handling-rules.md

- updated_at: 2026-07-12
- path: `docs/coding-rules/time-handling-rules.md`
- 触发规则：编写涉及时间/时区/日期处理的代码时阅读（高频）
- 内容摘要：时间处理规则，核心原则为"内外分离+就地转换"——内部用 UTC+ISO 8601，对外（用户/AI）用本地时区+YYYY-MM-DD HH:MM:SS，所有转换在边界处就地完成。区分时间戳字段与日期字段，约束后端时间生成/序列化/定时任务/大模型交互（execute 层转输入、工具函数转显示用输出、计算用字段保持 UTC）和前端日期格式化行为

## frontend-date-handling.md

- updated_at: 2026-04-15
- path: `docs/coding-rules/frontend-date-handling.md`
- 触发规则：前端处理时间date时阅读
- 内容摘要：前段处理时间格式规范

## test-rules.md

- updated_at: 2026-04-15
- path: `docs/coding-rules/test-rules.md`
- 触发规则：需要编写或者运行测试时阅读
- 内容摘要：规定了测试需要写在哪里，测试命名规范；测试数据来源以及测试如何验证

## other-model-rulse.md

- updated_at: 2026-04-17
- path: `docs/coding-rules/other-model-rulse.md`
- 触发规则：minimax模型需要阅读，其他模型不必阅读
- 内容摘要：加强minimax指令遵循

## create-table-rules.md

- updated_at: 2026-04-23
- path: `docs/coding-rules/create-table-rules.md`
- 触发规则：创建新表，修改现有的`lifeprism/repository/provider`和`lifeprism/repository/aggregators`下的文件时阅读
- 内容摘要：创建新表，新repository.provider和新aggregators时阅读

## repository-module-rules.md

- updated_at: 2026-07-13
- path: `docs/coding-rules/repository-module-rules.md`
- 触发规则：编写、修改或重构 `lifeprism/repository/` 模块下的 Provider、Aggregator 或 `__init__.py` 导出时阅读
- 内容摘要：Repository 数据访问层编码规则，覆盖三层架构（base_providers → providers/aggregators → __init__.py）、Provider 继承体系与元数据驱动 CRUD、Aggregator 组合模式（内部创建 Provider 实例禁止引入全局单例）、统一 `xxx_repository` 导出规范、LazySingleton 实例化策略、导入纪律（外部只能从 `lifeprism.repository` 导入）、时间处理规则（调用方边界处 date→UTC，Repository 层不收 date 参数）、常见反模式清单