# spec-2026-04-01-windows-monitor-integration

## 1. 概述
将 `windows_monitor` 采集程序集成到 `lifeprism` 核心系统中，替代或补充 ActivityWatch 监控方式。实现数据源统一、配置统一和生命周期管理统一。

## 2. 核心架构设计

### 2.1 数据层 (Storage)
- **配置定义**: 在 `lifeprism/config/database.py` 中新增 `WINDOW_EVENTS_CONFIG`。
- **表结构**: `window_events` 表，包含 `id`, `timestamp`, `duration`, `app`, `title` 字段。
- **提供者**: 新建 `lifeprism/storage/providers/window_data_provider.py`，继承 `LWBaseDataProvider`，负责窗口事件的持久化。

### 2.2 监控层 (Monitor)
- **重构导入**: 统一使用 `lifeprism.monitor.windows_monitor` 作为前缀，消除相对引用风险。
- **解耦操作**: `WindowMonitor` 内部移除直接对 `sqlite3` 的调用，改为调用 `LWWindowDataProvider`。
- **配置获取**: 移除 `monitor/windows_monitor/config.py`，直接从 `lifeprism.config.settings_manager` 获取采样频率、AFK 超时等参数。

### 2.3 配置与路由 (Config & API)
- **全局配置**: `settings.yaml` 增加 `monitor_type` 字段，可选值为 `"aw"` (默认) 或 `"lifeprism"`。
- **API 支持**: 现有的 `settings` API 将支持对该字段的读写。

### 2.4 生命周期管理 (Server)
- **多进程启动**: 在 `lifeprism/server/main.py` 的 `lifespan` 钩子中，根据 `settings.monitor_type` 动态启动 `windows_monitor` 进程。
- **信号处理**: 确保在服务器关闭时，主进程能正确停止监控子进程，避免僵尸进程。

## 3. 实现步骤预览
1. 修改 `database.py` 增加表定义。
2. 在 `storage/providers/` 下实现 `LWWindowDataProvider`。
3. 重构 `windows_monitor` 目录下的所有导入路径和日志记录方式。
4. 修改 `settings_manager.py` 增加 `monitor_type` 字段及其默认值。
5. 在 `server/main.py` 中实现多进程启动逻辑。

## 4. 风险与测试建议
- **性能**: `window_events` 写入频率较高（通常 1s 一次），需观察主 DB 的写入压力及锁争用情况。
- **稳定性**: 跨进程资源共享需谨慎处理，特别是数据库连接的初始化应在子进程内部完成。
- **兼容性**: 确保不影响现有的 `aw_db_manager` 只读逻辑。

## 5. 验收标准
- [ ] `lifeprism.db` 成功创建 `window_events` 表。
- [ ] 切换配置至 `lifeprism` 后，服务器启动能自动拉起监控进程。
- [ ] 监控产生的数据能正确写入 `window_events` 表。
- [ ] 停止服务器时，监控进程能正常退出。

🤖 Generated with [Claude Code](https://claude.com/claude-code)