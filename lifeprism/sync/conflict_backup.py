"""sync_conflict 双向备份 + 30 天清理机制

修复 sync_conflict/ 仅备份本地的 bug：冲突降级 keep_ours 后云端版本永久丢失，
用户无法对比本地与云端差异，也无法在选错 keep_ours 时恢复云端版本。

本模块提供三个核心能力：
1. ``flatten_file_path`` —— 将文件相对路径扁平化为文件名（用 ``__`` 分隔），
   避免 sync_conflict/{ts}/ 下嵌套子目录。
2. ``backup_conflict_versions`` —— 同时备份本地与云端两个版本到
   ``sync_conflict/{ts}/{flattened}.local.md`` 与 ``.remote.md``。
3. ``cleanup_expired_conflict_backups`` —— 清理超过 30 天的冲突备份子目录，
   在每次冲突备份时顺带触发。

设计决策：
- 路径扁平化而非嵌套：避免 Windows 路径长度问题，文件名即唯一标识
- 同时备份本地与云端：让用户具备完整的对比与恢复能力
- 30 天清理沿用数据备份 spec 策略（ADR-2026-07-17-data-backup-strategy.md）
- 向后兼容旧的单文件备份结构：不强制迁移，清理机制对旧结构同样生效

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-5-sync-conflict-dual-backup-and-cleanup.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 9、19（用户故事 30、31）
- ADR: docs/adr/2026-07-17-conflict-failure-policy.md（核心 ADR，要求双向备份）
- ADR: docs/adr/2026-07-17-data-backup-strategy.md（30 天清理沿用）
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from lifeprism.utils import get_logger

logger = get_logger(__name__)


# sync_conflict/ 备份保留期（天），与数据备份 spec 一致
CONFLICT_BACKUP_RETENTION_DAYS = 30

# 时间戳目录名格式（UTC 时间，文件系统友好：无冒号）
# 沿用旧实现格式，保持向后兼容；时间戳本身由 UTC aware datetime 生成
_CONFLICT_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"


def flatten_file_path(file_path: str) -> str:
    """将文件相对路径扁平化为文件名（用 ``__`` 分隔避免嵌套）

    设计意图：sync_conflict/{ts}/ 下不再创建子目录，避免 Windows 路径长度
    问题与目录创建副作用。文件相对路径中的目录分隔符（``/`` 或 ``\\``）
    统一替换为 ``__``，得到一个扁平化的文件名。

    Examples:
        >>> flatten_file_path("agent/behavior.md")
        'agent__behavior.md'
        >>> flatten_file_path("agent/subdir/file.md")
        'agent__subdir__file.md'
        >>> flatten_file_path("agent\\\\subdir\\\\file.md")
        'agent__subdir__file.md'

    Args:
        file_path: 文件相对路径（如 ``agent/behavior.md``），允许 ``/`` 或 ``\\`` 分隔

    Returns:
        扁平化后的文件名（如 ``agent__behavior.md``）
    """
    # 先替换反斜杠为正斜杠，再统一替换正斜杠为 __。
    # 采用两步替换而非一次性正则，保持纯字符串替换语义，行为可预测。
    normalized = file_path.replace("\\", "/")
    return normalized.replace("/", "__")


def cleanup_expired_conflict_backups(
    data_path: Path,
    max_age_days: int = CONFLICT_BACKUP_RETENTION_DAYS,
    now: datetime | None = None,
) -> int:
    """清理超过保留期的冲突备份子目录

    清理策略（沿用数据备份 spec，ADR-2026-07-17-data-backup-strategy.md）：
    - 30 天保留期，超期自动删除子目录
    - 按目录名中的时间戳判定过期（比 mtime 更稳定，不受文件系统复制/移动影响）
    - 保守策略：只删除名称符合 ``%Y%m%d_%H%M%S`` 格式的目录，跳过无法解析的目录

    边界语义：
    - ``max_age_days=30`` 表示"30 天内的都保留"
    - 恰好 30 天的目录保留（``age.days <= max_age_days``）
    - 第 31 天才视为过期（``age.days > max_age_days``）
    - 使用 ``age.days`` 而非 ``age > timedelta(days=...)`` 做判定，避免微秒精度
      导致"恰好 30 天"的目录被误删（目录名时间戳精度为秒，``now`` 含微秒）

    Args:
        data_path: lifeprism 数据根目录（``settings.lifeprism_data_path``）
        max_age_days: 保留期（天），默认 30；超过此天数的目录被删除
        now: 判定基准时间（UTC aware）；为 None 时使用 ``datetime.now(timezone.utc)``

    Returns:
        被删除的目录数量
    """
    if now is None:
        now = datetime.now(timezone.utc)
    # 防御性：确保 now 是 aware datetime（遵循 time-handling-rules §3.3）
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    sync_conflict_root = data_path / "sync_conflict"
    if not sync_conflict_root.exists():
        return 0

    deleted_count = 0
    for sub_dir in sync_conflict_root.iterdir():
        if not sub_dir.is_dir():
            continue

        # 解析目录名时间戳；无法解析的目录跳过（保守策略）
        ts = _parse_conflict_timestamp(sub_dir.name)
        if ts is None:
            continue

        # 判定过期：按天粒度比较，避免微秒精度问题
        # age.days 是 floor 运算，30 天 + 1 微秒 → days=30（保留）
        # 31 天整 → days=31（删除）
        age = now - ts
        if age.days > max_age_days:
            try:
                shutil.rmtree(sub_dir)
                deleted_count += 1
                logger.info(
                    "cleanup_expired_conflict_backups: 删除过期冲突备份 dir=%s, age_days=%d",
                    sub_dir,
                    age.days,
                )
            except OSError:
                logger.warning(
                    "cleanup_expired_conflict_backups: 删除目录失败 dir=%s",
                    sub_dir,
                    exc_info=True,
                )

    return deleted_count


def _parse_conflict_timestamp(dir_name: str) -> datetime | None:
    """解析冲突备份子目录名时间戳为 UTC aware datetime

    目录名格式：``%Y%m%d_%H%M%S``（如 ``20260717_154500``）。

    Args:
        dir_name: 目录名字符串

    Returns:
        解析成功返回 UTC aware datetime；格式不匹配返回 None
    """
    try:
        # strptime 返回 naive datetime，目录名约定为 UTC 时间
        # （由 datetime.now(timezone.utc).strftime 生成）
        return datetime.strptime(dir_name, _CONFLICT_TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def backup_conflict_versions(
    data_path: Path,
    file_path: str,
    local_content: str,
    remote_content: str,
    timestamp_str: str | None = None,
) -> Path:
    """同时备份冲突文件的本地与云端两个版本

    修复旧实现仅备份 local_content 的 bug：云端版本在降级 keep_ours 后永久丢失，
    用户无法对比本地与云端差异，也无法在选错 keep_ours 时恢复云端版本。

    备份目录结构（扁平化，路径用 ``__`` 分隔避免嵌套）::

        sync_conflict/
        └── 20260717_154500/
            ├── agent__behavior.md.local.md    ← 本地版本
            └── agent__behavior.md.remote.md   ← 云端版本

    设计要点：
    - 同一时间戳下多个冲突文件共享同一个时间戳子目录（调用方控制 timestamp_str）
    - 路径扁平化避免 Windows 路径长度问题
    - 时间戳默认由 UTC aware datetime 生成（遵循 time-handling-rules §3.1）
    - 目录名格式沿用旧实现 ``%Y%m%d_%H%M%S``，保持向后兼容
    - 每次备份完成后顺带触发 30 天清理（PRD 决策 9）

    Args:
        data_path: lifeprism 数据根目录（``settings.lifeprism_data_path``）
        file_path: 文件相对路径（如 ``agent/behavior.md``），允许 ``/`` 或 ``\\`` 分隔
        local_content: 本地版本内容（即将被合并结果覆盖的原始本地内容）
        remote_content: 云端版本内容（降级 keep_ours 后将永久丢失的云端内容）
        timestamp_str: 时间戳目录名（如 ``20260717_154500``）；
                       为 None 时自动生成当前 UTC 时间戳

    Returns:
        冲突备份目录路径（``sync_conflict/{ts}/``），便于调用方记录日志
    """
    # 生成时间戳目录名（UTC aware，遵循 time-handling-rules §3.1）
    if timestamp_str is None:
        timestamp_str = datetime.now(timezone.utc).strftime(_CONFLICT_TIMESTAMP_FORMAT)

    # 构建冲突备份目录：sync_conflict/{ts}/
    conflict_dir = (data_path / "sync_conflict" / timestamp_str).resolve()
    conflict_dir.mkdir(parents=True, exist_ok=True)

    # 扁平化文件路径作为备份文件名前缀
    flattened_name = flatten_file_path(file_path)

    # 备份本地版本：{flattened}.local.md
    local_backup_path = conflict_dir / f"{flattened_name}.local.md"
    local_backup_path.write_text(local_content, encoding="utf-8")

    # 备份云端版本：{flattened}.remote.md
    remote_backup_path = conflict_dir / f"{flattened_name}.remote.md"
    remote_backup_path.write_text(remote_content, encoding="utf-8")

    logger.info(
        "backup_conflict_versions: 已备份冲突文件 local+remote 版本 file_path=%s, backup_dir=%s",
        file_path,
        conflict_dir,
    )

    # PRD 决策 9：每次冲突备份时顺带检查并清理过期目录
    # 清理在备份完成后执行，确保本次备份的目录不受影响（新目录必然未过期）
    try:
        cleanup_expired_conflict_backups(data_path)
    except Exception:
        # 清理失败不影响备份主流程（仅记录日志）
        logger.warning(
            "backup_conflict_versions: 顺带清理过期冲突备份失败，不影响本次备份",
            exc_info=True,
        )

    return conflict_dir
