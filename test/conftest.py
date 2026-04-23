"""
全局测试配置

设置测试环境变量，确保测试使用独立的数据库。
"""
import os
import pytest
from pathlib import Path
import shutil


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    设置测试环境变量

    使用项目内的临时目录作为测试数据路径，避免污染真实数据。
    """
    # 使用项目内的临时目录
    project_root = Path(__file__).parent.parent
    test_data_path = project_root / "test_temp_data"

    # 清理旧的测试数据
    if test_data_path.exists():
        shutil.rmtree(test_data_path, ignore_errors=True)

    test_data_path.mkdir(parents=True, exist_ok=True)

    original_value = os.environ.get("LIFEPRISM_DATA_PATH")

    # 设置测试环境变量
    os.environ["LIFEPRISM_DATA_PATH"] = str(test_data_path)

    yield test_data_path

    # 恢复原始环境变量
    if original_value is not None:
        os.environ["LIFEPRISM_DATA_PATH"] = original_value
    else:
        os.environ.pop("LIFEPRISM_DATA_PATH", None)

    # 清理测试数据（可选）
    # shutil.rmtree(test_data_path, ignore_errors=True)


@pytest.fixture(scope="session")
def test_data_path(setup_test_environment):
    """返回测试数据路径"""
    return setup_test_environment
