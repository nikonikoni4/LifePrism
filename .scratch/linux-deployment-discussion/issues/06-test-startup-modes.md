# 测试 - 启动入口

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建集成测试，验证三种启动模式的导入和启动行为是否正确。

创建 `test/integration/test_startup_modes.py`，包含以下测试用例：

1. `test_main_imports_monitor_on_windows`
   - 验证 Windows 平台上能正常导入 Monitor 模块
   - Mock `sys.platform` 返回 `"win32"`

2. `test_main_web_demo_no_monitor_import`
   - 验证 Web Demo 入口不导入 Monitor 模块
   - 检查模块的 import 语句

3. `test_main_agent_only_no_fastapi_import`
   - 验证 Agent Only 入口不导入 FastAPI
   - 检查模块的 import 语句

4. `test_web_demo_startup_completes`
   - 验证 Web Demo 能完整启动
   - Mock 必要的依赖（数据库、Agent）

5. `test_agent_only_startup_completes`
   - 验证 Agent Only 能完整启动
   - Mock 必要的依赖（数据库、Agent、WeChat Channel）

参考现有测试：`test/core/integration/` 下的集成测试结构。

## Acceptance criteria

- [ ] 所有测试用例实现完整
- [ ] 测试能在 Windows 和 Linux 上运行
- [ ] 使用 Mock 隔离外部依赖
- [ ] 测试独立运行，不依赖其他测试状态
- [ ] 测试通过验证各启动模式的预期行为

## Blocked by

- `.scratch/linux-deployment-discussion/issues/01-monitor-platform-isolation.md`
- `.scratch/linux-deployment-discussion/issues/02-linux-web-demo-entrypoint.md`
- `.scratch/linux-deployment-discussion/issues/03-linux-agent-only-entrypoint.md`

## User stories covered

7. 作为开发者，我想在 Linux 开发环境下运行后端服务，以便使用 Linux 服务器进行开发和调试
