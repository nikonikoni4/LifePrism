"""
DataInitializer._initialize_daily_goal 单元测试

测试每日目标初始化的所有场景：
1. 无冲突：直接创建
2. 同名且同id：跳过
3. id相同但名不同：跳过
4. 同名但不同id：修改id
5. 极端情况（多条冲突）：跳过
"""

import pytest

from lifeprism.repository import lw_db_manager
from lifeprism.repository.data_initializer import DAILY_GOAL, DAILY_GOAL_ID, DataInitializer


@pytest.fixture
def data_initializer(test_data_path):
    """创建 DataInitializer 实例"""
    from lifeprism.config.settings_manager import settings

    settings._initialize()
    return DataInitializer()


@pytest.fixture
def clean_goal_table():
    """清空 goal 表"""
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goal")
    yield
    # 测试后清理
    with lw_db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM goal")


class TestInitializeDailyGoal:
    """测试 _initialize_daily_goal 方法的所有场景"""

    def test_case1_no_conflict_create_new(self, data_initializer, clean_goal_table):
        """
        场景1：无冲突，直接创建

        前置条件：goal 表为空
        预期结果：成功创建每日目标
        """
        # 执行初始化
        data_initializer._initialize_daily_goal()

        # 验证：应该创建了每日目标
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM goal WHERE id = ?", (DAILY_GOAL_ID,))
            result = cursor.fetchone()

        assert result is not None, "应该创建了每日目标"
        assert result[0] == DAILY_GOAL_ID
        assert result[1] == DAILY_GOAL["name"]

    def test_case2_same_name_and_id_skip(self, data_initializer, clean_goal_table):
        """
        场景2：同名且同id，跳过

        前置条件：已存在 id='goal-daily', name='每日目标' 的记录
        预期结果：跳过初始化，记录保持不变
        """
        # 预先插入完全相同的记录
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO goal (
                    id, name, content, color, status,
                    track_time_automatically, milestones,
                    time_unit, time_invested, order_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    DAILY_GOAL_ID,
                    DAILY_GOAL["name"],
                    "原始内容",
                    "#FF0000",
                    "active",
                    0,
                    "[]",
                    "HRS",
                    0,
                    0,
                ),
            )

        # 执行初始化
        data_initializer._initialize_daily_goal()

        # 验证：记录应该保持不变（content 仍是 '原始内容'）
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT content, color FROM goal WHERE id = ?", (DAILY_GOAL_ID,))
            result = cursor.fetchone()

        assert result[0] == "原始内容", "内容应该保持不变"
        assert result[1] == "#FF0000", "颜色应该保持不变"

    def test_case3_same_id_different_name_skip(self, data_initializer, clean_goal_table):
        """
        场景3：id相同但名不同，跳过

        前置条件：已存在 id='goal-daily', name='用户改的名字' 的记录
        预期结果：跳过初始化，用户修改的名字保持不变
        """
        # 预先插入 id 相同但名字不同的记录
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO goal (
                    id, name, content, color, status,
                    track_time_automatically, milestones,
                    time_unit, time_invested, order_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    DAILY_GOAL_ID,
                    "用户改的名字",
                    "用户内容",
                    "#00FF00",
                    "active",
                    0,
                    "[]",
                    "HRS",
                    0,
                    0,
                ),
            )

        # 执行初始化
        data_initializer._initialize_daily_goal()

        # 验证：名字应该保持不变
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name, content FROM goal WHERE id = ?", (DAILY_GOAL_ID,))
            result = cursor.fetchone()

        assert result[0] == "用户改的名字", "用户修改的名字应该保持不变"
        assert result[1] == "用户内容", "内容应该保持不变"

    def test_case4_same_name_different_id_update_id(self, data_initializer, clean_goal_table):
        """
        场景4：同名但不同id，修改id

        前置条件：已存在 id='goal-abc123', name='每日目标' 的记录
        预期结果：将 id 修改为 'goal-daily'
        """
        old_id = "goal-abc123"

        # 预先插入同名但不同 id 的记录
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO goal (
                    id, name, content, color, status,
                    track_time_automatically, milestones,
                    time_unit, time_invested, order_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    old_id,
                    DAILY_GOAL["name"],
                    "用户创建的内容",
                    "#0000FF",
                    "active",
                    1,
                    '["里程碑1"]',
                    "DAYS",
                    100,
                    5,
                ),
            )

        # 执行初始化
        data_initializer._initialize_daily_goal()

        # 验证：旧 id 的记录应该不存在了
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM goal WHERE id = ?", (old_id,))
            old_count = cursor.fetchone()[0]

        assert old_count == 0, "旧 id 的记录应该不存在"

        # 验证：新 id 的记录应该存在，且保留了原有数据
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, name, content, color, time_invested, order_index
                FROM goal WHERE id = ?
            """,
                (DAILY_GOAL_ID,),
            )
            result = cursor.fetchone()

        assert result is not None, "新 id 的记录应该存在"
        assert result[0] == DAILY_GOAL_ID, "id 应该是固定值"
        assert result[1] == DAILY_GOAL["name"], "名字应该保持"
        assert result[2] == "用户创建的内容", "内容应该保留"
        assert result[3] == "#0000FF", "颜色应该保留"
        assert result[4] == 100, "time_invested 应该保留"
        assert result[5] == 5, "order_index 应该保留"

    def test_case5_multiple_conflicts_skip(self, data_initializer, clean_goal_table):
        """
        场景5：极端情况（多条冲突），跳过

        前置条件：同时存在两条冲突记录
          - 记录1: id='goal-daily', name='其他名字'
          - 记录2: id='goal-xyz', name='每日目标'
        预期结果：跳过初始化，两条记录都保持不变
        """
        # 插入两条冲突记录
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # 记录1：id 相同但名字不同
            cursor.execute(
                """
                INSERT INTO goal (
                    id, name, content, color, status,
                    track_time_automatically, milestones,
                    time_unit, time_invested, order_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (DAILY_GOAL_ID, "其他名字", "内容1", "#FF0000", "active", 0, "[]", "HRS", 0, 0),
            )

            # 记录2：名字相同但 id 不同
            cursor.execute(
                """
                INSERT INTO goal (
                    id, name, content, color, status,
                    track_time_automatically, milestones,
                    time_unit, time_invested, order_index
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    "goal-xyz",
                    DAILY_GOAL["name"],
                    "内容2",
                    "#00FF00",
                    "active",
                    0,
                    "[]",
                    "HRS",
                    0,
                    0,
                ),
            )

        # 执行初始化
        data_initializer._initialize_daily_goal()

        # 验证：两条记录都应该保持不变
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # 检查记录1
            cursor.execute("SELECT name, content FROM goal WHERE id = ?", (DAILY_GOAL_ID,))
            record1 = cursor.fetchone()
            assert record1[0] == "其他名字", "记录1的名字应该保持不变"
            assert record1[1] == "内容1", "记录1的内容应该保持不变"

            # 检查记录2
            cursor.execute("SELECT id, content FROM goal WHERE name = ?", (DAILY_GOAL["name"],))
            record2 = cursor.fetchone()
            assert record2[0] == "goal-xyz", "记录2的id应该保持不变"
            assert record2[1] == "内容2", "记录2的内容应该保持不变"

    def test_plan_doc_initialization(self, data_initializer, clean_goal_table):
        """
        测试计划书初始化

        验证在每日目标存在后，会正确初始化计划书
        """
        # 先清空 plan_doc 表
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM plan_doc")

        # 执行初始化
        data_initializer._initialize_daily_goal()

        # 验证：应该创建了计划书
        with lw_db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, goal_id FROM plan_doc WHERE id = ?", ("每日目标-docs",))
            result = cursor.fetchone()

        assert result is not None, "应该创建了每日目标计划书"
        assert result[0] == "每日目标-docs"
        assert result[1] == DAILY_GOAL_ID
