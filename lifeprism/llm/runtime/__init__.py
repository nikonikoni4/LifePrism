"""LifePrism 对外部 myagent 执行内核的集成层。"""

from .service import AgentRuntime, agent_runtime

__all__ = ["AgentRuntime", "agent_runtime"]
