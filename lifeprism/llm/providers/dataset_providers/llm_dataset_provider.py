"""LLM 数据集提供者

提供 LLM 模块所需的通用数据库查询接口，专注于数据获取，不包含业务逻辑。
"""
from typing import Optional, List, Dict, Any

from lifeprism.storage import LWBaseDataProvider
from lifeprism.utils import get_logger, LazySingleton,DEBUG

logger = get_logger(__name__)
logger.setLevel(DEBUG)

class LLMDatasetProvider(LWBaseDataProvider):
    """LLM 数据集提供者

    提供 LLM 模块所需的数据查询接口，包括：
    - TodoList 查询
    - Token 使用量记录
    - 其他数据集查询（待扩展）
    """

    def __init__(self, db_manager=None):
        """初始化 LLM 数据集提供者

        Args:
            db_manager: DatabaseManager 实例，None 则使用全局单例
        """
        super().__init__(db_manager)

    # ==================== TodoList 查询 ====================

    def query_todos(
        self,
        start_date: str,
        end_date: Optional[str] = None,
        goal_id: Optional[str] = None,
        plandoc_id: Optional[str] = None,
        state: Optional[str] = None,
        include_cross_day: bool = True,
    ) -> List[Dict[str, Any]]:
        """查询 TodoList

        支持单日查询和日期范围查询。
        - 单日查询：只传 start_date，end_date 为 None
        - 日期范围查询：传 start_date 和 end_date

        Args:
            start_date: 开始日期（YYYY-MM-DD 格式）
            end_date: 结束日期（YYYY-MM-DD 格式，可选）
                     - None: 单日查询，只查询 start_date 当天
                     - 指定日期: 日期范围查询，查询 [start_date, end_date] 区间
            goal_id: 目标 ID 过滤（可选）
            plandoc_id: 计划文档 ID 过滤（可选）
            state: 状态过滤（可选，如 'active', 'completed', 'pool'）
            include_cross_day: 是否包含跨天未完成任务（默认 True）
                              仅在单日查询时生效

        Returns:
            List[Dict]: TodoList 列表，按日期和 order_index 排序

        Example:
            >>> provider = LLMDatasetProvider()
            >>> # 单日查询
            >>> todos = provider.query_todos(
            ...     start_date="2026-04-19",
            ...     goal_id="goal-abc123"
            ... )
            >>> # 日期范围查询
            >>> todos = provider.query_todos(
            ...     start_date="2026-04-19",
            ...     end_date="2026-04-21",
            ...     state="active"
            ... )
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                # 判断是单日查询还是日期范围查询
                is_single_date = (end_date is None)

                if is_single_date:
                    # 单日查询
                    if include_cross_day:
                        # 包含当天任务 + 跨天未完成任务
                        sql = """
                        SELECT * FROM todo_list
                        WHERE (date = ? OR (cross_day = 1 AND state = 'active' AND date < ?))
                        """
                        params = [start_date, start_date]
                    else:
                        # 仅当天任务
                        sql = """
                        SELECT * FROM todo_list
                        WHERE date = ?
                        """
                        params = [start_date]
                else:
                    # 日期范围查询
                    sql = """
                    SELECT * FROM todo_list
                    WHERE date >= ? AND date <= ?
                    """
                    params = [start_date, end_date]

                # 添加可选过滤条件
                if goal_id is not None:
                    sql += " AND link_to_goal_id = ?"
                    params.append(goal_id)

                if plandoc_id is not None:
                    sql += " AND plan_doc_id = ?"
                    params.append(plandoc_id)

                if state is not None:
                    sql += " AND state = ?"
                    params.append(state)

                # 排序
                if is_single_date:
                    sql += " ORDER BY order_index ASC"
                else:
                    sql += " ORDER BY date ASC, order_index ASC"

                cursor.execute(sql, params)

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                todos = [dict(zip(columns, row)) for row in rows]

                # 日志
                if is_single_date:
                    logger.debug(
                        f"查询单日 TodoList: {start_date}, "
                        f"goal_id={goal_id}, plandoc_id={plandoc_id}, state={state}, "
                        f"include_cross_day={include_cross_day}, 结果数量={len(todos)}"
                    )
                else:
                    logger.debug(
                        f"查询日期范围 TodoList: {start_date} -> {end_date}, "
                        f"goal_id={goal_id}, plandoc_id={plandoc_id}, state={state}, "
                        f"结果数量={len(todos)}"
                    )

                return todos

        except Exception as e:
            logger.error(f"查询 TodoList 失败: {e}", exc_info=True)
            return []

    # ==================== Token 使用量记录 ====================

    def save_usage(
        self,
        session_id: str,
        usage: Dict[str, Any],
        mode: str = 'chatbot'
    ) -> int:
        """保存或更新单个会话的 token 使用情况

        Args:
            session_id: 会话 ID
            usage: 使用量数据，应包含以下字段：
                - prompt_tokens: 输入 token 数
                - completion_tokens: 输出 token 数
                - total_tokens: 总 token 数
            mode: 模式（'chatbot' 或 'classification'，默认 'chatbot'）

        Returns:
            int: 受影响的行数

        Example:
            >>> provider = LLMDatasetProvider()
            >>> usage = {
            ...     'prompt_tokens': 100,
            ...     'completion_tokens': 50,
            ...     'total_tokens': 150
            ... }
            >>> provider.save_usage(
            ...     session_id='session-123',
            ...     usage=usage,
            ...     mode='chatbot'
            ... )
        """
        if not session_id or not usage:
            logger.warning("session_id 或 usage 为空，跳过保存")
            return 0

        try:
            # 适配 LWBaseDataProvider.upsert_session_tokens_usage 的参数格式
            usage_data = {
                'input_tokens': usage.get('prompt_tokens', 0),
                'output_tokens': usage.get('completion_tokens', 0),
                'total_tokens': usage.get('total_tokens', 0),
                'mode': mode
            }

            affected = self.upsert_session_tokens_usage(session_id, usage_data)
            logger.debug(
                f"保存 token 使用记录: session_id={session_id}, "
                f"mode={mode}, affected={affected}"
            )
            return affected

        except Exception as e:
            logger.error(f"保存 token 使用情况失败: {e}", exc_info=True)
            return 0

    def batch_save_usage(self, usage_list: List[Dict[str, Any]]) -> int:
        """批量保存 token 使用情况

        Args:
            usage_list: 使用量数据列表，每个字典应包含：
                - input_tokens: 输入 token 数
                - output_tokens: 输出 token 数
                - total_tokens: 总 token 数
                - search_count: 搜索次数（可选）
                - result_items_count: 结果项目数（可选）
                - mode: 模式（可选，默认 'classification'）

        Returns:
            int: 插入的行数

        Example:
            >>> provider = LLMDatasetProvider()
            >>> usage_list = [
            ...     {
            ...         'input_tokens': 100,
            ...         'output_tokens': 50,
            ...         'total_tokens': 150,
            ...         'mode': 'classification'
            ...     }
            ... ]
            >>> provider.batch_save_usage(usage_list)
        """
        if not usage_list:
            logger.warning("usage_list 为空，跳过保存")
            return 0

        try:
            affected = self.save_tokens_usage(usage_list)
            logger.debug(f"批量保存 token 使用记录: 数量={len(usage_list)}, affected={affected}")
            return affected

        except Exception as e:
            logger.error(f"批量保存 token 使用情况失败: {e}", exc_info=True)
            return 0

    # ==================== 截图查询 ====================

    def query_screenshots(
        self,
        start_time: str,
        end_time: str,
        capture_reason: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查询截图记录

        Args:
            start_time: 开始时间（ISO 格式）
            end_time: 结束时间（ISO 格式）
            capture_reason: 截图原因过滤（可选，如 'active', 'idle', 'periodic'）

        Returns:
            List[Dict]: 截图列表，按时间升序排序

        Example:
            >>> provider = LLMDatasetProvider()
            >>> screenshots = provider.query_screenshots(
            ...     start_time="2026-04-19 09:00:00",
            ...     end_time="2026-04-19 10:00:00",
            ...     capture_reason="active"
            ... )
        """
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()

                sql = """
                SELECT id, captured_at, file_path, window_app, window_title, capture_reason
                FROM screen_captures
                WHERE captured_at >= ? AND captured_at <= ?
                """
                params = [start_time, end_time]

                if capture_reason is not None:
                    sql += " AND capture_reason = ?"
                    params.append(capture_reason)

                sql += " ORDER BY captured_at ASC"

                cursor.execute(sql, params)

                columns = [description[0] for description in cursor.description]
                rows = cursor.fetchall()

                screenshots = [dict(zip(columns, row)) for row in rows]

                logger.debug(
                    f"查询截图: {start_time} -> {end_time}, "
                    f"capture_reason={capture_reason}, 结果数量={len(screenshots)}"
                )

                return screenshots

        except Exception as e:
            logger.error(f"查询截图失败: {e}", exc_info=True)
            return []


# 全局单例
llm_dataset_provider = LazySingleton(LLMDatasetProvider)
