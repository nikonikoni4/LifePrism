"""测试在启用 llm_call_logger 后是否能正常记录"""
import sys
sys.path.insert(0, '.')

import asyncio
from datetime import datetime
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.bus import InboundMessage, MessageType, bus
from lifeprism.llm.prompts import Prompts
from lifeprism.llm.utils import llm_call_logger


async def test_log_call_with_enabled():
    """测试启用后的 log_call"""
    print("=" * 60)
    print("测试启用 llm_call_logger 后的记录功能")
    print("=" * 60)

    # 1. 启用记录器
    print("\n1. 启用记录器:")
    llm_call_logger.enabled = True
    print(f"   - llm_call_logger.enabled: {llm_call_logger.enabled}")

    # 2. 模拟 agent_schedule_job.py 中的调用
    print("\n2. 模拟 LLM 调用:")
    msg = InboundMessage(
        MessageType.DREAM_TASK,
        content="测试活动总结",
        extra={"system_prompt": "你是一个活动总结助手"}
    )

    result = await bus.send(msg)

    record_id = llm_call_logger.log_call(
        msg, result,
        prompt_module=Prompts.Schedule.ACTIVITY_SUMMARY.module,
        prompt_name=Prompts.Schedule.ACTIVITY_SUMMARY.name
    )

    print(f"   - 返回的 record_id: {record_id}")
    print(f"   - 是否成功记录: {record_id is not None}")

    # 3. 检查输出文件
    print("\n3. 检查输出文件:")
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"

    print(f"   - 日志文件路径: {log_file}")
    print(f"   - 文件存在: {log_file.exists()}")

    if log_file.exists():
        import json
        with open(log_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"   - 文件版本: {data.get('version')}")
        print(f"   - 记录日期: {data.get('date')}")
        print(f"   - 记录数量: {len(data.get('calls', []))}")

        if data.get('calls'):
            last_call = data['calls'][-1]
            print(f"\n   最后一条记录详情:")
            print(f"   - ID: {last_call.get('id')}")
            print(f"   - 时间戳: {last_call.get('timestamp')}")
            print(f"   - prompt.module: {last_call.get('prompt', {}).get('module')}")
            print(f"   - prompt.name: {last_call.get('prompt', {}).get('name')}")
            print(f"   - 输入内容长度: {len(last_call.get('input', {}).get('text', ''))}")
            print(f"   - 输出内容长度: {len(last_call.get('output', {}).get('content', ''))}")
    else:
        print("   ❌ 文件不存在！")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    from lifeprism.llm.agent.loop import agent_loop

    async def main():
        loop_task = asyncio.create_task(agent_loop.loop())
        try:
            await test_log_call_with_enabled()
        finally:
            loop_task.cancel()

    asyncio.run(main())
