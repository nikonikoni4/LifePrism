"""定时任务服务

提供基于 APScheduler 的定时任务调度功能，支持间隔执行和 Cron 表达式。
"""

from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
from lifeprism.config.settings_manager import settings
from lifeprism.server.services.diary_service import generate_diary_ai_summary
from lifeprism.utils import get_logger
from datetime import datetime
logger = get_logger(__name__)

def _generate_diary_ai_summary():
    try:
        generate_diary_ai_summary(datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        logger.error(f"生成日记总结失败: {e}")

class ScheduleService:
    """定时任务调度服务（单例）

    使用 APScheduler 提供定时任务调度功能，支持：
    - 间隔执行（每隔 N 秒/分钟）
    - Cron 表达式调度
    - 任务生命周期管理
    """
    _SYSTEM_CRON_JOB_TIME = "0 10 * * *"
    def __init__(self) -> None:
        """初始化调度器"""
        self._scheduler: Optional[AsyncIOScheduler] = None
        logger.info("ScheduleService 初始化")
        if settings.auto_diary_summary:
            self.add_cron_job(_generate_diary_ai_summary, self._SYSTEM_CRON_JOB_TIME)
    def start(self) -> None:
        """启动调度器

        应在应用启动时调用（如 FastAPI 的 lifespan 事件）
        """
        if self._scheduler is not None:
            logger.warning("调度器已经启动，跳过重复启动")
            return

        self._scheduler = AsyncIOScheduler()
        self._scheduler.start()
        logger.info("定时任务调度器已启动")

    def shutdown(self) -> None:
        """关闭调度器

        应在应用关闭时调用（如 FastAPI 的 lifespan 事件）
        """
        if self._scheduler is None:
            logger.warning("调度器未启动，无需关闭")
            return

        self._scheduler.shutdown(wait=True)
        self._scheduler = None
        logger.info("定时任务调度器已关闭")

    def add_interval_job(  # 间隔执行任务
        self,
        func: Callable,
        seconds: Optional[int] = None,
        minutes: Optional[int] = None,
        hours: Optional[int] = None,
        job_id: Optional[str] = None,
    ) -> str:
        """添加间隔执行任务

        Args:
            func: 要执行的函数
            seconds: 间隔秒数
            minutes: 间隔分钟数
            hours: 间隔小时数
            job_id: 任务 ID（可选，用于后续移除任务）

        Returns:
            任务 ID

        Raises:
            RuntimeError: 调度器未启动
            ValueError: 未指定任何时间间隔
        """
        if self._scheduler is None:
            raise RuntimeError("调度器未启动，请先调用 start()")

        if seconds is None and minutes is None and hours is None:
            raise ValueError("必须指定至少一个时间间隔参数（seconds/minutes/hours）")

        trigger = IntervalTrigger(seconds=seconds, minutes=minutes, hours=hours)
        job: Job = self._scheduler.add_job(func, trigger, id=job_id)

        logger.info(
            f"添加间隔任务: {func.__name__}, "
            f"间隔={seconds}s/{minutes}m/{hours}h, "
            f"job_id={job.id}"
        )
        return job.id

    def add_cron_job(  # 定时任务
        self,
        func: Callable,
        cron_expr: str,
        job_id: Optional[str] = None,
    ) -> str:
        """添加 Cron 表达式任务

        Args:
            func: 要执行的函数
            cron_expr: Cron 表达式（如 "0 0 * * *" 表示每天零点）
            job_id: 任务 ID（可选，用于后续移除任务）

        Returns:
            任务 ID

        Raises:
            RuntimeError: 调度器未启动
        """
        if self._scheduler is None:
            raise RuntimeError("调度器未启动，请先调用 start()")

        trigger = CronTrigger.from_crontab(cron_expr)
        job: Job = self._scheduler.add_job(func, trigger, id=job_id)

        logger.info(f"添加 Cron 任务: {func.__name__}, cron={cron_expr}, job_id={job.id}")
        return job.id

    def remove_job(self, job_id: str) -> None:
        """移除指定任务

        Args:
            job_id: 任务 ID

        Raises:
            RuntimeError: 调度器未启动
        """
        if self._scheduler is None:
            raise RuntimeError("调度器未启动，请先调用 start()")

        self._scheduler.remove_job(job_id)
        logger.info(f"移除任务: job_id={job_id}")

    def get_jobs(self) -> list:
        """获取所有任务列表

        Returns:
            任务列表

        Raises:
            RuntimeError: 调度器未启动
        """
        if self._scheduler is None:
            raise RuntimeError("调度器未启动，请先调用 start()")

        return self._scheduler.get_jobs()


# 单例实例
schedule_service = ScheduleService()
