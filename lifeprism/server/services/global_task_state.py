"""全局任务状态互斥机制（单例）

职责：协调本地定时任务（10点序列 + 4h 任务）与云端 sync_once 的互斥

设计决策:
- 三态枚举（IDLE / LOCAL_TASK / CLOUD_SYNC）：显式状态，避免 bool 扩展
- threading.Condition 保护：跨线程安全（主 loop + 线程池 + 独立 threading.Thread）
  - 需要 wait/notify 能力（10点任务等待 CLOUD_SYNC 释放），故用 Condition 而非 Lock
  - asyncio.Lock 跨线程不安全，故不用
- LazySingleton 单例：与 backup_service 一致，延迟初始化

互斥规则:
- 本地任务启动前：try_acquire(LOCAL_TASK, timeout=300s)
  - 10点任务超时降级：仅跳过 incremental_sync，dreaming + backup_documents 仍执行
    （依赖全局前提 3、4：文件/数据库同步的自我纠正能力，见 ADR）
  - 4h 任务超时降级：跳过本次（4h 周期短，下次再处理）
- 云端 sync_once 启动前：try_acquire(CLOUD_SYNC, timeout=0)（不等待）
  - 失败放弃本次：调 POST /api/sync/heartbeat event=ping 报告本地在线
- 数据库备份不参与互斥（SQLite Online Backup API 不阻塞读写）

参考:
- ADR: docs/adr/2026-07-25-global-task-state.md（v1.1，含决策 5 超时降级策略与全局前提 3、4）
- Spec: docs/specs/2026-07-17-data-backup-spec.md（v3.0）
"""

import threading
import time
from enum import Enum

from lifeprism.utils import LazySingleton, get_logger

logger = get_logger(__name__)


class TaskState(Enum):
    """全局任务状态枚举

    IDLE: 空闲，任何任务可获取
    LOCAL_TASK: 本地任务在执行（10点序列 / 4h 任务）
    CLOUD_SYNC: 云端 sync_once 在执行
    """

    IDLE = "idle"
    LOCAL_TASK = "local_task"
    CLOUD_SYNC = "cloud_sync"


class GlobalTaskState:
    """全局任务状态（单例）

    用 threading.Condition 保护状态，提供 try_acquire / release 方法。

    线程安全说明:
    - threading.Condition 内部包含一个 Lock，跨线程安全
    - 10点任务在主 loop（asyncio）中，需通过 asyncio.to_thread 包裹 try_acquire
      避免阻塞主事件循环
    - sync_once 在线程池/独立 threading.Thread 中，可直接调用 try_acquire

    使用示例:

        # 4h 任务（_process_session_message）：超时直接跳过本次
        acquired = await asyncio.to_thread(
            global_task_state.try_acquire, TaskState.LOCAL_TASK, 300.0
        )
        if not acquired:
            return  # 超时跳过本次（4h 周期短，下次再处理）
        try:
            # 执行任务...
        finally:
            global_task_state.release()

        # 10点任务（_dreaming）：超时仅跳过 incremental_sync，dreaming + backup 仍执行
        # 参考 ADR 决策 5 超时降级策略
        acquired = await asyncio.to_thread(
            global_task_state.try_acquire, TaskState.LOCAL_TASK, 300.0
        )
        try:
            if acquired:
                # 依赖云端数据的子任务（incremental_sync），仅在获取锁时执行
                pass
            # 不依赖云端的子任务（dreaming / backup_documents）始终执行
            # （文件/数据库同步的自我纠正能力保证，见 ADR 全局前提 3、4）
        finally:
            if acquired:  # 关键守卫：未获取锁时不调用 release()
                global_task_state.release()

        # 云端 sync_once：不等待，失败调 ping
        if not global_task_state.try_acquire(TaskState.CLOUD_SYNC, 0):
            # 放弃本次，调 ping 心跳报告在线
            return
        try:
            # 执行 sync_once...
        finally:
            global_task_state.release()
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._state: TaskState = TaskState.IDLE

    @property
    def current_state(self) -> TaskState:
        """当前状态（只读，用于调试/日志）"""
        with self._cond:
            return self._state

    def try_acquire(self, target: TaskState, timeout: float) -> bool:
        """尝试获取任务状态（阻塞，可超时）

        仅当当前状态为 IDLE 时才能获取成功，获取后将状态置为 target。
        若状态非 IDLE，阻塞等待直到状态变为 IDLE 或超时。

        Args:
            target: 要获取的状态（LOCAL_TASK 或 CLOUD_SYNC）
            timeout: 超时秒数。0 表示不等待（立即返回）

        Returns:
            True 表示获取成功，False 表示超时

        Note:
            此方法是同步阻塞调用。在 asyncio 事件循环中调用时，
            必须用 ``await asyncio.to_thread(global_task_state.try_acquire, ...)``
            包裹，否则会阻塞主事件循环。
        """
        with self._cond:
            if self._state == TaskState.IDLE:
                self._state = target
                logger.debug("GlobalTaskState: %s -> %s", TaskState.IDLE.value, target.value)
                return True

            if timeout <= 0:
                return False

            deadline = time.monotonic() + timeout
            while self._state != TaskState.IDLE:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)

            self._state = target
            logger.debug("GlobalTaskState: %s -> %s", TaskState.IDLE.value, target.value)
            return True

    def release(self) -> None:
        """释放任务状态，重置为 IDLE，并唤醒所有等待者"""
        with self._cond:
            prev = self._state
            self._state = TaskState.IDLE
            self._cond.notify_all()
            logger.debug("GlobalTaskState: %s -> %s", prev.value, TaskState.IDLE.value)


# 单例实例（懒加载，与 backup_service 一致）
global_task_state = LazySingleton(GlobalTaskState)
