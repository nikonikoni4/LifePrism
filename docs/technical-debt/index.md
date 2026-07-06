## config-database-misplacement

- updated_at: 2026-07-06
- path: `docs/technical-debt/config-database-misplacement.md`
- 触发规则：修改 config 模块或 repository 模块的整体结构时阅读
- 内容摘要：config/database.py 定义了 38 张表的元数据，逻辑上应属于 repository 模块，因迁移风险暂放 config
