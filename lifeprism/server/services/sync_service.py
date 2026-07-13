"""
数据同步服务
负责从 ActivityWatch 同步数据并分类
"""

import asyncio
import time
from datetime import datetime, timedelta, timezone

from lifeprism.config import settings
from lifeprism.llm.function import screenshot_analysis, screenshot_behavior_summary
from lifeprism.repository import QueryOptions, todo_repository
from lifeprism.server.errors.error_codes import DEMO_MODE_NOT_SUPPORTED
from lifeprism.server.schemas.timeline_schemas import BehaviorAnalysisItem
from lifeprism.server.services.data_processing_service import DataProcessingService
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import ValidationError

logger = get_logger(__name__)


async def screen_behavior_anlysis(start_time: str, end_time: str) -> list[BehaviorAnalysisItem]:
    """
    分析规定时间内的屏幕截图,返回分析结果列表
    args :
        start_time : 开始时间，支持格式：
                    - "YYYY-MM-DD HH:MM:SS" (标准格式)
                    - "YYYY-MM-DDTHH:MM:SS" (ISO 8601格式)
        end_time : 结束时间，格式同上
    return

    """
    # 0. 统一转为 UTC ISO 8601 格式（遵循 time-handling-rules.md）
    # 有时区标识 → 已是 UTC，直接 .isoformat()
    # 无时区标识 → 视为本地时间（LLM 工具输入路径），用 local_to_utc_iso 转 UTC
    from lifeprism.utils.time_utils import local_to_utc_iso

    def _to_utc_iso(time_str: str) -> str:
        dt = datetime.fromisoformat(time_str)
        if dt.tzinfo is not None:
            return dt.isoformat()
        return local_to_utc_iso(time_str)

    start_time = _to_utc_iso(start_time)
    end_time = _to_utc_iso(end_time)

    # 1. 截断 start_time 到最早可用时间
    screenshot_retention_days = settings.get("screenshot_retention_days", 3)
    requested_start_time = datetime.fromisoformat(start_time)
    if requested_start_time.tzinfo is None:
        requested_start_time = requested_start_time.replace(tzinfo=timezone.utc)
    earliest_available_time = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(
        days=screenshot_retention_days
    )
    start_time = (
        max(requested_start_time, earliest_available_time).replace(microsecond=0).isoformat()
    )

    # 2.  查询todolist
    todolist, _ = todo_repository.query_todos(
        QueryOptions()
        .with_date_range(start_time[:10], end_time[:10])
        .with_order("date", desc=False)
    )
    if todolist:
        # 提取每个 todo 的 content 字段并格式化
        todo_contents = [f"- {todo.get('content', '')}" for todo in todolist]
        todolist = f"""
        ## 计划列表
        {chr(10).join(todo_contents)}
        """
    # 2. 分析屏幕截图
    analysis_results_list = await screenshot_analysis(start_time, end_time, todolist)

    # 3. 对分析结果进行摘要分析
    summary_results = await screenshot_behavior_summary(analysis_results_list, todolist)

    return summary_results


class SyncService:
    """
    数据同步服务

    整合现有业务逻辑，实现从 ActivityWatch 同步数据的完整流程
    """

    # 类级别的锁，确保所有实例共享同一个锁
    _sync_lock = asyncio.Lock()

    def __init__(self):
        self.data_processor = DataProcessingService()

    async def incremental_sync(self, auto_classify: bool = True) -> dict:
        """
        增量同步 ActivityWatch 数据 /  lifeprism windows_events（从数据库最新时间同步到现在）

        Args:
            auto_classify: 是否自动分类新应用

        Returns:
            Dict: 同步结果
        """
        # 演示模式守卫：非 full 模式下禁用数据同步
        if settings.run_mode != "full":
            logger.warning(
                "[incremental_sync] 当前运行模式为 %s，不支持数据同步", settings.run_mode
            )
            raise ValidationError(
                message="演示模式不支持数据同步",
                code=DEMO_MODE_NOT_SUPPORTED,
            )

        # 尝试获取锁，如果已被占用则立即返回
        if self._sync_lock.locked():
            logger.warning("[incremental_sync] 同步正在进行中，跳过本次请求")
            return {
                "status": "skipped",
                "synced_events": 0,
                "new_apps_classified": 0,
                "duration": 0,
                "message": "同步正在进行中，请稍后再试",
                "details": {},
            }

        async with self._sync_lock:
            logger.info("[incremental_sync] 获取同步锁，开始执行")
            start_time = time.time()

            # 使用 DataProcessingService 处理增量同步
            result = await self.data_processor.process_activitywatch_data(
                auto_classify=auto_classify
            )

            if settings.monitor_type == "lifeprism" and settings.get("screenshot_monitor", False):
                # 查询 behavior_analysis 表中最后一条记录的 end_time
                from lifeprism.repository import QueryOptions, behavior_analysis_repository

                # 获取最后一条记录（按 end_time 降序）
                options = QueryOptions().with_order("end_time", desc=True).with_limit(1)
                last_records, _ = behavior_analysis_repository.query_behaviors(options)

                if last_records:
                    # 使用最后一条记录的 end_time 作为起始时间
                    analysis_start_time = last_records[0]["end_time"]
                else:
                    # 如果表为空，使用当前时间往前推 1 天
                    analysis_start_time = (
                        datetime.now(timezone.utc) - timedelta(days=1)
                    ).isoformat()

                # 使用当前时间作为结束时间
                analysis_end_time = datetime.now(timezone.utc).isoformat()

                # 后台执行截图分析，不阻塞 sync 响应
                asyncio.create_task(screen_behavior_anlysis(analysis_start_time, analysis_end_time))

            duration = time.time() - start_time
            logger.info("[incremental_sync] 同步完成，耗时 %.2fs", duration)

            return {
                "status": "success",
                "synced_events": result["saved_events"],
                "new_apps_classified": result["classified_apps"],
                "duration": round(duration, 2),
                "message": "成功同步数据（增量模式）",
                "details": {
                    "sync_mode": result["sync_mode"],
                    "time_range": result["time_range"],
                    "total_events": result["total_events"],
                    "filtered_events": result["filtered_events"],
                    "apps_to_classify": result["apps_to_classify"],
                    "unclassified_events": result["unclassified_events"],
                },
            }

    async def sync_by_time_range(
        self, start_time: str, end_time: str, auto_classify: bool = True
    ) -> dict:
        """
        按时间范围同步 ActivityWatch 数据

        Args:
            start_time: 开始时间，格式: YYYY-MM-DD HH:MM:SS
            end_time: 结束时间，格式: YYYY-MM-DD HH:MM:SS
            auto_classify: 是否自动分类新应用

        Returns:
            Dict: 同步结果
        """
        # 演示模式守卫：非 full 模式下禁用数据同步
        if settings.run_mode != "full":
            logger.warning(
                "[sync_by_time_range] 当前运行模式为 %s，不支持数据同步", settings.run_mode
            )
            raise ValidationError(
                message="演示模式不支持数据同步",
                code=DEMO_MODE_NOT_SUPPORTED,
            )

        # 尝试获取锁，如果已被占用则立即返回
        if self._sync_lock.locked():
            logger.warning("[sync_by_time_range] 同步正在进行中，跳过本次请求")
            return {
                "status": "skipped",
                "synced_events": 0,
                "new_apps_classified": 0,
                "duration": 0,
                "message": "同步正在进行中，请稍后再试",
                "details": {},
            }

        async with self._sync_lock:
            logger.info("[sync_by_time_range] 获取同步锁，开始执行 (%s ~ %s)", start_time, end_time)
            sync_start = time.time()

            # 解析时间字符串
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")

            # 使用 DataProcessingService 处理数据
            result = await self.data_processor.process_activitywatch_data_by_time_range(
                start_time=start_dt, end_time=end_dt, auto_classify=auto_classify
            )
            if settings.monitor_type == "lifeprism" and settings.get("screenshot_monitor", False):
                # time_range 格式: "2026-04-19 11:00:00 ~ 2026-04-19 11:15:00"
                time_parts = result["time_range"].split(" ~ ")
                # 后台执行截图分析，不阻塞 sync 响应
                asyncio.create_task(screen_behavior_anlysis(time_parts[0], time_parts[1]))

            duration = time.time() - sync_start
            logger.info("[sync_by_time_range] 同步完成，耗时 %.2fs", duration)

            return {
                "status": "success",
                "synced_events": result["saved_events"],
                "new_apps_classified": result["classified_apps"],
                "duration": round(duration, 2),
                "message": "成功同步时间范围数据",
                "details": {
                    "sync_mode": "time_range",
                    "time_range": result["time_range"],
                    "total_events": result["total_events"],
                    "filtered_events": result["filtered_events"],
                    "apps_to_classify": result["apps_to_classify"],
                    "unclassified_events": result["unclassified_events"],
                },
            }


if __name__ == "__main__":
    import asyncio

    from lifeprism.llm.agent.loop import agent_loop

    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        # logger.info("[STARTUP] AgentLoop started") # logger is not imported in this file
        response = await screen_behavior_anlysis("2026-04-19 11:00:00", "2026-04-19 11:15:00")
        print(response)
        loop_task.cancel()  # Cancel the loop task when done to exit cleanly

    asyncio.run(main())
