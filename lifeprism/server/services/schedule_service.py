"""定时任务服务

提供基于 APScheduler 的定时任务调度功能，支持间隔执行和 Cron 表达式。
"""

import asyncio
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
from lifeprism.config.settings_manager import settings
from lifeprism.server.services.diary_service import generate_diary_ai_summary
from lifeprism.utils import get_logger
from datetime import datetime, timedelta
from lifeprism.llm.function.agent_schedule_job import update_memory,process_session_message
logger = get_logger(__name__)

# ===================== 测试配置宏 =====================
TEST_CRON_ENABLED = False      # 是否测试定时任务
TEST_INTERVAL_ENABLED = True   # 是否测试间隔任务
TEST_INTERVAL_MINUTES = 1      # 间隔任务测试参数（分钟）
TEST_CRON_AFTER_MINUTES = 1    # 定时任务测试参数（启动后N分钟触发）
# ====================================================

def _update_memory():
    try:
        generate_diary_ai_summary(datetime.now().strftime("%Y-%m-%d"))
        update_memory(datetime.now().strftime("%Y-%m-%d"))
    except Exception as e:
        logger.error(f"生成日记总结或更新记忆失败: {e}")
def _process_session_message():
    try:
        process_session_message()
    except Exception as e:
        logger.error(f"提取历史对话消息信息失败: {e}")
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
        
        # 注册系统任务（在 start() 后自动添加）
        self._system_jobs = []
        
        # 根据配置决定是否注册任务
        if settings.auto_summary_session:
            self._system_jobs.append({
                "func": _process_session_message,
                "trigger": "interval",
                "kwargs": {"hours": 4},
                "job_id": "process_session_message"
            })
        
        if settings.auto_update_memory:
            self._system_jobs.append({
                "func": _update_memory,
                "trigger": "cron",
                "kwargs": {"cron_expr": "0 10 * * *"},
                "job_id": "update_memory"
            })

        
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
        
        # 添加系统任务
        self._add_system_jobs()

    def _add_system_jobs(self) -> None:
        """添加系统预设任务，对于 Cron 任务，如果已过触发时间则异步执行一次"""
        now = datetime.now()
        for job_config in self._system_jobs:
            try:
                if job_config["trigger"] == "interval":
                    self.add_interval_job(job_config["func"], job_id=job_config["job_id"], **job_config["kwargs"])
                elif job_config["trigger"] == "cron":
                    self.add_cron_job(job_config["func"], job_config["kwargs"]["cron_expr"], job_id=job_config["job_id"])
                    # 检查是否已过今天的触发时间，如果是则异步执行一次
                    cron_expr = job_config["kwargs"]["cron_expr"]
                    parts = cron_expr.split()
                    target_hour, target_minute = int(parts[1]), int(parts[0])
                    if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                        logger.info(f"已过今日 {target_hour}:{target_minute:02d}，异步执行一次 {job_config['job_id']}")
                        import asyncio
                        asyncio.get_event_loop().create_task(self._run_job_async(job_config["func"]))
            except Exception as e:
                logger.error(f"添加系统任务 {job_config['job_id']} 失败: {e}")

    async def _run_job_async(self, func: Callable) -> None:
        """异步执行任务（在线程池中运行同步函数）"""
        import asyncio
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, func)

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

        # 构建 IntervalTrigger 参数，只传递非 None 的值
        interval_kwargs = {}
        if seconds is not None:
            interval_kwargs['seconds'] = seconds
        if minutes is not None:
            interval_kwargs['minutes'] = minutes
        if hours is not None:
            interval_kwargs['hours'] = hours
        
        trigger = IntervalTrigger(**interval_kwargs)
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


if __name__ == "__main__":
    from lifeprism.llm.agent.loop import agent_loop

    async def test_schedule():
        # 先启动 agent_loop
        loop_task = asyncio.create_task(agent_loop.loop())
        
        # 等待 agent_loop 初始化
        await asyncio.sleep(2)
        
        service = ScheduleService()
        service.start()
        
        execution_count_cron = 0
        execution_count_interval = 0
        
        def test_cron_job():
            nonlocal execution_count_cron
            execution_count_cron += 1
            logger.info(f"[测试] 定时任务执行次数: {execution_count_cron}")
        
        def test_interval_job():
            nonlocal execution_count_interval
            execution_count_interval += 1
            logger.info(f"[测试] 间隔任务执行次数: {execution_count_interval}")
        
        # 测试定时任务（启动后 N 分钟触发）
        if TEST_CRON_ENABLED:
            target_time = datetime.now() + timedelta(minutes=TEST_CRON_AFTER_MINUTES)
            cron_expr = f"{target_time.minute} {target_time.hour} * * *"
            logger.info(f"[测试] 添加定时任务，将在 {target_time.strftime('%H:%M')} 执行")
            service.add_cron_job(test_cron_job, cron_expr, job_id="test_cron")
        
        # 测试间隔任务
        if TEST_INTERVAL_ENABLED:
            logger.info(f"[测试] 添加间隔任务，每 {TEST_INTERVAL_MINUTES} 分钟执行一次")
            service.add_interval_job(test_interval_job, minutes=TEST_INTERVAL_MINUTES, job_id="test_interval")
        
        logger.info("[测试] 调度器运行中，按 Ctrl+C 停止...")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("[测试] 收到停止信号")
        finally:
            service.shutdown()
            loop_task.cancel()
            logger.info(f"[测试] 定时任务执行次数: {execution_count_cron}")
            logger.info(f"[测试] 间隔任务执行次数: {execution_count_interval}")

    asyncio.run(test_schedule())
