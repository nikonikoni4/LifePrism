---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 初始化数据备份 spec，覆盖文档全量备份、数据库定时备份、备份保留与清理、备份恢复 API；触发于 2026-07-16 behavior.md 被 CONFLICT_RESOLVE LLM 合并破坏的生产级 bug
abstract: 数据备份模块规格，定义本地数据（lifeprism_data_path 下的 user/diary/agent/session 目录与 lifewatch_ai.db）的定时全量备份、备份保留策略、备份完整性校验和恢复 API 的技术契约
status: draft
module: backup
---

# 数据备份模块规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿。覆盖文档定时全量备份、数据库定时备份、保留策略、恢复 API、冲突备份清理 |

## Overview

**业务问题**：2026-07-16 上午 07:45，CONFLICT_RESOLVE 流程在 LLM 合并 behavior.md 时因 LLM 工具化失控 + 内容过长，输出了被截断/精简的合并内容，sync_client 用其覆盖本地文件，导致用户长期累积的行为记录被永久丢失（详见 [docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)）。该事件暴露了三重防线全部失效：(1) 主动防御（LLM 工具白名单）失效；(2) 操作前备份（sync_conflict/）虽触发但用户未必察觉；(3) 定时全量备份完全缺失。本 spec 聚焦第 3 道防线。

**核心职责**：
- **定时全量备份**：按配置周期对指定目录与数据库文件执行 zip 全量备份，写入 `backups/` 目录
- **数据库在线备份**：使用 SQLite Online Backup API（`sqlite3.Connection.backup()`）保证备份一致性，不依赖文件复制
- **保留策略**：按"日备份保留 N 天、周备份保留 M 周"两档清理，避免无限增长
- **完整性校验**：备份完成后立即解压校验，校验失败立即标记并通知
- **恢复 API**：提供列出备份、查询内容、恢复单个文件、整包恢复 4 个端点
- **冲突备份清理**：将 `sync_conflict/` 纳入统一清理周期（30 天），避免无限增长

**不在本 spec 范围**：
- LLM 工具白名单的修复（见 history-bug 文档方案 A）
- 长文档分流冲突解决策略（见 history-bug 文档方案 B）
- 异地容灾备份（云副本、跨机器同步）
- 增量备份（先做全量，增量后续迭代）

## Scope

### 范围内

- 定时全量备份调度（生命周期独立于同步流程）
- SQLite 在线备份 API
- zip 打包 + 文件清单 manifest
- 保留策略（日/周两档）
- 完整性校验（解压 + 文件计数 + 关键文件抽样校验）
- 恢复 API（列出 / 查询 / 单文件恢复 / 整包恢复）
- 配置项（启用/禁用、周期、保留数量、目标目录）
- sync_conflict/ 清理（沿用保留策略机制）

### 范围外

- LLM 工具白名单改造 → [history-bug 2026-07-16](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md) 方案 A
- 长文档冲突解决策略 → 同上方案 B
- 数据库迁移前备份 → 已存在 [`migration_runner.py`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/migrations/migration_runner.py)（仅触发于 schema 升级）
- 配置文件迁移前备份 → 已存在 [`config_migrator.py`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/migrations/config_migrator.py)
- 冲突解决前备份 → 已存在 [`sync_client.py:1255-1259`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1255-L1259)（不重复实现，本 spec 仅补充清理机制）
- 云端副本 / 异地容灾 → 后续 spec

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 备份调度

- [ ] 默认每天凌晨 03:00 触发一次全量备份（cron 表达式可配置）
- [ ] 备份调度在 AgentLoop 启动后启动，AgentLoop 停止时停止
- [ ] 备份调度独立于同步流程，同步进行中时备份照常执行
- [ ] 备份失败不阻塞应用主流程，仅记录 ERROR 日志并标记
- [ ] 用户可通过 API 手动触发立即备份

### 备份范围

- [ ] 默认备份目录：`user/`、`diary/`、`agent/`、`session/`、`expand_dir/`
- [ ] 默认备份文件：`lifewatch_ai.db`（位于 `dataset/`）
- [ ] 排除目录：`backups/`（避免递归）、`sync_conflict/`（独立清理）、`debug_logs/`、`cache/`、`localData/`（Electron 配置，非用户数据）
- [ ] 排除文件：所有 `*.backup-v*` 后缀（迁移备份已独立管理）、所有 `*.bak`、`*.tmp`
- [ ] 备份目标路径：`{lifeprism_data_path}/backups/`

### 备份内容契约

- [ ] 每个备份是一个独立 zip 文件，命名 `backup-{YYYYMMDD-HHMMSS}.zip`
- [ ] zip 内含一个 `manifest.json`，记录备份元信息
- [ ] zip 内含一个 `data/` 目录，按原相对路径存放所有文件
- [ ] 数据库文件单独放在 `data/dataset/lifewatch_ai.db`，使用 SQLite Online Backup API 而非文件复制
- [ ] manifest.json 必须包含：备份时间戳、文件总数、总字节数、校验和、备份范围配置快照、备份版本号

### 完整性校验

- [ ] 备份完成后立即解压 manifest.json 验证可读
- [ ] 校验 zip 内文件数与备份时记录的文件数一致
- [ ] 抽样校验 3 个文件（behavior.md、lifewatch_ai.db、最近一份 session JSONL）的 SHA-256 与原始文件一致
- [ ] 校验失败时将备份重命名为 `backup-{ts}.zip.corrupted`，记录 ERROR 日志
- [ ] 校验失败不删除备份文件，由用户决定是否手动恢复

### 保留策略

- [ ] 日备份：保留最近 7 个 `backup-{YYYYMMDD-*}.zip`
- [ ] 周备份：每周日 03:00 触发的备份额外打标 `backup-{YYYYMMDD-HHMMSS}-weekly.zip`，保留最近 4 个
- [ ] 超出保留数量的旧备份自动删除（按 mtime 排序，删最早的）
- [ ] `sync_conflict/` 目录按 30 天保留，超期自动删除子目录

### 恢复 API

- [ ] `GET /api/backup/list`：列出所有备份（含 corrupted 标记），按时间倒序
- [ ] `GET /api/backup/{backup_name}/manifest`：返回指定备份的 manifest
- [ ] `GET /api/backup/{backup_name}/file?path={relative_path}`：从备份中提取单个文件内容（仅文本，二进制走下载）
- [ ] `GET /api/backup/{backup_name}/download`：下载整个备份 zip
- [ ] `POST /api/backup/{backup_name}/restore`：整包恢复（请求体指定要恢复的路径前缀，空=全部）
- [ ] `POST /api/backup/{backup_name}/restore-file`：恢复单个文件（请求体指定 `path` 和 `target_path`，可指定 dry_run 预览）
- [ ] `POST /api/backup/trigger`：手动触发立即备份
- [ ] 所有恢复操作前必须先备份当前版本到 `pre_restore/{timestamp}/`
- [ ] 恢复前必须停止同步流程（如运行中）

### 配置项

- [ ] `backup.enabled`：是否启用定时备份，默认 `true`
- [ ] `backup.cron`：cron 表达式，默认 `"0 3 * * *"`（每天 03:00）
- [ ] `backup.weekly_cron`：周备份 cron，默认 `"0 3 * * 0"`（每周日 03:00）
- [ ] `backup.daily_keep`：日备份保留数，默认 `7`
- [ ] `backup.weekly_keep`：周备份保留数，默认 `4`
- [ ] `backup.sync_conflict_keep_days`：sync_conflict 保留天数，默认 `30`
- [ ] `backup.include_dirs`：备份目录列表，默认 `["user", "diary", "agent", "session", "expand_dir"]`
- [ ] `backup.exclude_patterns`：排除文件 glob，默认 `["*.backup-v*", "*.bak", "*.tmp"]`
- [ ] 配置变更后通过 `POST /api/backup/reload` 重新加载调度

## Technical Contract

### 备份调度器

<key_function>
- lifeprism/backup/backup_scheduler.py
  - backup_scheduler.BackupScheduler.start:行号待补
  - backup_scheduler.BackupScheduler.stop:行号待补
  - backup_scheduler.BackupScheduler.trigger_now:行号待补
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `BackupScheduler(settings)` | 构造调度器，传入配置 | 在 AgentLoop 启动后实例化 |
| `start()` | 启动调度 | 幂等，重复调用无副作用 |
| `stop()` | 停止调度并等待进行中的备份完成 | timeout 60s |
| `trigger_now()` | 立即触发一次日备份 | 不影响下次定时触发 |

### 备份执行器

<key_function>
- lifeprism/backup/backup_executor.py
  - backup_executor.BackupExecutor.run_backup:行号待补
  - backup_executor.BackupExecutor._backup_database:行号待补
  - backup_executor.BackupExecutor._backup_directory:行号待补
  - backup_executor.BackupExecutor._verify_backup:行号待补
  - backup_executor.BackupExecutor._cleanup_old_backups:行号待补
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `run_backup(weekly: bool = False) -> BackupResult` | 执行一次完整备份 | 单次执行，幂等创建新文件 |
| `_backup_database(target_zip) -> None` | SQLite Online Backup | 使用 `sqlite3.Connection.backup()` |
| `_backup_directory(target_zip, dir_name) -> None` | 目录递归打包 | 跳过 exclude_patterns |
| `_verify_backup(zip_path, expected_files) -> VerifyResult` | 完整性校验 | 解压 manifest + 抽样 SHA-256 |
| `_cleanup_old_backups(daily_keep, weekly_keep) -> int` | 清理旧备份 | 返回删除数量 |

### 备份恢复器

<key_function>
- lifeprism/backup/backup_restorer.py
  - backup_restorer.BackupRestorer.list_backups:行号待补
  - backup_restorer.BackupRestorer.get_manifest:行号待补
  - backup_restorer.BackupRestorer.restore_file:行号待补
  - backup_restorer.BackupRestorer.restore_all:行号待补
  - backup_restorer.BackupRestorer._pre_restore_snapshot:行号待补
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `list_backups() -> list[BackupMeta]` | 列出所有备份 | 含 corrupted 标记 |
| `get_manifest(backup_name) -> Manifest` | 返回 manifest | 备份不存在抛 BackupNotFound |
| `restore_file(backup_name, file_path, target_path, dry_run=False) -> RestoreResult` | 恢复单文件 | dry_run 返回预览不写盘 |
| `restore_all(backup_name, path_prefix="", dry_run=False) -> RestoreResult` | 整包恢复 | 必须先停止同步 |
| `_pre_restore_snapshot() -> Path` | 恢复前快照 | 写入 `pre_restore/{timestamp}/` |

### 数据模型

**BackupMeta（manifest.json 顶层结构）**：

```json
{
  "version": 1,
  "backup_type": "daily | weekly",
  "created_at": "2026-07-17T03:00:00+08:00",
  "created_at_utc": "2026-07-16T19:00:00Z",
  "file_count": 42,
  "total_bytes": 1048576,
  "checksum": "sha256-of-zip",
  "include_dirs": ["user", "diary", "agent", "session", "expand_dir"],
  "exclude_patterns": ["*.backup-v*", "*.bak", "*.tmp"],
  "database_backed_up": true,
  "database_size_bytes": 524288,
  "verify_status": "verified | corrupted | pending",
  "verify_checked_at": "2026-07-17T03:00:05+08:00",
  "verify_sample_files": [
    {"path": "user/behavior.md", "sha256": "..."},
    {"path": "dataset/lifewatch_ai.db", "sha256": "..."},
    {"path": "session/{latest}.jsonl", "sha256": "..."}
  ]
}
```

**BackupResult**：

```python
@dataclass
class BackupResult:
    success: bool
    backup_name: str | None  # 失败时为 None
    zip_path: Path | None
    file_count: int
    total_bytes: int
    verify_status: str  # "verified" | "corrupted" | "skipped"
    error: str | None
    duration_seconds: float
```

**VerifyResult**：

```python
@dataclass
class VerifyResult:
    ok: bool
    expected_count: int
    actual_count: int
    sample_failures: list[str]  # 校验失败的文件路径
    error: str | None
```

### API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/backup/list` | 列出所有备份 |
| GET | `/api/backup/{backup_name}/manifest` | 获取 manifest |
| GET | `/api/backup/{backup_name}/file?path={rel}` | 提取单文件（文本） |
| GET | `/api/backup/{backup_name}/download` | 下载整个 zip |
| POST | `/api/backup/{backup_name}/restore` | 整包恢复 |
| POST | `/api/backup/{backup_name}/restore-file` | 恢复单文件 |
| POST | `/api/backup/trigger` | 手动触发备份 |
| POST | `/api/backup/reload` | 重载配置 |

**响应 Schema**：

```json
// GET /api/backup/list 响应
{
  "backups": [
    {
      "name": "backup-20260717-030000.zip",
      "type": "daily",
      "created_at": "2026-07-17T03:00:00+08:00",
      "size_bytes": 1048576,
      "file_count": 42,
      "verify_status": "verified",
      "corrupted": false
    }
  ],
  "total": 1
}
```

```json
// POST /api/backup/{name}/restore 请求体
{
  "path_prefix": "user/",   // 空 = 全部恢复
  "dry_run": false
}
```

```json
// POST /api/backup/{name}/restore 响应
{
  "success": true,
  "restored_files": ["user/behavior.md", "user/goals.md"],
  "skipped_files": [],
  "pre_restore_snapshot": "pre_restore/20260717-150000/",
  "sync_was_running": true,
  "sync_stopped": true
}
```

### 状态机规则

**备份状态流转**：

```
[空闲] --触发--> [扫描文件] --> [打包文档] --> [打包数据库] --> [校验] --> [完成]
                      |              |              |             |
                      v              v              v             v
                  [失败：扫描]  [失败：打包]   [失败：DB]  [标记corrupted]
```

**恢复状态流转**：

```
[请求恢复] --> [检查同步状态] --> [若运行中：停止同步]
                --> [创建 pre_restore 快照]
                --> [解压目标文件]
                --> [覆盖到目标路径]
                --> [恢复同步（如曾被停止）]
                --> [完成]
```

### SQLite 在线备份契约

**禁止**使用 `shutil.copy2` 备份数据库文件（WAL 模式下文件复制可能不一致）。

**必须**使用 `sqlite3.Connection.backup()` API：

```python
def _backup_database(self, target_path: Path) -> None:
    """使用 SQLite Online Backup API 备份数据库"""
    import sqlite3
    source = sqlite3.connect(str(self.settings.lw_db_path))
    target = sqlite3.connect(str(target_path))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
```

**约束**：
- 备份期间不阻塞读写（SQLite Online Backup 支持并发）
- 备份完成前执行 `PRAGMA wal_checkpoint(TRUNCATE)` 确保 WAL 数据落盘
- 备份目标文件必须不存在，否则 SQLite 报错

## Design Rationale

**为什么这样设计？**

1. **三道防线模型**：
   - 第一道：主动防御（LLM 工具白名单、文件大小检查）
   - 第二道：操作前备份（已存在的 sync_conflict/）
   - 第三道：定时全量备份（本 spec）
   
   2026-07-16 事件证明：第一、二道防线都可能失效，必须有第三道兜底。

2. **日备份 + 周备份两档**：
   - 日备份高频小容量，应对"刚改完就发现错了"
   - 周备份低频大容量，应对"几天后才发现问题"
   - 两档保留数量独立配置，平衡存储成本与可恢复性

3. **SQLite Online Backup API**：
   - WAL 模式下 `shutil.copy2` 可能复制到不一致的状态（WAL 文件未 checkpoint）
   - `sqlite3.Connection.backup()` 是 SQLite 官方推荐的在线备份方法
   - 备份期间不阻塞业务读写

4. **完整性校验**：
   - 备份失败不可见，只有校验才能发现
   - 抽样校验 3 个关键文件（behavior.md、lifewatch_ai.db、最近 session JSONL）兼顾效率与覆盖度
   - 校验失败的备份不删除，由用户决定

5. **恢复前快照**：
   - 恢复操作本身有风险（可能覆盖正确内容）
   - 恢复前先快照当前版本到 `pre_restore/{timestamp}/`，可双向撤销

6. **独立调度而非嵌入同步流程**：
   - 同步可能因网络问题失败
   - 备份必须独立运行，不受同步状态影响
   - 调度在 AgentLoop 启动后启动，确保主流程就绪

**有哪些约束？**

- 备份目标路径必须在 `lifeprism_data_path` 下（白名单要求）
- 备份文件命名必须包含时间戳，避免冲突
- 恢复操作必须串行（避免覆盖正在恢复的文件）
- 单次备份超时 300s（避免无限运行）

**有哪些已知限制？**

- 仅本地备份，无异地容灾
- 仅全量备份，无增量（首次迭代，待后续优化）
- 恢复操作需手动触发，无自动恢复策略
- 不备份 AW 数据库（外部只读数据库）
- 不备份 Electron 配置（localData/）
- 备份大小无硬上限，超大备份可能影响磁盘空间

**相关 ADR / Bug**：

- [history-bug 2026-07-16 CONFLICT_RESOLVE LLM 破坏 behavior.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)
- [data-sync-files-spec](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-files-spec.md)
- [repository-core-spec 数据库迁移备份](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-06-repository-core-spec.md)

## Interaction / UX Notes

前端管理界面（后续迭代）：

1. **设置页 → 备份**：展示备份列表、配置项、手动触发按钮
2. **恢复流程**：选择备份 → 选择恢复范围（全部/部分目录/单文件）→ 确认对话框 → 进度条 → 完成提示
3. **校验失败标记**：备份列表中 corrupted 备份用红色标记，提示"备份已损坏，请勿使用"

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **LLM 工具白名单改造**：[history-bug 2026-07-16](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md) 方案 A — 消除 CONFLICT_RESOLVE 给 LLM 注册写文件工具的根因
- **长文档冲突分流**：同上方案 B — 按内容大小走 3-way merge 或保留双方版本
- **数据库迁移前备份**：[migration_runner.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/migrations/migration_runner.py) — 仅触发于 schema 升级，本 spec 不重复实现
- **配置文件迁移前备份**：[config_migrator.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/migrations/config_migrator.py) — 同上
- **冲突解决前备份**：[sync_client.py:1255-1259](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1255-L1259) — 本 spec 仅补充其清理机制
- **异地容灾**：未来 spec — 云副本、跨机器同步、多副本一致性
- **增量备份**：未来 spec — 基于 file hash 的增量差异备份
