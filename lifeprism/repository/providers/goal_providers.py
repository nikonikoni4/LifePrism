"""
Goal Providers - 目标相关数据提供者

包含：
- GoalProvider: goal 表的数据访问
- GoalStatsProvider: goal_stats 表的数据访问
"""
from typing import Optional, List, Dict, Any, Tuple, Set
from datetime import datetime, timedelta
import uuid
import sqlite3

from lifeprism.repository import LWBaseDataProvider
from lifeprism.repository.providers.common_query_options import QueryOptions
from lifeprism.utils import get_logger, LazySingleton
from lifeprism.utils.exceptions import DataAccessError, ConflictError, ValidationError

logger = get_logger(__name__)


# ==================== GoalProvider ====================

class GoalProvider(LWBaseDataProvider):
    """
    目标数据提供者（对应 goal 表）

    职责：提供 goal 表的所有数据访问接口
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "goal"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = None
    _TIME_FIELD = None

    # 白名单字段集合
    _FILTER_FIELDS: Set[str] = {
        'id', 'name', 'status', 'link_to_category_id', 'link_to_sub_category_id',
        'start_date', 'expected_finished_at', 'track_time_automatically', 'order_index'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'name', 'order_index', 'created_at', 'start_date'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'name', 'content', 'color', 'link_to_category_id', 'link_to_sub_category_id',
        'start_date', 'expected_finished_at', 'value', 'commitment', 'time_unit',
        'time_invested', 'track_time_automatically', 'milestones', 'status', 'order_index',
        'time_invested_updated_at', 'created_at', 'updated_at'
    }
    _UPDATE_FIELDS: Set[str] = {
        'name', 'content', 'color', 'link_to_category_id', 'link_to_sub_category_id',
        'start_date', 'expected_finished_at', 'value', 'commitment', 'time_unit',
        'time_invested', 'track_time_automatically', 'milestones', 'status', 'order_index',
        'time_invested_updated_at'
    }

    # ==================== 核心方法（使用通用方法） ====================

    def query_goals(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'status': 'active'})
            records, total = provider.query_goals(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_goals(options)
        """
        return self._generic_query(options)

    def get_goals(
        self,
        status: Optional[str] = None,
        category_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        获取目标列表

        Args:
            status: 按状态筛选（active, completed, archived）
            category_id: 按分类筛选
            page: 页码（从1开始）
            page_size: 每页数量

        Returns:
            tuple: (目标列表, 总数)
        """
        filters = {}
        if status:
            filters['status'] = status
        if category_id:
            filters['link_to_category_id'] = category_id

        options = QueryOptions(
            filters=filters if filters else None,
            order_by='order_index',
            order_desc=False,
            page=page,
            page_size=page_size
        )
        return self._generic_query(options)

    def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """
        按 ID 获取单个目标

        Args:
            goal_id: 目标 ID (格式: goal-xxx)

        Returns:
            Optional[Dict]: 目标数据，不存在返回 None
        """
        options = QueryOptions(
            filters={'id': goal_id},
            order_by='id',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    def create_goal(self, data: Dict[str, Any]) -> Optional[str]:
        """
        创建新目标

        Args:
            data: 目标数据

        Returns:
            Optional[str]: 新目标 ID (格式: goal-xxx)

        Raises:
            ValidationError: 字段验证失败
            ConflictError: 记录已存在
            DataAccessError: 数据库操作失败
        """
        try:
            # 生成唯一 ID
            goal_id = f"goal-{str(uuid.uuid4())[:8]}"
            data['id'] = goal_id

            # 获取当前最大 order_index
            if 'order_index' not in data:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COALESCE(MAX(order_index), -1) + 1 FROM goal")
                    data['order_index'] = cursor.fetchone()[0]

            # 设置默认值
            data.setdefault('content', '')
            data.setdefault('color', '#5B8FF9')
            data.setdefault('time_unit', 'HRS')
            data.setdefault('time_invested', 0)
            data.setdefault('track_time_automatically', 1)
            data.setdefault('milestones', '[]')
            data.setdefault('status', 'active')

            # 白名单验证
            allowed_fields = self._UPDATE_FIELDS | {self._PRIMARY_KEY}
            invalid_fields = set(data.keys()) - allowed_fields
            if invalid_fields:
                raise ValidationError(f"Invalid insert fields: {invalid_fields}")

            self._generic_insert(data)
            logger.info("创建目标成功，ID: %s", goal_id)
            return goal_id

        except ValidationError:
            raise
        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                raise ConflictError(f"目标记录已存在") from e
            raise DataAccessError(f"数据完整性错误") from e
        except Exception as e:
            logger.error("创建目标失败: %s", e)
            raise DataAccessError(
                message=f"创建目标失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    def update_goal(self, goal_id: str, data: Dict[str, Any]) -> bool:
        """
        更新目标

        Args:
            goal_id: 目标 ID (格式: goal-xxx)
            data: 要更新的字段

        Returns:
            bool: 是否成功

        Raises:
            ValidationError: 字段验证失败
            DataAccessError: 数据库操作失败
        """
        if not data:
            return True

        try:
            # 白名单验证
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValidationError(f"Invalid update fields: {invalid_fields}")

            # goal 表不自动更新 updated_at，只更新传入的字段
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                set_clauses = [f"{key} = ?" for key in data.keys()]
                values = list(data.values()) + [goal_id]
                sql = f"UPDATE {self._TABLE_NAME} SET {', '.join(set_clauses)} WHERE {self._PRIMARY_KEY} = ?"
                cursor.execute(sql, values)
                success = cursor.rowcount > 0

            if success:
                logger.info("更新目标 %s 成功", goal_id)
            return success

        except ValidationError:
            raise
        except Exception as e:
            logger.error("更新目标 %s 失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"更新目标失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    def delete_goal(self, goal_id: str) -> bool:
        """
        删除目标

        Args:
            goal_id: 目标 ID (格式: goal-xxx)

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            # 先清除 todo_list 中关联的目标
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE todo_list SET link_to_goal_id = NULL WHERE link_to_goal_id = ?",
                    (goal_id,)
                )
                cleared_count = cursor.rowcount
                if cleared_count > 0:
                    logger.info("清除了 %s 个任务的目标关联", cleared_count)

            # 然后删除目标
            success = self._generic_delete(goal_id)
            if success:
                logger.info("删除目标 %s 成功", goal_id)
            return success

        except Exception as e:
            logger.error("删除目标 %s 失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"删除目标失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    # ==================== 业务方法 ====================

    def reorder_goals(self, goal_ids: List[str]) -> bool:
        """
        批量更新目标排序

        Args:
            goal_ids: 目标 ID 列表（按新顺序排列）

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                for index, goal_id in enumerate(goal_ids):
                    cursor.execute(
                        "UPDATE goal SET order_index = ? WHERE id = ?",
                        (index, goal_id)
                    )

                logger.info("重排序 %s 个目标成功", len(goal_ids))
                return True

        except Exception as e:
            logger.error("重排序目标失败: %s", e)
            raise DataAccessError(
                message=f"重排序目标失败",
                details={"goal_count": len(goal_ids), "error": str(e)}
            ) from e

    def get_active_goals(self) -> List[Dict[str, Any]]:
        """
        获取所有进行中的目标（用于前端选择绑定）

        Returns:
            List[Dict]: 目标列表，包含 id 和 name
        """
        options = QueryOptions(
            filters={'status': 'active'},
            fields=['id', 'name'],
            order_by='order_index',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def get_active_goals_with_category(self) -> List[Dict[str, Any]]:
        """
        获取所有绑定了分类的进行中目标（用于 Map Cache 编辑界面）

        只返回 link_to_category_id 不为空的目标

        Returns:
            List[Dict]: 目标列表，包含 id, name, link_to_category_id, link_to_sub_category_id

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, link_to_category_id, link_to_sub_category_id
                    FROM goal
                    WHERE status = 'active' AND link_to_category_id IS NOT NULL
                    ORDER BY order_index ASC
                """)

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("获取绑定分类的活跃目标列表失败: %s", e)
            raise DataAccessError(
                message=f"获取绑定分类的活跃目标列表失败",
                details={"error": str(e)}
            ) from e

    def get_goals_linked_to_category(self, category_id: str) -> List[Dict[str, Any]]:
        """
        获取关联到特定分类的所有目标

        Args:
            category_id: 分类 ID

        Returns:
            List[Dict]: 目标列表
        """
        options = QueryOptions(
            filters={'link_to_category_id': category_id},
            order_by='order_index',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results

    def get_active_goals_for_classify(self) -> List[Dict[str, Any]]:
        """
        获取所有活跃目标（用于 LLM 分类时的名称-ID映射）

        只返回满足以下条件的目标：
        1. 目标状态为 active
        2. 目标开启了自动时间追踪（track_time_automatically == 1）
        3. 目标必须绑定了主分类（link_to_category_id IS NOT NULL）
        4. 关联的主分类未被禁用（category.state != 0）
        5. 关联的子分类未被禁用（sub_category.state != 0 或未关联子分类）

        Returns:
            List[Dict]: 包含 id, name, link_to_category_id, link_to_sub_category_id 的目标列表

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT g.id, g.name, g.link_to_category_id, g.link_to_sub_category_id
                    FROM goal g
                    INNER JOIN category c ON g.link_to_category_id = c.id
                    LEFT JOIN sub_category sc ON g.link_to_sub_category_id = sc.id
                    WHERE g.status = 'active'
                      AND g.track_time_automatically = 1
                      AND g.link_to_category_id IS NOT NULL
                      AND c.state != 0
                      AND (sc.state IS NULL OR sc.state != 0)
                    ORDER BY g.order_index ASC
                """)

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error("获取活跃目标列表（用于分类）失败: %s", e)
            raise DataAccessError(
                message=f"获取活跃目标列表（用于分类）失败",
                details={"error": str(e)}
            ) from e

    def calculate_time_invested(self, goal_id: str) -> int:
        """
        从 user_app_behavior_log 计算目标的总投入时间

        Args:
            goal_id: 目标 ID

        Returns:
            int: 总投入时间（秒）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COALESCE(SUM(duration), 0) as total_seconds
                    FROM user_app_behavior_log
                    WHERE link_to_goal_id = ?
                """, (goal_id,))

                result = cursor.fetchone()
                total_seconds = int(result[0]) if result and result[0] else 0
                return total_seconds

        except Exception as e:
            logger.error("计算目标 %s 投入时间失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"计算目标投入时间失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    def update_time_invested(self, goal_id: str, time_invested: int) -> bool:
        """
        更新目标的投入时间和更新时间戳

        Args:
            goal_id: 目标 ID
            time_invested: 投入时间（秒）

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            data = {
                'time_invested': time_invested,
                'time_invested_updated_at': now
            }
            success = self._generic_update(goal_id, data)
            if success:
                logger.info("更新目标 %s 投入时间: %s 秒", goal_id, time_invested)
            return success

        except Exception as e:
            logger.error("更新目标 %s 投入时间失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"更新目标投入时间失败",
                details={"goal_id": goal_id, "time_invested": time_invested, "error": str(e)}
            ) from e


# ==================== GoalStatsProvider ====================

class GoalStatsProvider(LWBaseDataProvider):
    """
    目标统计数据提供者（对应 goal_stats 表）

    职责：提供 goal_stats 表的查询和更新操作
    支持懒加载：在查询时自动补全缺失日期的统计数据
    """

    # ==================== 表元数据定义 ====================

    _TABLE_NAME = "goal_stats"
    _PRIMARY_KEY = "id"
    _DATE_FIELD = "date"
    _TIME_FIELD = None

    # 白名单字段集合
    _FILTER_FIELDS: Set[str] = {
        'id', 'goal_id', 'date'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'goal_id'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'goal_id', 'date', 'time_spent', 'completed_todo_count'
    }
    _UPDATE_FIELDS: Set[str] = {
        'goal_id', 'date', 'time_spent', 'completed_todo_count'
    }

    # ==================== 核心方法（使用通用方法） ====================

    def query_goal_stats(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口

        Args:
            options: 查询选项
                - 支持 date_range: 日期范围查询（基于 date 字段）
                - 支持 filters: 字段过滤
                - 支持 order_by/order_desc: 排序
                - 支持 page/page_size: 分页

        Returns:
            (记录列表, 总记录数)

        Examples:
            # 基本查询
            options = QueryOptions(filters={'goal_id': 'goal-12345678'})
            records, total = provider.query_goal_stats(options)

            # 分页查询
            options = QueryOptions(page=1, page_size=20)
            records, total = provider.query_goal_stats(options)
        """
        return self._generic_query(options)

    def get_stats_by_goal(self, goal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        获取目标的统计历史数据

        Args:
            goal_id: 目标 ID
            limit: 返回最近 N 天的数据

        Returns:
            List[Dict]: 统计数据列表，按日期升序排列
        """
        options = QueryOptions(
            filters={'goal_id': goal_id},
            order_by='date',
            order_desc=True,
            limit=limit
        )
        results, _ = self._generic_query(options)
        # 返回时按日期升序
        results.reverse()
        return results

    def get_latest_stat_date(self, goal_id: str) -> Optional[str]:
        """
        获取目标统计的最后更新日期

        Args:
            goal_id: 目标 ID

        Returns:
            Optional[str]: 最后日期 (YYYY-MM-DD)，无数据返回 None

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MAX(date) FROM goal_stats WHERE goal_id = ?
                """, (goal_id,))

                result = cursor.fetchone()
                return result[0] if result and result[0] else None

        except Exception as e:
            logger.error("获取目标 %s 最新统计日期失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"获取目标最新统计日期失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    def get_stat_by_date(self, goal_id: str, date: str) -> Optional[Dict[str, Any]]:
        """
        获取指定日期的统计数据

        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)

        Returns:
            Optional[Dict]: 统计数据
        """
        options = QueryOptions(
            filters={'goal_id': goal_id, 'date': date},
            order_by='id',
            order_desc=False
        )
        results, _ = self._generic_query(options)
        return results[0] if results else None

    # ==================== 更新操作 ====================

    def upsert_stat(self, goal_id: str, date: str, time_spent: int, todo_count: int) -> bool:
        """
        插入或更新统计数据

        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)
            time_spent: 花费时间（秒）
            todo_count: 完成的待办数量

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 检查是否已存在
                cursor.execute("""
                    SELECT id FROM goal_stats WHERE goal_id = ? AND date = ?
                """, (goal_id, date))

                existing = cursor.fetchone()

                if existing:
                    # 更新
                    cursor.execute("""
                        UPDATE goal_stats
                        SET time_spent = ?, completed_todo_count = ?
                        WHERE goal_id = ? AND date = ?
                    """, (time_spent, todo_count, goal_id, date))

                else:
                    # 插入
                    cursor.execute("""
                        INSERT INTO goal_stats (goal_id, date, time_spent, completed_todo_count)
                        VALUES (?, ?, ?, ?)
                    """, (goal_id, date, time_spent, todo_count))

                logger.info("目标 %s 在 %s 的统计数据已更新", goal_id, date)
                return True

        except Exception as e:
            logger.error("更新目标 %s 在 %s 的统计数据失败: %s", goal_id, date, e)
            raise DataAccessError(
                message=f"更新目标统计数据失败",
                details={"goal_id": goal_id, "date": date, "error": str(e)}
            ) from e

    # ==================== 聚合操作 ====================

    def aggregate_time_spent_from_behavior_log(self, goal_id: str, date: str) -> int:
        """
        从 user_app_behavior_log 聚合指定日期的时间花费

        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)

        Returns:
            int: 花费时间（秒）

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 使用日期前缀匹配，避免时区问题
                date_prefix = f"{date}%"

                cursor.execute("""
                    SELECT COALESCE(SUM(duration), 0) as total_duration
                    FROM user_app_behavior_log
                    WHERE link_to_goal_id = ?
                      AND start_time LIKE ?
                """, (goal_id, date_prefix))

                result = cursor.fetchone()
                total = int(result[0]) if result and result[0] else 0
                logger.debug("aggregate_time_spent: goal_id=%s, date=%s, total=%s", goal_id, date, total)
                return total

        except Exception as e:
            logger.error("聚合目标 %s 在 %s 的时间花费失败: %s", goal_id, date, e)
            raise DataAccessError(
                message=f"聚合目标时间花费失败",
                details={"goal_id": goal_id, "date": date, "error": str(e)}
            ) from e

    def aggregate_completed_todos(self, goal_id: str, date: str) -> int:
        """
        从 todo_list 统计指定日期完成的待办数量

        Args:
            goal_id: 目标 ID
            date: 日期 (YYYY-MM-DD)

        Returns:
            int: 完成的待办数量

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT COUNT(*) as count
                    FROM todo_list
                    WHERE link_to_goal_id = ?
                      AND state = 'completed'
                      AND actual_finished_at = ?
                """, (goal_id, date))

                result = cursor.fetchone()
                return int(result[0]) if result and result[0] else 0

        except Exception as e:
            logger.error("统计目标 %s 在 %s 完成的待办数量失败: %s", goal_id, date, e)
            raise DataAccessError(
                message=f"统计目标完成的待办数量失败",
                details={"goal_id": goal_id, "date": date, "error": str(e)}
            ) from e

    def sync_stats_to_date(self, goal_id: str, target_date: str, start_date: str = None) -> bool:
        """
        同步统计数据到指定日期

        检查最后更新日期，补全缺失的日期数据

        Args:
            goal_id: 目标 ID
            target_date: 目标日期 (YYYY-MM-DD)
            start_date: 起始日期 (YYYY-MM-DD)，用于新 reward 时从特定日期开始统计

        Returns:
            bool: 是否成功

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            last_date = self.get_latest_stat_date(goal_id)
            logger.debug("sync_stats_to_date: goal_id=%s, target_date=%s, start_date=%s, last_date=%s", goal_id, target_date, start_date, last_date)

            target_dt = datetime.strptime(target_date, "%Y-%m-%d")

            if last_date is None:
                # 没有历史数据
                if start_date:
                    # 从 start_date 开始同步到 target_date
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    dates_to_sync = []
                    current = start_dt
                    while current <= target_dt:
                        dates_to_sync.append(current.strftime("%Y-%m-%d"))
                        current += timedelta(days=1)
                else:
                    # 只计算今天
                    dates_to_sync = [target_date]
            else:
                # 已有历史数据
                last_dt = datetime.strptime(last_date, "%Y-%m-%d")

                # 确定实际的起始日期
                if start_date:
                    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                    earliest_date = self._get_earliest_stat_date(goal_id)
                    earliest_dt = datetime.strptime(earliest_date, "%Y-%m-%d") if earliest_date else last_dt

                    if start_dt < earliest_dt:
                        # start_date 比现有最早的记录还早，需要向前补全
                        dates_to_sync = []
                        current = start_dt
                        while current < earliest_dt:
                            dates_to_sync.append(current.strftime("%Y-%m-%d"))
                            current += timedelta(days=1)
                        # 再加上从 last_date 之后到 target_date 的日期
                        if last_dt < target_dt:
                            current = last_dt + timedelta(days=1)
                            while current <= target_dt:
                                dates_to_sync.append(current.strftime("%Y-%m-%d"))
                                current += timedelta(days=1)
                        # 最后更新今天
                        if target_date not in dates_to_sync:
                            dates_to_sync.append(target_date)
                    else:
                        # 正常情况：补全从 last_date 之后到 target_date
                        if last_dt >= target_dt:
                            dates_to_sync = [target_date]
                        else:
                            dates_to_sync = []
                            current = last_dt + timedelta(days=1)
                            while current <= target_dt:
                                dates_to_sync.append(current.strftime("%Y-%m-%d"))
                                current += timedelta(days=1)

                else:
                    # 没有 start_date，正常补全
                    if last_dt >= target_dt:
                        dates_to_sync = [target_date]
                    else:
                        dates_to_sync = []
                        current = last_dt + timedelta(days=1)
                        while current <= target_dt:
                            dates_to_sync.append(current.strftime("%Y-%m-%d"))
                            current += timedelta(days=1)

            # 同步每个日期的数据
            for date in dates_to_sync:
                time_spent = self.aggregate_time_spent_from_behavior_log(goal_id, date)
                todo_count = self.aggregate_completed_todos(goal_id, date)
                self.upsert_stat(goal_id, date, time_spent, todo_count)

            logger.info("目标 %s 同步了 %s 天的统计数据", goal_id, len(dates_to_sync))
            return True

        except Exception as e:
            logger.error("同步目标 %s 统计数据失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"同步目标统计数据失败",
                details={"goal_id": goal_id, "target_date": target_date, "error": str(e)}
            ) from e

    def _get_earliest_stat_date(self, goal_id: str) -> Optional[str]:
        """
        获取目标统计的最早日期

        Args:
            goal_id: 目标 ID

        Returns:
            Optional[str]: 最早日期 (YYYY-MM-DD)，无数据返回 None

        Raises:
            DataAccessError: 数据库操作失败
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(date) FROM goal_stats WHERE goal_id = ?
                """, (goal_id,))

                result = cursor.fetchone()
                return result[0] if result and result[0] else None

        except Exception as e:
            logger.error("获取目标 %s 最早统计日期失败: %s", goal_id, e)
            raise DataAccessError(
                message=f"获取目标最早统计日期失败",
                details={"goal_id": goal_id, "error": str(e)}
            ) from e

    def get_cumulative_stats(self, goal_id: str, limit: int = 30) -> List[Dict[str, Any]]:
        """
        获取累积统计数据（用于图表展示）

        Args:
            goal_id: 目标 ID
            limit: 返回最近 N 天的数据

        Returns:
            List[Dict]: 累积统计数据
        """
        stats = self.get_stats_by_goal(goal_id, limit)

        cumulative_time = 0
        cumulative_todos = 0
        result = []

        for stat in stats:
            cumulative_time += stat.get('time_spent', 0)
            cumulative_todos += stat.get('completed_todo_count', 0)
            result.append({
                'date': stat['date'],
                'cumulative_time_spent': cumulative_time,
                'cumulative_todo_count': cumulative_todos
            })

        return result


