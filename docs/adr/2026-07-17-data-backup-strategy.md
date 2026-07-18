---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 2026-07-17
abstract: 数据备份采用平铺存储 + 复用现有 ScheduleService + 不做恢复 API（仅文档指导手工恢复）
status: decided
---

# 数据备份策略：平铺存储 + 复用调度器 + 不做恢复 API

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

2026-07-16 behavior.md 被破坏事件暴露了系统的最后一道防线缺失——数据被 AI 合并破坏后无任何回滚路径。现有备份机制仅触发于事件（数据库迁移、配置迁移、冲突解决前），完全缺失定时全量备份。

必须重新建立数据备份机制，覆盖文档目录与数据库文件，并明确恢复策略。

### 讨论范围

- 备份格式（zip vs 平铺）
- 备份频率与触发时机
- 调度器选择
- 恢复 API 是否实现

### 非讨论范围

- 备份范围（哪些目录）—— 见 ADR `2026-07-17-backup-sync-decoupled-scope.md`
- 冲突失败处理 —— 见 ADR `2026-07-17-conflict-failure-policy.md`
- 数据库同步冲突 —— 数据库仍走 row-level LWW

### 模糊信息的明确定义

- `平铺存储`：每个时间戳一个目录，目录内是原始文件结构（非 zip 压缩）
- `SQLite Online Backup API`：`sqlite3.Connection.backup(target)`，在线拷贝，不阻塞业务读写
- `pre_restore 快照`：恢复前对当前数据的自动备份

### 问题深度

涉及数据安全性与工程投入产出的权衡——是否为低频场景（年频恢复）投入 API/UI 成本。

## 现状

**现有备份机制（分散在 4 处）**：
- `migration_runner.py:71-105`：数据库迁移前备份（保留 3 个）
- `config_migrator.py:117-141`：配置迁移前备份
- `sync_client.py:1610-1614`：冲突解决前备份本地版本到 `sync_conflict/{ts}/`
- `wechat/auth.py:212-216`：文件损坏时零散备份

**关键缺失**：
- 无定时全量备份
- 无恢复 API
- 无统一备份模块
- sync_conflict/ 只备份本地不备份云端（已知 bug）

## 决策前提

- 前提 1（事实）：现有备份机制都是事件触发，无定时备份
- 前提 2（用户判断）：恢复场景频率极低（年频），为低频场景做 API/UI 投入产出比低
- 前提 3（用户判断）：用户是开发者，本地测试时可立即手工恢复，可接受无 API
- 前提 4（用户需求）：备份内容必须可查看，用文件管理器直接打开是关键需求
- 前提 5（事实）：项目已有 `ScheduleService`（基于 APScheduler 的 AsyncIOScheduler），非新增依赖
- 前提 6（事实）：LifePrism 数据量小（文档几 MB、数据库几 MB），3 份总和不超 50MB，无压缩需求
- 前提 7（事实）：现代备份工具（restic、borg）均采用平铺 + 去重，zip 适合归档不适合备份
- 前提 8（用户判断）：数据库备份频率需高于文档（数据库有 Monitor 高频写入）
- 前提 9（用户判断）：丢失窗口 8 小时对数据库可接受

## 可选方案

### 方案 A：zip 打包 + 独立 asyncio 调度器 + 完整恢复 API

**优势**

- 压缩节省 50-70% 空间
- 完整恢复体验

**劣势**

- 查看不便利（需解压）
- 引入独立调度器与现有架构不一致
- 恢复 API 工程量大，投入产出比低（年频使用）

### 方案 B：平铺存储 + 复用 ScheduleService + 不做恢复 API（当前选择）

**优势**

- 用户可直接用文件管理器查看备份内容（关键需求）
- 单文件恢复只需复制，无需解压
- 复用现有 ScheduleService（APScheduler 已是项目依赖）
- 数据库 .db 文件可用 DB Browser 直接打开
- 无 API 开发成本
- 与现有 async 架构一致

**劣势**

- 无压缩，空间占用大（但 LifePrism 数据量小，可接受）
- 恢复需手工操作（但频率极低，可接受）
- 用户需要阅读恢复说明文档

### 方案 C：完整 git-like（restic 风格）

引入 restic 风格的块级去重备份系统。

**优势**

- 高效增量备份
- 完整版本历史

**劣势**

- 依赖外部工具
- 对个人 PIM 应用过度设计
- 查看不便利（需通过工具命令）

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| 恢复频率低 + 查看便利性是硬需求 + 数据量小 | 方案 B（平铺 + 复用调度器 + 无 API） | 当前选择 |
| 数据量增长到 GB 级 + 需要增量备份 | 方案 C（git-like） | 备选触发条件 |
| 用户不在线时需要自动恢复 + 前端 UI 优先级提升 | 方案 A（zip + API） | 不推荐 |

## 最终决策

当前成立的前提：
- 前提 2（恢复频率低，年频）
- 前提 3（用户是开发者，可手工恢复）
- 前提 4（查看便利性是硬需求）
- 前提 5（ScheduleService 已存在）
- 前提 6（数据量小，无压缩需求）
- 前提 8（数据库频率需高于文档）
- 前提 9（8 小时丢失窗口可接受）

因此选择 **方案 B**，具体包括：

1. **平铺存储**：`{lifeprism_data_path}/backups/{docs,db}/{timestamp}/`
2. **文档备份频率**：每天 1 次，本地 03:00，保留 3 份
3. **数据库备份频率**：每 8 小时 1 次（本地 00/08/16 点），保留 3 份
4. **数据库备份方式**：SQLite Online Backup API（`sqlite3.Connection.backup(target)`）
5. **调度器**：复用现有 `ScheduleService`，在 `__init__` 中注册备份任务
6. **备份服务**：新建 `BackupService` 单例（职责：执行备份逻辑，不负责调度）
7. **不做恢复 API/UI**：恢复通过手工操作 + 文档指导（`templates/docs/lifewatch/06-数据备份与恢复.md`）
8. **完整性校验**：文档（文件数量 + hash 比对）+ 数据库（`PRAGMA integrity_check`），校验失败删除损坏备份
9. **云端 agent_only 不备份**：复用 `run_mode != "full"` 守卫

前提失效时的切换路径：
- 若恢复频率显著提升（如月频）→ 扩展为 API + Agent 通道（基于现有恢复文档）
- 若数据量增长到 GB 级 → 重新评估方案 C（git-like）

## 决策原因

- 原因 1：恢复频率极低（年频），为低频场景做 API/UI 投入产出比低
- 原因 2：查看便利性是硬需求，平铺比 zip 更优
- 原因 3：复用现有 ScheduleService 避免重复造轮子，与现有 async 架构一致
- 原因 4：数据库丢失窗口 8 小时可接受，无需更高频率
- 原因 5：用户是开发者，可手工恢复，未来如需 API 可基于文档扩展

## 后续影响

**代码结构**：
- 新建 `lifeprism/server/services/backup_service.py`（BackupService 单例）
- 新建 `lifeprism/backup/constants.py`（BACKUP_DIRS、BACKUP_EXCLUDED_FILENAMES、BACKUP_DB_FILES）
- 修改 `lifeprism/server/services/schedule_service.py`（注册备份任务）
- 创建 `templates/docs/lifewatch/06-数据备份与恢复.md`（恢复指导文档）

**测试**：
- 备份完整性校验测试
- 备份保留策略测试（保留 3 份）
- 调度集成测试

**文档**：
- `templates/docs/lifewatch/06-数据备份与恢复.md` 面向用户 + 面向 Agent 可读
- 未来 Agent 可通过 ReadFileTool 读取以指导用户操作

**关联文档**：
- `docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md`（触发本次决策的 bug）
- `.scratch/file-conflict-resolution-redesign/prd.md`（完整 PRD）
- `docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md`（冲突解决 ADR）
- `docs/adr/2026-07-17-backup-sync-decoupled-scope.md`（备份范围 ADR）
