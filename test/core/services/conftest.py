"""
测试数据准备工具

为 service 快照测试准备测试数据。
"""

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lifeprism.repository.providers import diary_provider, tokens_usage_provider
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
        diary_provider.update_diary(
            date,
            {
                "mood": ["calm", "happy", "very_happy"][i % 3],
                "importance": ["normal", "important"][i % 2],
                "custom_tags": '["测试", "数据"]',
                "word_count": 100 + i * 10,
            },
        )

        # 创建日记内容文件
        content = f"这是 {date} 的测试日记内容。\n\n今天是测试的第 {i + 1} 天。"
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
            cursor.execute(
                "DELETE FROM tokens_usage_log WHERE session_id = ?", (session_id_classification,)
            )
            cursor.execute(
                "DELETE FROM tokens_usage_log WHERE session_id = ?", (session_id_chatbot,)
            )

        conn.commit()

        # 插入新数据
        for i in range(10):
            date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
            created_at = f"{date} 10:00:00"

            # 创建 classification 模式的记录
            session_id_classification = f"c-{date}"
            cursor.execute(
                """
                INSERT INTO tokens_usage_log
                (session_id, input_tokens, output_tokens, total_tokens,
                 search_count, result_items_count, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id_classification,
                    500 + i * 50,
                    300 + i * 30,
                    800 + i * 80,
                    5 + i,
                    10 + i * 2,
                    "classification",
                    created_at,
                ),
            )
            test_sessions.append(session_id_classification)

            # 创建 chatbot 模式的记录
            session_id_chatbot = f"chatbot-{date}-{i}"
            cursor.execute(
                """
                INSERT INTO tokens_usage_log
                (session_id, input_tokens, output_tokens, total_tokens,
                 search_count, result_items_count, mode, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    session_id_chatbot,
                    1000 + i * 100,
                    800 + i * 80,
                    1800 + i * 180,
                    0,
                    0,
                    "chatbot",
                    created_at,
                ),
            )
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


@pytest.fixture(scope="session")
def prepare_cache_test_data(test_data_path):
    """
    准备 multi_purpose_map_cache 和 single_purpose_map_cache 测试数据

    创建多条缓存记录，确保测试数据非空。
    """
    # 确保数据库已初始化
    from lifeprism.config.settings_manager import settings

    settings._initialize()

    import uuid

    from lifeprism.repository.providers import category_provider, sub_category_provider

    # 确保有测试分类数据
    # 创建测试主分类
    test_category_id = "test_work"
    category_provider.insert_category(
        {"id": test_category_id, "name": "测试工作", "color": "#5B8FF9", "state": 1}
    )

    # 创建测试子分类
    test_sub_category_id = "test_coding"
    sub_category_provider.insert_sub_category(
        {
            "id": test_sub_category_id,
            "category_id": test_category_id,
            "name": "测试编码",
            "state": 1,
        }
    )

    # 准备测试数据
    multi_purpose_records = []
    single_purpose_records = []

    # 创建 multi_purpose_map_cache 测试数据（多用途应用，需要 title 区分）
    multi_apps = [
        ("chrome.exe", "GitHub - Pull Request", "Chrome浏览器", "GitHub代码审查"),
        ("chrome.exe", "YouTube - Video", "Chrome浏览器", "YouTube视频"),
        ("code.exe", "main.py - VSCode", "VSCode编辑器", "编辑Python文件"),
        ("code.exe", "test.js - VSCode", "VSCode编辑器", "编辑JavaScript文件"),
    ]

    for app, title, app_desc, title_analysis in multi_apps:
        multi_purpose_records.append(
            {
                "id": f"m-{uuid.uuid4().hex[:8]}",
                "app": app,
                "title": title,
                "app_description": app_desc,
                "title_analysis": title_analysis,
                "category_id": test_category_id,
                "sub_category_id": test_sub_category_id,
                "state": 1,
                "link_to_goal_id": None,
            }
        )

    # 创建 single_purpose_map_cache 测试数据（单用途应用，不需要 title）
    single_apps = [
        ("pycharm.exe", "PyCharm IDE", "PyCharm集成开发环境"),
        ("notepad++.exe", "Notepad++", "Notepad++文本编辑器"),
        ("git.exe", "Git", "Git版本控制工具"),
    ]

    for app, title, app_desc in single_apps:
        single_purpose_records.append(
            {
                "id": f"s-{uuid.uuid4().hex[:8]}",
                "app": app,
                "title": title,
                "app_description": app_desc,
                "category_id": test_category_id,
                "sub_category_id": test_sub_category_id,
                "state": 1,
                "link_to_goal_id": None,
            }
        )

    # 插入数据到数据库
    from lifeprism.repository import Database

    db = Database()

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # 清理可能存在的测试数据
        cursor.execute("DELETE FROM multi_purpose_map_cache WHERE id LIKE 'm-%'")
        cursor.execute("DELETE FROM single_purpose_map_cache WHERE id LIKE 's-%'")
        conn.commit()

        # 插入 multi_purpose_map_cache 数据
        for record in multi_purpose_records:
            cursor.execute(
                """
                INSERT INTO multi_purpose_map_cache
                (id, app, title, app_description, title_analysis, category_id, sub_category_id, state, link_to_goal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record["id"],
                    record["app"],
                    record["title"],
                    record["app_description"],
                    record["title_analysis"],
                    record["category_id"],
                    record["sub_category_id"],
                    record["state"],
                    record["link_to_goal_id"],
                ),
            )

        # 插入 single_purpose_map_cache 数据
        for record in single_purpose_records:
            cursor.execute(
                """
                INSERT INTO single_purpose_map_cache
                (id, app, title, app_description, category_id, sub_category_id, state, link_to_goal_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    record["id"],
                    record["app"],
                    record["title"],
                    record["app_description"],
                    record["category_id"],
                    record["sub_category_id"],
                    record["state"],
                    record["link_to_goal_id"],
                ),
            )

        conn.commit()

    return {
        "multi_purpose_records": multi_purpose_records,
        "single_purpose_records": single_purpose_records,
        "test_category_id": test_category_id,
        "test_sub_category_id": test_sub_category_id,
    }


@pytest.fixture(scope="function")
def use_cache_test_data(prepare_cache_test_data):
    """
    在测试函数中使用准备好的 cache 数据

    这个 fixture 确保数据在每个测试前都已准备好。
    """
    return prepare_cache_test_data
