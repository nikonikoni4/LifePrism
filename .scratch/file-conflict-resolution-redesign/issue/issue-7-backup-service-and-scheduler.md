# Issue 7: 新建 BackupService 平铺备份 + 复用 ScheduleService 调度

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 13-18）

## What to build

新建 BackupService 单例，实现文档和数据库的定时平铺备份，复用现有 ScheduleService 做调度。

**备份范围**（独立定义，不依赖 `SYNC_DIRECTORIES`）：

```python
# lifeprism/backup/constants.py（新建）

BACKUP_DIRS = [
    "session/",   # 聊天会话 JSONL
    "diary/",     # 日记 MD
    "agent/",     # Agent 身份/记忆/配置
    "user/",      # 用户级数据
    "plan/",      # 计划文档（仅备份，不加入同步范围）
]

BACKUP_EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}

BACKUP_DB_FILES = [
    "dataset/lifewatch_ai.db",   # 主数据库（全量备份，含所有表）
]
```

**注意**：
- `chat_history.db` 已弃用，不在备份范围
- 数据库是**全量备份**（不同于同步的 `SYNC_TABLES` 31 张表子集），包含本地产能表、配置表、file_sync_state 等所有表
- plan 加入备份但不加入同步（同步改造是独立决策）

**备份格式**：平铺 + 文件夹时间戳，不打包 zip

```
{lifeprism_data_path}/backups/
├── docs/
│   ├── 2026-07-17T03-00-00/         ← 每日文档快照
│   │   ├── session/
│   │   ├── diary/
│   │   ├── agent/
│   │   ├── user/
│   │   └── plan/
│   ├── 2026-07-16T03-00-00/
│   └── 2026-07-15T03-00-00/
└── db/
    ├── lifewatch_ai-2026-07-17T08-00-00.db    ← SQLite Online Backup 产物
    ├── lifewatch_ai-2026-07-17T16-00-00.db
    └── lifewatch_ai-2026-07-18T00-00-00.db
```

**选择平铺而非 zip 的理由**：
1. 用户可直接用文件管理器查看备份内容（关键需求）
2. 单文件恢复只需复制，无需解压
3. 数据库 .db 文件可用 DB Browser 直接打开
4. LifePrism 数据量小，无压缩需求
5. 现代备份工具（restic、borg）均采用平铺 + 去重

**备份频率**：

| 备份对象 | 频率 | 触发时间 | 保留份数 |
|---------|------|---------|---------|
| 文档 | 每天 1 次 | 本地 03:00 | 3 份 |
| 数据库 | 每 8 小时 1 次 | 本地 00:00 / 08:00 / 16:00 | 3 份 |

**调度机制**（复用现有 `ScheduleService`，`lifeprism/server/services/schedule_service.py`）：

```python
# schedule_service.py 修改

from lifeprism.server.services.backup_service import backup_service

class ScheduleService:
    def __init__(self) -> None:
        # ... 现有代码 ...

        # 注册备份任务
        self._system_jobs.extend([
            {
                "func": backup_service.backup_documents,
                "trigger": "cron",
                "kwargs": {"cron_expr": "0 3 * * *"},  # 每天本地 03:00
                "job_id": "backup_documents",
            },
            {
                "func": backup_service.backup_database,
                "trigger": "cron",
                "kwargs": {"cron_expr": "0 0,8,16 * * *"},  # 每天本地 00/08/16 点
                "job_id": "backup_database",
            },
        ])
```

**复用现有特性**：
- 本地时区处理：`pytz.timezone(get_user_timezone())`
- 状态持久化：`_save_cron_state` 机制（避免重启后重复执行）
- 启动补偿：错过 03:00 时启动后异步执行一次
- run_mode 守卫：`run_mode != "full"` 时跳过备份（云端 agent_only 不备份）

**BackupService 设计**：

```python
# lifeprism/server/services/backup_service.py（新建）

class BackupService:
    """备份服务（单例）
    
    职责：执行备份逻辑（不负责调度，调度由 ScheduleService 负责）
    """

    async def backup_documents(self) -> None:
        """文档全量备份（保留 3 份）
        
        流程：
        1. 创建 backups/docs/{timestamp}/ 目录
        2. 复制 BACKUP_DIRS 下的文件（排除 BACKUP_EXCLUDED_FILENAMES）
        3. 完整性校验：文件数量比对 + 每个文件 hash 比对
        4. 校验失败 → 删除损坏备份 → 记录 ERROR 日志
        5. 清理超过 3 份的旧备份（按时间戳排序，保留最新 3 份）
        """

    async def backup_database(self) -> None:
        """数据库全量备份（保留 3 份，使用 SQLite Online Backup API）
        
        流程：
        1. SQLite Online Backup: 
           source = sqlite3.connect(lifewatch_ai.db)
           target = sqlite3.connect(backups/db/lifewatch_ai-{timestamp}.db)
           source.backup(target)
        2. 完整性校验：PRAGMA integrity_check
        3. 校验失败 → 删除损坏备份 → 记录 ERROR 日志
        4. 清理超过 3 份的旧备份（按时间戳排序，保留最新 3 份）
        """

backup_service = BackupService()
```

**完整性校验（方案 A 完整校验）**：

- 文档备份校验：文件数量比对 + 每个文件 hash 比对
- 数据库备份校验：`PRAGMA integrity_check`
- 校验失败处理：删除损坏的备份目录/文件 + 记录 ERROR 日志 + 不影响其他任务

**职责分离**：

- `ScheduleService`：何时执行（cron、状态持久化、启动补偿）
- `BackupService`：如何执行（文件复制、SQLite Backup API、保留策略、完整性校验）

## Acceptance criteria

- [ ] 新建 `lifeprism/backup/constants.py`（BACKUP_DIRS / BACKUP_EXCLUDED_FILENAMES / BACKUP_DB_FILES）
- [ ] 新建 `lifeprism/server/services/backup_service.py`（BackupService 单例）
- [ ] 文档备份：每天 03:00 自动触发
- [ ] 数据库备份：每 8 小时（00/08/16 点）自动触发
- [ ] 备份位置：`{lifeprism_data_path}/backups/{docs,db}/{timestamp}/`
- [ ] 平铺存储（非 zip），支持文件管理器直接查看
- [ ] 文档备份覆盖 session/diary/agent/user/plan，排除 chat_history.json 和 bootstrap.md
- [ ] 数据库使用 SQLite Online Backup API 全量备份 lifewatch_ai.db
- [ ] 数据库备份文件命名：`lifewatch_ai-{timestamp}.db`
- [ ] 文档与数据库各自保留最新 3 份
- [ ] 文档备份完整性校验：文件数量 + hash 比对
- [ ] 数据库备份完整性校验：`PRAGMA integrity_check`
- [ ] 校验失败自动删除损坏备份并记录 ERROR 日志
- [ ] ScheduleService 注册两个 cron 任务（backup_documents / backup_database）
- [ ] 云端 agent_only 模式不执行备份（复用 `run_mode != "full"` 守卫）
- [ ] 启动补偿：错过 03:00 时启动后异步执行一次
- [ ] 单元测试覆盖备份逻辑（文件复制、保留策略、完整性校验）
- [ ] 集成测试覆盖端到端备份流程

## Blocked by

None - can start immediately

## User stories covered

PRD 用户故事：33（定时全量备份兜底）

## Related ADRs

- [docs/adr/2026-07-17-data-backup-strategy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-data-backup-strategy.md) - 数据备份策略（平铺存储 + 复用 ScheduleService + 不做恢复 API），本 issue 的核心 ADR
- [docs/adr/2026-07-17-backup-sync-decoupled-scope.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-backup-sync-decoupled-scope.md) - 备份范围与同步范围解耦（BACKUP_DIRS 独立定义，含 plan 不依赖 SYNC_DIRECTORIES）
- [docs/adr/2026-07-17-conflict-failure-policy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-failure-policy.md) - 云端 agent_only 模式不备份的决策依据
