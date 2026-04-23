"""
测试数据准备工具

为 diary_service 快照测试准备测试数据。
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from lifeprism.server.providers.diary_provider import diary_provider
from lifeprism.server.services import diary_service


@pytest.fixture(scope="session")
def prepare_diary_test_data(test_data_path):
    """
    准备 diary 测试数据

    创建多条日记记录，确保测试数据非空。
    """
    # 确保数据库已初始化
    from lifeprism.config.settings_manager import settings
    settings._initialize()

    # 创建测试日记
    base_date = datetime(2026, 4, 1)
    test_dates = []

    for i in range(10):
        date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        test_dates.append(date)

        # 创建日记记录
        diary_provider.create_diary(date)

        # 更新元数据
        diary_provider.update_diary(date, {
            'mood': ['calm', 'happy', 'very_happy'][i % 3],
            'importance': ['normal', 'important'][i % 2],
            'custom_tags': '["测试", "数据"]',
            'word_count': 100 + i * 10,
        })

        # 创建日记内容文件
        content = f"这是 {date} 的测试日记内容。\n\n今天是测试的第 {i+1} 天。"
        diary_service._write_diary_content(date, content)

    return test_dates


@pytest.fixture(scope="function")
def use_diary_test_data(prepare_diary_test_data):
    """
    在测试函数中使用准备好的数据

    这个 fixture 确保数据在每个测试前都已准备好。
    """
    return prepare_diary_test_data
