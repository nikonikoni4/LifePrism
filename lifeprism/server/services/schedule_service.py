"""定时任务服务

提供基于 APScheduler 的定时任务调度功能，支持间隔执行和 Cron 表达式。
"""

import asyncio
import json
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz
from apscheduler.job import Job
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from lifeprism.config import get_user_timezone
from lifeprism.config.settings_manager import settings
from lifeprism.llm.function.agent_schedule_job import dreaming, process_session_message
from lifeprism.server.services.backup_service import backup_service
from lifeprism.server.services.diary_service import generate_diary_ai_summary
from lifeprism.server.services.global_task_state import TaskState, global_task_state
from lifeprism.server.services.sync_service import SyncService
from lifeprism.utils import get_logger
from lifeprism.utils.time_utils import get_local_today

logger = get_logger(__name__)

# ===================== 测试配置 =====================
TEST_MODE = False  # 是否启用测试模式
TEST_INTERVAL_MINUTES = 1  # 间隔任务测试参数（覆盖原4h）
TEST_CRON_AFTER_MINUTES = 1  # 定时任务测试参数（启动后N分钟触发，覆盖原10:00）
# ====================================================


async def _dreaming():
    # 每天本地 10:00 执行时，获取昨天的完整数据（昨天04:00 ~ 今天04:00）
    # 基于本地时区计算"昨天"：用户在本地午夜前后看到的日期与预期一致。
    yesterday = (get_local_today() - timedelta(days=1)).isoformat()
    logger.info("[dreaming] 开始执行, 目标日期: %s", yesterday)

    # 全局任务状态互斥：获取 LOCAL_TASK 状态（5 分钟超时）
    # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 5
    # 通过 asyncio.to_thread 包裹避免阻塞主事件循环
    acquired = await asyncio.to_thread(global_task_state.try_acquire, TaskState.LOCAL_TASK, 300.0)
    if not acquired:
        # 超时降级：跳过 incremental_sync（依赖云端数据，CLOUD_SYNC 期间 Pull 可能不一致）
        # 但 dreaming 和 backup_documents 仍执行：
        # - 文件同步：下次 sync_once 时 Pre-sync 阶段会重新计算 hash，
        #   矩阵判定为 PUSH，推送完整 content，云端自动纠正半写入状态
        # - 数据库同步：last_sync_time 记录为 sync 开始时间（sync_cutoff_time），
        #   dreaming 写入的数据 updated_at > sync_cutoff_time，下次 sync 会被 Push
        # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 5 前提
        logger.warning(
            "[dreaming] 等待 CLOUD_SYNC 释放超时（5min），跳过 incremental_sync，仍执行 dreaming + backup"
        )

    try:
        # 1. 先执行增量同步，确保数据已分类和总结
        # 仅在成功获取 LOCAL_TASK 时执行（依赖云端数据，CLOUD_SYNC 期间 Pull 可能不一致）
        if acquired:
            try:
                sync_service = SyncService()
                logger.info("[dreaming] 开始增量同步数据")
                sync_result = await sync_service.incremental_sync(auto_classify=True)
                logger.info("[dreaming] 增量同步完成: %s", sync_result.get("message", ""))
            except Exception as e:
                logger.error("[dreaming] 增量同步失败: error=%s", e)
                # 同步失败不应阻止后续流程，继续执行

        # 2. dreaming（写 behavior.md / recent_state.md / user.md）
        # 超时降级时仍执行：文件同步可自我纠正（见上方注释）
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

        # 3. backup_documents（在 dreaming 之后，捕获最新写入的文件）
        # 超时降级时仍执行：备份本地数据，不依赖云端
        # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 2
        try:
            await backup_service.backup_documents()
        except Exception as e:
            logger.error("[dreaming] 文档备份失败: error=%s", e)
    finally:
        if acquired:
            global_task_state.release()


async def _process_session_message():
    # 全局任务状态互斥：获取 LOCAL_TASK 状态（5 分钟超时）
    # 4h 任务写 behavior.md（参与同步），需与 sync_once 互斥
    # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 3
    acquired = await asyncio.to_thread(global_task_state.try_acquire, TaskState.LOCAL_TASK, 300.0)
    if not acquired:
        logger.warning("[process_session_message] 等待 CLOUD_SYNC 释放超时（5min），跳过本次")
        return

    try:
        await process_session_message()
    except Exception as e:
        logger.error("提取历史对话消息信息失败: error=%s", e)
    finally:
        global_task_state.release()


class ScheduleService:
    """定时任务调度服务（单例）

    使用 APScheduler 提供定时任务调度功能，支持：
    - 间隔执行（每隔 N 秒/分钟）
    - Cron 表达式调度
    - 任务生命周期管理
    """

    _SYSTEM_CRON_JOB_TIME = "0 10 * * *"  # 本地 10:00
    _STATE_FILE_NAME = ".schedule_state.json"

    def __init__(self) -> None:
        """初始化调度器"""
        self._scheduler: AsyncIOScheduler | None = None
        self._state_file_path = Path(settings.lifeprism_data_path) / self._STATE_FILE_NAME
        logger.info("ScheduleService 初始化")

        # 注册系统任务（在 start() 后自动添加）
        self._system_jobs = []

        # 根据配置决定是否注册任务
        if settings.auto_summary_session:
            interval_minutes = TEST_INTERVAL_MINUTES if TEST_MODE else None
            interval_hours = None if TEST_MODE else 4
            self._system_jobs.append(
                {
                    "func": _process_session_message,
                    "trigger": "interval",
                    "kwargs": {"hours": interval_hours, "minutes": interval_minutes},
                    "job_id": "process_session_message",
                }
            )

        if settings.auto_update_memory or settings.auto_diary_summary:
            if TEST_MODE:
                # TEST_MODE 下基于 UTC 时间生成 cron 表达式（与 CronTrigger 的 UTC 时区一致）
                target_time = datetime.now(timezone.utc) + timedelta(
                    minutes=TEST_CRON_AFTER_MINUTES
                )
                cron_expr = f"{target_time.minute} {target_time.hour} * * *"
            else:
                cron_expr = "0 10 * * *"  # 本地 10:00
            self._system_jobs.append(
                {
                    "func": _dreaming,
                    "trigger": "cron",
                    "kwargs": {"cron_expr": cron_expr},
                    "job_id": "update_memory",
                }
            )

        # 注册备份任务（仅 full 模式注册，云端 agent_only/web_demo 不备份）
        # 数据库备份：每 8 小时（本地 00/08/16 点），保留 3 份
        # 设计依据：ADR docs/adr/2026-07-17-data-backup-strategy.md
        # 备份范围与同步范围解耦：ADR docs/adr/2026-07-17-backup-sync-decoupled-scope.md
        # 云端 agent_only 不备份：ADR docs/adr/2026-07-17-data-backup-strategy.md（决策 9）
        #
        # 文档备份 backup_documents 已移除独立 cron 注册，改为 _dreaming() 的子步骤执行
        # （位于 dreaming 之后捕获最新数据），与 dreaming 共享 skip_compensation=False 补执行机制
        # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 2
        #
        # 数据库备份不参与全局任务状态互斥（SQLite Online Backup API 不阻塞读写）
        # 参考 ADR docs/adr/2026-07-25-global-task-state.md 决策 6
        #
        # 注册时的 run_mode 守卫与 BackupService._check_run_mode() 形成双重保障：
        # - 注册时守卫：避免在非 full 模式下注册无用任务（节省调度器资源）
        # - 运行时守卫：防止 run_mode 在运行期切换后旧任务仍执行
        #
        # skip_compensation=True：数据库备份是周期性任务（每 8 小时），
        # 不是"每天一次"的任务，无需启动补偿。系统重启后下一个 cron 周期会自然触发，
        # 避免重启时立即执行备份造成 I/O 压力（也避免测试环境中后台备份干扰时序测试）。
        if settings.run_mode == "full":
            self._system_jobs.extend(
                [
                    {
                        "func": backup_service.backup_database,
                        "trigger": "cron",
                        "kwargs": {"cron_expr": "0 0,8,16 * * *"},  # 每天本地 00/08/16 点
                        "job_id": "backup_database",
                        "skip_compensation": True,
                    },
                ]
            )

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
            with open(self._state_file_path, encoding="utf-8") as f:
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
            with open(self._state_file_path, "w", encoding="utf-8") as f:
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
        today = get_local_today().isoformat()
        state = self._load_cron_state()
        last_execution = state.get(job_id)

        if last_execution == today:
            logger.debug("任务 %s 今天已执行过（%s），跳过", job_id, today)
            return False

        return True

    def start(self) -> None:
        """启动调度器

        应在应用启动时调用（如 FastAPI 的 lifespan 事件）

        当 run_mode != "full" 时，跳过系统任务注册（防御性守卫）。
        这些任务依赖 Monitor 采集的数据，在 web_demo / agent_only 模式下无意义。
        """
        if self._scheduler is not None:
            logger.warning("调度器已经启动，跳过重复启动")
            return

        if settings.run_mode != "full":
            logger.info(
                "run_mode=%s，跳过定时任务注册（仅 full 模式启用）",
                settings.run_mode,
            )
            return

        local_tz = pytz.timezone(get_user_timezone())
        self._scheduler = AsyncIOScheduler(timezone=local_tz)
        self._scheduler.start()
        logger.info("定时任务调度器已启动")

        # 添加系统任务
        self._add_system_jobs()

    def _add_system_jobs(self) -> None:
        """添加系统预设任务，对于 Cron 任务，如果已过触发时间且今天未执行则异步执行一次

        skip_compensation 标志：
        - 周期性任务（如备份）设置 ``skip_compensation=True`` 跳过启动补偿
        - 原因：周期性任务在下一个 cron 周期会自然触发，无需启动时立即执行
        - 避免系统重启时立即执行备份造成 I/O 压力
        """
        # 使用本地时间判断是否过触发时间（Cron 表达式基于本地时区）
        local_tz = pytz.timezone(get_user_timezone())
        now = datetime.now(local_tz)
        for job_config in self._system_jobs:
            try:
                if job_config["trigger"] == "interval":
                    self.add_interval_job(
                        job_config["func"], job_id=job_config["job_id"], **job_config["kwargs"]
                    )
                elif job_config["trigger"] == "cron":
                    job_id = job_config["job_id"]
                    self.add_cron_job(
                        job_config["func"], job_config["kwargs"]["cron_expr"], job_id=job_id
                    )

                    # skip_compensation 检查：周期性任务（如备份）跳过启动补偿
                    if job_config.get("skip_compensation", False):
                        logger.debug(
                            "任务 %s 配置 skip_compensation=True，跳过启动补偿",
                            job_id,
                        )
                        continue

                    # 启动补偿检查：仅对单值小时 cron 表达式生效
                    # 多值小时 cron（如 "0 0,8,16 * * *"）跳过启动补偿，
                    # 因为无法解析为单一触发时间点；cron 任务本身已通过 add_cron_job 注册，
                    # 将按计划执行，启动补偿不影响后续定时触发。
                    try:
                        cron_expr = job_config["kwargs"]["cron_expr"]
                        parts = cron_expr.split()
                        target_hour, target_minute = int(parts[1]), int(parts[0])

                        if now.hour > target_hour or (
                            now.hour == target_hour and now.minute >= target_minute
                        ):
                            if self._should_execute_cron_today(job_id):
                                logger.info(
                                    "已过今日 %s:%02d，异步执行一次 %s",
                                    target_hour,
                                    target_minute,
                                    job_id,
                                )
                                asyncio.get_event_loop().create_task(
                                    self._execute_cron_with_state(job_config["func"], job_id)
                                )
                            else:
                                logger.debug("任务 %s 今天已执行过，跳过补偿执行", job_id)
                    except ValueError:
                        # 多值 cron 表达式（如 "0 0,8,16 * * *"）无法解析为单值小时
                        # 跳过启动补偿，cron 任务将按计划执行
                        logger.debug(
                            "cron 表达式不支持启动补偿（多值字段），跳过 job_id=%s, cron_expr=%s",
                            job_id,
                            job_config["kwargs"]["cron_expr"],
                        )
            except Exception as e:
                logger.error("添加系统任务 %s 失败: error=%s", job_config["job_id"], e)

    async def _execute_cron_with_state(self, func: Callable, job_id: str) -> None:
        """执行 Cron 任务并记录状态

        Args:
            func: 要执行的函数
            job_id: 任务 ID
        """
        try:
            await func()
            today = get_local_today().isoformat()
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
        seconds: int | None = None,
        minutes: int | None = None,
        hours: int | None = None,
        job_id: str | None = None,
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
            interval_kwargs["seconds"] = seconds
        if minutes is not None:
            interval_kwargs["minutes"] = minutes
        if hours is not None:
            interval_kwargs["hours"] = hours

        local_tz = pytz.timezone(get_user_timezone())
        trigger = IntervalTrigger(**interval_kwargs, timezone=local_tz)
        job: Job = self._scheduler.add_job(func, trigger, id=job_id)

        logger.info(
            "添加间隔任务: %s, 间隔=%ss/%sm/%sh, job_id=%s",
            func.__name__,
            seconds,
            minutes,
            hours,
            job.id,
        )
        return job.id

    def add_cron_job(  # 定时任务
        self,
        func: Callable,
        cron_expr: str,
        job_id: str | None = None,
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

        local_tz = pytz.timezone(get_user_timezone())
        trigger = CronTrigger.from_crontab(cron_expr, timezone=local_tz)

        # 包装原函数，执行后记录状态
        async def wrapped_func():
            await func()
            if job_id:
                today = get_local_today().isoformat()
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
