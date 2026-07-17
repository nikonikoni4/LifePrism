import shutil
from pathlib import Path

import pytest

from lifeprism.llm.session.manager import ChatHistoryManager


# 1. 测试添加
@pytest.mark.core
class TestChatHistoryManager:
    def test_init_creates_directory(self):

        # 1. 测试路径不存在时是否能正常创建
        path = Path("test/core/unit/llm/chat_history/test/chat_history.json")
        manager = ChatHistoryManager(path)
        # 判断文件存不存在
        assert path.exists() == True, "无法创建新的文件夹"
        # 删除测试文件夹
        if path.parent.exists():
            shutil.rmtree(path.parent)
        # 2. 正常加载
        path = Path("test/core/unit/llm/chat_history/chat_history.json")
        manager = ChatHistoryManager(path)
