"""
Settings VLM API 测试

测试 POST /settings/test-vlm 接口
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from lifeprism.server.main import app


@pytest.mark.core
def test_test_vlm_success(monkeypatch):
    """测试 VLM 能力测试成功的情况"""
    from lifeprism.config import settings_manager

    # Mock test_connect 返回成功
    async def fake_test_connect():
        return {"success": True, "message": "连接成功"}

    # Mock test_vlm 返回成功
    async def fake_test_vlm():
        return {
            "success": True,
            "message": "VLM 图像理解测试成功",
            "model_response": "这是一张猫的图片",
        }

    # 捕获 settings.set 调用
    set_calls = {}
    original_set = settings_manager.settings.set

    def mock_set(key, value):
        set_calls[key] = value
        return original_set(key, value)

    monkeypatch.setattr("lifeprism.llm.function.test_connect.test_connect", fake_test_connect)
    monkeypatch.setattr("lifeprism.llm.function.test_vlm.test_vlm", fake_test_vlm)
    monkeypatch.setattr("lifeprism.config.settings_manager.settings.set", mock_set)

    client = TestClient(app)
    response = client.post("/api/v2/settings/test-vlm")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["is_vlm"] is True
    assert data["model_response"] == "这是一张猫的图片"
    assert data["cache_updated"] is True


@pytest.mark.core
def test_test_vlm_connection_failure(monkeypatch):
    """测试 VLM 能力测试 - 连接失败的情况"""

    async def fake_test_connect():
        return {"success": False, "message": "API Key 无效"}

    async def fake_test_vlm():
        return {"success": True, "message": "VLM 测试成功"}

    monkeypatch.setattr("lifeprism.llm.function.test_connect.test_connect", fake_test_connect)
    monkeypatch.setattr("lifeprism.llm.function.test_vlm.test_vlm", fake_test_vlm)

    client = TestClient(app)
    response = client.post("/api/v2/settings/test-vlm")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert "连接失败" in data["message"]
    assert data["is_vlm"] is False
    assert data["model_response"] is None


@pytest.mark.core
def test_test_vlm_vlm_test_failure(monkeypatch):
    """测试 VLM 能力测试 - VLM 测试本身失败的情况"""
    from lifeprism.config import settings_manager

    async def fake_test_connect():
        return {"success": True, "message": "连接成功"}

    async def fake_test_vlm():
        return {"success": False, "message": "该模型不支持图像理解"}

    # 捕获 settings.set 调用
    set_calls = {}
    original_set = settings_manager.settings.set

    def mock_set(key, value):
        set_calls[key] = value
        return original_set(key, value)

    monkeypatch.setattr("lifeprism.llm.function.test_connect.test_connect", fake_test_connect)
    monkeypatch.setattr("lifeprism.llm.function.test_vlm.test_vlm", fake_test_vlm)
    monkeypatch.setattr("lifeprism.config.settings_manager.settings.set", mock_set)

    client = TestClient(app)
    response = client.post("/api/v2/settings/test-vlm")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is False
    assert data["is_vlm"] is False
    assert data["cache_updated"] is True  # 失败也会写入缓存


@pytest.mark.core
def test_test_vlm_updates_is_vlm_cache(monkeypatch):
    """测试 VLM 能力测试后 is_vlm 缓存被正确更新"""
    from lifeprism.config import settings_manager

    async def fake_test_connect():
        return {"success": True, "message": "连接成功"}

    async def fake_test_vlm():
        return {"success": True, "message": "VLM 测试成功"}

    # 捕获 settings.get 和 settings.set 调用
    get_calls = {}
    set_calls = {}
    original_get = settings_manager.settings.get
    original_set = settings_manager.settings.set

    def mock_get(key, default=None):
        get_calls[key] = original_get(key, default)
        return get_calls[key]

    def mock_set(key, value):
        set_calls[key] = value
        return original_set(key, value)

    monkeypatch.setattr("lifeprism.llm.function.test_connect.test_connect", fake_test_connect)
    monkeypatch.setattr("lifeprism.llm.function.test_vlm.test_vlm", fake_test_vlm)
    monkeypatch.setattr("lifeprism.config.settings_manager.settings.get", mock_get)
    monkeypatch.setattr("lifeprism.config.settings_manager.settings.set", mock_set)

    client = TestClient(app)
    response = client.post("/api/v2/settings/test-vlm")
    assert response.status_code == 200

    # 验证 is_vlm 缓存被更新
    assert "is_vlm" in set_calls
    assert isinstance(set_calls["is_vlm"], dict)


@pytest.mark.core
def test_test_vlm_exception_handling(monkeypatch):
    """测试 VLM 能力测试 - 异常处理"""

    async def fake_test_connect_exception():
        raise RuntimeError("网络错误")

    monkeypatch.setattr(
        "lifeprism.llm.function.test_connect.test_connect", fake_test_connect_exception
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/api/v2/settings/test-vlm")
    assert response.status_code == 500
