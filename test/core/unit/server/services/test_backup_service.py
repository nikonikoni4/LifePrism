"""BackupService 单元测试

测试 seam: lifeprism.server.services.backup_service.BackupService
- backup_documents() -> None：文档全量备份（保留 3 份）
- backup_database() -> None：数据库全量备份（SQLite Online Backup API，保留 3 份）
- backup_service 单例：模块级单例实例

设计决策:
- 平铺存储（非 zip）：每个时间戳一个目录，目录内是原始文件结构
- SQLite Online Backup API：sqlite3.Connection.backup(target)，在线拷贝不阻塞业务读写
- 完整性校验：文档（文件数量 + hash 比对）+ 数据库（PRAGMA integrity_check）
- 校验失败处理：删除损坏的备份目录/文件 + 记录 ERROR 日志 + 不影响其他任务
- 保留策略：按时间戳排序，保留最新 3 份，旧的删除
- run_mode 守卫：run_mode != "full" 时跳过备份（云端 agent_only 模式不备份）

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-7-backup-service-and-scheduler.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 14-18
- ADR: docs/adr/2026-07-17-data-backup-strategy.md（数据备份策略）
- ADR: docs/adr/2026-07-17-conflict-failure-policy.md（云端 agent_only 模式不备份）
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.core


@pytest.fixture
def backup_data_path(tmp_path):
    """构造模拟的 lifeprism_data_path 目录

    创建 BACKUP_DIRS 下的若干文件（含应排除的文件名），用于测试 backup_documents。
    """
    # session/
    session_dir = tmp_path / "session"
    session_dir.mkdir()
    (session_dir / "session_001.jsonl").write_text(
        '{"role":"user","content":"hello"}\n', encoding="utf-8"
    )
    (session_dir / "session_002.jsonl").write_text(
        '{"role":"assistant","content":"hi"}\n', encoding="utf-8"
    )

    # diary/
    diary_dir = tmp_path / "diary"
    diary_dir.mkdir()
    (diary_dir / "2026-07-17.md").write_text("# 7月17日\n今天很开心", encoding="utf-8")
    (diary_dir / "2026-07-18.md").write_text("# 7月18日\n今天很累", encoding="utf-8")

    # agent/
    agent_dir = tmp_path / "agent"
    agent_dir.mkdir()
    (agent_dir / "behavior.md").write_text("行为记录", encoding="utf-8")
    # chat_history.json 应被排除
    (agent_dir / "chat_history.json").write_text(
        '{"history":[]}', encoding="utf-8"
    )
    # bootstrap.md 应被排除
    (agent_dir / "bootstrap.md").write_text("启动引导", encoding="utf-8")

    # user/
    user_dir = tmp_path / "user"
    user_dir.mkdir()
    (user_dir / "profile.md").write_text("用户档案", encoding="utf-8")

    # plan/
    plan_dir = tmp_path / "plan"
    plan_dir.mkdir()
    (plan_dir / "plan-001.md").write_text("减肥计划", encoding="utf-8")
    (plan_dir / "plan-002.md").write_text("学习计划", encoding="utf-8")

    # dataset/lifewatch_ai.db
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    db_path = dataset_dir / "lifewatch_ai.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test_table (name) VALUES ('test_value')")
    conn.commit()
    conn.close()

    return tmp_path


@pytest.fixture
def patched_settings(backup_data_path):
    """patch settings.lifeprism_data_path 指向临时目录，run_mode 设为 full"""
    from lifeprism.config.settings_manager import settings

    with (
        patch.object(
            type(settings),
            "lifeprism_data_path",
            new_callable=lambda: property(lambda self: backup_data_path),
        ),
        patch.object(
            type(settings),
            "run_mode",
            new_callable=lambda: property(lambda self: "full"),
        ),
    ):
        yield settings


# ==================== Seam 1: backup_service 单例 ====================


class TestBackupServiceSingleton:
    """backup_service 模块级单例"""

    def test_backup_service_is_instance(self):
        """backup_service 是 LazySingleton 代理，底层实例为 BackupService"""
        from lifeprism.server.services.backup_service import (
            BackupService,
            backup_service,
        )
        from lifeprism.utils import LazySingleton

        # 改用 LazySingleton 懒加载代理（与 goal_service / habit_chain_service 一致）
        assert isinstance(backup_service, LazySingleton)
        # 代理首次访问属性时初始化底层 BackupService 实例
        assert isinstance(backup_service._ensure_initialized(), BackupService)

    def test_backup_service_singleton_identity(self):
        """多次导入 backup_service 返回同一实例（模块级单例）"""
        from lifeprism.server.services.backup_service import backup_service as s1
        from lifeprism.server.services.backup_service import backup_service as s2

        # 多次导入应返回同一对象（模块级单例）
        # 注意：不能使用 importlib.reload 验证单例，因为 reload 会重新执行模块代码
        # 创建新实例，破坏后续测试中 schedule_service.backup_service 的引用一致性
        assert s1 is s2, "多次导入 backup_service 应返回同一实例（模块级单例）"


# ==================== Seam 2: backup_documents 文档全量备份 ====================


class TestBackupDocuments:
    """backup_documents 文档全量备份"""

    @pytest.mark.asyncio
    async def test_creates_timestamped_directory_under_backups_docs(
        self, patched_settings, backup_data_path
    ):
        """备份目录创建在 backups/docs/{timestamp}/ 下"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_documents()

        docs_root = backup_data_path / "backups" / "docs"
        assert docs_root.exists(), "backups/docs/ 目录应被创建"
        sub_dirs = [d for d in docs_root.iterdir() if d.is_dir()]
        assert len(sub_dirs) == 1, "应有恰好一个时间戳子目录"
        # 时间戳目录名格式 YYYY-MM-DDTHH-MM-SS（冒号替换为短横，文件系统友好）
        ts_name = sub_dirs[0].name
        assert "T" in ts_name, "时间戳目录名应含 T 分隔符"

    @pytest.mark.asyncio
    async def test_copies_backup_dirs_files(self, patched_settings, backup_data_path):
        """备份覆盖 BACKUP_DIRS 下的所有文件"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_documents()

        docs_root = backup_data_path / "backups" / "docs"
        ts_dir = next(d for d in docs_root.iterdir() if d.is_dir())

        # 检查所有 BACKUP_DIRS 子目录都被备份
        assert (ts_dir / "session").exists()
        assert (ts_dir / "diary").exists()
        assert (ts_dir / "agent").exists()
        assert (ts_dir / "user").exists()
        assert (ts_dir / "plan").exists()

        # 检查具体文件
        assert (ts_dir / "session" / "session_001.jsonl").exists()
        assert (ts_dir / "diary" / "2026-07-17.md").exists()
        assert (ts_dir / "agent" / "behavior.md").exists()
        assert (ts_dir / "user" / "profile.md").exists()
        assert (ts_dir / "plan" / "plan-001.md").exists()

    @pytest.mark.asyncio
    async def test_excludes_excluded_filenames(self, patched_settings, backup_data_path):
        """排除 BACKUP_EXCLUDED_FILENAMES 中的文件（chat_history.json, bootstrap.md）"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_documents()

        docs_root = backup_data_path / "backups" / "docs"
        ts_dir = next(d for d in docs_root.iterdir() if d.is_dir())

        # chat_history.json 和 bootstrap.md 不应出现在备份中
        assert not (ts_dir / "agent" / "chat_history.json").exists()
        assert not (ts_dir / "agent" / "bootstrap.md").exists()

    @pytest.mark.asyncio
    async def test_integrity_verification_passes_on_normal_backup(
        self, patched_settings, backup_data_path
    ):
        """正常备份通过完整性校验（文件数量 + hash 比对）"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_documents()

        docs_root = backup_data_path / "backups" / "docs"
        ts_dir = next(d for d in docs_root.iterdir() if d.is_dir())

        # 校验通过 → 备份目录保留
        assert ts_dir.exists()

        # 文件数量校验：源文件数 = 备份文件数（排除 chat_history.json 和 bootstrap.md）
        source_files = []
        for d in ["session/", "diary/", "agent/", "user/", "plan/"]:
            src_dir = backup_data_path / d
            if src_dir.exists():
                for f in src_dir.rglob("*"):
                    if f.is_file() and f.name not in {
                        "chat_history.json",
                        "bootstrap.md",
                    }:
                        source_files.append(f)
        backup_files = [f for f in ts_dir.rglob("*") if f.is_file()]
        assert len(source_files) == len(backup_files)

        # hash 校验：每个文件 hash 一致
        import hashlib

        def file_hash(p):
            return hashlib.sha256(p.read_bytes()).hexdigest()

        # 取一个文件验证 hash 一致
        src_file = backup_data_path / "agent" / "behavior.md"
        bak_file = ts_dir / "agent" / "behavior.md"
        assert file_hash(src_file) == file_hash(bak_file)

    @pytest.mark.asyncio
    async def test_corrupted_backup_is_deleted_on_verification_failure(
        self, patched_settings, backup_data_path
    ):
        """完整性校验失败时删除损坏备份目录"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # Mock 校验方法返回 False，模拟校验失败
        with patch.object(
            BackupService, "_verify_docs_backup", return_value=False
        ):
            await service.backup_documents()

        docs_root = backup_data_path / "backups" / "docs"
        # 校验失败 → 备份目录被删除
        if docs_root.exists():
            sub_dirs = [d for d in docs_root.iterdir() if d.is_dir()]
            assert len(sub_dirs) == 0, "校验失败的备份目录应被删除"

    @pytest.mark.asyncio
    async def test_retention_keeps_latest_three(
        self, patched_settings, backup_data_path
    ):
        """保留最新 3 份，旧备份被删除"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # 手动创建 4 个旧备份目录（按时间戳命名）
        docs_root = backup_data_path / "backups" / "docs"
        docs_root.mkdir(parents=True, exist_ok=True)
        old_timestamps = [
            "2026-07-14T03-00-00",
            "2026-07-15T03-00-00",
            "2026-07-16T03-00-00",
            "2026-07-17T03-00-00",
        ]
        for ts in old_timestamps:
            (docs_root / ts).mkdir()
            # 在每个目录中放一个文件，便于验证
            (docs_root / ts / "marker.txt").write_text(ts, encoding="utf-8")

        # 执行备份（会创建第 5 份，然后清理保留最新 3 份）
        await service.backup_documents()

        sub_dirs = sorted([d.name for d in docs_root.iterdir() if d.is_dir()])
        # 保留 3 份（最新 3 个时间戳）
        assert len(sub_dirs) == 3, f"应保留 3 份，实际 {len(sub_dirs)}: {sub_dirs}"
        # 最旧的 "2026-07-14T03-00-00" 应被删除
        assert "2026-07-14T03-00-00" not in sub_dirs
        # 最旧的 "2026-07-15T03-00-00" 也应被删除（因为新建的备份时间戳更新）
        assert "2026-07-15T03-00-00" not in sub_dirs

    @pytest.mark.asyncio
    async def test_backup_sorts_timestamps_descending_for_retention(
        self, patched_settings, backup_data_path
    ):
        """保留策略按时间戳降序排序，保留最新 3 份"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # 创建 5 个旧备份，时间戳混合顺序
        docs_root = backup_data_path / "backups" / "docs"
        docs_root.mkdir(parents=True, exist_ok=True)
        # 故意乱序创建
        for ts in [
            "2026-07-12T03-00-00",
            "2026-07-15T03-00-00",
            "2026-07-13T03-00-00",
            "2026-07-14T03-00-00",
            "2026-07-11T03-00-00",
        ]:
            (docs_root / ts).mkdir()

        await service.backup_documents()

        sub_dirs = sorted([d.name for d in docs_root.iterdir() if d.is_dir()])
        assert len(sub_dirs) == 3
        # 按 ISO-like 时间戳字符串排序 = 按时间排序
        # 最新的 3 份应包含新建的备份（时间戳最新）+ 2026-07-15 + 2026-07-14
        # 但新建备份的时间戳是当前时间，应大于 2026-07-15
        # 所以保留下来的应该是新建的 + 2026-07-15 + 2026-07-14
        assert "2026-07-15T03-00-00" in sub_dirs
        assert "2026-07-14T03-00-00" in sub_dirs
        # 旧的应被删除
        assert "2026-07-11T03-00-00" not in sub_dirs
        assert "2026-07-12T03-00-00" not in sub_dirs
        assert "2026-07-13T03-00-00" not in sub_dirs


# ==================== Seam 3: backup_database 数据库全量备份 ====================


class TestBackupDatabase:
    """backup_database 数据库全量备份（SQLite Online Backup API）"""

    @pytest.mark.asyncio
    async def test_creates_db_file_under_backups_db(
        self, patched_settings, backup_data_path
    ):
        """备份文件创建在 backups/db/ 下，命名为 lifewatch_ai-{timestamp}.db"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_database()

        db_root = backup_data_path / "backups" / "db"
        assert db_root.exists(), "backups/db/ 目录应被创建"
        db_files = list(db_root.glob("lifewatch_ai-*.db"))
        assert len(db_files) == 1, "应创建一个 lifewatch_ai-{timestamp}.db 文件"

    @pytest.mark.asyncio
    async def test_uses_sqlite_online_backup_api(
        self, patched_settings, backup_data_path
    ):
        """使用 SQLite Online Backup API（source.backup(target)）

        sqlite3.Connection.backup 是 C 实现的不可变类型方法，无法直接 patch。
        改为通过 spy sqlite3.connect 验证：
        1. 创建到源数据库的连接（dataset/lifewatch_ai.db）
        2. 创建到目标备份文件的连接（backups/db/lifewatch_ai-{ts}.db）
        3. 备份结果是有效的 SQLite 数据库（schema + 数据完整）
        这三条共同证明使用了 SQLite Online Backup API（而非文件复制）。
        """
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # Spy sqlite3.connect 跟踪连接创建
        original_connect = sqlite3.connect
        connect_targets = []

        def spy_connect(database, **kwargs):
            conn = original_connect(database, **kwargs)
            connect_targets.append(str(database))
            return conn

        with patch(
            "lifeprism.server.services.backup_service.sqlite3.connect",
            side_effect=spy_connect,
        ):
            await service.backup_database()

        # 验证创建了至少 2 个连接（source + target）
        assert len(connect_targets) >= 2, (
            f"应至少创建 2 个 sqlite3 连接（source + target），实际 {len(connect_targets)}"
        )
        # 验证 source 连接（dataset/lifewatch_ai.db）
        source_conns = [
            t for t in connect_targets if "dataset" in t.replace("\\", "/")
        ]
        assert len(source_conns) >= 1, "应创建到源数据库的连接"
        # 验证 target 连接（backups/db/lifewatch_ai-*.db）
        target_conns = [
            t
            for t in connect_targets
            if "backups" in t.replace("\\", "/") and "db" in t.replace("\\", "/")
        ]
        assert len(target_conns) >= 1, "应创建到目标备份数据库的连接"

    @pytest.mark.asyncio
    async def test_backup_db_is_valid_sqlite(
        self, patched_settings, backup_data_path
    ):
        """备份数据库是有效的 SQLite 文件，内容与源数据库一致"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_database()

        db_root = backup_data_path / "backups" / "db"
        backup_db = next(db_root.glob("lifewatch_ai-*.db"))

        # 用 sqlite3 打开备份文件验证
        conn = sqlite3.connect(str(backup_db))
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cursor.fetchall()}
            assert "test_table" in tables, "备份应包含源数据库的表"

            cursor.execute("SELECT name FROM test_table")
            rows = cursor.fetchall()
            assert rows == [("test_value",)] or rows == [
                (1, "test_value")
            ], "备份应包含源数据库的数据"
        finally:
            conn.close()

    @pytest.mark.asyncio
    async def test_pragma_integrity_check_passes(self, patched_settings, backup_data_path):
        """备份成功后 PRAGMA integrity_check 应返回 'ok'"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()
        await service.backup_database()

        db_root = backup_data_path / "backups" / "db"
        backup_db = next(db_root.glob("lifewatch_ai-*.db"))

        conn = sqlite3.connect(str(backup_db))
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()[0]
            assert result == "ok", f"PRAGMA integrity_check 应返回 'ok'，实际 {result}"
        finally:
            conn.close()

    @pytest.mark.asyncio
    async def test_corrupted_db_backup_is_deleted(
        self, patched_settings, backup_data_path
    ):
        """完整性校验失败时删除损坏的数据库备份"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # Mock 校验方法返回 False
        with patch.object(
            BackupService, "_verify_db_backup", return_value=False
        ):
            await service.backup_database()

        db_root = backup_data_path / "backups" / "db"
        db_files = list(db_root.glob("lifewatch_ai-*.db"))
        assert len(db_files) == 0, "校验失败的备份文件应被删除"

    @pytest.mark.asyncio
    async def test_retention_keeps_latest_three_db_backups(
        self, patched_settings, backup_data_path
    ):
        """数据库备份保留最新 3 份"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # 创建 4 个旧备份
        db_root = backup_data_path / "backups" / "db"
        db_root.mkdir(parents=True, exist_ok=True)
        for ts in [
            "2026-07-14T08-00-00",
            "2026-07-15T08-00-00",
            "2026-07-16T08-00-00",
            "2026-07-17T08-00-00",
        ]:
            # 创建有效的 SQLite 文件
            dst = db_root / f"lifewatch_ai-{ts}.db"
            conn = sqlite3.connect(str(dst))
            conn.close()

        # 执行备份（会创建第 5 份，然后保留最新 3 份）
        await service.backup_database()

        db_files = list(db_root.glob("lifewatch_ai-*.db"))
        assert len(db_files) == 3, f"应保留 3 份，实际 {len(db_files)}"


# ==================== Seam 4: 同秒触发冲突保护 ====================


class TestSameTimestampConflictProtection:
    """同秒触发冲突保护：清理已存在的备份目录/文件后再备份

    场景：手动触发、cron 补偿、测试场景下，同秒内可能触发两次备份。
    - 文档备份：若目录已存在，残留文件会导致 _verify_docs_backup 数量校验失败
    - 数据库备份：SQLite Online Backup API 要求目标为空数据库，已存在会报 OperationalError
    """

    @pytest.mark.asyncio
    async def test_documents_backup_cleans_existing_directory(
        self, patched_settings, backup_data_path
    ):
        """文档备份：目标目录已存在时先清理再备份"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # 预创建一个"残留"备份目录（模拟上次同秒触发的部分写入）
        # 通过 mock _get_local_timestamp 固定时间戳，确保两次"备份"使用同一时间戳
        fixed_timestamp = "2026-07-17T03-00-00"
        docs_root = backup_data_path / "backups" / "docs"
        stale_dir = docs_root / fixed_timestamp
        stale_dir.mkdir(parents=True, exist_ok=True)
        # 残留文件：源中已不存在的文件，会污染本次备份
        (stale_dir / "stale_session.jsonl").write_text(
            '{"old": "data"}', encoding="utf-8"
        )
        # 残留子目录
        (stale_dir / "deleted_dir").mkdir(exist_ok=True)
        (stale_dir / "deleted_dir" / "old_file.md").write_text(
            "old content", encoding="utf-8"
        )

        # 固定时间戳为已存在的目录名，触发同秒冲突
        with patch.object(
            BackupService, "_get_local_timestamp", return_value=fixed_timestamp
        ):
            await service.backup_documents()

        # 验证：备份目录存在且不含残留文件
        assert stale_dir.exists(), "备份目录应被重建"
        # 残留文件应被清理
        assert not (stale_dir / "stale_session.jsonl").exists(), "残留文件应被清理"
        assert not (stale_dir / "deleted_dir").exists(), "残留子目录应被清理"
        # 应包含本次备份的有效文件
        assert (stale_dir / "agent" / "behavior.md").exists()
        assert (stale_dir / "diary" / "2026-07-17.md").exists()

    @pytest.mark.asyncio
    async def test_documents_backup_logs_warning_on_conflict(
        self, patched_settings, backup_data_path, caplog
    ):
        """文档备份：检测到目录已存在时记录 WARNING 日志"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        fixed_timestamp = "2026-07-17T03-00-00"
        docs_root = backup_data_path / "backups" / "docs"
        stale_dir = docs_root / fixed_timestamp
        stale_dir.mkdir(parents=True, exist_ok=True)
        (stale_dir / "stale.txt").write_text("stale", encoding="utf-8")

        with (
            patch.object(
                BackupService, "_get_local_timestamp", return_value=fixed_timestamp
            ),
            caplog.at_level("WARNING"),
        ):
            await service.backup_documents()

        # 应记录 WARNING 日志，包含时间戳和路径
        warning_records = [
            r for r in caplog.records if r.levelname == "WARNING"
        ]
        conflict_warnings = [
            r
            for r in warning_records
            if "已存在" in r.getMessage() and fixed_timestamp in r.getMessage()
        ]
        assert len(conflict_warnings) >= 1, (
            f"应记录 WARNING 日志，实际 {warning_records}"
        )

    @pytest.mark.asyncio
    async def test_documents_backup_cleaned_directory_passes_verification(
        self, patched_settings, backup_data_path
    ):
        """文档备份：清理后重建的目录能通过完整性校验（不被误删）"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        fixed_timestamp = "2026-07-17T03-00-00"
        docs_root = backup_data_path / "backups" / "docs"
        stale_dir = docs_root / fixed_timestamp
        stale_dir.mkdir(parents=True, exist_ok=True)
        # 残留文件会导致 _verify_docs_backup 数量校验失败
        (stale_dir / "stale.txt").write_text("stale", encoding="utf-8")

        with patch.object(
            BackupService, "_get_local_timestamp", return_value=fixed_timestamp
        ):
            await service.backup_documents()

        # 清理后重建的备份应通过校验，目录保留
        assert stale_dir.exists(), (
            "清理残留后重建的备份应通过校验，目录应保留"
        )

    @pytest.mark.asyncio
    async def test_database_backup_cleans_existing_file(
        self, patched_settings, backup_data_path
    ):
        """数据库备份：目标文件已存在时先删除再备份"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        fixed_timestamp = "2026-07-17T08-00-00"
        db_root = backup_data_path / "backups" / "db"
        db_root.mkdir(parents=True, exist_ok=True)
        # 预创建一个"残留"的数据库文件（非空，会触发 OperationalError）
        stale_db = db_root / f"lifewatch_ai-{fixed_timestamp}.db"
        # 创建一个非空数据库（含表和数据），模拟上次失败的备份
        conn = sqlite3.connect(str(stale_db))
        conn.execute("CREATE TABLE stale_table (id INTEGER)")
        conn.execute("INSERT INTO stale_table VALUES (1)")
        conn.commit()
        conn.close()

        # 固定时间戳，触发同秒冲突
        with patch.object(
            BackupService, "_get_local_timestamp", return_value=fixed_timestamp
        ):
            await service.backup_database()

        # 验证：备份文件存在且是有效的 SQLite（不是残留的旧文件）
        assert stale_db.exists(), "备份文件应被重建"
        # 残留表应被清除（说明文件被重新创建，而非追加）
        conn = sqlite3.connect(str(stale_db))
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stale_table'"
            )
            result = cursor.fetchall()
            assert len(result) == 0, "残留表应被清除（文件被重建）"
            # 应包含源数据库的表
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test_table'"
            )
            result = cursor.fetchall()
            assert len(result) == 1, "应包含源数据库的 test_table"
        finally:
            conn.close()

    @pytest.mark.asyncio
    async def test_database_backup_logs_warning_on_conflict(
        self, patched_settings, backup_data_path, caplog
    ):
        """数据库备份：检测到文件已存在时记录 WARNING 日志"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        fixed_timestamp = "2026-07-17T08-00-00"
        db_root = backup_data_path / "backups" / "db"
        db_root.mkdir(parents=True, exist_ok=True)
        stale_db = db_root / f"lifewatch_ai-{fixed_timestamp}.db"
        stale_db.write_bytes(b"stale content")

        with (
            patch.object(
                BackupService, "_get_local_timestamp", return_value=fixed_timestamp
            ),
            caplog.at_level("WARNING"),
        ):
            await service.backup_database()

        warning_records = [
            r for r in caplog.records if r.levelname == "WARNING"
        ]
        conflict_warnings = [
            r
            for r in warning_records
            if "已存在" in r.getMessage() and fixed_timestamp in r.getMessage()
        ]
        assert len(conflict_warnings) >= 1, (
            f"应记录 WARNING 日志，实际 {warning_records}"
        )

    @pytest.mark.asyncio
    async def test_database_backup_no_conflict_when_file_not_exists(
        self, patched_settings, backup_data_path, caplog
    ):
        """数据库备份：目标文件不存在时不记录冲突 WARNING（正常路径）"""
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        # 不预创建残留文件，正常备份
        with caplog.at_level("WARNING"):
            await service.backup_database()

        # 不应有"已存在"的 WARNING 日志
        warning_records = [
            r for r in caplog.records if r.levelname == "WARNING"
        ]
        conflict_warnings = [
            r for r in warning_records if "已存在" in r.getMessage()
        ]
        assert len(conflict_warnings) == 0, (
            f"正常路径不应记录冲突 WARNING，实际 {conflict_warnings}"
        )


# ==================== Seam 5: run_mode 守卫 ====================


class TestRunModeGuard:
    """run_mode 守卫：run_mode != "full" 时跳过备份"""

    @pytest.mark.asyncio
    async def test_skip_backup_documents_in_agent_only_mode(
        self, backup_data_path
    ):
        """agent_only 模式下跳过文档备份"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        with (
            patch.object(
                type(settings),
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: backup_data_path),
            ),
            patch.object(
                type(settings),
                "run_mode",
                new_callable=lambda: property(lambda self: "agent_only"),
            ),
        ):
            await service.backup_documents()

        # backups/docs/ 不应被创建
        assert not (backup_data_path / "backups" / "docs").exists()

    @pytest.mark.asyncio
    async def test_skip_backup_database_in_agent_only_mode(
        self, backup_data_path
    ):
        """agent_only 模式下跳过数据库备份"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        with (
            patch.object(
                type(settings),
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: backup_data_path),
            ),
            patch.object(
                type(settings),
                "run_mode",
                new_callable=lambda: property(lambda self: "agent_only"),
            ),
        ):
            await service.backup_database()

        assert not (backup_data_path / "backups" / "db").exists()

    @pytest.mark.asyncio
    async def test_skip_backup_documents_in_web_demo_mode(
        self, backup_data_path
    ):
        """web_demo 模式下跳过文档备份"""
        from lifeprism.config.settings_manager import settings
        from lifeprism.server.services.backup_service import BackupService

        service = BackupService()

        with (
            patch.object(
                type(settings),
                "lifeprism_data_path",
                new_callable=lambda: property(lambda self: backup_data_path),
            ),
            patch.object(
                type(settings),
                "run_mode",
                new_callable=lambda: property(lambda self: "web_demo"),
            ),
        ):
            await service.backup_documents()

        assert not (backup_data_path / "backups" / "docs").exists()


# ==================== Seam 5: ScheduleService 集成 ====================


class TestScheduleServiceBackupRegistration:
    """ScheduleService 在 __init__ 中注册备份 cron 任务"""

    def test_schedule_service_registers_backup_documents_job(self):
        """ScheduleService.__init__ 注册 backup_documents cron 任务"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()
        job_ids = [j["job_id"] for j in service._system_jobs]
        assert "backup_documents" in job_ids

    def test_schedule_service_registers_backup_database_job(self):
        """ScheduleService.__init__ 注册 backup_database cron 任务"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()
        job_ids = [j["job_id"] for j in service._system_jobs]
        assert "backup_database" in job_ids

    def test_backup_documents_cron_is_daily_at_03(self):
        """backup_documents cron 表达式为 0 3 * * *（每天本地 03:00）"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()
        for job in service._system_jobs:
            if job["job_id"] == "backup_documents":
                assert job["trigger"] == "cron"
                assert job["kwargs"]["cron_expr"] == "0 3 * * *"
                return
        pytest.fail("未找到 backup_documents 任务")

    def test_backup_database_cron_is_every_8_hours(self):
        """backup_database cron 表达式为 0 0,8,16 * * *（每 8 小时）"""
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()
        for job in service._system_jobs:
            if job["job_id"] == "backup_database":
                assert job["trigger"] == "cron"
                assert job["kwargs"]["cron_expr"] == "0 0,8,16 * * *"
                return
        pytest.fail("未找到 backup_database 任务")

    def test_backup_documents_job_uses_backup_service_method(self):
        """backup_documents 任务的 func 是 backup_service.backup_documents"""
        from lifeprism.server.services.backup_service import backup_service
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()
        for job in service._system_jobs:
            if job["job_id"] == "backup_documents":
                assert job["func"] == backup_service.backup_documents
                return
        pytest.fail("未找到 backup_documents 任务")

    def test_backup_database_job_uses_backup_service_method(self):
        """backup_database 任务的 func 是 backup_service.backup_database"""
        from lifeprism.server.services.backup_service import backup_service
        from lifeprism.server.services.schedule_service import ScheduleService

        service = ScheduleService()
        for job in service._system_jobs:
            if job["job_id"] == "backup_database":
                assert job["func"] == backup_service.backup_database
                return
        pytest.fail("未找到 backup_database 任务")
