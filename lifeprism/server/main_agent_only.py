"""
LifePrism Linux Agent Only 启动入口

运行形态：Agent Loop + WeChat Channel（无 FastAPI，无 Monitor，无 ScheduleService）

适用场景：仅需 AI 助手对话能力，不需要 Web 界面。
Agent 通过微信渠道接收/回复消息，直接读写数据库。

与 Web Demo 模式的区别：
- 不启动 FastAPI 服务（无 HTTP API）
- 不启动 Monitor 模块
- 不启动 ScheduleService
- 资源占用更低

启动命令：
    python -m lifeprism.server.main_agent_only

环境变量：
    LIFEPRISM_DATA_PATH — 数据目录路径（可选，默认 localData/）
"""

import asyncio
import signal

# 配置初始化（必须在所有 lifeprism 模块之前）
from lifeprism.config.settings_manager import settings  # noqa: F401
from lifeprism.server.bootstrap import (
    init_database_full,
    start_agent_and_channel,
    stop_agent_and_channel,
)
from lifeprism.utils import get_logger

logger = get_logger(__name__)


async def main() -> None:
    """
    Agent Only 主循环。

    启动流程：
        1. 数据库初始化（建表 + 迁移 + 默认数据 + 资源文件）
        2. 启动 WeChat Channel（接收/发送消息）
        3. 启动 Agent Loop（处理消息、调用工具）
        4. 等待 Agent Loop 运行（直到收到终止信号）
        5. 优雅关闭
    """
    logger.info("=== LifePrism Agent Only 模式启动 ===")

    # 1. 数据库初始化
    logger.info("正在初始化数据库...")
    init_database_full()

    # 2. 启动 Agent + Channel
    logger.info("正在启动 Agent Loop 和 WeChat Channel...")
    loop_task, wechat_channel = await start_agent_and_channel()

    # 3. 注册信号处理（优雅关闭）
    stop_event = asyncio.Event()

    def _signal_handler(sig_name: str) -> None:
        logger.info("收到信号 %s，准备关闭...", sig_name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _signal_handler(s.name))
        except NotImplementedError:
            # Windows 不支持 add_signal_handler，回退到 signal.signal
            signal.signal(sig, lambda *_, _sig=sig: _signal_handler(_sig.name))

    # 4. 等待终止信号或 Agent Loop 异常退出
    done, pending = await asyncio.wait(
        {loop_task, asyncio.create_task(stop_event.wait())},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if loop_task in done:
        # Agent Loop 先结束（异常或正常退出）
        exc = loop_task.exception()
        if exc:
            logger.error("Agent Loop 异常退出: error=%s", exc, exc_info=exc)
        else:
            logger.info("Agent Loop 正常退出")

    # 5. 优雅关闭
    logger.info("正在关闭 Agent 和 Channel...")
    await stop_agent_and_channel(loop_task, wechat_channel)
    logger.info("=== LifePrism Agent Only 已关闭 ===")


if __name__ == "__main__":
    asyncio.run(main())
