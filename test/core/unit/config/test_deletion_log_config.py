"""DELETION_LOG_CONFIG 表配置单元测试

测试 seam: lifeprism.config.database.DELETION_LOG_CONFIG 字典结构

验证 Issue #05: 墓碑表建表（deletion_log schema）
- 字段名用 target_table 而非 table_name（避免与代码变量名混淆）
- update_at: True（LWW 比较用 updated_at；插入时 updated_at == created_at，墓碑不再修改）
- id 用 dl- 前缀（PRD 3 的 DeletionLogProvider 中通过 _generic_insert(id_prefix='dl-') 实现）

参考:
- Issue: .scratch/deletion-sync-01-schema/issues/05-deletion-log-table-and-adr.md
- PRD: .scratch/deletion-sync-01-schema/prd.md
- ADR: docs/adr/2026-07-22-deletion-log-table.md
"""

import pytest

pytestmark = pytest.mark.core


# ==================== 期望的 schema 真值表（独立于实现） ====================

EXPECTED_TABLE_NAME = "deletion_log"

EXPECTED_COLUMNS = {
    "id": {"type": "TEXT", "constraints": ["PRIMARY KEY"]},
    "target_table": {"type": "TEXT", "constraints": ["NOT NULL"]},
    "record_id": {"type": "TEXT", "constraints": ["NOT NULL"]},
    "source": {"type": "TEXT", "constraints": ["NOT NULL"]},
}


class TestDeletionLogConfigExists:
    """Seam 1: DELETION_LOG_CONFIG 在 lifeprism.config.database 中存在"""

    def test_config_exists_in_database_module(self):
        """lifeprism.config.database 模块导出 DELETION_LOG_CONFIG 属性"""
        from lifeprism.config import database as database_module

        assert hasattr(database_module, "DELETION_LOG_CONFIG"), (
            "database 模块应导出 DELETION_LOG_CONFIG"
        )

    def test_config_is_dict_type(self):
        """DELETION_LOG_CONFIG 应为 dict 类型"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        assert isinstance(DELETION_LOG_CONFIG, dict), (
            "DELETION_LOG_CONFIG 应为 dict，实际为 "
            f"{type(DELETION_LOG_CONFIG).__name__}"
        )

    def test_config_registered_in_table_configs(self):
        """DELETION_LOG_CONFIG 应注册到 TABLE_CONFIGS（key 为 deletion_log）"""
        from lifeprism.config.database import TABLE_CONFIGS

        assert "deletion_log" in TABLE_CONFIGS, (
            "TABLE_CONFIGS 应包含 'deletion_log' 键，当前 keys: "
            f"{sorted(TABLE_CONFIGS.keys())}"
        )

    def test_table_name_field_correct(self):
        """DELETION_LOG_CONFIG['table_name'] 应为 'deletion_log'"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        assert DELETION_LOG_CONFIG["table_name"] == EXPECTED_TABLE_NAME, (
            f"table_name 应为 {EXPECTED_TABLE_NAME!r}, "
            f"实际 {DELETION_LOG_CONFIG['table_name']!r}"
        )


class TestDeletionLogConfigColumns:
    """Seam 2: DELETION_LOG_CONFIG['columns'] 结构

    关键约束：字段名是 target_table 而非 table_name（避免与代码变量名混淆）
    """

    def test_columns_key_exists(self):
        """columns 字段存在"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        assert "columns" in DELETION_LOG_CONFIG, "DELETION_LOG_CONFIG 应有 'columns' 键"

    @pytest.mark.parametrize(
        "column_name,expected_spec",
        list(EXPECTED_COLUMNS.items()),
    )
    def test_each_expected_column_exists(self, column_name, expected_spec):
        """每个期望的列都存在且类型/约束匹配（参数化覆盖 4 个列）"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        columns = DELETION_LOG_CONFIG["columns"]
        assert column_name in columns, (
            f"columns 应包含 {column_name!r}，当前列: {sorted(columns.keys())}"
        )
        actual = columns[column_name]
        assert actual["type"] == expected_spec["type"], (
            f"{column_name} 的 type 应为 {expected_spec['type']!r}, "
            f"实际 {actual['type']!r}"
        )
        for constraint in expected_spec["constraints"]:
            assert constraint in actual["constraints"], (
                f"{column_name} 的 constraints 应包含 {constraint!r}, "
                f"实际 {actual['constraints']!r}"
            )

    def test_target_table_field_present_not_table_name(self):
        """关键字段名是 target_table（非 table_name）

        理由：避免与代码中 table_name 变量名混淆，语义更清晰
        参考 ADR: docs/adr/2026-07-22-deletion-log-table.md
        """
        from lifeprism.config.database import DELETION_LOG_CONFIG

        columns = DELETION_LOG_CONFIG["columns"]
        assert "target_table" in columns, (
            "columns 应包含 'target_table' 字段（被删记录所在表名）"
        )
        # 显式断言 columns 中没有 'table_name' 键（避免与代码变量名混淆）
        assert "table_name" not in columns, (
            "columns 不应有 'table_name' 键（已用 target_table 代替，"
            "避免与代码中 table_name 变量名混淆）"
        )

    def test_columns_only_contains_expected_keys(self):
        """columns 应恰好包含 4 个字段（id/target_table/record_id/source）

        时间戳字段（created_at/updated_at）由 timestamps=True 自动添加，
        不出现在 columns 中
        """
        from lifeprism.config.database import DELETION_LOG_CONFIG

        columns = DELETION_LOG_CONFIG["columns"]
        assert set(columns.keys()) == set(EXPECTED_COLUMNS.keys()), (
            f"columns keys 应为 {sorted(EXPECTED_COLUMNS.keys())}, "
            f"实际 {sorted(columns.keys())}"
        )


class TestDeletionLogConfigTimestamps:
    """Seam 3: DELETION_LOG_CONFIG 的时间戳配置

    - timestamps: True 自动添加 created_at, updated_at
    - update_at: True 使 has_updated_at() 返回 True，LWW 比较使用 updated_at 字段
    - 墓碑不更新，插入时 updated_at == created_at
    """

    def test_timestamps_is_true(self):
        """timestamps 应为 True（自动添加 created_at/updated_at）"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        assert DELETION_LOG_CONFIG.get("timestamps") is True, (
            "timestamps 应为 True，实际 "
            f"{DELETION_LOG_CONFIG.get('timestamps')!r}"
        )

    def test_update_at_is_true(self):
        """update_at 应为 True（LWW 比较使用 updated_at）

        理由：update_at=True 使 has_updated_at() 返回 True，
        LWW 比较使用 updated_at 字段；墓碑插入后不再修改，
        因此 updated_at == created_at，用 updated_at 比较等价于用 created_at 比较
        """
        from lifeprism.config.database import DELETION_LOG_CONFIG

        assert DELETION_LOG_CONFIG.get("update_at") is True, (
            "update_at 应为 True，实际 "
            f"{DELETION_LOG_CONFIG.get('update_at')!r}"
        )


class TestDeletionLogConfigTableConstraints:
    """Seam 4: DELETION_LOG_CONFIG 的 table_constraints（业务 UNIQUE）

    UNIQUE(target_table, record_id) 用于跨端去重：
    两设备删除同一记录时各生成不同 dl-* 主键墓碑，
    LWW 按 (target_table, record_id) 匹配，确保重复墓碑被 LWW 处理
    参考 ADR: docs/adr/2026-07-22-deletion-log-table.md 决策 3
    """

    def test_table_constraints_exists(self):
        """table_constraints 字段存在"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        assert "table_constraints" in DELETION_LOG_CONFIG, (
            "DELETION_LOG_CONFIG 应有 'table_constraints' 键"
        )

    def test_table_constraints_contains_unique_target_table_record_id(self):
        """table_constraints 应包含 UNIQUE(target_table, record_id)"""
        from lifeprism.config.database import DELETION_LOG_CONFIG

        constraints = DELETION_LOG_CONFIG.get("table_constraints", [])
        found = any(
            "UNIQUE" in c.upper()
            and "target_table" in c
            and "record_id" in c
            for c in constraints
        )
        assert found, (
            f"table_constraints 应包含 UNIQUE(target_table, record_id)，"
            f"实际 {constraints!r}"
        )
