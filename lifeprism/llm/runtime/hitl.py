"""Session 级一次注册、本轮绑定的原生人在回路策略。"""

from typing import Protocol

from myagent.agent.execption import MaxStepsExceededError
from myagent.agent.hitl.hitl import HITL
from myagent.agent.hitl.types import HITLMessage, HumanReturn

from lifeprism.utils import get_logger

logger = get_logger(__name__)


class InteractionClient(Protocol):
    """Runtime 启动 turn 前绑定归属，原生策略只请求用户决定。"""

    def bind(self, *, run_id: str, session_id: str) -> None: ...

    async def ask_human(self, message: HITLMessage) -> HumanReturn: ...


class HITLPolicy:
    """持久 context 的转接对象；清空 target 不注销原生事件回调。"""

    def __init__(self):
        self.target: InteractionClient | None = None
        self.native = HITL(self)

    def bind(self, client: InteractionClient, *, timeout: float, grant_steps: int) -> None:
        """仅在对应 Session 执行锁内安装本轮的接收人和参数。"""
        if self.target is not None:
            raise RuntimeError("Session 已绑定另一个人工交互客户端")
        self.native.timeout = timeout
        self.native.grant_steps = grant_steps
        self.target = client

    def clear(self, client: InteractionClient | None) -> None:
        """只清除自己的本轮引用，不抹掉其他轮次的绑定。"""
        if self.target is client:
            self.target = None

    async def ask_human(self, message: HITLMessage) -> HumanReturn:
        """原生 HITLChannel 实现；等待保持在原 turn 协程中。"""
        target = self.target
        if target is None:
            raise RuntimeError("本轮没有人工交互客户端")
        return await target.ask_human(message)

    async def maxstep_continue(self, payload, next_handler):
        """未绑定交互的后台/本地调用继续使用原来的策略链。"""
        if self.target is None:
            return await next_handler()
        if not isinstance(payload.error_type, MaxStepsExceededError):
            # 未匹配的错误静默委托：回调在每个错误上都会跑，记录会刷屏。
            return await self.native.maxstep_continue(payload, next_handler)
        self._log_trigger(payload)
        verdict = await self.native.maxstep_continue(payload, next_handler)
        self._log_verdict(payload, verdict)
        return verdict

    async def tool_breaker_continue(self, payload, next_handler):
        """工具熔断裁决由原生策略完成，接入层不修改 loop。"""
        if self.target is None:
            return await next_handler()
        # 复用原生判据（含 ExceptionGroup 展开），避免两处匹配逻辑漂移。
        if not self.native._is_tool_breaker(payload.error_type):
            return await self.native.tool_breaker_continue(payload, next_handler)
        self._log_trigger(payload)
        verdict = await self.native.tool_breaker_continue(payload, next_handler)
        self._log_verdict(payload, verdict)
        return verdict

    def _log_trigger(self, payload) -> None:
        """只记录错误类型与原生等待参数，不落错误正文。"""
        logger.info(
            "人工裁决触发: reason=%s, timeout=%s, grant_steps=%s",
            type(payload.error_type).__name__,
            self.native.timeout,
            self.native.grant_steps,
        )

    @staticmethod
    def _log_verdict(payload, verdict) -> None:
        """记录原生返回的裁决；verdict 只含 decision/grant/as_error 等枚举与整数。"""
        logger.info(
            "人工裁决结果: reason=%s, verdict=%s",
            type(payload.error_type).__name__,
            verdict,
        )
