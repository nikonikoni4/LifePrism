"""
本地 API 职责分离集成测试（Issue #25）

测试 seam: lifeprism.server.main 的路由注册行为

职责分离约定：
- 云端 API（main_agent_only.py，端口 8101）提供 /api/sync/pull、/push、/pull-files、
  /push-files、/heartbeat，供本地调用。
- 本地 API（main.py）只提供状态查询和配置生成：
  GET /api/sync/status、POST /api/sync/trigger、POST /api/sync/generate-cloud-config。

本测试验证 main.py 创建的 FastAPI 应用不再注册云端同步端点，
同时保留本地状态查询与配置生成端点。

测试策略：直接检查 app.routes 中的路径列表（方式 1），
避免触发 main.py 的 lifespan（数据库初始化、AgentLoop、微信渠道等副作用）。
"""
import pytest

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture(scope="module")
def local_app_paths():
    """获取 main.py 创建的 FastAPI 应用的全部路由路径集合

    延迟导入 lifeprism.server.main.app，仅在 fixture 首次被请求时执行。
    module 作用域：整个测试模块只导入一次，避免重复加载 main.py 的重依赖。
    """
    from lifeprism.server.main import app

    return {route.path for route in app.routes}


# ==================== 云端同步端点不应在本地注册 ====================


def test_local_does_not_have_sync_pull_endpoint(local_app_paths):
    """本地不存在 /api/sync/pull 端点（该端点应由云端 main_agent_only.py 提供）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/pull" in paths

    # Assert
    assert exists is False


def test_local_does_not_have_sync_push_endpoint(local_app_paths):
    """本地不存在 /api/sync/push 端点（该端点应由云端提供）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/push" in paths

    # Assert
    assert exists is False


def test_local_does_not_have_sync_pull_files_endpoint(local_app_paths):
    """本地不存在 /api/sync/pull-files 端点（该端点应由云端提供）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/pull-files" in paths

    # Assert
    assert exists is False


def test_local_does_not_have_sync_push_files_endpoint(local_app_paths):
    """本地不存在 /api/sync/push-files 端点（该端点应由云端提供）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/push-files" in paths

    # Assert
    assert exists is False


def test_local_does_not_have_sync_heartbeat_endpoint(local_app_paths):
    """本地不存在 /api/sync/heartbeat 端点（该端点应由云端提供）

    注意：main.py 的 send_heartbeat() 会作为客户端调用云端的
    /api/sync/heartbeat，但本地本身不应注册该端点。
    """
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/heartbeat" in paths

    # Assert
    assert exists is False


# ==================== 本地状态查询与配置生成端点应保留 ====================


def test_local_has_sync_status_endpoint(local_app_paths):
    """本地保留 /api/sync/status 端点（同步状态查询）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/status" in paths

    # Assert
    assert exists is True


def test_local_has_sync_trigger_endpoint(local_app_paths):
    """本地保留 /api/sync/trigger 端点（手动触发同步）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/trigger" in paths

    # Assert
    assert exists is True


def test_local_has_generate_cloud_config_endpoint(local_app_paths):
    """本地保留 /api/sync/generate-cloud-config 端点（生成云端配置）"""
    # Arrange
    paths = local_app_paths

    # Act
    exists = "/api/sync/generate-cloud-config" in paths

    # Assert
    assert exists is True
