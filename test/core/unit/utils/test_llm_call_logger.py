"""LLM 调用记录器测试"""

import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Dict, Any

from lifeprism.llm.utils import llm_call_logger


# 模拟 InboundMessage 和 OutboundMessage
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


def test_logger_disabled_by_default():
    """测试默认情况下记录器是禁用的"""
    # 默认应该是禁用状态
    assert llm_call_logger.enabled == False

    # 调用 log_call 应该返回 None
    msg = MockInboundMessage(
        type="chat",
        content="测试消息"
    )
    response = MockOutboundMessage(
        id="test-1",
        response=MockLLMResponse(content="测试回复")
    )

    result = llm_call_logger.log_call(msg, response)
    assert result is None

    print("✓ 测试通过：默认禁用状态")


def test_logger_enable_and_log():
    """测试启用记录器并记录调用"""
    # 启用记录器
    llm_call_logger.enabled = True

    try:
        # 创建测试消息
        msg = MockInboundMessage(
            type="general_task",
            content="这是一条测试消息",
            session_id="test-session-001",
            extra={
                "system_prompt": "你是一个测试助手"
            }
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

        # 记录调用
        record_id = llm_call_logger.log_call(
            inbound_msg=msg,
            outbound_msg=response,
            prompt_module="test",
            prompt_name="test_prompt",
            prompt_version="v1",
            model="gpt-4",
        )

        assert record_id is not None
        print(f"✓ 测试通过：成功记录调用，ID: {record_id}")

        # 验证日志文件是否创建
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"

        assert log_file.exists()
        print(f"✓ 测试通过：日志文件已创建: {log_file}")

        # 读取并验证内容
        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["version"] == "1.0"
        assert data["date"] == date_str
        assert len(data["calls"]) > 0

        # 找到刚才记录的调用
        call = next((c for c in data["calls"] if c["id"] == record_id), None)
        assert call is not None
        assert call["message_type"] == "general_task"
        assert call["prompt"]["module"] == "test"
        assert call["prompt"]["name"] == "test_prompt"
        assert call["input"]["text"] == "这是一条测试消息"
        assert call["output"]["content"] == "这是测试回复"
        assert call["tokens"]["total_tokens"] == 150

        print("✓ 测试通过：日志内容正确")

    finally:
        # 恢复禁用状态
        llm_call_logger.enabled = False


def test_multimodal_content():
    """测试多模态内容（包含图片）"""
    llm_call_logger.enabled = True

    try:
        # 创建包含 base64 图片的消息
        # 这是一个 1x1 像素的透明 PNG 图片
        tiny_png_base64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        msg = MockInboundMessage(
            type="general_task",
            content=[
                {"type": "text", "text": "分析这张图片"},
                {"type": "image_url", "image_url": {"url": tiny_png_base64}},
                {"type": "text", "text": "请详细描述"}
            ],
            extra={
                "system_prompt": "你是一个图片分析助手"
            }
        )

        response = MockOutboundMessage(
            id="test-2",
            response=MockLLMResponse(content="这是一张透明图片")
        )

        # 记录调用
        record_id = llm_call_logger.log_call(
            inbound_msg=msg,
            outbound_msg=response,
            prompt_module="test",
            prompt_name="image_analysis",
        )

        assert record_id is not None
        print(f"✓ 测试通过：成功记录多模态调用，ID: {record_id}")

        # 验证图片是否保存
        from datetime import datetime
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"

        with open(log_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        call = next((c for c in data["calls"] if c["id"] == record_id), None)
        assert call is not None
        assert call["input"]["content_type"] == "multimodal"
        assert len(call["input"]["images"]) == 1
        assert call["input"]["text"] == "分析这张图片\n请详细描述"

        # 验证图片文件存在
        image_filename = call["input"]["images"][0]
        image_path = llm_call_logger.image_dir / image_filename
        assert image_path.exists()

        print(f"✓ 测试通过：图片已保存: {image_filename}")

    finally:
        llm_call_logger.enabled = False


def test_export_by_prompt():
    """测试按 prompt 导出数据集"""
    llm_call_logger.enabled = True

    try:
        # 记录几条测试数据
        for i in range(3):
            msg = MockInboundMessage(
                type="general_task",
                content=f"测试消息 {i}",
                extra={"system_prompt": "测试提示词"}
            )
            response = MockOutboundMessage(
                id=f"test-{i}",
                response=MockLLMResponse(content=f"测试回复 {i}")
            )
            llm_call_logger.log_call(
                inbound_msg=msg,
                outbound_msg=response,
                prompt_module="test",
                prompt_name="export_test",
                prompt_version="v1",
            )

        # 导出数据集
        dataset = llm_call_logger.export_by_prompt(
            prompt_module="test",
            prompt_name="export_test",
            prompt_version="v1"
        )

        assert len(dataset) >= 3
        print(f"✓ 测试通过：成功导出 {len(dataset)} 条记录")

        # 验证数据结构
        for item in dataset:
            assert "id" in item
            assert "timestamp" in item
            assert "input" in item
            assert "output" in item

        print("✓ 测试通过：导出数据结构正确")

    finally:
        llm_call_logger.enabled = False


if __name__ == "__main__":
    print("开始测试 LLM 调用记录器...\n")

    test_logger_disabled_by_default()
    print()

    test_logger_enable_and_log()
    print()

    test_multimodal_content()
    print()

    test_export_by_prompt()
    print()

    print("所有测试通过！✓")
