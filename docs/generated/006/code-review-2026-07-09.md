# Code Review Report

**审查范围**: Issue #12 同步状态 UI（后端 API + 前端组件 + 测试）
**审查时间**: 2026-07-09 14:23
**变更文件**:
- `lifeprism/server/api/sync_status_api.py` (新增)
- `lifeprism/repository/sync_repository.py` (新增 count_rows 方法)
- `lifeprism/server/main.py` (lifespan 中创建 SyncClient)
- `lifeprism/server/api/__init__.py` (导出路由)
- `frontend/apps/settings/components/SyncStatusSection.tsx` (新增)
- `frontend/apps/settings/syncApi.ts` (新增方法)
- `frontend/apps/settings/syncTypes.ts` (新增类型)
- `frontend/apps/settings/syncUtils.ts` (新增)
- `frontend/apps/settings/SettingsApp.tsx` (集成组件)
- `frontend/apps/settings/index.ts` (导出)
- `test/core/integration/api/test_sync_status_api.py` (新增)
- `frontend/apps/settings/syncStatusApi.test.ts` (新增)
- `frontend/apps/settings/components/SyncStatusSection.test.tsx` (新增)

## 架构上下文

### 相关 ADR
- `2026-07-09-sync-atomicity-strategy.md`: 同步原子性策略 (decided)
- `2026-07-09-rest-polling-communication.md`: REST 轮询通信架构 (decided)
- `2026-07-09-lww-conflict-resolution.md`: LWW 冲突解决 (decided)

### 相关编码规范
- `docs/coding-rules/backend-api-rules.md`: API 层不使用 try/except
- `docs/coding-rules/backend-core-rules.md`: 4.3 命名约定（`_` 前缀=私有）、第 5 节异常处理、第 7 节单例原则
- `docs/coding-rules/backend-error-handling.md`: 错误处理分层

### 决策覆盖
- 8/13 变更文件有 ADR 关联
- 后端 API 层符合"不直接编写 SQL"规范（通过 SyncRepository）

## 审查结果

Found 13 issues:

### Issue 1: trigger_sync 存在 check-then-set 竞态条件（TOCTOU）
- **类型**: Architecture / Security
- **置信度**: 92
- **位置**: `lifeprism/server/api/sync_status_api.py:92-102`
- **详情**: 第 92 行 `if sync_client._is_syncing` 检查与第 102 行 `sync_client._is_syncing = True` 设置之间是非原子的。两个并发的 `POST /api/sync/trigger` 请求（或手动触发 + 定时同步）可同时通过检查、同时启动后台线程，导致并发执行 `sync_once`。并发同步会重复处理增量数据，并各自基于不同基准更新 `sync.last_sync_time`，可能造成数据重复写入或 `last_sync_time` 回退丢数据。
- **依据**: `SyncClient._run_sync_loop`（`sync_client.py:94-97`）存在相同的非原子 check-then-set 模式，二者叠加放大竞态窗口。应在 SyncClient 内提供 `threading.Lock` 保护的原子方法 `try_start_sync()`。

### Issue 2: async 端点中执行阻塞式同步数据库 I/O
- **类型**: Performance
- **置信度**: 90
- **位置**: `lifeprism/server/api/sync_status_api.py:65-66`
- **详情**: `get_sync_status` 是 `async def`，FastAPI 不会将其放入线程池执行。而 `count_rows` 执行的是同步 `sqlite3` 阻塞调用。13 次 `COUNT(*)` 期间整个事件循环被阻塞，所有其他 HTTP 请求被挂起。
- **依据**: FastAPI 已知陷阱——`async def` 端点中的同步阻塞 I/O 会阻塞事件循环。`SyncClient._run_sync_loop` 已正确使用 `asyncio.to_thread` 包装同步调用，API 层应保持一致。改为 `def`（让 FastAPI 线程池化）或内部用 `await asyncio.to_thread()`。

### Issue 3: TriggerSyncResponse 类型与后端响应不匹配
- **类型**: Architecture
- **置信度**: 98
- **位置**: `frontend/apps/settings/syncTypes.ts:31-36`
- **详情**: 后端 `trigger_sync` 返回 `{"message": "同步已触发", "status": "syncing"}`，而前端类型定义为 `{ success: boolean; message?: string }`。后端无 `success` 字段，类型缺少 `status` 字段。当前 `handleTriggerSync` 未使用返回值故暂无运行时崩溃，但任何后续代码若写 `if (result.success)` 会得到 `undefined`（恒假），是潜在陷阱。
- **依据**: 前后端 API 契约不一致。应改为 `{ message: string; status: string }`。

### Issue 4: toast.success('同步已完成') 语义错误，误导用户
- **类型**: Code Quality
- **置信度**: 95
- **位置**: `frontend/apps/settings/components/SyncStatusSection.tsx:74`
- **详情**: 后端 `trigger_sync` 通过后台线程执行同步并立即返回 202。`triggerSync()` resolve 时同步尚未完成，只是"已触发"。代码注释 `// 同步完成后立即刷新状态`（第 72 行）与后端行为矛盾。向用户提示"同步已完成"是事实性错误。
- **依据**: 应改为"同步已触发，正在后台执行"。

### Issue 5: 409 冲突响应未正确处理，错误信息丢失
- **类型**: Code Quality
- **置信度**: 85
- **位置**: `frontend/apps/settings/syncApi.ts:121-124`
- **详情**: 当同步已在进行中时，后端返回 409 + `{"message": "同步正在进行中", "status": "syncing"}`。前端 `triggerSync` 把非 ok 响应统一走错误分支，且只解析 `errorData.detail`（409 body 中不存在 `detail`），回退到 `触发同步失败: Conflict`。后端有意义的 message 被丢弃。
- **依据**: 应对 409 单独处理（视为预期情况而非错误，或至少提取 `errorData.message`）。

### Issue 6: 直接读写 SyncClient 私有属性 `_is_syncing`
- **类型**: Architecture
- **置信度**: 85
- **位置**: `lifeprism/server/api/sync_status_api.py:54,92,102,137`
- **详情**: API 层直接访问下划线前缀的私有属性 `_is_syncing`。若 SyncClient 将并发控制改为锁或信号量，API 层会静默失效。应暴露公共接口：`is_syncing` 只读 property + 原子的 `try_start_sync()` 方法。
- **依据**: `backend-core-rules.md` 4.3 命名约定（`_` 前缀=私有）。与 Issue 1 同源——封装为原子方法可一并解决竞态。

### Issue 7: count_rows 完全缺少单元测试
- **类型**: Testing
- **置信度**: 95
- **位置**: `lifeprism/repository/sync_repository.py:117`（实现）；`test/core/integration/repository/test_sync_repository.py`（缺失）
- **详情**: `count_rows` 在 `/api/sync/status` 中被直接调用，是核心数据来源。但 test_sync_repository.py 覆盖了 6 个方法，唯独没有 `count_rows` 的测试。`count_rows` 内部的表名白名单校验、数据库异常路径均未被验证。API 测试中 count_rows 被整体 mock 为返回 42，真实实现从未被测试。
- **依据**: 应补充 count_rows 的单元测试（正常计数、空表、无效表名抛异常）。

### Issue 8: _run_sync_background 异常处理未测试
- **类型**: Testing
- **置信度**: 92
- **位置**: `lifeprism/server/api/sync_status_api.py:122-137`
- **详情**: `_run_sync_background` 包含 `try/except/finally`，是防止 `_is_syncing` 永久卡在 `True` 的关键安全机制。全仓库测试目录中无任何 `_run_sync_background` 的匹配。该函数是模块级函数，可直接单元测试（传入 mock sync_client 并让 sync_once 抛异常，验证 `_is_syncing` 被重置 + 日志输出）。
- **依据**: `test_scheduled_sync.py` 测试了 `_run_sync_loop` 的 try/finally，但 `_run_sync_background` 是不同函数，从未被测试。

### Issue 9: trigger 测试未验证核心副作用（sync_once 调用 + _is_syncing 生命周期）
- **类型**: Testing
- **置信度**: 90
- **位置**: `test/core/integration/api/test_sync_status_api.py:169-176`
- **详情**: `test_trigger_returns_202` 仅断言 HTTP 202 + 响应体，未验证 `sync_once` 是否被后台线程调用、`_is_syncing` 是否被设置再重置。即使删掉 `thread.start()` 或 `_run_sync_background` 调用，该测试仍会通过。
- **依据**: 应补充断言 `mock_sync_client.sync_once.assert_called_once()` 和 `_is_syncing` 生命周期验证。

### Issue 10: toast.success('同步已完成') 未被测试
- **类型**: Testing
- **置信度**: 95
- **位置**: `frontend/apps/settings/components/SyncStatusSection.tsx:74`；`SyncStatusSection.test.tsx`（缺失）
- **详情**: 组件测试验证了失败路径的 `toast.error`，但成功路径的 `toast.success` 从未被断言。成功反馈行为完全未覆盖。
- **依据**: 应补充 `expect(toast.success).toHaveBeenCalledWith('同步已完成')` 断言（修复 Issue 4 后更新文案）。

### Issue 11: 魔法数字 5000 / 30000 未提取为常量
- **类型**: Code Quality
- **置信度**: 90
- **位置**: `frontend/apps/settings/components/SyncStatusSection.tsx:60`
- **详情**: `5000`（syncing 间隔）与 `30000`（idle 间隔）为裸数字，文件头注释也重复了这两个语义。应提取为模块级命名常量。
- **依据**: 代码可维护性最佳实践。

### Issue 12: 创建了两个独立的 SyncRepository 实例
- **类型**: Architecture
- **置信度**: 80
- **位置**: `lifeprism/server/main.py:296` 与 `lifeprism/server/api/sync_status_api.py:31`
- **详情**: `main.py` 创建 SyncRepository 实例 A 注入 SyncClient，`sync_status_api.py` 在模块级创建实例 B 供 count_rows 使用。两者虽委托同一个全局 db_manager，但架构不一致。若未来 SyncRepository 引入缓存/状态，两实例将产生分歧。
- **依据**: `backend-core-rules.md` 第 7 节单例原则。建议 API 层复用 `request.app.state.sync_client.sync_repository`。

### Issue 13: /status 端点对 13 张表逐表获取连接（N+1 式查询）
- **类型**: Performance
- **置信度**: 80
- **位置**: `lifeprism/server/api/sync_status_api.py:65-66` → `sync_repository.py:134-138`
- **详情**: 循环中每次 `count_rows` 都独立执行 `with self.db.get_connection() as conn`。13 次连接获取 + 13 个独立事务。该端点可能被前端高频轮询（每 30 秒或 5 秒）。建议新增 `count_rows_batch(table_names) -> dict` 在单一连接内执行多次 COUNT(*)。
- **依据**: `backend-core-rules.md` 第 7 节批处理原则。

## 变更摘要

Issue #12 实现了同步状态查询和手动触发同步功能。后端新增 `GET /api/sync/status`（返回上次同步时间、状态、各表记录数）和 `POST /api/sync/trigger`（后台线程执行同步，立即返回 202）。前端新增 `SyncStatusSection` 组件，展示状态徽章、相对时间、记录数列表，支持手动同步按钮和自动刷新。共新增 50 个测试。

主要问题集中在：(1) 并发控制缺乏原子性（竞态条件 + 私有属性直接访问）；(2) async 端点中阻塞式 I/O；(3) 前端类型契约与后端不一致；(4) 同步完成提示语义错误；(5) 测试覆盖缺口（count_rows / _run_sync_background / 副作用验证）。
