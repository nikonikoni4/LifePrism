"""hash_id schema 字段单元测试

测试 seam: lifeprism.config.database.TABLE_CONFIGS 中 6 张目标表的 hash_id 字段配置

约束:
- hash_id 定位为同步专用标识，不作为主键
- 类型 TEXT，约束 ["NOT NULL", "UNIQUE"]
- _PRIMARY_KEY 保持为 id（自增）不变

参考:
- Issue: .scratch/deletion-sync-01-schema/issues/01-hash-id-schema-foundation.md
- PRD: .scratch/deletion-sync-01-schema/prd.md
- ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md
- ADR: docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md
"""

import pytest

pytestmark = pytest.mark.core


# Issue 验收标准中明文规定的 6 张目标表
TARGET_TABLES = [
    "timeline_custom_block",
    "time_paradoxes",
    "mood_impacts",
    "habit_chains",
    "habit_chain_nodes",
    "user_app_behavior_log",
]


class TestHashIdFieldExists:
    """6 张目标 AUTOINCREMENT 表的 TABLE_CONFIGS 配置中存在 hash_id 字段"""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_field_exists_in_each_table(self, table_name):
        """6 张目标表都应在 columns 中定义 hash_id 字段"""
        from lifeprism.config.database import TABLE_CONFIGS

        config = TABLE_CONFIGS[table_name]
        assert "hash_id" in config["columns"], (
            f"{table_name} 缺少 hash_id 字段，当前列: "
            f"{sorted(config['columns'].keys())}"
        )

    def test_all_six_target_tables_have_hash_id(self):
        """一次性验证 6 张表全部都有 hash_id（聚合视图，便于回归排查）"""
        from lifeprism.config.database import TABLE_CONFIGS

        missing = [
            t for t in TARGET_TABLES if "hash_id" not in TABLE_CONFIGS[t]["columns"]
        ]
        assert missing == [], f"以下表缺少 hash_id 字段: {missing}"


class TestHashIdFieldType:
    """hash_id 字段的类型必须为 TEXT"""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_type_is_text(self, table_name):
        """hash_id 类型为 TEXT（兼容跨端字符串传输）"""
        from lifeprism.config.database import TABLE_CONFIGS

        column = TABLE_CONFIGS[table_name]["columns"]["hash_id"]
        assert column["type"] == "TEXT", (
            f"{table_name}.hash_id 类型应为 TEXT，实际 {column['type']!r}"
        )


class TestHashIdFieldConstraints:
    """hash_id 字段的约束必须为 ["NOT NULL", "UNIQUE"]"""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_constraints_correct(self, table_name):
        """hash_id 约束为 ["NOT NULL", "UNIQUE"]，新库建表时即生效"""
        from lifeprism.config.database import TABLE_CONFIGS

        column = TABLE_CONFIGS[table_name]["columns"]["hash_id"]
        assert column["constraints"] == ["NOT NULL", "UNIQUE"], (
            f"{table_name}.hash_id 约束应为 ['NOT NULL', 'UNIQUE']，"
            f"实际 {column['constraints']!r}"
        )

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_has_not_null(self, table_name):
        """hash_id 包含 NOT NULL 约束"""
        from lifeprism.config.database import TABLE_CONFIGS

        constraints = TABLE_CONFIGS[table_name]["columns"]["hash_id"]["constraints"]
        assert "NOT NULL" in constraints, (
            f"{table_name}.hash_id 缺少 NOT NULL 约束: {constraints!r}"
        )

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_has_unique(self, table_name):
        """hash_id 包含 UNIQUE 约束（跨端去重关键）"""
        from lifeprism.config.database import TABLE_CONFIGS

        constraints = TABLE_CONFIGS[table_name]["columns"]["hash_id"]["constraints"]
        assert "UNIQUE" in constraints, (
            f"{table_name}.hash_id 缺少 UNIQUE 约束: {constraints!r}"
        )


class TestHashIdFieldComment:
    """hash_id 字段应包含说明性 comment（便于 DBA 识别同步专用语义）"""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_has_comment(self, table_name):
        """hash_id 字段定义了非空 comment"""
        from lifeprism.config.database import TABLE_CONFIGS

        column = TABLE_CONFIGS[table_name]["columns"]["hash_id"]
        assert "comment" in column, f"{table_name}.hash_id 缺少 comment"
        assert isinstance(column["comment"], str) and column["comment"], (
            f"{table_name}.hash_id comment 应为非空字符串"
        )


class TestHashIdFieldIsNotPrimaryKey:
    """hash_id 不应作为主键（PRIMARY KEY 必须仍为 id 字段）"""

    @pytest.mark.parametrize("table_name", TARGET_TABLES)
    def test_hash_id_is_not_primary_key(self, table_name):
        """hash_id 字段的 constraints 不应包含 PRIMARY KEY"""
        from lifeprism.config.database import TABLE_CONFIGS

        constraints = TABLE_CONFIGS[table_name]["columns"]["hash_id"]["constraints"]
        assert "PRIMARY KEY" not in constraints, (
            f"{table_name}.hash_id 不应作为主键，约束: {constraints!r}"
        )


class TestTextPrimaryKeyTablesUnaffected:
    """18 张 TEXT 主键表不应新增 hash_id 字段（避免破坏性改动）"""

    # 抽样若干 TEXT 主键表（非目标 AUTOINCREMENT 表）
    TEXT_PK_TABLES = [
        "todo_list",
        "goal",
        "goal_journal",
        "plan_doc",
        "category",
        "sub_category",
        "habits",
        "habit_challenges",
        "habit_checkins",
        "diary",
        "mood_types",
        "mood_entries",
        "user_values",
        "commitments",
        "custom_record_types",
        "custom_record_fields",
        "screen_captures",
        "wechat_account_state",
    ]

    @pytest.mark.parametrize("table_name", TEXT_PK_TABLES)
    def test_text_pk_table_has_no_hash_id(self, table_name):
        """TEXT 主键表不应有 hash_id 字段（hash_id 仅用于 AUTOINCREMENT 表）"""
        from lifeprism.config.database import TABLE_CONFIGS

        if table_name not in TABLE_CONFIGS:
            pytest.skip(f"{table_name} 不在 TABLE_CONFIGS（可能已重命名）")
        columns = TABLE_CONFIGS[table_name]["columns"]
        assert "hash_id" not in columns, (
            f"{table_name} 不应有 hash_id 字段（仅 6 张 AUTOINCREMENT 表需要）"
        )
