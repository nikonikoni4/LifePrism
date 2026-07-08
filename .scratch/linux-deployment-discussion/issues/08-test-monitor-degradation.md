# 测试 - Monitor 降级

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建单元测试，验证 Monitor 模块在非 Windows 平台上的降级行为是否正确。

创建 `test/core/unit/monitor/test_monitor_platform_check.py`，包含以下测试用例：

1. `test_monitor_import_fails_gracefully_on_linux`
   - 验证 Linux 平台上 Monitor 导入失败不会导致程序崩溃
   - Mock `sys.platform` 返回 `"linux"`
   - 验证能捕获 ImportError 并继续运行

2. `test_monitor_type_ignored_on_non_windows`
   - 验证非 Windows 平台忽略 `monitor_type` 配置
   - Mock `sys.platform` 和配置
   - 验证即使 `monitor_type == "lifeprism"` 也不启动 Monitor

3. `test_monitor_startup_warning_logged`
   - 验证 Linux 上尝试启动 Monitor 时记录 warning 日志
   - Mock `sys.platform` 和 logger
   - 验证日志内容包含平台信息和跳过原因

参考现有测试：`test/core/unit/monitor/` 下的 Monitor 测试。

## Acceptance criteria

- [ ] 所有测试用例实现完整
- [ ] 测试能验证 Monitor 在非 Windows 平台的降级行为
- [ ] 测试能验证 ImportError 被正确捕获
- [ ] 测试能验证 warning 日志记录
- [ ] 使用 Mock 隔离平台和依赖
- [ ] 测试独立运行，不依赖其他测试状态

## Blocked by

- `.scratch/linux-deployment-discussion/issues/01-monitor-platform-isolation.md`

## User stories covered

7. 作为开发者，我想在 Linux 开发环境下运行后端服务，以便使用 Linux 服务器进行开发和调试
