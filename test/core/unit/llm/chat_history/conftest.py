import pytest
from pathlib import Path

@pytest.fixture
def new_chat_hisotry_json():
    """一个全新的chat_history.json内容，无任何内容"""
    # 创建文件
    path = Path("test/core/unit/llm/chat_history/chat_history.json")
    # 返回文件地址
    yield path
    # 删除文件
    