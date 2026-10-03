"""聊天与后台 Agent 运行共享的模型调用准入限流。"""

import asyncio
import time


class ModelCallLimiter:
    """按统一准入速率串行化模型请求。

    聊天轮次与后台总线任务共用同一个 limiter 实例，因此速率上限作用于整个进程，
    而不是单个会话。

    Attributes:
        interval: 两次准入之间必须间隔的最小秒数。
    """

    def __init__(self, rpm: float = 60, safety_factor: float = 0.7):
        """由提供商声明的速率推导准入间隔。

        Args:
            rpm: 提供商允许的每分钟请求数上限。
            safety_factor: 实际使用的 ``rpm`` 比例；取值小于 1 可为重试与并发
                调用方留出余量。
        """
        self.interval = 60 / (rpm * safety_factor)
        self._lock = asyncio.Lock()
        self._last: float | None = None

    async def acquire(self) -> None:
        """阻塞到本调用方获准发出一次模型请求为止。

        等待者按到达顺序在 ``_lock`` 上排队。在 ``asyncio.sleep`` 期间被取消的
        等待者会释放锁但不更新 ``_last``，因此不消耗配额；下一个调用方仍以最近
        一次真正发生过的准入为起点计算等待时间。
        """
        async with self._lock:
            if self._last is not None:
                delay = self.interval - (time.monotonic() - self._last)
                if delay > 0:
                    await asyncio.sleep(delay)
            self._last = time.monotonic()
