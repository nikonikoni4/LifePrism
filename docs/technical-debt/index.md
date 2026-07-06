# Technical Debt Index

技术债记录目录。

---

## api-redundant-exception-handling
- updated_at: 2026-07-06
- path: `docs/technical-debt/api-redundant-exception-handling.md`
- 触发规则：编写或修改 API 路由异常处理逻辑时阅读
- 内容摘要：记录 API 层冗余 try/except 代码问题（约 74 处），明确正确做法（API 层不需要 try/except，让异常冒泡到全局处理器），包含清理计划和预期收益

## session-query-tool-return-type
- created_at: 2026-07-06
- severity: medium
- path: `docs/technical-debt/session-query-tool-return-type.md`
- 触发规则：修改 `session_query.py` 或工具返回类型规范时阅读
- 内容摘要：Session Query 工具返回 `str` 与 PRD 设计的 `dict/list` 不一致，方法签名使用 `Any` 违反类型注解规范。提供两种修复方案：回退到 PRD 设计或修改 PRD 统一返回字符串
