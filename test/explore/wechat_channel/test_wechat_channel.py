"""微信 Channel 测试入口"""
import asyncio
import time
from lifeprism.llm.channel.wechat import WechatChannel, WechatConfig
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import OutboundMessage, LLMResponse
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

last_sender = None


async def main():
    """测试微信 channel"""
    global last_sender

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
        global last_sender
        last_sender = msg.extra.get('sender_id')
        print(f"\n[收到消息] {last_sender}: {msg.content}")
        if msg.extra.get('media'):
            print(f"[媒体文件] {msg.extra['media']}")
        print("回复> ", end="", flush=True)

    bus.subscribe_inbound(handle_inbound)

    # 启动 channel
    logger.info("启动微信 channel...")
    await channel.start()

    if not channel._running:
        logger.error("启动失败")
        return

    print("\n微信 channel 已启动")
    print("等待微信消息，收到消息后可输入回复...")
    print("按 Ctrl+C 退出\n")

    # 输入循环
    async def input_loop():
        while channel._running:
            try:
                text = await asyncio.to_thread(input, "回复> ")
                if not text.strip():
                    continue
                if not last_sender:
                    print("还没有收到任何消息，无法发送")
                    continue

                reply = OutboundMessage(
                    id=f"manual_{last_sender}_{int(time.time())}",
                    response=LLMResponse(content=text),
                    session_id=f"wechat:{last_sender}"
                )
                await channel.send(reply)
                print(f"[已发送] -> {last_sender}")
            except EOFError:
                break

    try:
        await input_loop()
    except KeyboardInterrupt:
        logger.info("收到中断信号")
    finally:
        await channel.stop()
        logger.info("微信 channel 已停止")


if __name__ == "__main__":
    asyncio.run(main())
