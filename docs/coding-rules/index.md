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
- 触发规则：编写涉及时间/时区/日期处理的代码时阅读
- 内容摘要：全栈时间处理规范，UTC 存储 + ISO 8601 格式 + 展示层本地化，区分时间戳字段与日期字段，约束后端时间生成/序列化/解析/定时任务和前端日期格式化行为

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