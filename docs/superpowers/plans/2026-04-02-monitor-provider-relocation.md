# Monitor Provider Relocation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Relocate and rename `LWWindowDataProvider` to `MonitorDataProvider` in the `monitor` module and update all references.

**Architecture:** Move the provider to its dedicated monitor sub-module, rename it for clarity, and update imports across repository, monitor, and test modules.

**Tech Stack:** Python, FastAPI, Pytest

---

### Task 1: Rename Class in Provider File

**Files:**
- Modify: `lifeprism/monitor/provider/window_data_provider.py`

- [ ] **Step 1: Update class name and docstrings**

```python
# Change LWWindowDataProvider to MonitorDataProvider
class MonitorDataProvider(LWBaseDataProvider):
    """
    窗口事件数据提供者 (Monitor 专用)
    """
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
```

- [ ] **Step 2: Commit**

```bash
git add lifeprism/monitor/provider/window_data_provider.py
git commit -m "refactor(monitor): rename LWWindowDataProvider to MonitorDataProvider"
```

### Task 2: Update repository Module Exports

**Files:**
- Modify: `lifeprism/repository/__init__.py`

- [ ] **Step 1: Remove old provider from repository init**

```python
# Remove these lines:
# from .providers.window_data_provider import LWWindowDataProvider
# "LWWindowDataProvider",
```

- [ ] **Step 2: Commit**

```bash
git add lifeprism/repository/__init__.py
git commit -m "refactor(repository): remove LWWindowDataProvider from repository exports"
```

### Task 3: Update Monitor Module References

**Files:**
- Modify: `lifeprism/monitor/windows_monitor/monitor.py`
- Modify: `lifeprism/monitor/windows_monitor/main.py`

- [ ] **Step 1: Update imports and usage in monitor.py**

```python
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
# ...
    def __init__(self, provider: MonitorDataProvider):
```

- [ ] **Step 2: Update imports and usage in main.py**

```python
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
# ...
    provider = MonitorDataProvider()
```

- [ ] **Step 3: Commit**

```bash
git add lifeprism/monitor/windows_monitor/monitor.py lifeprism/monitor/windows_monitor/main.py
git commit -m "refactor(monitor): update references to MonitorDataProvider"
```

### Task 4: Update Tests and Verify

**Files:**
- Modify: `test/integration/test_monitor_flow.py`
- Modify: `test/repository/test_window_provider.py`

- [ ] **Step 1: Update test/integration/test_monitor_flow.py**

```python
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
# ...
        self.provider = MonitorDataProvider(db_manager=self.db_manager)
```

- [ ] **Step 2: Update test/repository/test_window_provider.py**

```python
from lifeprism.monitor.provider.window_data_provider import MonitorDataProvider
# ...
class TestMonitorDataProvider(unittest.TestCase):
    def setUp(self):
        self.provider = MonitorDataProvider(db_manager=self.db_manager)
```

- [ ] **Step 3: Run tests**

Run: `pytest test/integration/test_monitor_flow.py test/repository/test_window_provider.py`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add test/integration/test_monitor_flow.py test/repository/test_window_provider.py
git commit -m "test: update monitor provider tests"
```
