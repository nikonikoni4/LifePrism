"""微信 Channel 测试入口"""
import asyncio
from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import OutboundMessage, LLMResponse
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)


async def main():
    """测试微信 channel"""
    # 配置
    config = WechatConfig(
        enabled=True,
        allow_from=["*"]  # 允许所有用户
    )

    # 创建消息队列
    bus = MessageQueue()

    # 创建 channel
    channel = WechatChannel(config, bus)

    # 订阅入站消息
    async def handle_inbound(msg):
        logger.info(f"收到消息: {msg.content}")
        logger.info(f"发送者: {msg.extra.get('sender_id')}")

        # 自动回复
        reply = OutboundMessage(
            id=f"reply_{msg.extra.get('sender_id')}",
            response=LLMResponse(content=f"收到你的消息: {msg.content}"),
            session_id=msg.session_id
        )
        await channel.send(reply)

    bus.subscribe_inbound(handle_inbound)

    # 启动 channel
    logger.info("启动微信 channel...")
    await channel.start()

    if not channel._running:
        logger.error("启动失败")
        return

    logger.info("微信 channel 已启动，等待消息...")

    try:
        # 保持运行
        while channel._running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    finally:
        await channel.stop()
        logger.info("微信 channel 已停止")


if __name__ == "__main__":
    asyncio.run(main())
