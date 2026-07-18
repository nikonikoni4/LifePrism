"""备份常量单元测试

测试 seam: lifeprism.backup.constants 模块导出的常量值

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-7-backup-service-and-scheduler.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 13（备份范围与格式）
- ADR: docs/adr/2026-07-17-backup-sync-decoupled-scope.md（BACKUP_DIRS 独立定义，含 plan 不依赖 SYNC_DIRECTORIES）
"""

import pytest

pytestmark = pytest.mark.core


class TestBackupDirs:
    """BACKUP_DIRS 独立定义备份范围（含 plan，不依赖 SYNC_DIRECTORIES）"""

    def test_backup_dirs_contains_session(self):
        """BACKUP_DIRS 包含 session/（聊天会话 JSONL）"""
        from lifeprism.backup.constants import BACKUP_DIRS

        assert "session/" in BACKUP_DIRS

    def test_backup_dirs_contains_diary(self):
        """BACKUP_DIRS 包含 diary/（日记 MD）"""
        from lifeprism.backup.constants import BACKUP_DIRS

        assert "diary/" in BACKUP_DIRS

    def test_backup_dirs_contains_agent(self):
        """BACKUP_DIRS 包含 agent/（Agent 身份/记忆/配置）"""
        from lifeprism.backup.constants import BACKUP_DIRS

        assert "agent/" in BACKUP_DIRS

    def test_backup_dirs_contains_user(self):
        """BACKUP_DIRS 包含 user/（用户级数据）"""
        from lifeprism.backup.constants import BACKUP_DIRS

        assert "user/" in BACKUP_DIRS

    def test_backup_dirs_contains_plan(self):
        """BACKUP_DIRS 包含 plan/（计划文档，仅备份不加入同步范围）"""
        from lifeprism.backup.constants import BACKUP_DIRS

        assert "plan/" in BACKUP_DIRS

    def test_backup_dirs_has_exactly_five_entries(self):
        """BACKUP_DIRS 恰好 5 个条目（session/diary/agent/user/plan）"""
        from lifeprism.backup.constants import BACKUP_DIRS

        assert len(BACKUP_DIRS) == 5
        assert set(BACKUP_DIRS) == {
            "session/",
            "diary/",
            "agent/",
            "user/",
            "plan/",
        }


class TestBackupExcludedFilenames:
    """BACKUP_EXCLUDED_FILENAMES 排除规则（与同步排除规则一致）"""

    def test_excludes_chat_history_json(self):
        """排除 chat_history.json（由 dreaming task 写入，云端不变更）"""
        from lifeprism.backup.constants import BACKUP_EXCLUDED_FILENAMES

        assert "chat_history.json" in BACKUP_EXCLUDED_FILENAMES

    def test_excludes_bootstrap_md(self):
        """排除 bootstrap.md（Agent 启动引导配置，各端独立维护）"""
        from lifeprism.backup.constants import BACKUP_EXCLUDED_FILENAMES

        assert "bootstrap.md" in BACKUP_EXCLUDED_FILENAMES

    def test_excluded_is_set_type(self):
        """BACKUP_EXCLUDED_FILENAMES 是 set 类型（支持 O(1) 查询）"""
        from lifeprism.backup.constants import BACKUP_EXCLUDED_FILENAMES

        assert isinstance(BACKUP_EXCLUDED_FILENAMES, set)


class TestBackupDbFiles:
    """BACKUP_DB_FILES 数据库全量备份清单（含所有表，非 SYNC_TABLES 子集）"""

    def test_includes_lifewatch_ai_db(self):
        """BACKUP_DB_FILES 包含 dataset/lifewatch_ai.db（主数据库全量备份）"""
        from lifeprism.backup.constants import BACKUP_DB_FILES

        assert "dataset/lifewatch_ai.db" in BACKUP_DB_FILES

    def test_excludes_chat_history_db(self):
        """BACKUP_DB_FILES 不包含 chat_history.db（已弃用）"""
        from lifeprism.backup.constants import BACKUP_DB_FILES

        for db_path in BACKUP_DB_FILES:
            assert "chat_history.db" not in db_path

    def test_is_list_type(self):
        """BACKUP_DB_FILES 是 list 类型（保持顺序，便于扩展）"""
        from lifeprism.backup.constants import BACKUP_DB_FILES

        assert isinstance(BACKUP_DB_FILES, list)
