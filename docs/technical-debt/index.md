## behavior-md-large-file-one-way-sync

- updated_at: 2026-07-15
- path: `docs/technical-debt/behavior-md-large-file-one-way-sync.md`
- 触发规则：修改文件同步冲突判定、dreaming task 写入逻辑、或 behavior.md/recent_state.md 相关代码时阅读
- 内容摘要：behavior.md（~130KB）仅由本地 dreaming task 写入，但 CONFLICT_RESOLVE 仍将其纳入 AI 合并浪费 85K+ tokens。需增加单向同步白名单 + 按月份拆分大文件

## conflict-resolve-ai-merged-garbage

- updated_at: 2026-07-15
- path: `docs/technical-debt/conflict-resolve-ai-merged-garbage.md`
- 触发规则：修改 CONFLICT_RESOLVE 流程、文件同步冲突处理、或 Agent 工具注册时阅读
- 内容摘要：AI 在 CONFLICT_RESOLVE 中自行创建 _merged.md 垃圾文件 + 大量 token 浪费在权限错误重试 + 提示词硬编码未纳入 prompt 系统

## config-database-misplacement

- updated_at: 2026-07-06
- path: `docs/technical-debt/config-database-misplacement.md`
- 触发规则：修改 config 模块或 repository 模块的整体结构时阅读
- 内容摘要：config/database.py 定义了 38 张表的元数据，逻辑上应属于 repository 模块，因迁移风险暂放 config
