"""定时任务服务

提供基于 APScheduler 的定时任务调度功能，支持间隔执行和 Cron 表达式。
"""

import asyncio
import json
from pathlib import Path
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.job import Job
from lifeprism.config.settings_manager import settings
from lifeprism.server.services.diary_service import generate_diary_ai_summary
from lifeprism.utils import get_logger
from datetime import datetime, timedelta
from lifeprism.llm.function.agent_schedule_job import dreaming,process_session_message
from lifeprism.server.services.sync_service import SyncService
logger = get_logger(__name__)

# ===================== 测试配置 =====================
TEST_MODE = False                    # 是否启用测试模式
TEST_INTERVAL_MINUTES = 1           # 间隔任务测试参数（覆盖原4h）
TEST_CRON_AFTER_MINUTES = 1         # 定时任务测试参数（启动后N分钟触发，覆盖原10:00）
# ====================================================

async def _dreaming():
    # 每天10点执行时，获取昨天的完整数据（昨天04:00 ~ 今天04:00）
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logger.info("[dreaming] 开始执行, 目标日期: %s", yesterday)

    # 先执行增量同步，确保数据已分类和总结
    try:
        sync_service = SyncService()
        logger.info("[dreaming] 开始增量同步数据")
        sync_result = await sync_service.incremental_sync(auto_classify=True)
        logger.info("[dreaming] 增量同步完成: %s", sync_result.get('message', ''))
    except Exception as e:
        logger.error("[dreaming] 增量同步失败: error=%s", e)
        # 同步失败不应阻止后续流程，继续执行

    if settings.auto_diary_summary:
        try:
            await generate_diary_ai_summary(yesterday)
        except Exception as e:
            logger.error("生成日记总结失败: error=%s", e)
    if settings.auto_update_memory:
        try:
            await dreaming(yesterday)
        except Exception as e:
            logger.error("更新记忆失败: error=%s", e)
async def _process_session_message():
    try:
        await process_session_message()
    except Exception as e:
        logger.error("提取历史对话消息信息失败: error=%s", e)
class ScheduleService:
    """定时任务调度服务（单例）

    使用 APScheduler 提供定时任务调度功能，支持：
    - 间隔执行（每隔 N 秒/分钟）
    - Cron 表达式调度
    - 任务生命周期管理
    """
    _SYSTEM_CRON_JOB_TIME = "0 10 * * *"
    _STATE_FILE_NAME = ".schedule_state.json"

    def __init__(self) -> None:
        """初始化调度器"""
        self._scheduler: Optional[AsyncIOScheduler] = None
        self._state_file_path = Path(settings.lifeprism_data_path) / self._STATE_FILE_NAME
        logger.info("ScheduleService 初始化")

        # 注册系统任务（在 start() 后自动添加）
        self._system_jobs = []

        # 根据配置决定是否注册任务
        if settings.auto_summary_session:
            interval_minutes = TEST_INTERVAL_MINUTES if TEST_MODE else None
            interval_hours = None if TEST_MODE else 4
            self._system_jobs.append({
                "func": _process_session_message,
                "trigger": "interval",
                "kwargs": {"hours": interval_hours, "minutes": interval_minutes},
                "job_id": "process_session_message"
            })

        if settings.auto_update_memory or settings.auto_diary_summary:
            if TEST_MODE:
                target_time = datetime.now() + timedelta(minutes=TEST_CRON_AFTER_MINUTES)
                cron_expr = f"{target_time.minute} {target_time.hour} * * *"
            else:
                cron_expr = "0 10 * * *"
            self._system_jobs.append({
                "func": _dreaming,
                "trigger": "cron",
                "kwargs": {"cron_expr": cron_expr},
                "job_id": "update_memory"
            })

    def _load_cron_state(self) -> dict:
        """加载 Cron 任务执行状态

        Returns:
            dict: {job_id: last_execution_date}

        Note:
            当前使用简单的 dict 存储状态。若未来需要管理更多状态字段（如执行次数、
            失败记录、配置参数等），建议重构为类集成模式，参考 lifeprism.llm.prompts.prompt_loader.Prompts
            的设计：

            ```python
            @dataclass
            class CronJobState:
                job_id: str
                last_execution_date: str
                execution_count: int = 0
                last_error: Optional[str] = None

            class ScheduleStates:
                class UpdateMemory:
                    JOB_ID = "update_memory"
                    # 其他配置...

                class ProcessSession:
                    JOB_ID = "process_session_message"
                    # 其他配置...
            ```

            这样可以提供类型安全、IDE 自动补全和集中管理的优势。
        """
        if not self._state_file_path.exists():
            return {}

        try:
            with open(self._state_file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning("加载任务状态文件失败: %s，将使用空状态", e)
            return {}

    def _save_cron_state(self, job_id: str, execution_date: str) -> None:
        """保存 Cron 任务执行状态

        Args:
            job_id: 任务 ID
            execution_date: 执行日期（格式：YYYY-MM-DD）
        """
        try:
            state = self._load_cron_state()
            state[job_id] = execution_date

            self._state_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)

            logger.debug("保存任务状态: %s -> %s", job_id, execution_date)
        except Exception as e:
            logger.error("保存任务状态失败: error=%s", e)

    def _should_execute_cron_today(self, job_id: str) -> bool:
        """判断 Cron 任务今天是否应该执行

        Args:
            job_id: 任务 ID

        Returns:
            bool: True 表示应该执行，False 表示今天已执行过
        """
        today = datetime.now().strftime("%Y-%m-%d")
        state = self._load_cron_state()
        last_execution = state.get(job_id)

        if last_execution == today:
            logger.debug("任务 %s 今天已执行过（%s），跳过", job_id, today)
            return False

        return True

        
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
        """添加系统预设任务，对于 Cron 任务，如果已过触发时间且今天未执行则异步执行一次"""
        now = datetime.now()
        for job_config in self._system_jobs:
            try:
                if job_config["trigger"] == "interval":
                    self.add_interval_job(job_config["func"], job_id=job_config["job_id"], **job_config["kwargs"])
                elif job_config["trigger"] == "cron":
                    job_id = job_config["job_id"]
                    self.add_cron_job(job_config["func"], job_config["kwargs"]["cron_expr"], job_id=job_id)

                    # 检查是否已过今天的触发时间且今天未执行
                    cron_expr = job_config["kwargs"]["cron_expr"]
                    parts = cron_expr.split()
                    target_hour, target_minute = int(parts[1]), int(parts[0])

                    if now.hour > target_hour or (now.hour == target_hour and now.minute >= target_minute):
                        if self._should_execute_cron_today(job_id):
                            logger.info("已过今日 %s:%02d，异步执行一次 %s", target_hour, target_minute, job_id)
                            asyncio.get_event_loop().create_task(self._execute_cron_with_state(job_config["func"], job_id))
                        else:
                            logger.debug("任务 %s 今天已执行过，跳过补偿执行", job_id)
            except Exception as e:
                logger.error("添加系统任务 %s 失败: error=%s", job_config['job_id'], e)

    async def _execute_cron_with_state(self, func: Callable, job_id: str) -> None:
        """执行 Cron 任务并记录状态

        Args:
            func: 要执行的函数
            job_id: 任务 ID
        """
        try:
            await func()
            today = datetime.now().strftime("%Y-%m-%d")
            self._save_cron_state(job_id, today)
        except Exception as e:
            logger.error("执行任务 %s 失败: error=%s", job_id, e)

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
            "添加间隔任务: %s, 间隔=%ss/%sm/%sh, job_id=%s",
            func.__name__, seconds, minutes, hours, job.id
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

        # 包装原函数，执行后记录状态
        async def wrapped_func():
            await func()
            if job_id:
                today = datetime.now().strftime("%Y-%m-%d")
                self._save_cron_state(job_id, today)

        job: Job = self._scheduler.add_job(wrapped_func, trigger, id=job_id)

        logger.info("添加 Cron 任务: %s, cron=%s, job_id=%s", func.__name__, cron_expr, job.id)
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
        logger.info("移除任务: job_id=%s", job_id)

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
        
        logger.info("[测试] 调度器运行中，按 Ctrl+C 停止...")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("[测试] 收到停止信号")
        finally:
            service.shutdown()
            loop_task.cancel()

    asyncio.run(test_schedule())
