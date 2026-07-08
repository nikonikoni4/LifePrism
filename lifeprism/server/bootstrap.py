"""
启动共享模块

提取三个启动入口（main.py / main_web_demo.py / main_agent_only.py）共用的初始化逻辑：
- 数据库初始化链（资源文件 → 建表 → 迁移 → 默认数据 → 分类颜色）
- Agent Loop + WeChat Channel 的启动与停止

各入口按需调用这些函数，避免代码重复，同时保持入口文件的职责单一。
"""

import asyncio

from lifeprism.config.settings_manager import settings
from lifeprism.repository.data_initializer import initialize_default_data
from lifeprism.repository.lw_table_manager import init_database
from lifeprism.repository.migrations.migration_runner import run_migrations
from lifeprism.repository.resource_initializer import initialize_resources
from lifeprism.server.providers.category_color_provider import initialize_category_colors
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def init_database_full() -> None:
    """
    执行完整的数据库初始化链。

    顺序：
        1. initialize_resources()  — 复制模板文件（prompts/config 等）
        2. init_database()         — 建表
        3. run_migrations()        — 数据库迁移
        4. initialize_default_data() — 写入默认数据
        5. initialize_category_colors() — 初始化分类颜色

    异常处理：每步独立 try/except，资源初始化失败不阻塞后续步骤，
    数据库核心步骤失败则向上抛出（与 main.py 原有行为一致）。
    """
    # 1. 资源文件初始化（非致命）
    logger.info("正在初始化资源文件...")
    try:
        initialize_resources()
    except Exception as e:
        logger.warning("资源文件初始化失败（非致命）: error=%s", e)

    # 2. 数据库表结构初始化（致命）
    logger.info("正在初始化 LifeWatch 数据库...")
    try:
        init_database()
        run_migrations(str(settings.lw_db_path))
        initialize_default_data()
        initialize_category_colors()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error("数据库初始化失败: error=%s", e)
        raise


async def start_agent_and_channel() -> tuple[asyncio.Task, object]:
    """
    启动 WeChat Channel 和 Agent Loop。

    Returns:
        tuple: (agent_loop_task, wechat_channel)
        - agent_loop_task: AgentLoop 的 asyncio.Task，用于后续取消
        - wechat_channel: wechat_channel 单例，用于后续停止
    """
    from lifeprism.llm.agent.loop import agent_loop
    from lifeprism.llm.channel import wechat_channel

    # 启动微信渠道
    try:
        await wechat_channel.start()
        logger.info("微信渠道启动成功")
    except Exception as e:
        logger.warning("启动微信渠道失败: error=%s", e)

    # 启动 AgentLoop
    loop_task = asyncio.create_task(agent_loop.loop())
    logger.info("AgentLoop started")

    return loop_task, wechat_channel


async def stop_agent_and_channel(loop_task: asyncio.Task, wechat_channel: object) -> None:
    """
    停止 WeChat Channel 和 Agent Loop。

    Args:
        loop_task: start_agent_and_channel() 返回的 asyncio.Task
        wechat_channel: start_agent_and_channel() 返回的 wechat_channel 单例
    """
    # 停止微信渠道
    if wechat_channel and wechat_channel._running:
        await wechat_channel.stop()

    # 取消 AgentLoop
    if loop_task and not loop_task.done():
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            logger.info("[SHUTDOWN] AgentLoop stopped")
