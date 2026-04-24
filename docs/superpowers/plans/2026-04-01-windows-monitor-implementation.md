# Windows Monitor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移植 ActivityWatch 的窗口监控功能到 `lifeprism/monitor/windows-monitor`，实现独立运行、直接操作 SQLite 数据库以及高效的合并存储策略。

**Architecture:** 采用模块化设计，包括 Windows API 封装、SQLite 存储管理、核心监控逻辑和配置入口。不依赖 ActivityWatch 核心库，采用合并相同连续窗口的策略减少磁盘 I/O。

**Tech Stack:** Python, pywin32, WMI, sqlite3

---

### Task 1: 初始化项目结构与配置

**Files:**
- Create: `lifeprism/monitor/windows-monitor/config.py`
- Create: `lifeprism/monitor/windows-monitor/exceptions.py`

- [ ] **Step 1: 创建异常定义**
```python
class MonitorError(Exception): pass
class FatalError(MonitorError): pass
```
- [ ] **Step 2: 创建配置逻辑**
复刻 `aw_watcher_window/config.py` 的核心配置项，移除 macOS 相关项。
```python
def get_default_config():
    return {
        "poll_time": 1.0,
        "exclude_titles": [],
        "db_path": "window_activity.db"
    }
```
- [ ] **Step 3: 提交代码**
```bash
git add lifeprism/monitor/windows-monitor/config.py lifeprism/monitor/windows-monitor/exceptions.py
git commit -m "feat(monitor): init config and exceptions"
```

### Task 2: 实现 Windows API 封装

**Files:**
- Create: `lifeprism/monitor/windows-monitor/windows_api.py`

- [ ] **Step 1: 编写窗口获取逻辑**
从 `activitywatch/aw-watcher-window/aw_watcher_window/windows.py` 移植并精简。
```python
import win32gui, win32process, win32api, wmi, os
from typing import Optional

c = wmi.WMI()

def get_active_window_handle(): return win32gui.GetForegroundWindow()
def get_window_title(hwnd): return win32gui.GetWindowText(hwnd)

def get_app_name(hwnd):
    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        process = win32api.OpenProcess(0x0400, False, pid)
        path = win32process.GetModuleFileNameEx(process, 0)
        win32api.CloseHandle(process)
        return os.path.basename(path)
    except: return get_app_name_wmi(hwnd)

def get_app_name_wmi(hwnd):
    _, pid = win32process.GetWindowThreadProcessId(hwnd)
    for p in c.query(f"SELECT Name FROM Win32_Process WHERE ProcessId = {pid}"): return p.Name
    return "unknown"
```
- [ ] **Step 2: 编写测试脚本并运行**
- [ ] **Step 3: 提交代码**

### Task 3: 实现 SQLite 存储层

**Files:**
- Create: `lifeprism/monitor/windows-monitor/repository.py`

- [ ] **Step 1: 实现数据库初始化与插入**
```python
import sqlite3, json

class repository:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS window_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT, duration REAL, app TEXT, title TEXT
            )""")

    def save_event(self, timestamp, duration, app, title):
        self.conn.execute(
            "INSERT INTO window_events (timestamp, duration, app, title) VALUES (?, ?, ?, ?)",
            (timestamp, duration, app, title)
        )
        self.conn.commit()
```
- [ ] **Step 2: 验证数据写入**
- [ ] **Step 3: 提交代码**

### Task 4: 实现核心监控逻辑 (合并存储)

**Files:**
- Create: `lifeprism/monitor/windows-monitor/monitor.py`
- Create: `lifeprism/monitor/windows-monitor/main.py`

- [ ] **Step 1: 实现 Monitor 类**
实现轮询、窗口对比和时长计算。
- [ ] **Step 2: 实现 main 入口**
处理参数、日志和优雅退出 (SIGINT)。
- [ ] **Step 3: 综合测试**
运行程序并观察数据库记录。
- [ ] **Step 4: 提交代码**
