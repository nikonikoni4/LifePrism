"""SSH 隧道管理 API 集成测试

测试 seam:
- POST /api/v2/settings/ssh-tunnel/enable - 自动生成密钥对 + 派生公钥 + 保留已有私钥
- GET /api/v2/settings/ssh-tunnel/public-key - 派生公钥 / 无私钥返回空字符串
- POST /api/v2/settings/ssh-tunnel/test - 调用 SSHTunnel.test_connection()
- 路由仅在 full 模式注册（agent_only 模式不暴露）

使用最小化 FastAPI 应用测试 ssh_tunnel 路由，避免完整 app lifespan 的副作用。

Mock 策略:
- Mock settings.get_storage_key / set_storage_key（避免写入真实 keyring）
- Mock asyncssh.generate_private_key / import_private_key（避免真实密钥操作）
- Mock SSHTunnel.test_connection（避免真实 SSH 连接）

参考:
- Issue: .scratch/ssh-tunnel-integration/issues/04-ssh-tunnel-api.md
- PRD: .scratch/ssh-tunnel-integration/prd.md
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from lifeprism.server.errors import to_http_exception
from lifeprism.utils.exceptions import LWBaseError

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


def _create_test_app():
    """创建最小化 FastAPI 应用（仅包含 ssh_tunnel 路由 + 全局异常处理器）"""
    from lifeprism.server.api.ssh_tunnel_api import router as ssh_tunnel_router

    test_app = FastAPI()

    @test_app.exception_handler(LWBaseError)
    async def lw_base_error_handler(request: Request, exc: LWBaseError):
        http_exc = to_http_exception(exc)
        return JSONResponse(
            status_code=http_exc.status_code,
            content=http_exc.detail,
        )

    test_app.include_router(ssh_tunnel_router, prefix="/api/v2")
    return TestClient(test_app)


@pytest.fixture
def client():
    """创建测试客户端（包含 ssh_tunnel 路由）"""
    return _create_test_app()


def _make_mock_private_key(public_key_str: str = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockPublicKeyDataForTestOnly"):
    """构造 mock asyncssh 私钥对象

    Args:
        public_key_str: 公钥字符串（OpenSSH 格式，以 ssh-ed25519 开头）

    Returns:
        MagicMock 模拟 asyncssh 私钥对象
    """
    key = MagicMock()
    key.export_public_key.return_value = public_key_str.encode("utf-8")
    key.export_private_key.return_value = (
        b"-----BEGIN OPENSSH PRIVATE KEY-----\n"
        b"fake_private_key_data_for_test_only\n"
        b"-----END OPENSSH PRIVATE KEY-----\n"
    )
    return key


@pytest.fixture
def mock_no_private_key():
    """Mock keyring 中无私钥的场景

    - settings.get_storage_key("ssh_tunnel_private_key") 返回 None
    - settings.set_storage_key 不实际写入
    """
    with (
        patch(
            "lifeprism.server.api.ssh_tunnel_api.settings.get_storage_key",
            return_value=None,
        ) as mock_get,
        patch(
            "lifeprism.server.api.ssh_tunnel_api.settings.set_storage_key"
        ) as mock_set,
    ):
        yield mock_get, mock_set


@pytest.fixture
def mock_existing_private_key():
    """Mock keyring 中已有私钥的场景

    - settings.get_storage_key("ssh_tunnel_private_key") 返回 PEM 字符串
    - settings.set_storage_key 不应被调用（保留不覆盖）
    """
    existing_pem = (
        "-----BEGIN OPENSSH PRIVATE KEY-----\n"
        "existing_fake_private_key_data\n"
        "-----END OPENSSH PRIVATE KEY-----\n"
    )
    with (
        patch(
            "lifeprism.server.api.ssh_tunnel_api.settings.get_storage_key",
            return_value=existing_pem,
        ) as mock_get,
        patch(
            "lifeprism.server.api.ssh_tunnel_api.settings.set_storage_key"
        ) as mock_set,
    ):
        yield mock_get, mock_set, existing_pem


# ==================== POST /api/v2/settings/ssh-tunnel/enable ====================


class TestEnableEndpoint:
    """测试 POST /api/v2/settings/ssh-tunnel/enable 端点"""

    def test_enable_generates_new_keypair_when_no_private_key(
        self, client, mock_no_private_key
    ):
        """Seam 1: keyring 无私钥时自动生成 ed25519 密钥对 + 返回 is_new=true

        验证:
        - 调用 asyncssh.generate_private_key('ssh-ed25519')
        - 私钥写入 keyring（调用 set_storage_key）
        - 返回 is_new=true
        """
        mock_get, mock_set = mock_no_private_key
        mock_key = _make_mock_private_key()

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.asyncssh.generate_private_key",
            return_value=mock_key,
        ) as mock_generate:
            response = client.post("/api/v2/settings/ssh-tunnel/enable")

        assert response.status_code == 200
        data = response.json()
        assert data["is_new"] is True
        # 验证调用了 generate_private_key
        mock_generate.assert_called_once_with("ssh-ed25519")
        # 验证私钥写入 keyring
        mock_set.assert_called_once()
        args, _ = mock_set.call_args
        assert args[0] == "ssh_tunnel_private_key"

    def test_enable_keeps_existing_keypair_when_private_key_exists(
        self, client, mock_existing_private_key
    ):
        """Seam 2: keyring 已有私钥时保留不覆盖 + 返回 is_new=false

        验证:
        - 不调用 asyncssh.generate_private_key
        - 不调用 set_storage_key（保留不覆盖）
        - 返回 is_new=false
        """
        mock_get, mock_set, _ = mock_existing_private_key
        mock_key = _make_mock_private_key()

        with (
            patch(
                "lifeprism.server.api.ssh_tunnel_api.asyncssh.generate_private_key",
                return_value=mock_key,
            ) as mock_generate,
            patch(
                "lifeprism.server.api.ssh_tunnel_api.asyncssh.import_private_key",
                return_value=mock_key,
            ) as mock_import,
        ):
            response = client.post("/api/v2/settings/ssh-tunnel/enable")

        assert response.status_code == 200
        data = response.json()
        assert data["is_new"] is False
        # 验证未生成新密钥
        mock_generate.assert_not_called()
        # 验证未覆盖写入
        mock_set.assert_not_called()
        # 验证从已有私钥派生公钥（import_private_key 被调用）
        mock_import.assert_called_once()

    def test_enable_returns_public_key_with_correct_format(
        self, client, mock_no_private_key
    ):
        """Seam 3: 返回的公钥格式正确（以 'ssh-ed25519 ' 开头）

        验证:
        - 返回的 public_key 字段非空
        - public_key 以 'ssh-ed25519 ' 开头
        """
        mock_get, mock_set = mock_no_private_key
        expected_public_key = (
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIMockPublicKeyDataForTestOnly"
        )
        mock_key = _make_mock_private_key(public_key_str=expected_public_key)

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.asyncssh.generate_private_key",
            return_value=mock_key,
        ):
            response = client.post("/api/v2/settings/ssh-tunnel/enable")

        assert response.status_code == 200
        data = response.json()
        assert "public_key" in data
        assert data["public_key"].startswith("ssh-ed25519 ")
        assert data["public_key"] == expected_public_key


# ==================== GET /api/v2/settings/ssh-tunnel/public-key ====================


class TestPublicKeyEndpoint:
    """测试 GET /api/v2/settings/ssh-tunnel/public-key 端点"""

    def test_public_key_returns_derived_public_key_when_private_key_exists(
        self, client, mock_existing_private_key
    ):
        """Seam 1: keyring 有私钥时返回派生公钥

        验证:
        - 调用 asyncssh.import_private_key 从私钥派生公钥
        - 返回的 public_key 是从私钥派生而来
        """
        mock_get, mock_set, existing_pem = mock_existing_private_key
        expected_public_key = (
            "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIDerivedPublicKeyFromExisting"
        )
        mock_key = _make_mock_private_key(public_key_str=expected_public_key)

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.asyncssh.import_private_key",
            return_value=mock_key,
        ) as mock_import:
            response = client.get("/api/v2/settings/ssh-tunnel/public-key")

        assert response.status_code == 200
        data = response.json()
        assert data["public_key"] == expected_public_key
        # 验证从 keyring 读取的私钥被传给 import_private_key
        mock_import.assert_called_once_with(existing_pem)

    def test_public_key_returns_empty_string_when_no_private_key(
        self, client, mock_no_private_key
    ):
        """Seam 2: keyring 无私钥时返回空字符串（不抛错）

        验证:
        - 不抛出异常
        - 返回的 public_key 为空字符串
        - 不调用 asyncssh.import_private_key（无私钥可派生）
        """
        mock_get, mock_set = mock_no_private_key

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.asyncssh.import_private_key"
        ) as mock_import:
            response = client.get("/api/v2/settings/ssh-tunnel/public-key")

        assert response.status_code == 200
        data = response.json()
        assert data["public_key"] == ""
        # 验证未尝试导入私钥
        mock_import.assert_not_called()


# ==================== POST /api/v2/settings/ssh-tunnel/test ====================


class TestTestEndpoint:
    """测试 POST /api/v2/settings/ssh-tunnel/test 端点"""

    def test_test_endpoint_calls_ssh_tunnel_test_connection(self, client, mock_existing_private_key):
        """Seam 1: 调用 SSHTunnel.test_connection()（mock SSHTunnel.test_connection）

        验证:
        - 创建 SSHTunnel 实例时使用请求参数 + keyring 私钥
        - 调用 test_connection()
        """
        mock_get, mock_set, existing_pem = mock_existing_private_key
        mock_tunnel = MagicMock()
        mock_tunnel.test_connection = AsyncMock(
            return_value={
                "status": "ok",
                "remote_response": {"status": "healthy"},
            }
        )

        request_body = {
            "host": "example.com",
            "port": 22,
            "username": "testuser",
            "local_port": 8102,
            "remote_port": 8102,
        }

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.SSHTunnel",
            return_value=mock_tunnel,
        ) as mock_tunnel_cls:
            response = client.post(
                "/api/v2/settings/ssh-tunnel/test", json=request_body
            )

        assert response.status_code == 200
        # 验证 SSHTunnel 实例化参数
        mock_tunnel_cls.assert_called_once()
        _, kwargs = mock_tunnel_cls.call_args
        assert kwargs["host"] == "example.com"
        assert kwargs["port"] == 22
        assert kwargs["username"] == "testuser"
        assert kwargs["local_port"] == 8102
        assert kwargs["remote_port"] == 8102
        assert kwargs["private_key"] == existing_pem
        # 验证调用 test_connection
        mock_tunnel.test_connection.assert_awaited_once()

    def test_test_endpoint_returns_success_result(
        self, client, mock_existing_private_key
    ):
        """Seam 2: 返回测试结果（成功场景）

        验证:
        - 返回 test_connection 的成功结果（status=ok + remote_response）
        """
        mock_get, mock_set, _ = mock_existing_private_key
        success_result = {
            "status": "ok",
            "remote_response": {"status": "healthy", "service": "lifeprism-api"},
        }
        mock_tunnel = MagicMock()
        mock_tunnel.test_connection = AsyncMock(return_value=success_result)

        request_body = {
            "host": "example.com",
            "port": 22,
            "username": "testuser",
            "local_port": 8102,
            "remote_port": 8102,
        }

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.SSHTunnel",
            return_value=mock_tunnel,
        ):
            response = client.post(
                "/api/v2/settings/ssh-tunnel/test", json=request_body
            )

        assert response.status_code == 200
        data = response.json()
        assert data == success_result
        assert data["status"] == "ok"
        assert "remote_response" in data

    def test_test_endpoint_returns_failure_result(
        self, client, mock_existing_private_key
    ):
        """Seam 3: 返回测试结果（失败场景，如"密钥被拒绝"/"远程 8102 不可达"）

        验证:
        - 返回 test_connection 的失败结果（status=error + error + code）
        - 不抛异常到 API 层（错误已由 test_connection 内部捕获并结构化返回）
        """
        mock_get, mock_set, _ = mock_existing_private_key
        failure_result = {
            "status": "error",
            "error": "SSH 密钥被拒绝，请检查私钥是否正确以及云端 authorized_keys 是否配置",
            "code": "SSH_KEY_REJECTED",
        }
        mock_tunnel = MagicMock()
        mock_tunnel.test_connection = AsyncMock(return_value=failure_result)

        request_body = {
            "host": "example.com",
            "port": 22,
            "username": "testuser",
            "local_port": 8102,
            "remote_port": 8102,
        }

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.SSHTunnel",
            return_value=mock_tunnel,
        ):
            response = client.post(
                "/api/v2/settings/ssh-tunnel/test", json=request_body
            )

        assert response.status_code == 200
        data = response.json()
        assert data == failure_result
        assert data["status"] == "error"
        assert "密钥被拒绝" in data["error"]
        assert data["code"] == "SSH_KEY_REJECTED"

    def test_test_endpoint_no_orphan_process(self, client, mock_existing_private_key):
        """Seam 4: 不留孤儿进程（test_connection 内部关闭连接）

        验证:
        - SSHTunnel.test_connection() 内部已完成 close()（参考 ssh_tunnel.py 实现）
        - API 层不再额外调用 close()（避免重复关闭）
        """
        mock_get, mock_set, _ = mock_existing_private_key
        mock_tunnel = MagicMock()
        mock_tunnel.test_connection = AsyncMock(
            return_value={"status": "ok", "remote_response": {}}
        )
        mock_tunnel.close = AsyncMock()

        request_body = {
            "host": "example.com",
            "port": 22,
            "username": "testuser",
            "local_port": 8102,
            "remote_port": 8102,
        }

        with patch(
            "lifeprism.server.api.ssh_tunnel_api.SSHTunnel",
            return_value=mock_tunnel,
        ):
            response = client.post(
                "/api/v2/settings/ssh-tunnel/test", json=request_body
            )

        assert response.status_code == 200
        # test_connection 内部已关闭连接，API 层不应再次调用 close()
        mock_tunnel.test_connection.assert_awaited_once()
        mock_tunnel.close.assert_not_called()


# ==================== 路由注册（run_mode 守卫） ====================


class TestRouteRegistration:
    """测试 SSH 隧道管理 API 路由注册的 run_mode 守卫

    验证:
    - main.py（full 模式）注册 ssh_tunnel_router
    - main_agent_only.py（agent_only 模式）不注册 ssh_tunnel_router
    """

    def test_ssh_tunnel_routes_registered_in_full_mode(self):
        """Seam 1: main.py（full 模式）注册 SSH 隧道管理 API 路由

        验证 main.py 创建的 FastAPI 应用包含三个 SSH 隧道管理端点。
        直接检查 app.routes，避免触发 lifespan 副作用。
        """
        from lifeprism.server.main import app

        paths = {route.path for route in app.routes}
        assert "/api/v2/settings/ssh-tunnel/enable" in paths, (
            "main.py（full 模式）应注册 POST /api/v2/settings/ssh-tunnel/enable"
        )
        assert "/api/v2/settings/ssh-tunnel/public-key" in paths, (
            "main.py（full 模式）应注册 GET /api/v2/settings/ssh-tunnel/public-key"
        )
        assert "/api/v2/settings/ssh-tunnel/test" in paths, (
            "main.py（full 模式）应注册 POST /api/v2/settings/ssh-tunnel/test"
        )

    def test_ssh_tunnel_routes_not_registered_in_agent_only_mode(self):
        """Seam 2: main_agent_only.py（agent_only 模式）不注册 SSH 隧道管理 API 路由

        通过检查 main_agent_only.py 源码不包含 ssh_tunnel_router 引用，
        确保云端不会暴露 SSH 隧道管理 API。
        """
        import inspect

        import lifeprism.server.main_agent_only as main_agent_only

        source = inspect.getsource(main_agent_only)
        assert "ssh_tunnel_router" not in source, (
            "main_agent_only.py（agent_only 模式）不应注册 ssh_tunnel_router"
        )
        assert "ssh-tunnel" not in source, (
            "main_agent_only.py（agent_only 模式）不应包含 ssh-tunnel 路由路径"
        )
