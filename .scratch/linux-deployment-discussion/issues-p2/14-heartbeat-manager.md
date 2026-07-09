# 心跳状态管理器

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 消息路由与本地在线判断

---

## What to build

实现云端心跳状态管理器（`HeartbeatManager`），用于判断本地是否在线，解决微信消息群发导致的重复回复问题。

**问题背景**：微信消息会群发到本地和云端两个后端，如果两端都处理会导致用户收到 2 条相同回复。需要云端判断本地是否在线，在线时跳过处理，离线时接管。

**设计要求**：
- 纯内存状态管理（不使用数据库，云端服务长期运行）
- 线程安全（多个请求可能并发访问）
- 支持显式 offline 事件（本地正常关闭时立即生效）
- 超时判断：15 分钟（10 分钟同步间隔 + 5 分钟容错）

**实现端到端**：

1. 新增 `lifeprism/sync/heartbeat_manager.py`：

```python
from datetime import datetime
from threading import Lock

class HeartbeatManager:
    """本地在线状态管理（纯内存）"""
    def __init__(self):
        self._last_heartbeat: datetime | None = None
        self._last_event: str | None = None  # 'online' | 'offline'
        self._lock = Lock()
    
    def update_heartbeat(self):
        """更新心跳时间（每次 sync/pull 时调用）"""
        with self._lock:
            self._last_heartbeat = datetime.now()
    
    def set_event(self, event: str):
        """设置生命周期事件（'online' | 'offline'）"""
        with self._lock:
            self._last_event = event
            self._last_heartbeat = datetime.now()
    
    def is_local_online(self) -> bool:
        """判断本地是否在线"""
        with self._lock:
            if self._last_event == "offline":
                return False  # 显式 offline
            if self._last_heartbeat is None:
                return False  # 从未连接
            elapsed = (datetime.now() - self._last_heartbeat).total_seconds()
            return elapsed < 900  # 15 分钟 = 900 秒

# 单例
heartbeat_manager = HeartbeatManager()
```

2. 在 `lifeprism/sync/__init__.py` 中导出单例
3. 单元测试（`test/unit/sync/test_heartbeat_manager.py`）：
   - 初始状态为离线
   - update_heartbeat() 后在线
   - 超时后离线
   - 显式 offline 事件立即生效
   - 线程安全

---

## Acceptance criteria

- [ ] `HeartbeatManager` 类实现完整
- [ ] 单例 `heartbeat_manager` 可导入使用
- [ ] `is_local_online()` 初始状态返回 `False`
- [ ] `update_heartbeat()` 调用后 `is_local_online()` 返回 `True`
- [ ] 超过 15 分钟后 `is_local_online()` 返回 `False`
- [ ] `set_event("offline")` 后立即返回 `False`（不等超时）
- [ ] `set_event("online")` 重置状态
- [ ] 线程安全测试通过（并发调用不崩溃）
- [ ] 日志记录：状态变化时记录 DEBUG 级别日志

---

## Blocked by

None - 可以立即开始
