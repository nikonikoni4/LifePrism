"""测试 llm_call_logger 配置和输出"""

import asyncio
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.bus import InboundMessage, MessageType, bus
from lifeprism.llm.prompts import Prompts
from lifeprism.llm.utils import llm_call_logger


async def test_llm_call_logger():
    """测试 LLM 调用记录器"""
    print("=" * 60)
    print("测试 LLM 调用记录器配置和输出")
    print("=" * 60)

    # 1. 检查配置
    print(f"\n1. 配置检查:")
    config_value = settings.get("llm_call_logger_enabled", None)
    print(f"   - config.yaml 中的值: {config_value}")
    print(f"   - llm_call_logger.enabled: {llm_call_logger.enabled}")

    # 2. 检查日志目录
    print(f"\n2. 日志目录:")
    print(f"   - log_dir: {llm_call_logger.log_dir}")
    print(f"   - image_dir: {llm_call_logger.image_dir}")
    print(f"   - log_dir 存在: {llm_call_logger.log_dir.exists()}")

    # 3. 测试未启用时的行为
    print(f"\n3. 测试未启用时的行为:")
    msg = InboundMessage(
        MessageType.DREAM_TASK, content="测试消息", extra={"system_prompt": "你是一个测试助手"}
    )
    result = await bus.send(msg)
    record_id = llm_call_logger.log_call(
        msg, result, prompt_module="test", prompt_name="test_prompt"
    )
    print(f"   - 返回的 record_id: {record_id}")
    print(f"   - 预期: None (因为未启用)")

    # 4. 启用并测试
    print(f"\n4. 启用记录器并测试:")
    llm_call_logger.enabled = True
    print(f"   - 设置 enabled = True")

    msg2 = InboundMessage(
        MessageType.DREAM_TASK,
        content="第二条测试消息",
        extra={"system_prompt": "你是一个测试助手"},
    )
    result2 = await bus.send(msg2)
    record_id2 = llm_call_logger.log_call(
        msg2, result2, prompt_module="test", prompt_name="test_prompt_enabled"
    )
    print(f"   - 返回的 record_id: {record_id2}")
    print(f"   - 预期: UUID 字符串")

    # 5. 检查输出文件
    print(f"\n5. 检查输出文件:")
    from datetime import datetime

    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"
    print(f"   - 日志文件路径: {log_file}")
    print(f"   - 文件存在: {log_file.exists()}")

    if log_file.exists():
        import json

        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"   - 记录数量: {len(data.get('calls', []))}")
        if data.get("calls"):
            print(f"   - 最后一条记录 ID: {data['calls'][-1].get('id')}")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    from lifeprism.llm.agent.loop import agent_loop

    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        try:
            await test_llm_call_logger()
        finally:
            loop_task.cancel()

    asyncio.run(main())
