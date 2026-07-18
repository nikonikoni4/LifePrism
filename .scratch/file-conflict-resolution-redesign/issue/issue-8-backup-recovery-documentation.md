# Issue 8: 数据备份与恢复指导文档

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 18）

## What to build

创建数据备份与恢复指导文档，面向 Agent 可读，未来 Agent 可通过 ReadFileTool 读取以指导用户手工恢复操作。

**决策前提**：
1. 恢复场景频率极低（年频）
2. 为低频场景做 API/UI 投入产出比低
3. 本地测试时用户可立即手工恢复（用户是开发者，熟悉文件操作）
4. 未来如有需要，可基于此文档扩展为 API + Agent 通道

**决策**：
- ❌ 不做恢复 API
- ❌ 不做前端恢复 UI
- ❌ 不做 Agent 恢复通道
- ✅ 仅做备份，恢复通过手工操作
- ✅ 写恢复说明文档：`templates/docs/lifewatch/06-数据备份与恢复.md`

**文档内容要点**：

10 章节结构：
1. 备份位置说明（`{lifeprism_data_path}/backups/`）
2. 文档备份结构说明（`backups/docs/{timestamp}/`）
3. 数据库备份结构说明（`backups/db/lifewatch_ai-{timestamp}.db`）
4. 文档恢复操作步骤（复制单个文件或整个时间戳目录）
5. 数据库恢复操作步骤（关闭服务 → 替换 .db 文件 → 重启服务）
6. 恢复前手动备份建议（复制到 `backups/pre_restore-{ts}/`）
7. 恢复后对 file_sync_state 的影响（下次同步会触发 CONFLICT，预期行为）
8. sync_conflict/ 目录说明（冲突备份，保留 30 天）
9. 6 个 FAQ（常见恢复场景）
10. 技术附录（SQLite Online Backup API、PRAGMA integrity_check、平铺存储设计理由）

**关键设计点**：
- 不需要 pre_restore 快照机制：用户手工恢复时自行决定是否先备份当前状态
- 文档应强烈建议恢复前手动备份当前数据（复制到 `backups/pre_restore-{ts}/`）
- 数据库恢复必须停服（SQLite 文件被覆盖时不能有连接）
- 文档恢复不停服，但需暂停 sync_client（避免恢复过程中同步覆盖）
- 文档面向 Agent 可读，未来 Agent 可通过 ReadFileTool 读取以指导用户

## Acceptance criteria

- [ ] 创建 `templates/docs/lifewatch/06-数据备份与恢复.md`
- [ ] 文档包含 10 个章节
- [ ] 文档包含 6 个 FAQ
- [ ] 文档包含技术附录
- [ ] 文档说明备份位置（`{lifeprism_data_path}/backups/`）
- [ ] 文档说明文档备份结构（`backups/docs/{timestamp}/`）
- [ ] 文档说明数据库备份结构（`backups/db/lifewatch_ai-{timestamp}.db`）
- [ ] 文档包含文档恢复操作步骤（复制单个文件或整个时间戳目录）
- [ ] 文档包含数据库恢复操作步骤（关闭服务 → 替换 .db 文件 → 重启服务）
- [ ] 文档强调恢复前手动备份当前数据（复制到 `backups/pre_restore-{ts}/`）
- [ ] 文档说明恢复后对 file_sync_state 的影响（下次同步触发 CONFLICT，预期行为）
- [ ] 文档说明 sync_conflict/ 目录（冲突备份，保留 30 天）
- [ ] 文档面向 Agent 可读（未来可通过 ReadFileTool 读取指导用户）
- [ ] 文档审阅通过

## Blocked by

- Issue 7: 新建 BackupService 平铺备份 + 复用 ScheduleService 调度（需要知道实际备份格式才能写恢复步骤）

## User stories covered

PRD 用户故事：33（恢复兜底，与 Issue 7 共同覆盖）

## Related ADRs

- [docs/adr/2026-07-17-data-backup-strategy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md) - 数据备份策略（决策前提：恢复场景频率极低 + 用户是开发者可手工恢复 + 不做恢复 API），本 issue 的核心 ADR
- [docs/adr/2026-07-17-conflict-failure-policy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-failure-policy.md) - sync_conflict/ 目录说明（冲突备份，保留 30 天），恢复文档需说明此目录用途
