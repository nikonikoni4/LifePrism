"""
数据库初始数据初始化模块
在新安装环境中，当数据库表为空时，添加默认的分类、示例目标和示例计划书
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# 默认分类配置
DEFAULT_CATEGORIES = [
    {'id': 'cat-work', 'name': '工作', 'color': '#5B8FF9'},
    {'id': 'cat-study', 'name': '学习', 'color': '#5AD8A6'},
    {'id': 'cat-entertainment', 'name': '娱乐', 'color': '#F6BD16'},
    {'id': 'cat-other', 'name': '其他', 'color': '#E8684A'},
]

# 每个主分类的默认子分类
DEFAULT_SUB_CATEGORIES = [
    {'id': 'subcat-work-other', 'category_id': 'cat-work', 'name': '其他'},
    {'id': 'subcat-study-other', 'category_id': 'cat-study', 'name': '其他'},
    {'id': 'subcat-entertainment-other', 'category_id': 'cat-entertainment', 'name': '其他'},
    {'id': 'subcat-other-other', 'category_id': 'cat-other', 'name': '其他'},
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
    'content': '示例计划书',
    'status': 'active',
    'order_index': 0,
}

# 示例计划书 MD 文件名
EXAMPLE_PLAN_DOC_MD_FILENAME = "示例-planDoc.md"


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
            self._initialize_default_sub_categories()
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

    def _initialize_default_sub_categories(self):
        """
        初始化默认子分类

        只有当 sub_category 表为空时才添加默认子分类
        """
        if not self._is_table_empty('sub_category'):
            logger.debug("sub_category 表已有数据，跳过默认子分类初始化")
            return

        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                for sub in DEFAULT_SUB_CATEGORIES:
                    cursor.execute("""
                        INSERT INTO sub_category (id, category_id, name, state)
                        VALUES (?, ?, ?, 1)
                    """, (sub['id'], sub['category_id'], sub['name']))

                logger.info(f"成功初始化 {len(DEFAULT_SUB_CATEGORIES)} 个默认子分类")

        except Exception as e:
            logger.error(f"初始化默认子分类失败: {e}")
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

        只有当 plan_doc 表为空时才添加示例计划书，并生成对应的 MD 文件
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

            # 生成示例 MD 文件
            self._generate_example_plan_doc_md()

        except Exception as e:
            logger.error(f"初始化示例计划书失败: {e}")
            raise

    def _generate_example_plan_doc_md(self):
        """
        生成示例计划书 MD 文件

        打包环境：由 resource_initializer 已提前复制，此处仅做兜底检查
        开发环境：文件应已存在于 localData/plan/，不做复制
        """
        try:
            from lifeprism.config.settings_manager import settings
            plan_dir = Path(settings.lifeprism_data_path) / "plan"
            plan_dir.mkdir(parents=True, exist_ok=True)
            md_path = plan_dir / EXAMPLE_PLAN_DOC_MD_FILENAME

            if md_path.exists():
                logger.debug(f"示例计划书 MD 文件已存在，跳过: {md_path}")
                return

            import sys
            if not getattr(sys, 'frozen', False):
                # 开发环境：source == target，无法复制，仅记录
                logger.debug(f"开发环境，示例计划书不存在: {md_path}")
                return

            # 打包环境：从 exe 内嵌资源读取（兜底，正常由 resource_initializer 处理）
            source = Path(sys._MEIPASS) / "templates" / "plan" / EXAMPLE_PLAN_DOC_MD_FILENAME
            if source.exists():
                content = source.read_text(encoding='utf-8')
                md_path.write_text(content, encoding='utf-8')
                logger.info(f"生成示例计划书 MD 文件: {md_path}")
            else:
                logger.warning(f"示例计划书源文件不存在: {source}")
        except Exception as e:
            logger.error(f"生成示例计划书 MD 文件失败: {e}")


def initialize_default_data():
    """
    便捷函数：初始化默认数据

    在应用启动时调用此函数来添加默认分类、示例目标和示例计划书
    """
    DataInitializer().initialize_default_data()
