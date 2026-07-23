"""
从数据库中读取数据,计算统计指标,为前端显示提供数据支持

DEPRECATED: 本文件中 10 个业务方法已迁移到 computer_usage_repository
（ComputerUsageProvider + ComputerUsageAggregator）。保留这些方法仅作为
基线测试（test_statistical_data_providers_baseline.py）的对照基准。
将在基类 11 个遗留方法迁移完成后删除整个文件。

请勿在新代码中调用这些方法，应使用：
    from lifeprism.repository import computer_usage_repository
"""

from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import LazySingleton, get_logger
from lifeprism.utils.time_utils import build_utc_time_range, utc_to_local_display

logger = get_logger(__name__)


class ServerLWDataProvider(LWBaseDataProvider):
    """
    Server 模块专用数据提供者

    继承 LWBaseDataProvider，提供前端 API 所需的统计和查询方法
    内部使用 self.db 访问数据库（来自父类）

    DEPRECATED: 10 个业务方法已迁移到 computer_usage_repository。
    保留仅作为基线测试对照，请勿在新代码中直接调用。
    """

    def get_active_time(self, date) -> int:
        """
        获取指定日期的总活跃时长
        return
            int, 活跃时长(秒)
        """
        self.current_date = date
        sql = """
        SELECT SUM(duration)
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time))
            result = cursor.fetchone()

        return result[0] if result and result[0] is not None else 0

    def get_top_applications(self, date, top_n) -> list[dict]:
        """
        获取指定日期的Top应用排行
        arg:
            date: 日期字符串 (YYYY-MM-DD)
            top_n: int, Top N
        return
            list[dict], Top应用排行:
                name: str, 应用名称
                duration: int, 活跃时长(秒)
        """
        self.current_date = date
        sql = """
        SELECT app, CAST(SUM(duration) AS INTEGER) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY app
        ORDER BY total_duration DESC
        LIMIT ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time, top_n))
            results = cursor.fetchall()

        return [{"name": row[0], "duration": row[1]} for row in results]

    def get_top_title(self, date, top_n) -> list[dict]:
        """
        获取指定日期的Top窗口标题排行
        arg:
            date: 日期字符串 (YYYY-MM-DD)
            top_n: int, Top N
        return
            list[dict], Top窗口标题排行:
                name: str, 窗口标题
                duration: int, 活跃时长(秒)
        """
        self.current_date = date
        sql = """
        SELECT title, CAST(SUM(duration) AS INTEGER) as total_duration
        FROM user_app_behavior_log
        WHERE start_time >= ? AND start_time <= ?
        GROUP BY title
        ORDER BY total_duration DESC
        LIMIT ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (self._start_time, self._end_time, top_n))
            results = cursor.fetchall()

        return [{"name": row[0], "duration": row[1]} for row in results]

    def get_daily_active_time(
        self, start_date: str, end_date: str, category_id: str = None, sub_category_id: str = None
    ) -> list[dict]:
        """
        获取指定日期范围内每天的活跃时长（只使用一次SQL查询）
        arg:
            start_date: str, 开始日期（YYYY-MM-DD 格式）
            end_date: str, 结束日期（YYYY-MM-DD 格式）
            category_id: str, 主分类ID筛选（可选）
            sub_category_id: str, 子分类ID筛选（可选）
        return
            list[dict], 每天的活动数据:
                date: str, 日期（YYYY-MM-DD 格式）
                active_time_percentage: int, 活动时长占比（%）
        """
        # 将本地日期范围转换为 UTC ISO 8601 时间范围
        start_utc, _ = build_utc_time_range(start_date)
        _, end_utc = build_utc_time_range(end_date)

        # 构建动态SQL查询
        where_conditions = ["start_time >= ?", "start_time <= ?"]
        params = [start_utc, end_utc]

        if category_id:
            where_conditions.append("category_id = ?")
            params.append(category_id)

        if sub_category_id:
            where_conditions.append("sub_category_id = ?")
            params.append(sub_category_id)

        # 不在 SQL 中按 DATE(start_time) 分组（会按 UTC 日期分组导致跨时区错位），
        # 而是查出原始数据后在 Python 层按本地日期分组。
        sql = f"""
        SELECT
            start_time,
            duration
        FROM user_app_behavior_log
        WHERE {" AND ".join(where_conditions)}
        ORDER BY start_time
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            results = cursor.fetchall()

        # 按本地日期分组聚合
        daily_durations: dict[str, int] = {}
        for row in results:
            start_time_iso = row[0]
            duration = row[1] if row[1] is not None else 0
            try:
                local_date = utc_to_local_display(start_time_iso)[:10]
            except (ValueError, TypeError):
                continue
            daily_durations[local_date] = daily_durations.get(local_date, 0) + duration

        # 转换为响应格式并计算百分比
        daily_activities = []
        for local_date, total_duration in sorted(daily_durations.items()):
            # 按当天总秒数 86400 计算占比
            active_time_percentage = int(total_duration * 100 / 86400) if total_duration > 0 else 0
            daily_activities.append(
                {
                    "date": local_date,
                    "active_time_percentage": active_time_percentage,
                }
            )

        return daily_activities

    def get_activity_log_by_id(self, log_id: str) -> dict | None:
        """
        根据 ID 获取单条活动日志

        Args:
            log_id: 日志ID

        Returns:
            dict: 日志详情，如果不存在返回 None
        """
        sql = """
        SELECT
            uabl.id,
            uabl.start_time,
            uabl.end_time,
            uabl.duration,
            uabl.app,
            uabl.title,
            uabl.category_id,
            c.name as category_name,
            uabl.sub_category_id,
            sc.name as sub_category_name
        FROM user_app_behavior_log uabl
        LEFT JOIN category c ON uabl.category_id = c.id
        LEFT JOIN sub_category sc ON uabl.sub_category_id = sc.id
        WHERE uabl.id = ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (log_id,))
            row = cursor.fetchone()

        if not row:
            return None

        return {
            "id": str(row[0]),
            "start_time": row[1],
            "end_time": row[2],
            "duration": row[3],
            "app": row[4],
            "title": row[5],
            "category_id": str(row[6]) if row[6] else None,
            "category_name": row[7],
            "sub_category_id": str(row[8]) if row[8] else None,
            "sub_category_name": row[9],
        }

    def update_event_category(
        self, event_id: str, category_id: str, sub_category_id: str = None
    ) -> bool:
        """
        更新事件的分类信息

        Args:
            event_id: 事件ID
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）

        Returns:
            bool: 是否更新成功
        """
        sql = """
        UPDATE user_app_behavior_log
        SET category_id = ?, sub_category_id = ?
        WHERE id = ?
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category_id, sub_category_id, event_id))
            conn.commit()
            return cursor.rowcount > 0

    def batch_update_event_category(
        self, event_ids: list[str], category_id: str, sub_category_id: str = None
    ) -> int:
        """
        批量更新事件分类，返回更新数量

        Args:
            event_ids: 事件ID列表
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）

        Returns:
            int: 成功更新的数量
        """
        if not event_ids:
            return 0
        placeholders = ",".join("?" * len(event_ids))
        sql = f"""
        UPDATE user_app_behavior_log
        SET category_id = ?, sub_category_id = ?
        WHERE id IN ({placeholders})
        """

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (category_id, sub_category_id, *event_ids))
            conn.commit()
            return cursor.rowcount

    def delete_event(self, event_id: str) -> bool:
        """
        删除单条事件

        Args:
            event_id: 事件ID

        Returns:
            bool: 是否删除成功
        """
        sql = "DELETE FROM user_app_behavior_log WHERE id = ?"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (event_id,))
            conn.commit()
            return cursor.rowcount > 0

    def batch_delete_events(self, event_ids: list[str]) -> int:
        """
        批量删除事件，返回删除数量

        Args:
            event_ids: 事件ID列表

        Returns:
            int: 成功删除的数量
        """
        if not event_ids:
            return 0
        placeholders = ",".join("?" * len(event_ids))
        sql = f"DELETE FROM user_app_behavior_log WHERE id IN ({placeholders})"

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, event_ids)
            conn.commit()
            return cursor.rowcount

    def update_logs_by_app_title(
        self,
        app: str,
        title: str | None,
        is_multipurpose_app: bool,
        category_id: str,
        sub_category_id: str | None = None,
        goal_id: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
    ) -> int:
        """
        根据 app 和可选的 title 批量更新日志分类

        匹配逻辑：
        - 单用途应用 (is_multipurpose_app=False): 仅按 app 匹配
        - 多用途应用 (is_multipurpose_app=True): 按 app + title 匹配

        Args:
            app: 应用名称
            title: 窗口标题（多用途应用时必须提供）
            is_multipurpose_app: 是否为多用途应用
            category_id: 主分类ID
            sub_category_id: 子分类ID（可选）
            goal_id: 目标ID（None=不修改, ''=清除, 'goal-xxx'=设置）
            start_time: 开始时间 ISO 8601 格式（可选）
            end_time: 结束时间 ISO 8601 格式（可选）

        Returns:
            int: 成功更新的数量
        """
        # 构建 SET 子句
        set_parts = ["category_id = ?", "sub_category_id = ?"]
        params = [category_id, sub_category_id]

        # goal_id 处理：None=不修改，""=清除，"goal-xxx"=设置
        if goal_id is not None:
            set_parts.append("link_to_goal_id = ?")
            # ""空字符串转换为 None（清除）
            params.append(goal_id if goal_id else None)

        # 构建 WHERE 条件
        where_parts = ["app = ?"]
        where_params = [app]

        if is_multipurpose_app:
            # 多用途应用：匹配 app + title
            if title is None:
                raise ValueError("多用途应用必须提供 title 参数")
            where_parts.append("title = ?")
            where_params.append(title)

        # UTC 时间范围过滤
        if start_time:
            where_parts.append("start_time >= ?")
            where_params.append(start_time)
        if end_time:
            where_parts.append("start_time <= ?")
            where_params.append(end_time)

        sql = f"""
        UPDATE user_app_behavior_log
        SET {", ".join(set_parts)}
        WHERE {" AND ".join(where_parts)}
        """

        all_params = params + where_params

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, all_params)
            conn.commit()
            updated_count = cursor.rowcount

        time_range_msg = ""
        if start_time or end_time:
            time_range_msg = f" (时间范围: {start_time or '开始'} ~ {end_time or '至今'})"

        logger.info(
            f"根据 app='{app}' {'+ title' if is_multipurpose_app else ''}{time_range_msg} 更新了 {updated_count} 条日志"
        )
        return updated_count


server_lw_data_provider = LazySingleton(ServerLWDataProvider)
