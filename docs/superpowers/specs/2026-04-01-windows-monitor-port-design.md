# Spec: Windows Monitor Port (aw-watcher-window)

## 1. 目标 (Objectives)
将 `activitywatch/aw-watcher-window` 的功能移植到 `lifeprism/monitor/windows-monitor`，作为一个独立的监控模块运行。该模块专注于 Windows 平台，不依赖 ActivityWatch 的核心库 (`aw-client`, `aw-core`)，直接操作本地 SQLite 数据库。

## 2. 核心架构 (Architecture)

### 2.1 模块结构
- `windows_api.py`: 封装 Windows 原生 API 调用 (`pywin32`, `WMI`)。
- `repository.py`: 数据库持久化逻辑，使用 `sqlite3`。
- `monitor.py`: 轮询逻辑、心跳检测与合并存储算法。
- `main.py`: 入口文件，处理命令行参数、日志配置和退出处理。
- `config.py`: 配置管理（默认值与配置文件）。

### 2.2 数据流
1. `monitor.py` 按 `poll_time` (默认 1s) 调用 `windows_api.py` 获取当前窗口信息。
2. 检查当前窗口是否在过滤列表 (`exclude_titles`) 中。
3. **合并存储策略**: 
   - 在内存中维护 `current_window` 和 `start_time`。
   - 如果新窗口与 `current_window` 相同，则累加时长。
   - 如果不同，则计算前一个窗口的 `duration`，调用 `repository.py` 写入数据库，并重置 `current_window`。
4. 程序退出前（收到 SIGINT/SIGTERM），强制刷盘最后一条记录。

## 3. 技术规范 (Technical Specifications)

### 3.1 数据库结构 (SQLite)
数据库路径: `lifeprism/monitor/windows-monitor/window_activity.db`
表名: `window_events`
| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | INTEGER | 主键 (AUTOINCREMENT) |
| timestamp | TEXT | ISO8601 格式 (UTC) |
| duration | REAL | 持续时间 (秒) |
| app | TEXT | 应用程序名称 (e.g., chrome.exe) |
| title | TEXT | 窗口标题 |

### 3.2 依赖项
- `pywin32`: 调用 `win32gui`, `win32process`, `win32api`。
- `WMI`: 作为获取应用名称的 Fallback 方案。
- `sqlite3`: 内置标准库。
- `logging`: 内置标准库，用于记录运行日志。

## 4. 关键算法: 合并存储 (Merge-on-Save)
```python
if new_window == current_window:
    # 相同窗口，继续等待下一次轮询
    pass
else:
    # 窗口切换
    duration = now - start_time
    save_to_db(current_window, start_time, duration)
    current_window = new_window
    start_time = now
```

## 5. 测试计划 (Test Plan)
1. **单元测试**: 
   - 测试 `windows_api.py` 是否能正确获取各种窗口（普通窗口、管理员权限窗口、UWP 应用）。
   - 测试 `repository.py` 的读写和初始化逻辑。
2. **集成测试**: 
   - 运行 `main.py`，在不同应用间切换，手动检查数据库是否按预期生成记录并正确计算 `duration`。
   - 检查正常退出后最后一条记录是否已存入。

## 6. 预期成果 (Expected Results)
- 实现一个能够全天候稳定运行的本地监控模块。
- 数据库格式精简，每条记录记录一次窗口停留时长。
- 无额外繁重依赖，易于集成到 LifeWatch-AI 后端项目中。

## 7. 安全与隐私 (Security & Privacy)
- 仅收集 `app` 和 `title`，不收集键盘按键、鼠标位置或屏幕截图。
- `exclude_titles` 可用于动态配置过滤不必要的敏感窗口记录。