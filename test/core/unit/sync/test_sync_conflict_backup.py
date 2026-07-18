"""sync_conflict 双向备份 + 30 天清理机制单元测试

测试 seam:
- Seam 1: flatten_file_path(file_path: str) -> str —— 路径扁平化（用 __ 分隔避免嵌套）
- Seam 2: backup_conflict_versions(...) -> Path —— 同时备份本地与云端两个版本
- Seam 3: cleanup_expired_conflict_backups(...) -> int —— 清理超过 30 天的冲突备份子目录
- Seam 4: 向后兼容 —— 旧的单文件备份结构不被破坏，清理机制对旧结构也生效

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-5-sync-conflict-dual-backup-and-cleanup.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 9、19（用户故事 30、31）
- ADR: docs/adr/2026-07-17-conflict-failure-policy.md（核心 ADR，要求双向备份）
- ADR: docs/adr/2026-07-17-data-backup-strategy.md（30 天清理沿用）
- Bug 根因: sync_client.py 旧实现仅备份 local_content，remote_content 永久丢失
"""

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: flatten_file_path 路径扁平化 ====================


class TestFlattenFilePath:
    """flatten_file_path 将文件相对路径转换为扁平化文件名

    设计意图：sync_conflict/{ts}/ 下不再嵌套子目录，避免 Windows 路径长度
    与目录创建副作用。路径分隔符统一替换为 `__`。
    """

    def test_simple_path_uses_double_underscore_separator(self):
        """简单单层路径 agent/behavior.md → agent__behavior.md"""
        from lifeprism.sync.conflict_backup import flatten_file_path

        assert flatten_file_path("agent/behavior.md") == "agent__behavior.md"

    def test_deep_path_uses_double_underscore_separator(self):
        """多层路径 agent/subdir/file.md → agent__subdir__file.md"""
        from lifeprism.sync.conflict_backup import flatten_file_path

        assert flatten_file_path("agent/subdir/file.md") == "agent__subdir__file.md"

    def test_windows_backslash_path_normalized(self):
        """Windows 反斜杠路径 agent\\subdir\\file.md → agent__subdir__file.md"""
        from lifeprism.sync.conflict_backup import flatten_file_path

        assert flatten_file_path("agent\\subdir\\file.md") == "agent__subdir__file.md"

    def test_mixed_slashes_normalized(self):
        """混合斜杠 agent/subdir\\file.md → agent__subdir__file.md"""
        from lifeprism.sync.conflict_backup import flatten_file_path

        assert flatten_file_path("agent/subdir\\file.md") == "agent__subdir__file.md"

    def test_no_directory_separator_unchanged(self):
        """无目录分隔符的纯文件名保持不变"""
        from lifeprism.sync.conflict_backup import flatten_file_path

        assert flatten_file_path("behavior.md") == "behavior.md"

    def test_multiple_consecutive_separators_collapsed(self):
        """连续分隔符（如错拼的路径）被分别替换为 __，不特殊合并

        选择保守策略：不做"合并连续分隔符"的特殊处理，保持函数纯替换语义，
        避免引入隐藏的路径规范化逻辑。
        """
        from lifeprism.sync.conflict_backup import flatten_file_path

        # "a//b" -> "a____b"（两个 / 各自替换为 __）
        # 这是保守且可预测的行为
        assert flatten_file_path("a//b.md") == "a____b.md"

    def test_filename_with_dot_preserved(self):
        """文件名中的点被保留（不视为分隔符）"""
        from lifeprism.sync.conflict_backup import flatten_file_path

        assert flatten_file_path("diary/2026-07-14.md") == "diary__2026-07-14.md"


# ==================== Seam 2: backup_conflict_versions 双向备份 ====================


class TestBackupConflictVersions:
    """backup_conflict_versions 同时备份本地与云端两个版本

    修复 sync_client.py 旧实现仅备份 local_content 的 bug：
    云端版本在降级 keep_ours 后永久丢失，用户无法对比与恢复。

    备份目录结构（扁平化，路径用 ``__`` 分隔避免嵌套）::

        sync_conflict/
        └── 20260717_154500/
            ├── agent__behavior.md.local.md    ← 本地版本
            └── agent__behavior.md.remote.md   ← 云端版本
    """

    def test_creates_both_local_and_remote_backup_files(self, tmp_path):
        """触发冲突备份后同时生成 .local.md 与 .remote.md 两个文件"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="# 本地内容",
            remote_content="# 云端内容",
            timestamp_str="20260717_154500",
        )

        # 期望两个备份文件都存在
        local_backup = result / "agent__behavior.md.local.md"
        remote_backup = result / "agent__behavior.md.remote.md"
        assert local_backup.is_file(), "应存在 .local.md 本地版本备份"
        assert remote_backup.is_file(), "应存在 .remote.md 云端版本备份"

    def test_local_backup_content_matches_local_input(self, tmp_path):
        """.local.md 文件内容应与传入的 local_content 完全一致"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        local_content = "# 本地日记\n今天心情不错"
        remote_content = "# 云端日记\n今天天气晴朗"

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="diary/2026-07-14.md",
            local_content=local_content,
            remote_content=remote_content,
            timestamp_str="20260717_154500",
        )

        local_backup = result / "diary__2026-07-14.md.local.md"
        assert local_backup.read_text(encoding="utf-8") == local_content

    def test_remote_backup_content_matches_remote_input(self, tmp_path):
        """.remote.md 文件内容应与传入的 remote_content 完全一致"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        local_content = "# 本地日记"
        remote_content = "# 云端日记\n今天天气晴朗"

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="diary/2026-07-14.md",
            local_content=local_content,
            remote_content=remote_content,
            timestamp_str="20260717_154500",
        )

        remote_backup = result / "diary__2026-07-14.md.remote.md"
        assert remote_backup.read_text(encoding="utf-8") == remote_content

    def test_uses_timestamp_subdirectory_under_sync_conflict(self, tmp_path):
        """备份目录位于 sync_conflict/{timestamp}/ 下"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local",
            remote_content="remote",
            timestamp_str="20260717_154500",
        )

        expected_dir = (tmp_path / "sync_conflict" / "20260717_154500").resolve()
        assert result.resolve() == expected_dir

    def test_deep_path_uses_flattened_filename(self, tmp_path):
        """深层路径 agent/subdir/file.md → agent__subdir__file.md.local.md / .remote.md"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/subdir/file.md",
            local_content="local",
            remote_content="remote",
            timestamp_str="20260717_154500",
        )

        assert (result / "agent__subdir__file.md.local.md").is_file()
        assert (result / "agent__subdir__file.md.remote.md").is_file()

    def test_windows_backslash_path_uses_flattened_filename(self, tmp_path):
        """Windows 反斜杠路径 agent\\subdir\\file.md → agent__subdir__file.md.*"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent\\subdir\\file.md",
            local_content="local",
            remote_content="remote",
            timestamp_str="20260717_154500",
        )

        assert (result / "agent__subdir__file.md.local.md").is_file()
        assert (result / "agent__subdir__file.md.remote.md").is_file()

    def test_creates_sync_conflict_dir_if_not_exists(self, tmp_path):
        """sync_conflict/ 目录不存在时应自动创建（含 timestamp 子目录）"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        # 确认 sync_conflict 不存在
        assert not (tmp_path / "sync_conflict").exists()

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local",
            remote_content="remote",
            timestamp_str="20260717_154500",
        )

        assert result.is_dir(), "备份目录应被创建"
        assert (tmp_path / "sync_conflict").is_dir(), "sync_conflict/ 应被创建"

    def test_default_timestamp_generated_when_not_provided(self, tmp_path):
        """未传 timestamp_str 时自动生成当前 UTC 时间戳（%Y%m%d_%H%M%S 格式）"""
        import re

        from lifeprism.sync.conflict_backup import backup_conflict_versions

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local",
            remote_content="remote",
        )

        # 目录名应符合 %Y%m%d_%H%M%S 格式（8 位日期 + _ + 6 位时间）
        dir_name = result.name
        assert re.match(r"^\d{8}_\d{6}$", dir_name), (
            f"目录名应符合 %%Y%%m%%d_%%H%%M%%S 格式，实际: {dir_name}"
        )

    def test_backup_returns_conflict_directory_path(self, tmp_path):
        """返回值是冲突备份目录路径（sync_conflict/{ts}/），便于调用方记录日志"""
        from pathlib import Path

        from lifeprism.sync.conflict_backup import backup_conflict_versions

        result = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local",
            remote_content="remote",
            timestamp_str="20260717_154500",
        )

        assert isinstance(result, Path)
        assert result.is_dir()

    def test_multiple_files_same_timestamp_share_directory(self, tmp_path):
        """同一时间戳下多个冲突文件共享同一个时间戳子目录"""
        from lifeprism.sync.conflict_backup import backup_conflict_versions

        ts = "20260717_154500"
        result1 = backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local1",
            remote_content="remote1",
            timestamp_str=ts,
        )
        result2 = backup_conflict_versions(
            data_path=tmp_path,
            file_path="diary/2026-07-14.md",
            local_content="local2",
            remote_content="remote2",
            timestamp_str=ts,
        )

        # 两个文件备份到同一个时间戳目录
        assert result1 == result2
        # 目录下应有 4 个文件（2 个文件 × 2 个版本）
        assert len(list(result1.iterdir())) == 4


# ==================== Seam 3: cleanup_expired_conflict_backups 30 天清理 ====================


class TestCleanupExpiredConflictBackups:
    """cleanup_expired_conflict_backups 清理超过 30 天的冲突备份子目录

    清理策略（沿用数据备份 spec，ADR-2026-07-17-data-backup-strategy.md）：
    - 30 天保留期，超期自动删除子目录
    - 按目录名中的时间戳判定过期（比 mtime 更稳定，不受文件系统复制/移动影响）
    - 每次 conflict backup 时顺带检查并清理过期目录
    """

    def test_deletes_directory_older_than_30_days(self, tmp_path):
        """超过 30 天的子目录应被删除"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import (
            CONFLICT_BACKUP_RETENTION_DAYS,
            cleanup_expired_conflict_backups,
        )

        # 当前时间（UTC）
        now = datetime.now(timezone.utc)

        # 创建一个 31 天前的备份目录
        old_ts = (now - timedelta(days=31)).strftime("%Y%m%d_%H%M%S")
        old_dir = tmp_path / "sync_conflict" / old_ts
        old_dir.mkdir(parents=True)
        (old_dir / "agent__behavior.md.local.md").write_text("local", encoding="utf-8")
        (old_dir / "agent__behavior.md.remote.md").write_text("remote", encoding="utf-8")

        # 执行清理
        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            max_age_days=CONFLICT_BACKUP_RETENTION_DAYS,
            now=now,
        )

        # 旧目录应被删除
        assert deleted_count == 1
        assert not old_dir.exists()

    def test_keeps_directory_within_30_days(self, tmp_path):
        """30 天内的子目录应被保留"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import (
            CONFLICT_BACKUP_RETENTION_DAYS,
            cleanup_expired_conflict_backups,
        )

        now = datetime.now(timezone.utc)

        # 创建一个 10 天前的备份目录
        recent_ts = (now - timedelta(days=10)).strftime("%Y%m%d_%H%M%S")
        recent_dir = tmp_path / "sync_conflict" / recent_ts
        recent_dir.mkdir(parents=True)
        (recent_dir / "agent__behavior.md.local.md").write_text("local", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            max_age_days=CONFLICT_BACKUP_RETENTION_DAYS,
            now=now,
        )

        # 近期目录应被保留
        assert deleted_count == 0
        assert recent_dir.exists()

    def test_boundary_29_days_kept(self, tmp_path):
        """边界：29 天前的目录保留（未超过 30 天）"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import (
            CONFLICT_BACKUP_RETENTION_DAYS,
            cleanup_expired_conflict_backups,
        )

        now = datetime.now(timezone.utc)

        # 29 天前的目录
        boundary_ts = (now - timedelta(days=29)).strftime("%Y%m%d_%H%M%S")
        boundary_dir = tmp_path / "sync_conflict" / boundary_ts
        boundary_dir.mkdir(parents=True)
        (boundary_dir / "test.md.local.md").write_text("x", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            max_age_days=CONFLICT_BACKUP_RETENTION_DAYS,
            now=now,
        )

        assert deleted_count == 0
        assert boundary_dir.exists(), "29 天前的目录应保留（未超过 30 天）"

    def test_boundary_31_days_deleted(self, tmp_path):
        """边界：31 天前的目录删除（已超过 30 天）"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import (
            CONFLICT_BACKUP_RETENTION_DAYS,
            cleanup_expired_conflict_backups,
        )

        now = datetime.now(timezone.utc)

        # 31 天前的目录
        boundary_ts = (now - timedelta(days=31)).strftime("%Y%m%d_%H%M%S")
        boundary_dir = tmp_path / "sync_conflict" / boundary_ts
        boundary_dir.mkdir(parents=True)
        (boundary_dir / "test.md.local.md").write_text("x", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            max_age_days=CONFLICT_BACKUP_RETENTION_DAYS,
            now=now,
        )

        assert deleted_count == 1
        assert not boundary_dir.exists(), "31 天前的目录应删除（已超过 30 天）"

    def test_boundary_exactly_30_days_kept(self, tmp_path):
        """边界：恰好 30 天前的目录保留（保留期含 30 天，第 31 天才删除）

        语义：保留期 30 天 = "30 天内的都保留" = "第 31 天才视为过期"
        """
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import (
            CONFLICT_BACKUP_RETENTION_DAYS,
            cleanup_expired_conflict_backups,
        )

        now = datetime.now(timezone.utc)

        # 恰好 30 天前的目录
        boundary_ts = (now - timedelta(days=30)).strftime("%Y%m%d_%H%M%S")
        boundary_dir = tmp_path / "sync_conflict" / boundary_ts
        boundary_dir.mkdir(parents=True)
        (boundary_dir / "test.md.local.md").write_text("x", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            max_age_days=CONFLICT_BACKUP_RETENTION_DAYS,
            now=now,
        )

        assert deleted_count == 0, "恰好 30 天的目录应保留（保留期含 30 天）"
        assert boundary_dir.exists()

    def test_mixed_old_and_new_directories(self, tmp_path):
        """混合场景：旧目录被删除，新目录被保留"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import (
            CONFLICT_BACKUP_RETENTION_DAYS,
            cleanup_expired_conflict_backups,
        )

        now = datetime.now(timezone.utc)

        # 创建 3 个目录：50 天前、5 天前、40 天前
        old_ts1 = (now - timedelta(days=50)).strftime("%Y%m%d_%H%M%S")
        new_ts = (now - timedelta(days=5)).strftime("%Y%m%d_%H%M%S")
        old_ts2 = (now - timedelta(days=40)).strftime("%Y%m%d_%H%M%S")

        for ts in [old_ts1, new_ts, old_ts2]:
            d = tmp_path / "sync_conflict" / ts
            d.mkdir(parents=True)
            (d / "test.md.local.md").write_text("x", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            max_age_days=CONFLICT_BACKUP_RETENTION_DAYS,
            now=now,
        )

        # 2 个旧目录被删除，1 个新目录保留
        assert deleted_count == 2
        assert not (tmp_path / "sync_conflict" / old_ts1).exists()
        assert not (tmp_path / "sync_conflict" / old_ts2).exists()
        assert (tmp_path / "sync_conflict" / new_ts).exists()

    def test_no_sync_conflict_dir_returns_zero(self, tmp_path):
        """sync_conflict/ 不存在时返回 0，不抛异常"""
        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        # 不创建 sync_conflict 目录
        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            now=datetime.now(timezone.utc),
        )

        assert deleted_count == 0

    def test_empty_sync_conflict_dir_returns_zero(self, tmp_path):
        """sync_conflict/ 存在但为空时返回 0"""
        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        (tmp_path / "sync_conflict").mkdir(parents=True)

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            now=datetime.now(timezone.utc),
        )

        assert deleted_count == 0

    def test_returns_count_of_deleted_directories(self, tmp_path):
        """返回值是被删除的目录数量"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        now = datetime.now(timezone.utc)

        # 创建 5 个旧目录
        for days_ago in [35, 40, 50, 60, 100]:
            ts = (now - timedelta(days=days_ago)).strftime("%Y%m%d_%H%M%S")
            d = tmp_path / "sync_conflict" / ts
            d.mkdir(parents=True)
            (d / "test.md.local.md").write_text("x", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            now=now,
        )

        assert deleted_count == 5

    def test_skips_non_timestamp_named_directories(self, tmp_path):
        """跳过名称不符合时间戳格式的目录（保守策略，不删除无法识别的目录）

        设计原因：避免误删用户手工创建或未来其他用途的目录。
        只有能解析为 %Y%m%d_%H%M%S 格式的目录才参与过期判定。
        """
        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        # 不符合时间戳格式的目录
        weird_dir = tmp_path / "sync_conflict" / "weird_name"
        weird_dir.mkdir(parents=True)
        (weird_dir / "test.md").write_text("x", encoding="utf-8")

        # 一个时间戳格式但很旧的目录（应被删除）
        old_ts = "20200101_000000"
        old_dir = tmp_path / "sync_conflict" / old_ts
        old_dir.mkdir(parents=True)
        (old_dir / "test.md.local.md").write_text("x", encoding="utf-8")

        deleted_count = cleanup_expired_conflict_backups(
            data_path=tmp_path,
            now=datetime.now(timezone.utc),
        )

        # 只删除时间戳格式的旧目录，跳过 weird_name
        assert deleted_count == 1
        assert not old_dir.exists()
        assert weird_dir.exists(), "非时间戳格式的目录应被保留（保守策略）"

    def test_default_now_uses_current_utc_time(self, tmp_path):
        """未传 now 时使用当前 UTC 时间作为判定基准"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        # 创建一个 100 天前的目录（确保任何运行时刻都视为过期）
        very_old_ts = (datetime.now(timezone.utc) - timedelta(days=100)).strftime(
            "%Y%m%d_%H%M%S"
        )
        old_dir = tmp_path / "sync_conflict" / very_old_ts
        old_dir.mkdir(parents=True)
        (old_dir / "test.md.local.md").write_text("x", encoding="utf-8")

        # 不传 now，使用默认当前时间
        deleted_count = cleanup_expired_conflict_backups(data_path=tmp_path)

        assert deleted_count == 1
        assert not old_dir.exists()


# ==================== Seam 3 补充: cleanup 触发时机 ====================


class TestCleanupTriggerOnBackup:
    """backup_conflict_versions 在备份完成后顺带触发清理

    PRD 决策 9：每次冲突备份时顺带检查并清理过期目录。
    这样无需独立的定时任务，清理频率与备份频率天然对齐。
    """

    def test_backup_triggers_cleanup_of_old_directories(self, tmp_path):
        """冲突备份时自动清理过期的旧目录"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import backup_conflict_versions

        now = datetime.now(timezone.utc)

        # 预置一个 50 天前的过期目录
        old_ts = (now - timedelta(days=50)).strftime("%Y%m%d_%H%M%S")
        old_dir = tmp_path / "sync_conflict" / old_ts
        old_dir.mkdir(parents=True)
        (old_dir / "old__file.md.local.md").write_text("old", encoding="utf-8")

        # 触发新的冲突备份（应顺带清理过期目录）
        backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local",
            remote_content="remote",
            timestamp_str=now.strftime("%Y%m%d_%H%M%S"),
        )

        # 过期目录应被清理
        assert not old_dir.exists(), "备份时应顺带清理过期目录"

    def test_backup_keeps_recent_directories_after_cleanup(self, tmp_path):
        """冲突备份时清理不影响近期目录"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import backup_conflict_versions

        now = datetime.now(timezone.utc)

        # 预置一个 5 天前的近期目录
        recent_ts = (now - timedelta(days=5)).strftime("%Y%m%d_%H%M%S")
        recent_dir = tmp_path / "sync_conflict" / recent_ts
        recent_dir.mkdir(parents=True)
        (recent_dir / "recent__file.md.local.md").write_text("recent", encoding="utf-8")

        # 触发新的冲突备份
        backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="local",
            remote_content="remote",
            timestamp_str=now.strftime("%Y%m%d_%H%M%S"),
        )

        # 近期目录应被保留
        assert recent_dir.exists(), "清理不应影响近期目录"


# ==================== Seam 4: 向后兼容（旧的单文件备份结构） ====================


class TestBackwardCompatibility:
    """向后兼容：旧的单文件备份结构不被破坏，清理机制对旧结构也生效

    旧实现（sync_client.py L1610-1614）的备份结构::

        sync_conflict/
        └── 20260717_154500/
            └── agent/              ← 嵌套子目录
                └── behavior.md     ← 单文件，无 .local.md / .remote.md 后缀

    新实现的备份结构::

        sync_conflict/
        └── 20260717_154500/
            ├── agent__behavior.md.local.md    ← 扁平化 + .local.md 后缀
            └── agent__behavior.md.remote.md   ← 扁平化 + .remote.md 后缀

    向后兼容策略：
    1. 旧结构不被破坏（不强制迁移）
    2. 清理机制对旧结构同样生效（按目录名时间戳判定，与目录内文件结构无关）
    3. 新备份使用新结构
    """

    def test_old_single_file_backup_structure_preserved_by_cleanup(self, tmp_path):
        """清理机制不会破坏旧的单文件备份结构（仅按时间戳判定，不修改目录内容）"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        now = datetime.now(timezone.utc)

        # 模拟旧结构的近期备份（嵌套子目录 + 单文件）
        recent_ts = (now - timedelta(days=5)).strftime("%Y%m%d_%H%M%S")
        old_struct_dir = tmp_path / "sync_conflict" / recent_ts / "agent"
        old_struct_dir.mkdir(parents=True)
        old_file = old_struct_dir / "behavior.md"
        old_file.write_text("旧版本地备份内容", encoding="utf-8")

        # 执行清理
        cleanup_expired_conflict_backups(data_path=tmp_path, now=now)

        # 近期旧结构目录应被完整保留
        assert old_struct_dir.exists(), "近期旧结构目录应保留"
        assert old_file.exists(), "旧结构文件应保留"
        assert old_file.read_text(encoding="utf-8") == "旧版本地备份内容"

    def test_cleanup_deletes_old_structure_when_expired(self, tmp_path):
        """清理机制对旧结构同样生效：过期则删除整个时间戳子目录"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        now = datetime.now(timezone.utc)

        # 模拟旧结构的过期备份（50 天前）
        old_ts = (now - timedelta(days=50)).strftime("%Y%m%d_%H%M%S")
        old_struct_dir = tmp_path / "sync_conflict" / old_ts / "agent"
        old_struct_dir.mkdir(parents=True)
        (old_struct_dir / "behavior.md").write_text("旧版备份", encoding="utf-8")

        # 执行清理
        deleted_count = cleanup_expired_conflict_backups(data_path=tmp_path, now=now)

        # 整个时间戳子目录应被删除（含嵌套子目录与文件）
        assert deleted_count == 1
        assert not (tmp_path / "sync_conflict" / old_ts).exists(), (
            "过期的旧结构目录应被删除（含嵌套子目录）"
        )

    def test_old_and_new_structure_coexist(self, tmp_path):
        """旧结构与新结构可共存于同一 sync_conflict/ 目录"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import backup_conflict_versions

        now = datetime.now(timezone.utc)

        # 预置旧结构备份（5 天前，近期）
        old_ts = (now - timedelta(days=5)).strftime("%Y%m%d_%H%M%S")
        old_dir = tmp_path / "sync_conflict" / old_ts / "agent"
        old_dir.mkdir(parents=True)
        (old_dir / "behavior.md").write_text("旧结构备份", encoding="utf-8")

        # 创建新结构备份（当前时间）
        backup_conflict_versions(
            data_path=tmp_path,
            file_path="agent/behavior.md",
            local_content="新结构本地",
            remote_content="新结构云端",
            timestamp_str=now.strftime("%Y%m%d_%H%M%S"),
        )

        # 两种结构共存
        old_backup_file = tmp_path / "sync_conflict" / old_ts / "agent" / "behavior.md"
        new_local_file = (
            tmp_path / "sync_conflict" / now.strftime("%Y%m%d_%H%M%S")
            / "agent__behavior.md.local.md"
        )
        new_remote_file = (
            tmp_path / "sync_conflict" / now.strftime("%Y%m%d_%H%M%S")
            / "agent__behavior.md.remote.md"
        )

        assert old_backup_file.exists(), "旧结构备份应保留"
        assert new_local_file.exists(), "新结构本地备份应存在"
        assert new_remote_file.exists(), "新结构云端备份应存在"

    def test_old_structure_with_nested_path_preserved(self, tmp_path):
        """旧结构中的深层嵌套路径（如 agent/subdir/file.md）也能被正确处理"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        now = datetime.now(timezone.utc)

        # 旧结构的深层嵌套（近期，保留）
        recent_ts = (now - timedelta(days=3)).strftime("%Y%m%d_%H%M%S")
        deep_old_dir = (
            tmp_path / "sync_conflict" / recent_ts / "agent" / "subdir"
        )
        deep_old_dir.mkdir(parents=True)
        (deep_old_dir / "file.md").write_text("深层旧结构", encoding="utf-8")

        # 执行清理
        cleanup_expired_conflict_backups(data_path=tmp_path, now=now)

        # 深层旧结构应被保留
        assert deep_old_dir.exists()
        assert (deep_old_dir / "file.md").exists()

    def test_old_structure_expired_with_nested_path_deleted(self, tmp_path):
        """旧结构中的深层嵌套过期目录被完整删除"""
        from datetime import timedelta

        from lifeprism.sync.conflict_backup import cleanup_expired_conflict_backups

        now = datetime.now(timezone.utc)

        # 旧结构的深层嵌套（过期，60 天前）
        old_ts = (now - timedelta(days=60)).strftime("%Y%m%d_%H%M%S")
        deep_old_dir = (
            tmp_path / "sync_conflict" / old_ts / "agent" / "subdir"
        )
        deep_old_dir.mkdir(parents=True)
        (deep_old_dir / "file.md").write_text("深层旧结构", encoding="utf-8")

        # 执行清理
        deleted_count = cleanup_expired_conflict_backups(data_path=tmp_path, now=now)

        # 整个时间戳目录（含深层嵌套）应被删除
        assert deleted_count == 1
        assert not (tmp_path / "sync_conflict" / old_ts).exists()
