"""后台总线消费者；Agent 的实际执行由 myagent Runtime 承担。"""

import asyncio

from lifeprism.llm.bus import OutboundMessage, bus
from lifeprism.llm.runtime import agent_runtime
from lifeprism.utils import LazySingleton, get_logger

logger = get_logger(__name__)


class AgentBusWorker:
    """消费后台总线请求并交给 Agent Runtime 执行。

    后台请求由调用方同步等待，因此运行失败必须包装成携带错误的
    ``OutboundMessage`` 发布出去；若让异常直接冒出，调用方会一直阻塞到超时。
    本 worker 同时负责 Runtime 生命周期：:meth:`loop` 进入时启动，退出时先关闭
    Runtime 再关闭总线。
    """

    def __init__(self, queue=None, runtime=None):
        """绑定要消费的总线与要使用的 Runtime。

        Args:
            queue: 提供 ``consume_inbound``、``publish_outbound``、
                ``bind_execution``、``close`` 的总线对象；默认使用进程级的
                ``bus``。
            runtime: 执行请求的 Agent Runtime；默认使用进程级的
                ``agent_runtime`` 单例。
        """
        self._bus = queue if queue is not None else bus
        self._runtime = runtime if runtime is not None else agent_runtime
        self._running = False
        self._active_tasks: set[asyncio.Task] = set()

    async def _dispatch(self, message) -> None:
        """执行一条后台请求并发布其结果。

        运行失败会转换成携带错误的 ``OutboundMessage``，让等待中的调用方立即
        被拒绝，而不是一直等到超时。

        Args:
            message: 待执行的后台入站请求。
        """
        try:
            response = await self._runtime.execute(message)
        except Exception as exc:
            logger.error("后台 Agent 请求失败: id=%s error=%s", message.id, exc)
            response = OutboundMessage(id=message.id, session_id=message.session_id, error=str(exc))
        await self._bus.publish_outbound(response)

    async def loop(self) -> None:
        """持续消费后台请求，直到总线或所有者停止本循环。

        每条请求在独立任务中运行并注册到总线上，使调用方的取消能传导到它发起的
        模型调用。退出时先取消并回收全部在途任务，再依次关闭 Runtime 与总线。

        Raises:
            RuntimeError: 本 worker 的循环已在运行。
        """
        if self._running:
            raise RuntimeError("Agent bus consumer already running")
        self._runtime.start()
        self._running = True
        try:
            while self._running:
                message = await self._bus.consume_inbound()
                if message._cancelled:
                    continue
                task = asyncio.create_task(self._dispatch(message))
                self._bus.bind_execution(message.id, task)
                self._active_tasks.add(task)
                task.add_done_callback(self._task_done)
        finally:
            self._running = False
            for task in list(self._active_tasks):
                task.cancel()
            await asyncio.gather(*self._active_tasks, return_exceptions=True)
            self._active_tasks.clear()
            try:
                await self._runtime.close()
            finally:
                await self._bus.close()

    def _task_done(self, task: asyncio.Task) -> None:
        """回收已完成的派发任务，并记录非预期的失败。

        Args:
            task: 刚刚结束的派发任务。
        """
        self._active_tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.error("后台结果派发失败: %s", task.exception())

    def stop(self) -> None:
        """置为停止状态；应用侧还需取消并 await 自己的 loop 任务，以解除队列读取阻塞。"""
        self._running = False


agent_loop = LazySingleton(AgentBusWorker)
