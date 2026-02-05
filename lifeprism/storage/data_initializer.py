"""
数据库初始数据初始化模块
在新安装环境中，当数据库表为空时，添加默认的分类、示例目标和示例计划书
"""
import logging

logger = logging.getLogger(__name__)


# 默认分类配置
DEFAULT_CATEGORIES = [
    {'id': 'cat-work', 'name': '工作', 'color': '#5B8FF9'},
    {'id': 'cat-study', 'name': '学习', 'color': '#5AD8A6'},
    {'id': 'cat-entertainment', 'name': '娱乐', 'color': '#F6BD16'},
    {'id': 'cat-other', 'name': '其他', 'color': '#E8684A'},
]

# 示例目标 ID（固定，用于关联 plan_doc）
EXAMPLE_GOAL_ID = 'goal-example'

# 示例目标配置
EXAMPLE_GOAL = {
    'id': EXAMPLE_GOAL_ID,
    'name': '示例',
    'content': '''这是一个例子：

1. 目标界面中可编辑，卡片颜色，目标分类，开始和结束时间等基础属性。
2. 编写目标的价值和承诺，解释为什么需要做这个目标，这很重要！
3. 在配置中可选择自动跟踪，当为目标设置了分类类别和自动跟踪时，会依据电脑使用数据自动跟踪目标投入时间
4. 为你的目标添加里程碑吧！查看当前目标进度
5. 可在最下方为你的目标添加log，记录目标过程！''',
    'color': '#5B8FF9',
    'status': 'active',
    'track_time_automatically': 0,  # 示例目标不开启自动追踪
    'milestones': '[]',
    'time_unit': 'HRS',
    'time_invested': 0,
    'order_index': 0,
}

# 示例计划书配置
EXAMPLE_PLAN_DOC = {
    'id': '示例-planDoc',
    'goal_id': EXAMPLE_GOAL_ID,
    'content': '''# 示例计划书

这是一个示例计划书，用于展示计划书的基本结构和功能。

## 如何使用计划书

1. **创建任务**：在计划书中使用 `- [ ]` 语法创建待办任务
2. **同步到任务池**：计划书中的任务会自动同步到任务池
3. **跟踪进度**：完成任务后，勾选复选框即可

## 示例任务列表

- [ ] 这是第一个示例任务
- [ ] 这是第二个示例任务
- [ ] 这是第三个示例任务

## 提示

- 计划书支持 Markdown 格式
- 可以添加标题、列表、代码块等
- 任务完成后会自动更新进度
''',
    'status': 'active',
    'order_index': 0,
}


class DataInitializer:
    """
    数据库初始数据初始化器

    负责在新安装环境中添加默认的分类、示例目标和示例计划书
    """

    def __init__(self, db_manager=None):
        """
        初始化数据初始化器

        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        if db_manager is None:
            from lifeprism.storage import lw_db_manager
            self.db = lw_db_manager
        else:
            self.db = db_manager

    def initialize_default_data(self):
        """
        初始化默认数据

        检查 category、goal、plan_doc 表是否为空，为空时添加默认数据
        """
        try:
            self._initialize_default_categories()
            self._initialize_example_goal()
            self._initialize_example_plan_doc()
            logger.info("默认数据初始化检查完成")
        except Exception as e:
            logger.error(f"初始化默认数据失败: {e}")
            raise

    def _is_table_empty(self, table_name: str) -> bool:
        """
        检查表是否为空

        Args:
            table_name: 表名

        Returns:
            bool: 表是否为空
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                return count == 0
        except Exception as e:
            logger.error(f"检查表 {table_name} 是否为空失败: {e}")
            return False

    def _initialize_default_categories(self):
        """
        初始化默认分类

        只有当 category 表为空时才添加默认分类
        """
        if not self._is_table_empty('category'):
            logger.debug("category 表已有数据，跳过默认分类初始化")
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                for cat in DEFAULT_CATEGORIES:
                    cursor.execute("""
                        INSERT INTO category (id, name, color, state)
                        VALUES (?, ?, ?, 1)
                    """, (cat['id'], cat['name'], cat['color']))

                logger.info(f"成功初始化 {len(DEFAULT_CATEGORIES)} 个默认分类")

        except Exception as e:
            logger.error(f"初始化默认分类失败: {e}")
            raise

    def _initialize_example_goal(self):
        """
        初始化示例目标

        只有当 goal 表为空时才添加示例目标
        """
        if not self._is_table_empty('goal'):
            logger.debug("goal 表已有数据，跳过示例目标初始化")
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO goal (
                        id, name, content, color, status,
                        track_time_automatically, milestones,
                        time_unit, time_invested, order_index
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    EXAMPLE_GOAL['id'],
                    EXAMPLE_GOAL['name'],
                    EXAMPLE_GOAL['content'],
                    EXAMPLE_GOAL['color'],
                    EXAMPLE_GOAL['status'],
                    EXAMPLE_GOAL['track_time_automatically'],
                    EXAMPLE_GOAL['milestones'],
                    EXAMPLE_GOAL['time_unit'],
                    EXAMPLE_GOAL['time_invested'],
                    EXAMPLE_GOAL['order_index'],
                ))

                logger.info(f"成功初始化示例目标，ID: {EXAMPLE_GOAL['id']}")

        except Exception as e:
            logger.error(f"初始化示例目标失败: {e}")
            raise

    def _initialize_example_plan_doc(self):
        """
        初始化示例计划书

        只有当 plan_doc 表为空时才添加示例计划书
        """
        if not self._is_table_empty('plan_doc'):
            logger.debug("plan_doc 表已有数据，跳过示例计划书初始化")
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO plan_doc (
                        id, goal_id, content, status, order_index
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    EXAMPLE_PLAN_DOC['id'],
                    EXAMPLE_PLAN_DOC['goal_id'],
                    EXAMPLE_PLAN_DOC['content'],
                    EXAMPLE_PLAN_DOC['status'],
                    EXAMPLE_PLAN_DOC['order_index'],
                ))

                logger.info(f"成功初始化示例计划书，ID: {EXAMPLE_PLAN_DOC['id']}")

        except Exception as e:
            logger.error(f"初始化示例计划书失败: {e}")
            raise


def initialize_default_data():
    """
    便捷函数：初始化默认数据

    在应用启动时调用此函数来添加默认分类、示例目标和示例计划书
    """
    DataInitializer().initialize_default_data()
