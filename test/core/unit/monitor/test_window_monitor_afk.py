"""WindowMonitor AFK 判定单元测试

验证媒体播放时的 AFK 判定有上限，修复"全屏看视频/玩游戏时离开后时长无限积累"的 bug。

背景：
- 修复前：is_any_video_playing()=True 时永不判 AFK，离开期间时长无限积累
- 修复后：媒体播放时使用 afk_timeout_media（默认 3600s）作为 AFK 上限
- 非媒体场景仍使用 afk_timeout（默认 180s），不受 afk_timeout_media 影响
"""

import sys
from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.core


@pytest.fixture(autouse=True)
def mock_windows_api():
    """Mock windows_api 模块，避免 win32api 依赖"""
    mock_module = MagicMock()
    original = sys.modules.get("lifeprism.monitor.windows_monitor.windows_api")
    sys.modules["lifeprism.monitor.windows_monitor.windows_api"] = mock_module
    yield
    if original is not None:
        sys.modules["lifeprism.monitor.windows_monitor.windows_api"] = original
    else:
        sys.modules.pop("lifeprism.monitor.windows_monitor.windows_api", None)


def _make_monitor(monkeypatch, afk_timeout=180.0, afk_timeout_media=3600.0):
    """构造 WindowMonitor 实例，mock settings 注入测试配置值"""
    mock_settings = MagicMock()
    mock_settings.get.side_effect = lambda key, default=None: {
        "poll_time": 1.0,
        "exclude_titles": [],
        "afk_timeout": afk_timeout,
        "afk_timeout_media": afk_timeout_media,
    }.get(key, default)
    monkeypatch.setattr(
        "lifeprism.monitor.windows_monitor.monitor.settings", mock_settings
    )
    from lifeprism.monitor.windows_monitor.monitor import WindowMonitor

    return WindowMonitor(provider=MagicMock())


class TestWindowMonitorAfkMediaTimeout:
    """媒体播放时的 AFK 判定应有上限（修复核心）"""

    def test_media_playing_idle_exceeds_media_timeout_is_afk(self, monkeypatch):
        """媒体播放 + idle_time > afk_timeout_media → 应判 AFK

        修复前此场景会返回 False（永不 AFK），导致时长无限积累
        """
        monitor = _make_monitor(monkeypatch, afk_timeout_media=3600.0)
        assert monitor._compute_afk_state(idle_time=3601.0, video_playing=True) is True

    def test_media_playing_idle_below_media_timeout_not_afk(self, monkeypatch):
        """媒体播放 + idle_time < afk_timeout_media → 不应判 AFK"""
        monitor = _make_monitor(monkeypatch, afk_timeout_media=3600.0)
        assert monitor._compute_afk_state(idle_time=3000.0, video_playing=True) is False

    def test_media_playing_idle_equals_media_timeout_not_afk(self, monkeypatch):
        """媒体播放 + idle_time == afk_timeout_media → 不应判 AFK（> 判定）"""
        monitor = _make_monitor(monkeypatch, afk_timeout_media=3600.0)
        assert monitor._compute_afk_state(idle_time=3600.0, video_playing=True) is False


class TestWindowMonitorAfkBaseTimeout:
    """非媒体播放时仍使用基础 afk_timeout"""

    def test_no_media_idle_exceeds_base_timeout_is_afk(self, monkeypatch):
        """非媒体 + idle_time > afk_timeout → 应判 AFK"""
        monitor = _make_monitor(monkeypatch, afk_timeout=180.0)
        assert monitor._compute_afk_state(idle_time=181.0, video_playing=False) is True

    def test_no_media_idle_below_base_timeout_not_afk(self, monkeypatch):
        """非媒体 + idle_time < afk_timeout → 不应判 AFK"""
        monitor = _make_monitor(monkeypatch, afk_timeout=180.0)
        assert monitor._compute_afk_state(idle_time=179.0, video_playing=False) is False

    def test_no_media_ignores_media_timeout(self, monkeypatch):
        """非媒体时即使 idle > media_timeout 但 < afk_timeout 也不应判 AFK

        验证 media_timeout 不会反向影响非媒体场景
        """
        monitor = _make_monitor(monkeypatch, afk_timeout=180.0, afk_timeout_media=60.0)
        # media_timeout 故意设很小（60s），但非媒体场景不应受影响
        assert monitor._compute_afk_state(idle_time=100.0, video_playing=False) is False
