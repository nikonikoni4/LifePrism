"""
ValueProvider 基线测试

目的：在迁移到 repository/providers/ 之前，先补齐基线测试覆盖现有公共接口行为。
迁移后此测试的导入路径切换到 repository.providers，再次运行以验证行为等价。

注意：基线测试只覆盖"正常路径"行为（CRUD 成功路径），不覆盖异常路径
（异常路径在迁移前后行为不同：旧实现返回 None/False，新实现抛出 DataAccessError，
这部分由 test_value_provider_migration.py 中的迁移后测试覆盖）。

依据 issue: 05-value-provider-migration
"""

import pytest

# 迁移后从 repository.providers 导入（验证行为等价）
from lifeprism.repository.providers.value_provider import ValueProvider

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def value_provider(test_data_path):
    """创建 ValueProvider 实例并初始化 user_values 表

    fixture 同时创建 commitments 表（外键子表，供级联测试场景使用）
    和 deletion_log 表（迁移后 delete_value 写墓碑预留，基线测试也建好以避免迁移后改 fixture）。
    """
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    provider = ValueProvider()

    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        # user_values 表（参考 USER_VALUES_CONFIG schema）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS user_values (
                id TEXT PRIMARY KEY NOT NULL,
                keywords TEXT NOT NULL UNIQUE,
                content_positive TEXT,
                content_negative TEXT,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        # commitments 表（外键子表，供级联测试场景使用）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS commitments (
                id TEXT PRIMARY KEY NOT NULL,
                content TEXT NOT NULL,
                value_id TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT,
                updated_at TEXT,
                CHECK(status IN ('active', 'completed', 'archived')),
                FOREIGN KEY (value_id) REFERENCES user_values(id) ON DELETE SET NULL
            )
            """
        )
        # deletion_log 表（迁移后 delete_value 会写墓碑）
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS deletion_log (
                id TEXT PRIMARY KEY,
                target_table TEXT NOT NULL,
                record_id TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT,
                updated_at TEXT,
                UNIQUE(target_table, record_id)
            )
            """
        )
        conn.commit()

    # 清理旧的测试数据（避免不同测试间状态污染）
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_values")
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()

    yield provider

    # 清理表
    with provider.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM user_values")
        cursor.execute("DELETE FROM commitments")
        cursor.execute("DELETE FROM deletion_log")
        conn.commit()


@pytest.fixture
def sample_value_data():
    """测试用的价值数据"""
    return {
        "keywords": "成长;自律",
        "content_positive": "我想成为持续成长的人",
        "content_negative": "我不想成为停滞不前的人",
        "sort_order": 10,
    }


# ==================== 基线测试：公共接口行为 ====================


class TestValueProviderBaseline:
    """基线测试：验证 ValueProvider 公共接口行为

    这些测试在迁移前后都应通过，证明 CRUD 行为等价。
    """

    def test_create_value_returns_val_prefix_id(self, value_provider, sample_value_data):
        """创建价值返回 val- 前缀的 ID"""
        value_id = value_provider.create_value(sample_value_data)

        assert value_id is not None
        assert value_id.startswith("val-"), (
            f"ID 应以 'val-' 开头，实际: {value_id}"
        )
        # val- (4 字符) + 8 位 hex = 12 字符
        assert len(value_id) == 12, f"ID 长度应为 12，实际: {len(value_id)}"

    def test_get_value_by_id_returns_created_value(
        self, value_provider, sample_value_data
    ):
        """按 ID 查询返回新创建的价值"""
        value_id = value_provider.create_value(sample_value_data)

        value = value_provider.get_value_by_id(value_id)

        assert value is not None
        assert value["id"] == value_id
        assert value["keywords"] == "成长;自律"
        assert value["content_positive"] == "我想成为持续成长的人"
        assert value["content_negative"] == "我不想成为停滞不前的人"
        assert value["sort_order"] == 10

    def test_get_value_by_id_returns_none_for_nonexistent(self, value_provider):
        """查询不存在的 ID 返回 None"""
        value = value_provider.get_value_by_id("val-nonexist")

        assert value is None

    def test_get_values_returns_list_sorted_by_sort_order_desc(
        self, value_provider, sample_value_data
    ):
        """获取价值列表返回列表，按 sort_order DESC, created_at DESC 排序"""
        # 创建第一条 sort_order=10
        value_provider.create_value(sample_value_data)
        # 创建第二条 sort_order=20（应排在前面）
        value_provider.create_value(
            {
                "keywords": "健康",
                "content_positive": "保持健康",
                "content_negative": None,
                "sort_order": 20,
            }
        )

        values = value_provider.get_values()

        assert isinstance(values, list)
        assert len(values) == 2
        # sort_order=20 应排在前面（DESC）
        assert values[0]["sort_order"] == 20
        assert values[1]["sort_order"] == 10

    def test_get_values_returns_empty_list_when_no_data(self, value_provider):
        """无数据时返回空列表"""
        values = value_provider.get_values()

        assert values == []

    def test_update_value_updates_fields(self, value_provider, sample_value_data):
        """更新价值字段成功"""
        value_id = value_provider.create_value(sample_value_data)

        result = value_provider.update_value(
            value_id,
            {
                "keywords": "成长;自律;专注",
                "content_positive": "更新后的正向描述",
            },
        )

        assert result is True

        value = value_provider.get_value_by_id(value_id)
        assert value["keywords"] == "成长;自律;专注"
        assert value["content_positive"] == "更新后的正向描述"
        # 未更新的字段应保持原值
        assert value["content_negative"] == "我不想成为停滞不前的人"
        assert value["sort_order"] == 10

    def test_update_value_with_empty_data_returns_true(
        self, value_provider, sample_value_data
    ):
        """空数据更新返回 True（无操作）"""
        value_id = value_provider.create_value(sample_value_data)

        result = value_provider.update_value(value_id, {})

        assert result is True

    def test_update_value_nonexistent_returns_false(self, value_provider):
        """更新不存在的价值返回 False"""
        result = value_provider.update_value("val-nonexist", {"keywords": "x"})

        assert result is False

    def test_delete_value_removes_record(self, value_provider, sample_value_data):
        """删除价值后记录消失（单表删除，不含级联）"""
        value_id = value_provider.create_value(sample_value_data)

        result = value_provider.delete_value(value_id)

        assert result is True
        # 验证记录已被删除
        value = value_provider.get_value_by_id(value_id)
        assert value is None

    def test_delete_value_nonexistent_returns_false(self, value_provider):
        """删除不存在的价值返回 False"""
        result = value_provider.delete_value("val-nonexist")

        assert result is False
