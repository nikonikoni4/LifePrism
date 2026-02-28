"""
全局测试配置
"""
import pytest
from lifeprism.storage.lw_table_manager import init_database


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """在所有测试开始前初始化数据库表（CREATE TABLE IF NOT EXISTS，幂等）"""
    init_database()
