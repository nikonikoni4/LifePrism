# Monitor 模块平台隔离

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

实现 Monitor 模块的延迟导入和平台检查，使其仅在 Windows 平台上启动，Linux 平台优雅降级。

修改 `lifeprism/server/main.py`：
1. 将 Monitor 模块的导入从文件顶部移到条件块内部
2. 增加平台检查：`if sys.platform != "win32"` 直接跳过 Monitor 启动
3. 增加 ImportError 捕获，当缺少 `pywin32` 等依赖时优雅降级
4. 记录 warning 级别日志，说明 Monitor 在非 Windows 平台被跳过

## Acceptance criteria

- [ ] Windows 平台上，当 `monitor_type == "lifeprism"` 时，Monitor 正常启动
- [ ] Linux 平台上，即使 `monitor_type == "lifeprism"`，Monitor 也被跳过，记录 warning 日志
- [ ] 缺少 `pywin32` 等依赖时，不会导致启动失败，而是记录 warning 并跳过
- [ ] 日志输出清晰说明 Monitor 被跳过的原因（平台或依赖缺失）

## Blocked by

None - can start immediately

## User stories covered

7. 作为开发者，我想在 Linux 开发环境下运行后端服务，以便使用 Linux 服务器进行开发和调试
