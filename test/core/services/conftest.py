"""
测试数据准备工具

为 service 快照测试准备测试数据。
"""
import pytest
from datetime import datetime, timedelta
from pathlib import Path

from lifeprism.server.providers.diary_provider import diary_provider
from lifeprism.server.services import diary_service
from lifeprism.storage.providers import tokens_usage_provider


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


@pytest.fixture(scope="session")
def prepare_tokens_usage_test_data(test_data_path):
    """
    准备 tokens_usage_log 测试数据

    创建多条 token 使用记录，确保测试数据非空。
    """
    # 确保数据库已初始化
    from lifeprism.config.settings_manager import settings
    settings._initialize()

    # 创建测试数据
    base_date = datetime(2026, 1, 9)
    test_sessions = []

    # 直接使用数据库连接插入数据，以便设置 created_at
    with tokens_usage_provider.db.get_connection() as conn:
        cursor = conn.cursor()

        # 先清理可能存在的测试数据
        for i in range(10):
            date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            session_id_classification = f"c-{date}"
            session_id_chatbot = f"chatbot-{date}-{i}"
            cursor.execute("DELETE FROM tokens_usage_log WHERE session_id = ?", (session_id_classification,))
            cursor.execute("DELETE FROM tokens_usage_log WHERE session_id = ?", (session_id_chatbot,))

        conn.commit()

        # 插入新数据
        for i in range(10):
            date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            created_at = f"{date} 10:00:00"

            # 创建 classification 模式的记录
            session_id_classification = f"c-{date}"
            cursor.execute("""
                INSERT INTO tokens_usage_log
                (session_id, input_tokens, output_tokens, total_tokens,
                 search_count, result_items_count, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id_classification,
                500 + i * 50,
                300 + i * 30,
                800 + i * 80,
                5 + i,
                10 + i * 2,
                'classification',
                created_at
            ))
            test_sessions.append(session_id_classification)

            # 创建 chatbot 模式的记录
            session_id_chatbot = f"chatbot-{date}-{i}"
            cursor.execute("""
                INSERT INTO tokens_usage_log
                (session_id, input_tokens, output_tokens, total_tokens,
                 search_count, result_items_count, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                session_id_chatbot,
                1000 + i * 100,
                800 + i * 80,
                1800 + i * 180,
                0,
                0,
                'chatbot',
                created_at
            ))
            test_sessions.append(session_id_chatbot)

        conn.commit()

    return test_sessions


@pytest.fixture(scope="function")
def use_tokens_usage_test_data(prepare_tokens_usage_test_data):
    """
    在测试函数中使用准备好的 tokens_usage 数据

    这个 fixture 确保数据在每个测试前都已准备好。
    """
    return prepare_tokens_usage_test_data

