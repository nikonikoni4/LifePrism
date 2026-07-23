"""time_paradoxes 表 id 字段约束测试

测试 seam: lifeprism.config.database.TABLE_CONFIGS["time_paradoxes"]["columns"]["id"]

Issue 01 要求:
- time_paradoxes 的 id 字段从 ["PRIMARY KEY", "NOT NULL"] 改为
  ["PRIMARY KEY", "AUTOINCREMENT"]
- 该表未投入使用，无需向后兼容

参考:
- Issue: .scratch/deletion-sync-01-schema/issues/01-hash-id-schema-foundation.md
- PRD: .scratch/deletion-sync-01-schema/prd.md
"""

import pytest

pytestmark = pytest.mark.core


class TestTimeParadoxesIdAutoincrement:
    """time_paradoxes 表的 id 字段约束包含 AUTOINCREMENT"""

    def test_id_constraints_contains_autoincrement(self):
        """time_paradoxes.id 的 constraints 列表中包含 'AUTOINCREMENT'"""
        from lifeprism.config.database import TABLE_CONFIGS

        id_constraints = TABLE_CONFIGS["time_paradoxes"]["columns"]["id"]["constraints"]
        assert "AUTOINCREMENT" in id_constraints, (
            f"time_paradoxes.id 约束应包含 AUTOINCREMENT，实际: {id_constraints!r}"
        )

    def test_id_constraints_contains_primary_key(self):
        """time_paradoxes.id 仍保留 PRIMARY KEY 约束（保持主键身份）"""
        from lifeprism.config.database import TABLE_CONFIGS

        id_constraints = TABLE_CONFIGS["time_paradoxes"]["columns"]["id"]["constraints"]
        assert "PRIMARY KEY" in id_constraints, (
            f"time_paradoxes.id 应保留 PRIMARY KEY，实际: {id_constraints!r}"
        )

    def test_id_constraints_exact_value(self):
        """time_paradoxes.id 约束恰好为 ["PRIMARY KEY", "AUTOINCREMENT"]"""
        from lifeprism.config.database import TABLE_CONFIGS

        id_constraints = TABLE_CONFIGS["time_paradoxes"]["columns"]["id"]["constraints"]
        assert id_constraints == ["PRIMARY KEY", "AUTOINCREMENT"], (
            f"time_paradoxes.id 约束应为 ['PRIMARY KEY', 'AUTOINCREMENT']，"
            f"实际: {id_constraints!r}"
        )

    def test_id_constraints_not_contains_not_null(self):
        """time_paradoxes.id 不应再单独包含 NOT NULL（AUTOINCREMENT 已隐含 NOT NULL）"""
        from lifeprism.config.database import TABLE_CONFIGS

        id_constraints = TABLE_CONFIGS["time_paradoxes"]["columns"]["id"]["constraints"]
        assert "NOT NULL" not in id_constraints, (
            f"time_paradoxes.id 不应再包含 NOT NULL（AUTOINCREMENT 已隐含），"
            f"实际: {id_constraints!r}"
        )

    def test_id_type_is_integer(self):
        """time_paradoxes.id 类型保持 INTEGER（AUTOINCREMENT 仅支持 INTEGER 主键）"""
        from lifeprism.config.database import TABLE_CONFIGS

        id_type = TABLE_CONFIGS["time_paradoxes"]["columns"]["id"]["type"]
        assert id_type == "INTEGER", (
            f"time_paradoxes.id 类型应为 INTEGER，实际: {id_type!r}"
        )
