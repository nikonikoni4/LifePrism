import asyncio
import json
from pydantic import BaseModel, Field
from typing import Optional

# 模拟 ChatStreamEvent 结构
class ChatStreamEvent(BaseModel):
    type: str
    session_id: Optional[str] = None
    session_name: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None

def test_serialization():
    event = ChatStreamEvent(type="session", session_id="123", session_name="test")

    print("Testing model_dump_json()...")
    try:
        # Pydantic v2 推荐方法
        result = event.model_dump_json(exclude_none=True)
        print(f"Result: {result}")
        data = json.loads(result)
        assert "type" in data
        assert "session_id" in data
        assert "message" not in data
        print("SUCCESS: model_dump_json works as expected.")
    except Exception as e:
        print(f"FAILED: model_dump_json failed: {e}")

    print("\nTesting ensure_ascii compatibility (manual check)...")
    # model_dump_json 不直接支持 ensure_ascii 参数，但默认输出是 UTF-8
    event_cn = ChatStreamEvent(type="content", message="你好")
    result_cn = event_cn.model_dump_json()
    print(f"Result with Chinese: {result_cn}")
    if "\\u" not in result_cn:
        print("SUCCESS: model_dump_json outputs raw UTF-8 (equivalent to ensure_ascii=False).")
    else:
        print("NOTE: model_dump_json escaped unicode.")

if __name__ == "__main__":
    test_serialization()
