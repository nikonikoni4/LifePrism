"""直接测试 log_call 方法"""
import sys
sys.path.insert(0, '.')

from datetime import datetime
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.utils import llm_call_logger

# 模拟 InboundMessage 和 OutboundMessage
class MockInboundMessage:
    def __init__(self):
        self.type = "DREAM_TASK"
        self.content = "测试内容"
        self.extra = {"system_prompt": "测试 system prompt"}
        self.session_id = "test_session"
        self.channel = "test_channel"

class MockResponse:
    def __init__(self):
        self.content = "测试响应内容"
        self.usage = {"input_tokens": 100, "output_tokens": 50}

class MockOutboundMessage:
    def __init__(self):
        self.response = MockResponse()

print("=" * 60)
print("直接测试 log_call 方法")
print("=" * 60)

# 1. 测试未启用时
print("\n1. 测试未启用时:")
print(f"   - llm_call_logger.enabled: {llm_call_logger.enabled}")

msg = MockInboundMessage()
result = MockOutboundMessage()

record_id = llm_call_logger.log_call(
    msg, result,
    prompt_module="test_module",
    prompt_name="test_prompt"
)

print(f"   - 返回的 record_id: {record_id}")
print(f"   - 预期: None")

# 2. 启用后测试
print("\n2. 启用后测试:")
llm_call_logger.enabled = True
print(f"   - llm_call_logger.enabled: {llm_call_logger.enabled}")

record_id2 = llm_call_logger.log_call(
    msg, result,
    prompt_module="test_module",
    prompt_name="test_prompt_enabled"
)

print(f"   - 返回的 record_id: {record_id2}")
print(f"   - 是否为 UUID: {record_id2 is not None and len(record_id2) == 36}")

# 3. 检查文件
print("\n3. 检查输出文件:")
date_str = datetime.now().strftime("%Y-%m-%d")
log_file = llm_call_logger.log_dir / f"llm_calls_{date_str}.json"

print(f"   - 日志文件路径: {log_file}")
print(f"   - 文件存在: {log_file.exists()}")

if log_file.exists():
    import json
    with open(log_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"   - 记录数量: {len(data.get('calls', []))}")
    if data.get('calls'):
        last_call = data['calls'][-1]
        print(f"\n   最后一条记录:")
        print(f"   - ID: {last_call.get('id')}")
        print(f"   - prompt.module: {last_call.get('prompt', {}).get('module')}")
        print(f"   - prompt.name: {last_call.get('prompt', {}).get('name')}")
        print(f"   - 输入文本: {last_call.get('input', {}).get('text')}")
        print(f"   - 输出内容: {last_call.get('output', {}).get('content')}")

print("\n" + "=" * 60)
print("测试完成 ✓")
print("=" * 60)
