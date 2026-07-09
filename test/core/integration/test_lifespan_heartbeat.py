"""
生命周期心跳发送集成测试

测试 seam:
- send_heartbeat() 函数的行为：
  - online/offline 事件正确调用 API
  - 未配置时静默跳过
  - 网络失败不阻塞流程
  - 日志记录正确

send_heartbeat 使用 httpx.AsyncClient（异步），测试通过 patch
lifeprism.server.main.httpx.AsyncClient 模拟 async context manager。

参考: Issue #20 - 本地生命周期心跳发送
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.core


# ==================== 辅助函数 ====================


def _make_mock_response(status_code=200):
    """构建 mock httpx.Response 对象"""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _configure_async_client_mock(mock_async_client, response=None, side_effect=None):
    """配置已 patch 的 httpx.AsyncClient，使其表现为 async context manager。

    send_heartbeat 中的用法：
        async with httpx.AsyncClient() as client:
            response = await client.post(...)

    本函数将 mock_async_client 配置为：
    - mock_async_client() 返回一个 async context manager
    - async with 进入后得到 mock_client
    - await mock_client.post(...) 返回 response 或抛出 side_effect

    Args:
        mock_async_client: 已通过 patch 替换 httpx.AsyncClient 的 MagicMock
        response: client.post 返回的 mock 响应（与 side_effect 互斥）
        side_effect: client.post 抛出的异常（与 response 互斥）

    Returns:
        mock_post: client.post 的 AsyncMock，用于断言调用参数
    """
    mock_post = AsyncMock()
    if side_effect is not None:
        mock_post.side_effect = side_effect
    else:
        mock_post.return_value = response or _make_mock_response(status_code=200)

    # async with ... as client 暴露的 client 对象
    mock_client = MagicMock()
    mock_client.post = mock_post

    # httpx.AsyncClient() 返回的 async context manager
    mock_cm = AsyncMock()
    mock_cm.__aenter__.return_value = mock_client
    mock_cm.__aexit__.return_value = None

    mock_async_client.return_value = mock_cm
    return mock_post


# ==================== Seam: send_heartbeat() 行为 ====================


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test_key")
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_online_calls_api(mock_get_setting, mock_get_key, mock_async_client):
    """发送 online 事件时调用 POST /api/sync/heartbeat，请求体包含 {"event": "online"}"""
    # Arrange
    mock_get_setting.return_value = "https://remote.example.com"
    mock_post = _configure_async_client_mock(
        mock_async_client, response=_make_mock_response(status_code=200)
    )

    # Act
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("online")

    # Assert
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.kwargs["json"] == {"event": "online"}
    assert call_args.kwargs["url"] == "https://remote.example.com/api/sync/heartbeat"
    assert call_args.kwargs["headers"]["Authorization"] == "Bearer test_key"


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test_key")
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_offline_calls_api(mock_get_setting, mock_get_key, mock_async_client):
    """发送 offline 事件时调用 API，请求体包含 {"event": "offline"}"""
    # Arrange
    mock_get_setting.return_value = "https://remote.example.com"
    mock_post = _configure_async_client_mock(
        mock_async_client, response=_make_mock_response(status_code=200)
    )

    # Act
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("offline")

    # Assert
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.kwargs["json"] == {"event": "offline"}
    assert call_args.kwargs["url"] == "https://remote.example.com/api/sync/heartbeat"


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test_key")
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_skips_when_no_remote_url(
    mock_get_setting, mock_get_key, mock_async_client
):
    """未配置 remote_url 时跳过发送（不创建 AsyncClient）"""
    # Arrange
    mock_get_setting.return_value = None

    # Act
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("online")

    # Assert: AsyncClient 未被实例化（无网络请求）
    mock_async_client.assert_not_called()


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value=None)
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_skips_when_no_api_key(
    mock_get_setting, mock_get_key, mock_async_client
):
    """未配置 api_key 时跳过发送"""
    # Arrange
    mock_get_setting.return_value = "https://remote.example.com"

    # Act
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("online")

    # Assert: AsyncClient 未被实例化（无网络请求）
    mock_async_client.assert_not_called()


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test_key")
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_network_failure_does_not_raise(
    mock_get_setting, mock_get_key, mock_async_client
):
    """网络失败时不抛出异常（仅记录 WARNING）"""
    # Arrange
    mock_get_setting.return_value = "https://remote.example.com"
    _configure_async_client_mock(
        mock_async_client, side_effect=ConnectionError("Network unreachable")
    )

    # Act & Assert: 不应抛出异常
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("online")


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test_key")
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_logs_success(mock_get_setting, mock_get_key, mock_async_client, caplog):
    """成功发送时记录 INFO 日志"""
    # Arrange
    mock_get_setting.return_value = "https://remote.example.com"
    _configure_async_client_mock(
        mock_async_client, response=_make_mock_response(status_code=200)
    )
    caplog.set_level(logging.INFO, logger="lifeprism.server.main")

    # Act
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("online")

    # Assert
    assert any(
        "心跳事件已发送" in record.message and record.levelno == logging.INFO
        for record in caplog.records
    )


@patch("lifeprism.server.main.httpx.AsyncClient")
@patch("lifeprism.sync.sync_config.get_sync_api_key", return_value="test_key")
@patch("lifeprism.config.settings_manager.get_setting")
async def test_send_heartbeat_logs_warning_on_failure(
    mock_get_setting, mock_get_key, mock_async_client, caplog
):
    """失败时记录 WARNING 日志"""
    # Arrange
    mock_get_setting.return_value = "https://remote.example.com"
    _configure_async_client_mock(
        mock_async_client, side_effect=ConnectionError("Network unreachable")
    )
    caplog.set_level(logging.WARNING, logger="lifeprism.server.main")

    # Act
    from lifeprism.server.main import send_heartbeat

    await send_heartbeat("online")

    # Assert
    assert any(
        "心跳事件发送失败" in record.message and record.levelno == logging.WARNING
        for record in caplog.records
    )
