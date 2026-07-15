"""
HeartbeatManager 单元测试

测试 seam:
- Seam 1: is_local_online() - 初始状态、在线判断、超时判断
- Seam 2: set_event() - offline 立即生效、online 重置状态
- Seam 3: update_heartbeat() - 更新心跳、覆盖 offline（同步即在线）
- Seam 4: 线程安全 - 多线程并发调用不崩溃

参考: docs/specs/ 中 sync 相关规格
"""

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: is_local_online() ====================


def test_is_local_online_initial_state_online():
    """初始状态：默认假定本地在线（15 分钟窗口等待首次同步）"""
    # Arrange
    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()

    # Act
    result = manager.is_local_online()

    # Assert
    assert result is True


def test_is_local_online_true_after_update_heartbeat():
    """update_heartbeat() 后：心跳已更新，返回 True"""
    # Arrange
    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()

    # Act
    manager.update_heartbeat()
    result = manager.is_local_online()

    # Assert
    assert result is True


def test_is_local_online_false_after_timeout():
    """超过 15 分钟（900 秒）超时后返回 False"""
    # Arrange
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch

    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()
    base_time = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    timeout_time = base_time + timedelta(seconds=901)

    # Act: 模拟时间流逝
    with patch("lifeprism.sync.heartbeat_manager.datetime") as mock_datetime:
        # 第一次调用 datetime.now(timezone.utc) -> update_heartbeat 记录 base_time
        mock_datetime.now.return_value = base_time
        manager.update_heartbeat()

        # 第二次调用 datetime.now(timezone.utc) -> is_local_online 检查时已超时
        mock_datetime.now.return_value = timeout_time
        result = manager.is_local_online()

    # Assert
    assert result is False


# ==================== Seam 2: set_event() ====================


def test_set_event_offline_immediately_false():
    """set_event("offline") 后立即返回 False（不等超时）"""
    # Arrange
    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()
    manager.update_heartbeat()  # 先确保在线

    # Act
    manager.set_event("offline")
    result = manager.is_local_online()

    # Assert
    assert result is False


def test_set_event_online_resets_state():
    """set_event("online") 重置状态为在线"""
    # Arrange
    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()
    manager.set_event("offline")  # 先离线
    assert manager.is_local_online() is False  # 确认离线

    # Act
    manager.set_event("online")
    result = manager.is_local_online()

    # Assert
    assert result is True


# ==================== Seam 3: update_heartbeat() 覆盖 offline ====================


def test_update_heartbeat_overrides_offline_event():
    """offline 后调用 update_heartbeat() 恢复在线（同步即在线）"""
    # Arrange
    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()
    manager.set_event("offline")  # 显式离线
    assert manager.is_local_online() is False  # 确认离线

    # Act: 同步请求到达，证明本地在线，清除 offline
    manager.update_heartbeat()
    result = manager.is_local_online()

    # Assert: 恢复在线（同步即在线）
    assert result is True


# ==================== Seam 4: 线程安全 ====================


def test_thread_safety_no_crash():
    """多线程并发调用 update_heartbeat / is_local_online / set_event 不崩溃"""
    # Arrange
    import threading

    from lifeprism.sync.heartbeat_manager import HeartbeatManager

    manager = HeartbeatManager()
    errors = []

    def worker():
        try:
            for _ in range(100):
                manager.update_heartbeat()
                manager.is_local_online()
                manager.set_event("online")
        except Exception as e:
            errors.append(e)

    # Act: 启动 10 个线程并发调用
    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Assert: 无异常发生
    assert len(errors) == 0
