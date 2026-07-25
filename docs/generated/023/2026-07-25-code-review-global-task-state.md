# Code Review Report

**审查范围**: GlobalTaskState 全局任务状态互斥机制（新增 2 文件 + 修改 5 文件）
**审查时间**: 2026-07-25
**审查方式**: 8 维度并行子 agent 审查（Security / Performance / Architecture / Code Quality / Best Practices / Testing / Documentation / 代码注释合规）
**变更文件**:
- `lifeprism/server/services/global_task_state.py`（新增）
- `test/core/unit/server/services/test_global_task_state.py`（新增）
- `lifeprism/sync/sync_client.py`（修改）
- `lifeprism/server/services/schedule_service.py`（修改）
- `lifeprism/server/main.py`（修改）
- `lifeprism/server/api/sync_status_api.py`（修改）
- `test/core/unit/server/services/test_backup_service.py`（修改）

## 架构上下文

### 相关 ADR

- [2026-07-25-global-task-state.md](../../adr/2026-07-25-global-task-state.md) (v1.1, decided): 本审查核心 ADR，引入 GlobalTaskState 单例 + 三态枚举 + threading.Condition 互斥机制。v1.1 修订了决策 5 超时降级策略（dreaming 超时后仍执行），新增全局前提 3、4（文件/数据库同步自我纠正能力）
- [2026-07-17-data-backup-strategy.md](../../adr/2026-07-17-data-backup-strategy.md) (accepted): 数据备份策略，本 ADR 决策 2 修改其中"文档每天 03:00 备份一次"的决策
- [2026-07-17-backup-sync-decoupled-scope.md](../../adr/2026-07-17-backup-sync-decoupled-scope.md) (accepted): 备份范围与同步范围解耦
- [2026-07-17-conflict-failure-policy.md](../../adr/2026-07-17-conflict-failure-policy.md) (accepted): 冲突失败处理
- [2026-07-14-sync-full-sync-strategy.md](../../adr/2026-07-14-sync-full-sync-strategy.md) (accepted): 全量同步策略

### 相关 Spec

- [2026-07-17-data-backup-spec.md](../../specs/2026-07-17-data-backup-spec.md) v3.0: 数据备份模块规格，决策 2 修改 backup_documents 触发方式（从独立 03:00 cron 改为 10点任务子步骤）

### 决策覆盖

- 5/5 变更文件均有 ADR 关联（核心 ADR 2026-07-25-global-task-state.md）
- 1/5 变更文件同时关联备份策略 ADR 和备份 spec
- ADR 8 个决策在代码中均正确落地（决策 1/2/3/4/5/6/7/8 逐项核对通过）
- 全局前提 3、4（文件/数据库同步自我纠正）在 sync_client.py 的 sync_cutoff_time 改动中体现

## 审查结果

Found 10 issues（置信度 ≥ 80，8 维度并行审查后去重合并）:

### Issue 1: `global_task_state.py` 模块 docstring 超时降级描述与 ADR v1.1 决策 5 矛盾

- **类型**: Documentation / Architecture / 代码注释合规
- **置信度**: 100
- **位置**: [global_task_state.py:13-14](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/global_task_state.py#L13-L14)
- **详情**: 模块 docstring 第 13-14 行写道：
  ```
  - 本地任务启动前：try_acquire(LOCAL_TASK, timeout=300s)
    - 超时降级：跳过整个 10点任务（dreaming 写 behavior.md 会与 sync 冲突）
  ```
  这与 ADR v1.1 三处直接矛盾：
  1. ADR v1.1 修订记录（第 17 行）明确："修订决策 5 超时降级策略（dreaming 在超时后仍执行）"
  2. ADR 决策 5 超时降级表（第 256-262 行）：`incremental_sync` 跳过，但 `dreaming` 和 `backup_documents` **仍执行**
  3. ADR 决策 5（第 264 行）："为什么不直接跳过整个 10点任务：dreaming 和 backup 不依赖云端，跳过会丢失当日 AI 总结和备份，不划算。"

  括号内理由"dreaming 写 behavior.md 会与 sync 冲突"也是 v1.0 的旧理由，v1.1 已通过全局前提 3、4（文件/数据库同步的自我纠正能力）推翻该理由。

  **关键**：实际代码实现（`schedule_service.py:49-94`）是**符合 ADR v1.1 的**——超时后仅跳过 incremental_sync，dreaming 和 backup_documents 仍执行。问题仅在于 docstring 未随 ADR v1.1 修订同步更新，停留在 v1.0 描述，会误导后续维护者。
- **依据**: [ADR v1.1 第 17 行修订记录](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L17)、[ADR 决策 5 第 256-264 行](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L256-L264)、[schedule_service.py:49-94 实际实现](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L49-L94)

### Issue 2: `test_global_task_state.py` 缺少 `@pytest.mark.core` 测试标记

- **类型**: Testing
- **置信度**: 95
- **位置**: [test/core/unit/server/services/test_global_task_state.py](file:///d:/desktop/软件开发/LifeWatch-AI/test/core/unit/server/services/test_global_task_state.py)（整个文件）
- **详情**: 该测试文件位于 `test/core/unit/` 目录下，但**既无模块级 `pytestmark = pytest.mark.core`，也无任何 `@pytest.mark.core` 装饰器**。对比同目录下的 [test_backup_service.py:30](file:///d:/desktop/软件开发/LifeWatch-AI/test/core/unit/server/services/test_backup_service.py#L30) 有 `pytestmark = pytest.mark.core`。这会导致该测试文件无法通过 `pytest -m core` 过滤运行，可能在 CI 中被遗漏。
- **依据**: [docs/coding-rules/test-rules.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/coding-rules/test-rules.md) 规则 4 测试标记表："core/ | `@pytest.mark.core`"（必须标记）；[test_backup_service.py:30](file:///d:/desktop/软件开发/LifeWatch-AI/test/core/unit/server/services/test_backup_service.py#L30) 同目录文件的正确示范

### Issue 3: 3 处集成互斥逻辑完全缺失测试

- **类型**: Testing
- **置信度**: 92
- **位置**: [schedule_service.py:37-94](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L37-L94)（`_dreaming`）、[schedule_service.py:97-115](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L97-L115)（`_process_session_message`）、[sync_client.py:181-232](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L181-L232)（`_run_sync_loop`）、[main.py:309-371](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L309-L371)（`_start_sync_on_startup`）、[sync_status_api.py:161-194](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_status_api.py#L161-L194)（`_run_sync_background`）
- **详情**: ADR 决策 3/4/5 定义了复杂的互斥行为，但 5 处集成互斥逻辑**均无任何测试**覆盖。具体缺失：
  - `_dreaming` 超时降级路径（acquired=False 时跳过 incremental_sync 但仍执行 dreaming + backup_documents）— ADR 决策 5 核心行为
  - `_dreaming` 异常路径 release() 调用（incremental_sync/dreaming/backup_documents 抛异常时是否正确 release）
  - `_dreaming` acquired=False 时 finally 中 `if acquired:` 守卫不调用 release()
  - `_process_session_message` 超时返回（acquired=False 时 early return）
  - `_run_sync_loop` try_acquire 失败后调用 `_send_ping` + continue
  - `_run_sync_loop` sync_once 异常时 release() 在内层 finally 被调用
  - `_start_sync_on_startup` try_acquire 失败后调用 `_send_ping`
  - `_run_sync_background` try_acquire 失败后调用 `_send_ping`

  这些行为涉及锁的正确释放，若 release() 未被调用会导致 GlobalTaskState 永久卡在 LOCAL_TASK/CLOUD_SYNC，使后续所有 sync 和本地任务全部被阻塞（死锁）。
- **依据**: [CLAUDE.md 核心规则 5 "Bug 先测试"](file:///d:/desktop/软件开发/LifeWatch-AI/CLAUDE.md)、[test-rules.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/coding-rules/test-rules.md) 规则 1、[ADR 决策 3/4/5](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L210-L264)

### Issue 4: GlobalTaskState 类 docstring 使用示例与 10点任务实际用法不一致

- **类型**: Documentation / 代码注释合规
- **置信度**: 90
- **位置**: [global_task_state.py:57-67](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/global_task_state.py#L57-L67)
- **详情**: 类 docstring 的"使用示例"标注为"# 本地任务（10点 / 4h）"，但示例代码：
  ```python
  acquired = await asyncio.to_thread(
      global_task_state.try_acquire, TaskState.LOCAL_TASK, 300.0
  )
  if not acquired:
      return  # 超时跳过
  try:
      # 执行任务...
  finally:
      global_task_state.release()
  ```
  该示例只匹配 4h `_process_session_message` 的行为（超时后 `return`），但**不匹配** 10点 `_dreaming` 的实际用法：
  - `_dreaming`（schedule_service.py:49-94）超时后**不 return**，继续执行 dreaming + backup_documents
  - 仅 `incremental_sync` 受 `if acquired:` 守卫跳过
  - `finally` 块中用 `if acquired:` 守卫 release（避免未获取就释放）

  示例把"10点 / 4h"合并描述，但 10点任务的超时降级策略远比示例复杂（参考 ADR 决策 5）。读者按此示例实现 10点任务会得到错误行为。
- **依据**: [schedule_service.py:49-94 _dreaming 实际实现](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L49-L94)、[schedule_service.py:104-115 _process_session_message 实际实现](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L104-L115)、[ADR 决策 5 超时降级表](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L256-L262)

### Issue 5: `main.py` `_start_sync_on_startup` docstring 未反映 CLOUD_SYNC 互斥逻辑

- **类型**: Documentation
- **置信度**: 90
- **位置**: [main.py:319-326](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L319-L326)
- **详情**: 函数 docstring 的"并发控制"部分仅描述 `try_start_sync()`：
  ```
  并发控制：
  - 通过 try_start_sync() 原子锁判断是否可启动
  - sync_once() 完成后调用 finish_sync() 释放锁
  - 若启动同步未完成时定时同步触发，try_start_sync() 返回 False，定时同步跳过
  ```
  未提及本次新增的 CLOUD_SYNC 互斥逻辑（代码 343-365 行实现了 `try_acquire(CLOUD_SYNC, 0)` + 失败调 ping）。函数体内的内联注释描述正确，但 docstring 与函数行为不完全对齐。对比 `sync_client.py:188-191` 和 `sync_status_api.py:168-170` 的同类 docstring 均已补充 CLOUD_SYNC 互斥说明，main.py 遗漏。
- **依据**: [main.py:343-365 函数体实现](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L343-L365)、[ADR 决策 4](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L225-L242)

### Issue 6: `_send_ping` 使用过宽的 `except Exception` 违反项目自身规范

- **类型**: Best Practices / Code Quality
- **置信度**: 90
- **位置**: [sync_client.py:163-164](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L163-L164)
- **详情**: `_send_ping` 使用 `except Exception as e:` 捕获所有异常并仅记录 WARNING 日志。这会吞掉编程错误（如 `TypeError`、`AttributeError`、`KeyError`），使 bug 难以发现。

  **违反项目自身规范**：同文件 [sync_client.py:58-59](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L58-L59) 明确注释"不使用 except Exception 避免吞掉编程错误"，本方法违反了项目自己的约定。

  **与同文件惯例不一致**：`_pull_deletion_log`、`_push_deletion_log`、`_advance_remote_parent_after_initial_sync` 等同类 HTTP 方法均使用 `except (httpx.HTTPStatusError, httpx.RequestError)` 精确捕获，本方法不一致。

  建议改为：`except (httpx.HTTPError, OSError) as e:`
- **依据**: [sync_client.py:58-59 项目自身注释](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L58-L59)、同文件多处 `except (httpx.HTTPStatusError, httpx.RequestError)` 惯例

### Issue 7: `_send_ping` 新方法无任何单元测试

- **类型**: Testing
- **置信度**: 88
- **位置**: [sync_client.py:135-164](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L135-L164)（`_send_ping` 方法）
- **详情**: `_send_ping` 是本次新增的同步 HTTP 调用方法，包含 3 条独立执行路径，**全部未测试**：
  1. 配置缺失路径（`remote_url` 或 `api_key` 为空 → 记录 debug 日志并 return）
  2. HTTP 成功路径（`response.raise_for_status()` 通过 → 记录 info 日志）
  3. HTTP 失败路径（`raise_for_status()` 抛异常 → 记录 warning 日志，不传播异常）

  该方法在 3 处被调用（`_run_sync_loop`、`_start_sync_on_startup`、`_run_sync_background`），是 ADR 决策 4"调 ping 端点报告在线"的关键实现。若 `_send_ping` 行为异常（如异常未捕获传播到调用方），会导致 sync 循环或启动流程中断。
- **依据**: [test-rules.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/coding-rules/test-rules.md) 规则 1、[ADR 决策 4](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L225-L242)

### Issue 8: 外部访问 `_send_ping` 私有方法违反封装约定

- **类型**: Code Quality / Best Practices
- **置信度**: 85
- **位置**: [main.py:353](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L353)（`await asyncio.to_thread(sync_client._send_ping)`）、[sync_status_api.py:184](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_status_api.py#L184)（`sync_client._send_ping()`）、[sync_client.py:143](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L143)（docstring 中自述 `sync_client._send_ping` 作为外部调用方式）
- **详情**: `_send_ping` 方法使用单下划线前缀（Python 约定"内部使用"），但实际被 `main.py` 和 `sync_status_api.py` 外部调用。更值得注意的是，`_send_ping` 的 docstring 自己也写了 `sync_client._send_ping` 作为调用方式，说明开发者明知会被外部调用却仍保留了下划线前缀，自相矛盾。应去掉下划线命名为 `send_ping`（公共方法），与 `SyncClient` 已有公共方法 `try_start_sync` / `finish_sync` / `sync_once` 保持一致的可见性。
- **依据**: PEP 8 — "Use one leading underscore only for non-public methods and instance variables."；ADR 决策 4 明确要求 3 处外部入口调用此方法

### Issue 9: `last_sync_time` 改用 `sync_cutoff_time` 无回归测试

- **类型**: Testing
- **置信度**: 85
- **位置**: [sync_client.py:271-279, 335-338](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L271-L279)
- **详情**: 本次变更将 `last_sync_time` 从"同步结束时间"改为"同步开始时间"（`sync_cutoff_time = datetime.now(timezone.utc).isoformat()` 在 sync_once 开头计算，末尾用 `set_setting("sync.last_sync_time", sync_cutoff_time)` 写入）。这是一个**防数据丢失的关键行为变更**：

  若改回结束时间，sync 期间其他任务（dreaming / AgentLoop）写入的数据 `updated_at` 落在 `(T_start, T_end)` 区间，会被永久排除在下次同步之外。ADR 全局前提 4 明确指出此前提是决策 5 超时降级策略的根本依据，并引用了 history-bugs/2026-07-25-sync-last-sync-time-update-point-data-loss.md。

  但该行为变更**无任何回归测试**验证：
  - sync 期间有数据写入时，下次 sync 是否包含该数据
  - `sync_cutoff_time` 是否在 sync_once 开头计算（而非末尾）
  - `set_setting("sync.last_sync_time", ...)` 是否使用开始时间值
- **依据**: [ADR 全局前提 4](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L359)、[CLAUDE.md 核心规则 5 "Bug 先测试"](file:///d:/desktop/软件开发/LifeWatch-AI/CLAUDE.md)、[history-bugs/2026-07-25-sync-last-sync-time-update-point-data-loss.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-25-sync-last-sync-time-update-point-data-loss.md)

### Issue 10: ADR 决策 2 执行序列图在超时分支错误标注 `release()`

- **类型**: Documentation
- **置信度**: 80
- **位置**: [ADR 2026-07-25-global-task-state.md:191-204](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-25-global-task-state.md#L191-L204)
- **详情**: ADR 的执行序列图在"超时降级"分支中列出"末尾 release()"，这是不正确的。当 `try_acquire` 超时返回 False 时，状态从未被设置为 LOCAL_TASK，因此**不应调用 release()**。代码实现 [schedule_service.py:92-94](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L92-L94) 通过 `if acquired: global_task_state.release()` 守卫确保超时时不调用 release()。

  ADR 图示的"末尾 release()"会误导开发者在超时路径也调用 release()，而 `release()` 实现（[global_task_state.py:127-133](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/global_task_state.py#L127-L133)）是无条件重置状态为 IDLE 并 notify_all()，若超时后另一线程已获取 CLOUD_SYNC，错误调用 release() 会把 CLOUD_SYNC 重置为 IDLE，破坏互斥语义。
- **依据**: [schedule_service.py:92-94 `if acquired:` 守卫](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/schedule_service.py#L92-L94)、[global_task_state.py:127-133 release() 无条件重置](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/global_task_state.py#L127-L133)

## 变更摘要

本次变更新增 GlobalTaskState 全局任务状态互斥机制，用于协调本地定时任务（10点序列 + 4h 任务）与云端 sync_once 的跨线程互斥。

**核心实现**：
- `GlobalTaskState` 单例类，三态枚举（IDLE/LOCAL_TASK/CLOUD_SYNC），用 `threading.Condition` 保护，提供 `try_acquire`（阻塞+超时）和 `release` 方法
- 10点任务（`_dreaming`）入口 `try_acquire(LOCAL_TASK, 300s)`，5 分钟超时；超时后仅跳过 incremental_sync，dreaming + backup_documents 仍执行（符合 ADR v1.1 决策 5）
- 4h 任务（`_process_session_message`）入口 `try_acquire(LOCAL_TASK, 300s)`，5 分钟超时；超时跳过本次
- 云端 sync_once 三处触发入口（`_run_sync_loop` / `_start_sync_on_startup` / `_run_sync_background`）均加 `try_acquire(CLOUD_SYNC, 0)`，失败调 ping 端点
- `backup_documents` 从独立 03:00 cron 移除，改为 `_dreaming` 子步骤（在 dreaming 之后捕获最新数据）
- `last_sync_time` 改用 sync_cutoff_time（sync 开始时间）而非结束时间，避免 sync 期间写入的数据被永久排除

**变更行数**：
- `global_task_state.py`: +137 行（新增）
- `test_global_task_state.py`: +228 行（新增，15 个单元测试）
- `sync_client.py`: +44 行（_send_ping 方法 + _run_sync_loop 互斥 + sync_cutoff_time 改动）
- `schedule_service.py`: +50/-15 行（_dreaming/_process_session_message 加锁 + 删除 backup_documents cron）
- `main.py`: +20/-5 行（_start_sync_on_startup 加 CLOUD_SYNC 互斥）
- `sync_status_api.py`: +25/-3 行（_run_sync_background 加 CLOUD_SYNC 互斥）
- `test_backup_service.py`: +10/-30 行（更新 3 个测试反映 backup_documents 不再独立 cron）

**符合 ADR 的部分**：
- 决策 1（三态枚举 + threading.Condition）：实现正确 ✓
- 决策 2（backup_documents 并入 10点任务）：实现正确 ✓
- 决策 3（4h 持 LOCAL_TASK）：实现正确 ✓
- 决策 4（云端遇冲突放弃 + ping）：三处触发入口均正确实现 ✓
- 决策 5（10点任务超时降级策略）：**代码实现正确**（超时后 dreaming + backup 仍执行），但 global_task_state.py docstring 描述错误（见 Issue 1）
- 决策 6（数据库备份不参与互斥）：实现正确 ✓
- 决策 7（threading.Condition）：选型正确 ✓
- 决策 8（与 _is_syncing 共存）：实现正确 ✓

**问题分布**：
- Documentation: 4 个（Issue 1/4/5/10）
- Testing: 4 个（Issue 2/3/7/9）
- Code Quality / Best Practices: 2 个（Issue 6/8）

**正向结论**：
- Security 维度无问题（认证、密钥保护、SSRF、锁释放配对均正确）
- Performance 维度无 ≥80 分问题（所有性能 trade-off 均在 ADR 已知限制中记录）
- ADR 8 个决策在代码层面全部正确落地
- GlobalTaskState 类本身有 15 个高质量单元测试覆盖核心行为
