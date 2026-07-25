"""GlobalTaskState 单元测试

验证全局任务状态互斥机制的核心行为：
- 三态枚举的获取与释放
- 阻塞等待 + 超时返回
- 跨线程 notify 唤醒
- 并发只有一个成功

参考 ADR docs/adr/2026-07-25-global-task-state.md
"""

import threading
import time

import pytest

from lifeprism.server.services.global_task_state import (
    GlobalTaskState,
    TaskState,
)

pytestmark = pytest.mark.core


@pytest.fixture
def state():
    """每个测试用例独立的 GlobalTaskState 实例（避免单例污染）"""
    return GlobalTaskState()


# ==================== 基本获取与释放 ====================


class TestTryAcquire:
    """try_acquire 基本行为测试"""

    def test_try_acquire_idle_returns_true(self, state):
        """IDLE 状态下获取成功"""
        assert state.try_acquire(TaskState.LOCAL_TASK, 0) is True
        assert state.current_state == TaskState.LOCAL_TASK

    def test_try_acquire_cloud_sync_returns_true(self, state):
        """获取 CLOUD_SYNC 也能成功"""
        assert state.try_acquire(TaskState.CLOUD_SYNC, 0) is True
        assert state.current_state == TaskState.CLOUD_SYNC

    def test_try_acquire_blocked_returns_false(self, state):
        """非 IDLE 状态下 timeout=0 立即返回 False"""
        state.try_acquire(TaskState.LOCAL_TASK, 0)
        # 已被 LOCAL_TASK 占用，CLOUD_SYNC 获取失败
        assert state.try_acquire(TaskState.CLOUD_SYNC, 0) is False
        assert state.current_state == TaskState.LOCAL_TASK  # 状态不变

    def test_try_acquire_timeout_zero_immediate_return(self, state):
        """timeout=0 不阻塞，立即返回"""
        state.try_acquire(TaskState.CLOUD_SYNC, 0)
        start = time.monotonic()
        result = state.try_acquire(TaskState.LOCAL_TASK, 0)
        elapsed = time.monotonic() - start
        assert result is False
        assert elapsed < 0.1  # 应立即返回

    def test_try_acquire_timeout_returns_false(self, state):
        """超时后返回 False"""
        state.try_acquire(TaskState.CLOUD_SYNC, 0)
        start = time.monotonic()
        result = state.try_acquire(TaskState.LOCAL_TASK, 0.3)
        elapsed = time.monotonic() - start
        assert result is False
        assert 0.3 <= elapsed < 0.5  # 等待约 0.3 秒后超时


class TestRelease:
    """release 行为测试"""

    def test_release_resets_to_idle(self, state):
        """release 后状态重置为 IDLE"""
        state.try_acquire(TaskState.LOCAL_TASK, 0)
        state.release()
        assert state.current_state == TaskState.IDLE

    def test_release_allows_reacquire(self, state):
        """release 后可再次获取"""
        state.try_acquire(TaskState.LOCAL_TASK, 0)
        state.release()
        assert state.try_acquire(TaskState.CLOUD_SYNC, 0) is True

    def test_release_when_idle_is_noop(self, state):
        """IDLE 状态下 release 不报错（幂等）"""
        state.release()
        assert state.current_state == TaskState.IDLE


# ==================== 跨线程 notify 唤醒 ====================


class TestNotifyWaiters:
    """release 唤醒等待线程测试"""

    def test_release_notifies_waiter(self, state):
        """release 唤醒等待的线程"""
        state.try_acquire(TaskState.CLOUD_SYNC, 0)

        result = {"acquired": None}

        def waiter():
            result["acquired"] = state.try_acquire(TaskState.LOCAL_TASK, 2.0)

        t = threading.Thread(target=waiter)
        t.start()

        # 等待 waiter 进入 wait 状态
        time.sleep(0.1)
        state.release()  # 唤醒 waiter

        t.join(timeout=1.0)
        assert result["acquired"] is True
        assert state.current_state == TaskState.LOCAL_TASK

    def test_multiple_waiters_all_notified(self, state):
        """notify_all 唤醒所有等待者（但只有一个能获取）"""
        state.try_acquire(TaskState.CLOUD_SYNC, 0)

        results = {"w1": None, "w2": None, "w3": None}

        def waiter(name):
            results[name] = state.try_acquire(TaskState.LOCAL_TASK, 2.0)

        threads = [threading.Thread(target=waiter, args=(f"w{i}",)) for i in range(1, 4)]
        for t in threads:
            t.start()

        time.sleep(0.1)
        state.release()

        for t in threads:
            t.join(timeout=2.0)

        # 三个等待者中只有一个能获取成功
        acquired_count = sum(1 for v in results.values() if v is True)
        assert acquired_count == 1
        # 最终状态是 LOCAL_TASK（被成功获取的那个线程设置的）
        assert state.current_state == TaskState.LOCAL_TASK


# ==================== 并发获取只有一个成功 ====================


class TestConcurrentAcquire:
    """并发场景测试"""

    def test_concurrent_acquire_only_one_wins(self, state):
        """多线程并发获取，只有一个成功"""
        results = []
        lock = threading.Lock()

        def worker():
            r = state.try_acquire(TaskState.LOCAL_TASK, 0)
            with lock:
                results.append(r)

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) == 1  # 只有一个 True
        assert state.current_state == TaskState.LOCAL_TASK

    def test_acquire_release_then_other_acquires(self, state):
        """A 获取后释放，B 能获取"""
        assert state.try_acquire(TaskState.LOCAL_TASK, 0) is True

        result_b = {"got": None}

        def worker():
            result_b["got"] = state.try_acquire(TaskState.CLOUD_SYNC, 2.0)

        t = threading.Thread(target=worker)
        t.start()

        time.sleep(0.1)
        state.release()
        t.join(timeout=1.0)

        assert result_b["got"] is True
        assert state.current_state == TaskState.CLOUD_SYNC


# ==================== 边界条件 ====================


class TestEdgeCases:
    """边界条件测试"""

    def test_acquire_after_release_after_timeout(self, state):
        """超时后再 release，新获取能成功"""
        state.try_acquire(TaskState.CLOUD_SYNC, 0)
        # 第一次获取超时
        assert state.try_acquire(TaskState.LOCAL_TASK, 0.1) is False
        # release 后重新获取
        state.release()
        assert state.try_acquire(TaskState.LOCAL_TASK, 0) is True

    def test_reacquire_same_state_after_release(self, state):
        """release 后可以再次获取相同的状态"""
        state.try_acquire(TaskState.LOCAL_TASK, 0)
        state.release()
        # 同一线程可以再次获取 LOCAL_TASK
        assert state.try_acquire(TaskState.LOCAL_TASK, 0) is True
        assert state.current_state == TaskState.LOCAL_TASK

    def test_current_state_thread_safe(self, state):
        """current_state 是线程安全的只读属性"""
        state.try_acquire(TaskState.LOCAL_TASK, 0)

        states = []

        def reader():
            for _ in range(10):
                states.append(state.current_state)
                time.sleep(0.001)

        t = threading.Thread(target=reader)
        t.start()
        t.join()

        # 所有读取都应是 LOCAL_TASK（未被 release）
        assert all(s == TaskState.LOCAL_TASK for s in states)
