"""备份模块共享常量

独立定义备份范围，**不依赖** ``lifeprism.sync.constants.SYNC_DIRECTORIES``。
设计依据：同步和备份职责不同（同步是多端一致性，备份是数据安全性），
范围应独立演进，不应强行耦合。

参考:
- ADR: docs/adr/2026-07-17-backup-sync-decoupled-scope.md（备份范围与同步范围解耦）
- ADR: docs/adr/2026-07-17-data-backup-strategy.md（数据备份策略）
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-7-backup-service-and-scheduler.md
"""

# 文档备份范围：相对 lifeprism_data_path 的目录路径
#
# 与 SYNC_DIRECTORIES 的差异：多 plan/（计划文档，仅备份不加入同步范围）
# 与 SYNC_DIRECTORIES 的一致性：session/ diary/ agent/ user/ 内容保持一致（纪律性约束，非代码依赖）
BACKUP_DIRS = [
    "session/",  # 聊天会话 JSONL
    "diary/",  # 日记 MD
    "agent/",  # Agent 身份/记忆/配置
    "user/",  # 用户级数据
    "plan/",  # 计划文档（仅备份，不加入同步范围）
]

# 备份排除文件名（与同步 EXCLUDED_FILENAMES 保持一致）
# - chat_history.json: 由 dreaming task 写入，云端无 dreaming 不变更
# - bootstrap.md: Agent 启动引导配置，由模板初始化，各端独立维护
BACKUP_EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}

# 数据库全量备份清单：相对 lifeprism_data_path 的路径
#
# 注意：
# - 数据库是**全量备份**（不同于同步的 SYNC_TABLES 31 张表子集），包含所有表
# - chat_history.db 已弃用，不在备份范围
BACKUP_DB_FILES = [
    "dataset/lifewatch_ai.db",  # 主数据库（全量备份，含所有表）
]
