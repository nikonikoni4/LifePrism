# Windows Monitor Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 `windows_monitor` 采集逻辑深度集成到 LifeWatch-AI 系统中，通过 `settings` 切换监控模式，并在服务器启动时自动拉起多进程监控任务。

**Architecture:** 
- 数据存储：在主数据库 `lifeprism.db` 中新增 `window_events` 表，通过 `LWWindowDataProvider` 统一管理。
- 监控逻辑：重构 `windows_monitor` 模块，剥离其自身的存储逻辑，改为调用主系统的 Provider。
- 生命周期：服务器 `lifespan` 钩子负责根据配置启动/停止监控子进程。

**Tech Stack:** Python, FastAPI, SQLite, Multiprocessing.

---

### Task 1: 数据库配置与表定义

**Files:**
- Modify: `lifeprism/config/database.py`

- [ ] **Step 1: 编写失败测试**

```python
from lifeprism.config.database import TABLE_CONFIGS
def test_window_events_config_exists():
    assert "window_events" in TABLE_CONFIGS
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `pytest tests/config/test_database.py` (如果文件不存在先创建)
Expected: FAIL with `AssertionError` (key "window_events" not found).

- [ ] **Step 3: 实现配置**

在 `lifeprism/config/database.py` 中添加：
```python
WINDOW_EVENTS_CONFIG = {
    'table_name': 'window_events',
    'columns': {
        'id': {
            'type': 'INTEGER',
            'constraints': ['PRIMARY KEY', 'AUTOINCREMENT'],
            'comment': '唯一标识符'
        },
        'timestamp': {
            'type': 'TEXT',
            'constraints': ['NOT NULL'],
            'comment': '事件开始时间 (ISO格式)'
        },
        'duration': {
            'type': 'REAL',
            'constraints': ['NOT NULL'],
            'comment': '持续秒数'
        },
        'app': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '应用程序名称'
        },
        'title': {
            'type': 'TEXT',
            'constraints': [],
            'comment': '窗口标题'
        }
    },
    'indexes': [
        {'name': 'idx_window_events_timestamp', 'columns': ['timestamp']}
    ],
    'timestamps': True
}

# 并将其加入 TABLE_CONFIGS 字典
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/config/test_database.py`

- [ ] **Step 5: Commit**

```bash
git add lifeprism/config/database.py
git commit -m "feat(config): add window_events table configuration"
```

### Task 2: 实现 Window Data Provider

**Files:**
- Create: `lifeprism/repository/providers/window_data_provider.py`
- Modify: `lifeprism/repository/__init__.py`

- [ ] **Step 1: 编写 TDD 测试**

在 `tests/repository/test_window_provider.py` 中编写 `save_event` 的测试。

- [ ] **Step 2: 实现 LWWindowDataProvider**

```python
from lifeprism.repository.base_providers import LWBaseDataProvider
class LWWindowDataProvider(LWBaseDataProvider):
    def save_event(self, timestamp, duration, app, title):
        sql = "INSERT INTO window_events (timestamp, duration, app, title) VALUES (?, ?, ?, ?)"
        self.db.execute_non_query(sql, (timestamp, duration, app, title))
```

- [ ] **Step 3: 验证并 Commit**

### Task 3: 重构 Monitor 模块

**Files:**
- Modify: `lifeprism/monitor/windows_monitor/*.py`

- [ ] **Step 1: 批量更新导入路径**
将所有相对导入改为 `lifeprism.monitor.windows_monitor` 开头的绝对导入。
- [ ] **Step 2: 注入 Provider 替换本地 repository**
修改 `WindowMonitor.__init__` 接受 `LWWindowDataProvider` 实例。
- [ ] **Step 3: 移除冗余文件**
删除 `monitor/windows_monitor/repository.py` 和 `config.py`。

### Task 4: 服务器集成与多进程管理

**Files:**
- Modify: `lifeprism/config/settings_manager.py`
- Modify: `lifeprism/server/main.py`

- [ ] **Step 1: 增加 monitor_type 设置**
- [ ] **Step 2: 实现进程拉起逻辑**
在 `main.py` 的 `lifespan` 钩子中：
```python
if settings.monitor_type == "lifeprism":
    from lifeprism.monitor.windows_monitor.main import start_monitor_process
    monitor_process = start_monitor_process()
```
- [ ] **Step 3: 信号处理与资源回收**
确保 `monitor_process.terminate()` 在退出时被调用。

### Task 5: 最终验证与清理

- [ ] **Step 1: 运行完整系统测试**
- [ ] **Step 2: 验证数据库迁移脚本**
- [ ] **Step 3: Commit 最终集成代码**

🤖 Generated with [Claude Code](https://claude.com/claude-code)