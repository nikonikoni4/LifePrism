# Technical Debt Index

技术债记录目录。

---

## api-redundant-exception-handling
- updated_at: 2026-07-06
- path: `docs/technical-debt/api-redundant-exception-handling.md`
- 触发规则：编写或修改 API 路由异常处理逻辑时阅读
- 内容摘要：记录 API 层冗余 try/except 代码问题（约 74 处），明确正确做法（API 层不需要 try/except，让异常冒泡到全局处理器），包含清理计划和预期收益
