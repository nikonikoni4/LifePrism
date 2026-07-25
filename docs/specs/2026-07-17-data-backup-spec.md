---
version: 2.0
created_at: 2026-07-17
updated_at: 2026-07-25
last_updated: 重写 spec 与实际实现对对齐。v1.0 描述的 zip 打包 + 恢复 API + manifest 方案已被 ADR 否决（决策为平铺存储 + 无 API），v2.0 同步代码现状并补充同秒触发冲突保护机制
abstract: 数据备份模块规格，定义本地数据（lifeprism_data_path 下的 session/diary/agent/user/plan 目录与 dataset/lifewatch_ai.db）的定时全量备份、备份保留策略、备份完整性校验的技术契约。备份采用平铺存储（非 zip），不做恢复 API（恢复通过文档指导手工操作）
status: current
module: backup
---

# 数据备份模块规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿（zip + 恢复 API + manifest 方案，未实现） |
| 2.0 | 重写为与实际实现对齐：平铺存储 + 无 API + 保留 3 份 + 同秒触发冲突保护；删除 WAL checkpoint 要求（Online Backup API 自动处理 WAL） |

## Overview

**业务问题**：2026-07-16 上午 07:45，CONFLICT_RESOLVE 流程在 LLM 合并 behavior.md 时因 LLM 工具化失控 + 内容过长，输出了被截断/精简的合并内容，sync_client 用其覆盖本地文件，导致用户长期累积的行为记录被永久丢失（详见 [docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)）。该事件暴露了三重防线全部失效：(1) 主动防御（LLM 工具白名单）失效；(2) 操作前备份（sync_conflict/）虽触发但用户未必察觉；(3) 定时全量备份完全缺失。本 spec 聚焦第 3 道防线。

**核心职责**：
- **定时全量备份**：按 cron 周期对指定目录与数据库文件执行平铺全量备份，写入 `backups/` 目录
- **数据库在线备份**：使用 SQLite Online Backup API（`sqlite3.Connection.backup()`）保证备份一致性，不依赖文件复制
- **保留策略**：按时间戳字符串排序（ISO-like 字典序 = 时间序），文档与数据库各自保留最新 3 份
- **完整性校验**：备份完成后立即校验，校验失败删除损坏备份
- **不做恢复 API**：恢复通过文档指导手工操作（[templates/docs/lifewatch/06-数据备份与恢复.md](file:///d:/desktop/软件开发/LifeWatch-AI/templates/docs/lifewatch/06-数据备份与恢复.md)）

**决策依据**：[ADR 2026-07-17-data-backup-strategy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md)（方案 B：平铺存储 + 复用 ScheduleService + 不做恢复 API）

**不在本 spec 范围**：
- LLM 工具白名单的修复（见 history-bug 文档方案 A）
- 长文档分流冲突解决策略（见 history-bug 文档方案 B）
- 异地容灾备份（云副本、跨机器同步）
- 增量备份（先做全量，增量后续迭代）
- 数据库迁移前备份（已存在 `migration_runner._backup_database`）
- 配置文件迁移前备份（已存在 `config_migrator`）
- 冲突解决前备份（已存在 `sync_client`，本 spec 仅补充其清理机制）

## Scope

### 范围内

- 定时全量备份调度（生命周期独立于同步流程）
- SQLite 在线备份 API（`sqlite3.Connection.backup()`）
- 平铺存储（非 zip，每个时间戳一个目录）
- 保留策略（文档与数据库各自保留最新 3 份）
- 完整性校验（文档：文件数量 + SHA-256 比对；数据库：`PRAGMA integrity_check`）
- 同秒触发冲突保护（清理已存在的备份目录/文件后再备份）
- 配置项（run_mode 守卫，复用 ScheduleService 注册机制）

### 范围外

- **恢复 API**：恢复通过文档指导手工操作（[ADR 决策](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md)）
- **manifest.json**：平铺存储无 manifest，文件本身就是元数据
- **zip 打包**：已被 ADR 否决，理由是用户需直接用文件管理器查看
- **数据库迁移前备份**：[migration_runner.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/migrations/migration_runner.py) 已独立实现
- **配置文件迁移前备份**：[config_migrator.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/migrations/config_migrator.py) 已独立实现
- **冲突解决前备份**：[sync_client.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py) 已独立实现
- **sync_conflict/ 清理**：由 `backup_conflict_versions` 函数内联触发，不依赖调度器

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 备份调度

- [x] 文档备份默认每天本地 03:00 触发一次全量备份（cron `0 3 * * *`）
- [x] 数据库备份默认每 8 小时触发一次（本地 00/08/16 点，cron `0 0,8,16 * * *`）
- [x] 备份调度在 `ScheduleService.__init__` 中注册（仅 `run_mode == "full"` 时注册）
- [x] 备份调度独立于同步流程，同步进行中时备份照常执行
- [x] 备份失败不阻塞应用主流程，仅记录 ERROR 日志
- [x] `skip_compensation=True`：跳过启动补偿，避免重启时立即备份造成 I/O 压力
- [x] run_mode 双重守卫：注册时守卫 + 运行时 `_check_run_mode()` 守卫

### 备份范围

- [x] 默认备份目录：`session/`、`diary/`、`agent/`、`user/`、`plan/`（共 5 个，定义在 `lifeprism/backup/constants.py: BACKUP_DIRS`）
- [x] 默认备份文件：`dataset/lifewatch_ai.db`（定义在 `BACKUP_DB_FILES`）
- [x] 排除文件：`chat_history.json`、`bootstrap.md`（定义在 `BACKUP_EXCLUDED_FILENAMES`）
- [x] 备份目标路径：`{lifeprism_data_path}/backups/{docs,db}/`
- [x] 与同步范围解耦（参考 [ADR 2026-07-17-backup-sync-decoupled-scope.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-backup-sync-decoupled-scope.md)）

### 备份内容契约

- [x] 文档备份：`backups/docs/{timestamp}/`，每个时间戳对应一个目录，目录内是原始文件结构（平铺，非 zip）
- [x] 数据库备份：`backups/db/lifewatch_ai-{timestamp}.db`，每个时间戳对应一个独立的 SQLite 文件
- [x] 时间戳格式：`YYYY-MM-DDTHH-MM-SS`（本地时区，冒号替换为短横，Windows 文件系统友好）
- [x] 数据库使用 SQLite Online Backup API（`sqlite3.Connection.backup(target)`），不使用 `shutil.copy2`
- [x] **不需要 `PRAGMA wal_checkpoint(TRUNCATE)`**：Online Backup API 内部按 page 复制时自动包含 WAL 中已提交的 page，构建一致快照（详见技术契约 §SQLite 在线备份契约）

### 完整性校验

- [x] 文档备份校验：文件数量比对 + 文件列表比对（相对路径集合） + 每个文件 SHA-256 hash 比对
- [x] 数据库备份校验：`PRAGMA integrity_check` 返回 `ok`
- [x] 校验失败 → 删除损坏备份目录/文件 + 记录 ERROR 日志 + 不影响其他任务

### 保留策略

- [x] 文档备份：保留最新 3 份（按时间戳字符串降序排序，删除超出部分）
- [x] 数据库备份：保留最新 3 份（同上）
- [x] `pre_restore-*` 快照：不自动清理（用户手工管理）
- [x] `sync_conflict/` 目录：30 天保留期（由 `backup_conflict_versions` 内联清理）

### 同秒触发冲突保护

- [x] 文档备份：若 `backups/docs/{timestamp}/` 已存在，先 `rmtree` 清理旧目录再 mkdir
- [x] 数据库备份：若 `backups/db/lifewatch_ai-{timestamp}.db` 已存在，先 `unlink` 旧文件再备份
- [x] 清理时记录 WARNING 日志（含时间戳与目标路径）
- [x] 安全性保障：APScheduler 默认 `max_instances=1` 防止同一任务并发执行；跨任务（文档 vs 数据库）使用不同子目录不冲突

### run_mode 守卫

- [x] `run_mode != "full"` 时跳过备份（云端 `agent_only` 与 `web_demo` 模式不备份）
- [x] 注册时守卫：`ScheduleService.__init__` 仅在 `run_mode == "full"` 时注册备份任务
- [x] 运行时守卫：`BackupService._check_run_mode()` 防止 run_mode 在运行期切换后旧任务仍执行

## Technical Contract

### 备份服务

<key_function>
- lifeprism/server/services/backup_service.py
  - BackupService.backup_documents:行号见源码
  - BackupService.backup_database:行号见源码
  - BackupService._verify_docs_backup:行号见源码
  - BackupService._verify_db_backup:行号见源码
  - BackupService._cleanup_old_doc_backups:行号见源码
  - BackupService._cleanup_old_db_backups:行号见源码
  - BackupService._check_run_mode:行号见源码
  - BackupService._get_local_timestamp:行号见源码
  - backup_service:模块级单例（LazySingleton）
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `async backup_documents() -> None` | 文档全量备份（保留 3 份） | 校验失败删除备份，不影响其他任务 |
| `async backup_database() -> None` | 数据库全量备份（保留 3 份） | 使用 SQLite Online Backup API |
| `BACKUP_RETENTION_COUNT = 3` | 备份保留份数常量 | 文档与数据库共用 |

### 备份常量

<key_function>
- lifeprism/backup/constants.py
  - BACKUP_DIRS: 文档备份目录列表
  - BACKUP_EXCLUDED_FILENAMES: 排除文件名集合
  - BACKUP_DB_FILES: 数据库备份文件列表
</key_function>

**常量值**：

```python
BACKUP_DIRS = ["session/", "diary/", "agent/", "user/", "plan/"]
BACKUP_EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}
BACKUP_DB_FILES = ["dataset/lifewatch_ai.db"]
```

### 调度集成

<key_function>
- lifeprism/server/services/schedule_service.py
  - ScheduleService.__init__: 在 __init__ 中注册备份任务
</key_function>

**调度配置**：

| 任务 | cron 表达式 | job_id | skip_compensation |
|------|------------|--------|-------------------|
| 文档备份 | `0 3 * * *`（每天本地 03:00） | `backup_documents` | True |
| 数据库备份 | `0 0,8,16 * * *`（每 8 小时） | `backup_database` | True |

**时区**：本地时区（`pytz.timezone(get_user_timezone())`），与 cron 触发时间一致。

### 数据结构

**备份目录结构**：

```
{lifeprism_data_path}/backups/
├── docs/                                    # 文档备份
│   ├── 2026-07-17T03-00-00/                 # 时间戳目录（本地时区）
│   │   ├── session/                          # 聊天会话 JSONL
│   │   ├── diary/                            # 日记 Markdown
│   │   ├── agent/                            # Agent 身份、记忆、配置
│   │   ├── user/                             # 用户级数据
│   │   └── plan/                             # 计划文档
│   ├── 2026-07-16T03-00-00/
│   └── 2026-07-15T03-00-00/
└── db/                                      # 数据库备份
    ├── lifewatch_ai-2026-07-17T08-00-00.db
    ├── lifewatch_ai-2026-07-17T16-00-00.db
    └── lifewatch_ai-2026-07-18T00-00-00.db
```

**时间戳格式**：
- 格式：`YYYY-MM-DDTHH-MM-SS`（本地时区，冒号 `:` 替换为短横 `-` 兼容 Windows 文件系统）
- 这是文件系统 artifact，不是数据库时间戳字段
- 内部日志记录使用 UTC ISO 8601（遵循 time-handling-rules §3.1）

### SQLite 在线备份契约

**必须**使用 `sqlite3.Connection.backup()` API：

```python
source = sqlite3.connect(str(src_db))
target = sqlite3.connect(str(dst_db))
try:
    source.backup(target)
finally:
    target.close()
    source.close()
```

**禁止**使用 `shutil.copy2` 备份数据库文件（WAL 模式下文件复制可能不一致）。

**约束**：
- 备份期间不阻塞读写（SQLite Online Backup 支持并发）
- **不需要 `PRAGMA wal_checkpoint(TRUNCATE)`**：Online Backup API 内部按 page 复制时自动包含 WAL 中已提交的 page，构建一致快照
- 与 `shutil.copy2` 不同（参考 `migration_runner._backup_database`，迁移前备份使用 copy2 必须 checkpoint）
- 备份目标文件必须不存在，否则 SQLite 报 `OperationalError`（已通过同秒触发冲突保护处理）

### 完整性校验契约

**文档备份校验**（`_verify_docs_backup`）：

1. 文件数量比对：源文件数 == 备份文件数
2. 文件列表比对：相对路径集合一致
3. 文件内容比对：每个文件 SHA-256 hash 一致

**数据库备份校验**（`_verify_db_backup`）：

```python
cursor.execute("PRAGMA integrity_check")
result = cursor.fetchone()[0]
return result == "ok"
```

**校验失败处理**：
- 删除损坏的备份目录/文件
- 记录 ERROR 日志（含失败原因）
- 不影响其他任务（调度器独立）

### 保留策略契约

**清理策略**：按时间戳字符串降序排序（ISO-like 字典序 = 时间序），保留最新 N 份。

```python
# 文档备份
sub_dirs = [d for d in docs_root.iterdir() if d.is_dir()]
sub_dirs.sort(key=lambda d: d.name, reverse=True)
for old_dir in sub_dirs[keep_count:]:
    shutil.rmtree(old_dir)

# 数据库备份
db_files = [f for f in db_root.iterdir() if f.is_file() and f.suffix == ".db"]
db_files.sort(key=lambda f: f.name, reverse=True)
for old_file in db_files[keep_count:]:
    old_file.unlink()
```

### 同秒触发冲突保护契约

**触发场景**：手动触发、cron 补偿、测试场景下，同秒内可能触发两次备份。

**文档备份处理**：

```python
if backup_dir.exists():
    logger.warning("文档备份目录已存在，先清理旧目录 timestamp=%s, backup_dir=%s", ...)
    shutil.rmtree(backup_dir, ignore_errors=True)
backup_dir.mkdir(parents=True, exist_ok=True)
```

**数据库备份处理**：

```python
if dst_db.exists():
    logger.warning("数据库备份文件已存在，先删除旧文件 timestamp=%s, backup_path=%s", ...)
    with contextlib.suppress(OSError):
        dst_db.unlink()
```

**安全性保障**：
- APScheduler 默认 `max_instances=1` 防止同一任务并发执行
- 跨任务（文档 vs 数据库）使用不同子目录 `backups/docs` vs `backups/db`，不冲突

### 状态机规则

**备份状态流转**：

```
[空闲] --触发--> [检查 run_mode] --> [创建备份目录/文件]
                                          |
                                          v
                                  [复制文件 / SQLite Backup]
                                          |
                                          v
                                  [完整性校验]
                                          |
                              +-----------+-----------+
                              |                       |
                              v                       v
                          [校验通过]              [校验失败]
                              |                       |
                              v                       v
                          [保留备份]              [删除备份 + ERROR]
                              |                       |
                              +-----------+-----------+
                                          |
                                          v
                                  [清理超出保留份数的旧备份]
                                          |
                                          v
                                      [完成]
```

## Design Rationale

**为什么这样设计？**

1. **三道防线模型**：
   - 第一道：主动防御（LLM 工具白名单、文件大小检查）
   - 第二道：操作前备份（已存在的 sync_conflict/）
   - 第三道：定时全量备份（本 spec）
   
   2026-07-16 事件证明：第一、二道防线都可能失效，必须有第三道兜底。

2. **平铺存储而非 zip 打包**：
   - 用户可直接用文件管理器查看备份内容（关键需求，ADR 决策依据）
   - 单文件恢复只需复制，无需解压
   - 数据库 `.db` 文件可用 DB Browser 直接打开
   - LifePrism 数据量小（文档几 MB、数据库几 MB），3 份总和不超 50MB，无压缩需求

3. **复用 ScheduleService 而非独立调度器**：
   - 项目已有基于 APScheduler 的 AsyncIOScheduler
   - 避免引入独立调度器与现有架构不一致
   - 与现有 async 架构一致

4. **不做恢复 API**：
   - 恢复场景频率极低（年频），为低频场景做 API/UI 投入产出比低
   - 用户是开发者，本地测试时可立即手工恢复
   - 恢复通过文档指导（`templates/docs/lifewatch/06-数据备份与恢复.md`）+ Agent 可读设计

5. **SQLite Online Backup API 而非 shutil.copy2**：
   - 在线拷贝，不阻塞业务读写
   - 路径完全自定义，避免文件锁冲突
   - 原子性，不会产生半截损坏文件
   - **自动处理 WAL 数据**：按 page 复制时自动包含 WAL 中已提交的 page，无需 `PRAGMA wal_checkpoint(TRUNCATE)`

6. **保留 3 份而非日 7 周 4**：
   - 数据量小，3 份足够覆盖大多数恢复场景
   - 简化配置，避免引入日/周两档管理复杂度

7. **完整性校验 + 失败删除**：
   - 备份失败不可见，只有校验才能发现
   - 文档：数量 + 路径 + SHA-256 三层校验
   - 数据库：`PRAGMA integrity_check` 比 hash 校验更可靠（检测逻辑损坏）
   - 校验失败立即删除，避免污染保留份数

8. **同秒触发冲突保护**：
   - 时间戳精度为秒，手动触发/测试场景下可能同秒触发
   - 文档备份：残留文件会导致校验失败误删有效备份
   - 数据库备份：SQLite Online Backup API 要求目标为空数据库
   - 简单清理已存在的目录/文件即可解决，符合"简单优于复杂"原则

**有哪些约束？**

- 备份目标路径必须在 `lifeprism_data_path` 下（白名单要求）
- 备份文件命名必须包含时间戳，避免冲突
- 数据库恢复必须停服（SQLite 文件被覆盖时不能有连接）
- 文档恢复需暂停 sync_client（避免恢复过程中同步覆盖）

**有哪些已知限制？**

- 仅本地备份，无异地容灾
- 仅全量备份，无增量（首次迭代，待后续优化）
- 恢复操作需手动触发，无自动恢复策略
- 不备份 AW 数据库（外部只读数据库）
- 不备份 Electron 配置（localData/）
- 备份大小无硬上限，超大备份可能影响磁盘空间
- 时间戳精度为秒，同秒触发需通过冲突保护机制处理

**相关 ADR / Bug**：

- [history-bug 2026-07-16 CONFLICT_RESOLVE LLM 破坏 behavior.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)
- [ADR 2026-07-17-data-backup-strategy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md)（平铺存储 + 复用调度器 + 不做恢复 API）
- [ADR 2026-07-17-backup-sync-decoupled-scope.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-backup-sync-decoupled-scope.md)（备份范围与同步范围解耦）
- [恢复指导文档](file:///d:/desktop/软件开发/LifeWatch-AI/templates/docs/lifewatch/06-数据备份与恢复.md)

## Interaction / UX Notes

前端管理界面（后续迭代）：

1. **设置页 → 备份**：展示备份列表、配置项、手动触发按钮
2. **恢复流程**：参考 `templates/docs/lifewatch/06-数据备份与恢复.md` 手工操作
3. **校验失败标记**：通过日志查看 ERROR 关键词

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **LLM 工具白名单改造**：[history-bug 2026-07-16](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md) 方案 A
- **长文档冲突分流**：同上方案 B
- **数据库迁移前备份**：[migration_runner.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/migrations/migration_runner.py) 已独立实现
- **配置文件迁移前备份**：[config_migrator.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/migrations/config_migrator.py) 已独立实现
- **冲突解决前备份**：[sync_client.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py) 已独立实现
- **异地容灾**：未来 spec — 云副本、跨机器同步、多副本一致性
- **增量备份**：未来 spec — 基于 file hash 的增量差异备份
- **恢复 API/UI**：[ADR 决策](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md) 已明确不做，未来如需要可基于恢复文档扩展
