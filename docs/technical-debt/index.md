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

## initial-sync-test-coverage

- updated_at: 2026-07-17
- path: `docs/technical-debt/initial-sync-test-coverage.md`
- 触发规则：修改 sync_client 首次同步分支、sync_cloud_api 端点、sync_repository 时阅读
- 内容摘要：首次同步全清流程 8 个核心方法（query_all/delete_all_rows/3个API端点/4个sync_client方法）无单元测试和集成测试覆盖，涉及 Row 3 矩阵判定陷阱（P0）和 N+1 查询回归（P0）的回归风险

## sync-client-class-bloat

- updated_at: 2026-07-17
- path: `docs/technical-debt/sync-client-class-bloat.md`
- 触发规则：修改同步模块整体结构、SyncClient 大幅改动时阅读
- 内容摘要：SyncClient（1780+ 行）承担首次同步 + 增量同步两条流程，在下次同步大改时抽取独立 InitialSyncService 类

## deletion-sync-p2-issues

- updated_at: 2026-07-24
- path: `docs/technical-debt/deletion-sync-p2-issues.md`
- 触发规则：修改墓碑同步端点、DeletionLogProvider 写入方法、或 SYNC_TABLES 过滤逻辑时阅读
- 内容摘要：删除同步 Stage 3 代码审查 4 个 P2 问题——通用通道缺防御性过滤（deletion_log 误加回会双重同步）、墓碑端点用 list[dict] 而非 Pydantic 模型、DeletionLogProvider 三方法重复代码、云侧端点缺 TestClient 集成测试

## mood-impacts-autoincrement-id

- updated_at: 2026-07-17
- path: `docs/technical-debt/mood-impacts-autoincrement-id.md`
- 触发规则：修改 mood_impacts 表结构或 MoodImpactProvider 时阅读
- 内容摘要：mood_impacts 是唯一使用 INTEGER AUTOINCREMENT 主键的表，与项目 TEXT hash ID 风格不一致。经 ADR 2026-07-17 验证无功能影响，建议在下次涉及该表结构变更时统一
