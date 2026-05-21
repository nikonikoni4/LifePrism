"""LLM 调用记录器简单测试"""

import sys
sys.path.insert(0, '.')

from dataclasses import dataclass
from typing import Optional, Dict, Any
from lifeprism.llm.utils import llm_call_logger


# 模拟消息类
@dataclass
class MockInboundMessage:
    type: str
    content: str | list | None
    session_id: Optional[str] = None
    channel: str = "local"
    extra: Optional[Dict[str, Any]] = None


@dataclass
class MockLLMResponse:
    content: str
    usage: Optional[Dict[str, Any]] = None


@dataclass
class MockOutboundMessage:
    id: str
    response: Optional[MockLLMResponse] = None
    session_id: Optional[str] = None


def main():
    print("=" * 60)
    print("LLM 调用记录器测试")
    print("=" * 60)
    print()

    # 测试 1：默认禁用状态
    print("测试 1：默认禁用状态")
    print(f"  记录器状态: {'启用' if llm_call_logger.enabled else '禁用'}")

    msg = MockInboundMessage(type="chat", content="测试消息")
    response = MockOutboundMessage(id="test-1", response=MockLLMResponse(content="测试回复"))
    result = llm_call_logger.log_call(msg, response)

    print(f"  调用 log_call 返回: {result}")
    print(f"  [OK] 测试通过：默认禁用时返回 None")
    print()

    # 测试 2：启用并记录
    print("测试 2：启用记录器并记录调用")
    llm_call_logger.enabled = True
    print(f"  记录器状态: {'启用' if llm_call_logger.enabled else '禁用'}")

    msg = MockInboundMessage(
        type="general_task",
        content="这是一条测试消息",
        session_id="test-session-001",
        extra={"system_prompt": "你是一个测试助手"}
    )

    response = MockOutboundMessage(
        id="test-1",
        response=MockLLMResponse(
            content="这是测试回复",
            usage={
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150
            }
        ),
        session_id="test-session-001"
    )

    record_id = llm_call_logger.log_call(
        inbound_msg=msg,
        outbound_msg=response,
        prompt_module="test",
        prompt_name="test_prompt",
        prompt_version="v1",
        model="gpt-4",
    )

    print(f"  记录 ID: {record_id}")
    print(f"  日志目录: {llm_call_logger.log_dir}")
    print(f"  [OK] 测试通过：成功记录调用")
    print()

    # 测试 3：多模态内容
    print("测试 3：记录多模态内容（包含图片）")
    tiny_png_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

    msg = MockInboundMessage(
        type="general_task",
        content=[
            {"type": "text", "text": "分析这张图片"},
            {"type": "image_url", "image_url": {"url": tiny_png_base64}},
            {"type": "text", "text": "请详细描述"}
        ],
        extra={"system_prompt": "你是一个图片分析助手"}
    )

    response = MockOutboundMessage(
        id="test-2",
        response=MockLLMResponse(content="这是一张透明图片")
    )

    record_id = llm_call_logger.log_call(
        inbound_msg=msg,
        outbound_msg=response,
        prompt_module="test",
        prompt_name="image_analysis",
    )

    print(f"  记录 ID: {record_id}")
    print(f"  图片目录: {llm_call_logger.image_dir}")
    print(f"  [OK] 测试通过：成功记录多模态调用")
    print()

    # 测试 4：导出数据集
    print("测试 4：按 prompt 导出数据集")
    dataset = llm_call_logger.export_by_prompt(
        prompt_module="test",
        prompt_name="test_prompt",
        prompt_version="v1"
    )

    print(f"  导出记录数: {len(dataset)}")
    if dataset:
        print(f"  第一条记录 ID: {dataset[0]['id']}")
        print(f"  输入文本: {dataset[0]['input']['text'][:30]}...")
        print(f"  输出文本: {dataset[0]['output']['content'][:30]}...")
    print(f"  [OK] 测试通过：成功导出数据集")
    print()

    # 恢复禁用状态
    llm_call_logger.enabled = False

    print("=" * 60)
    print("所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    main()
