# Code Review Report

**审查范围**: `b1a15ee3..6a95eb4f`（feature commit + fix commit，43 文件 +11857/-449 行）
**审查时间**: 2026-07-18
**备注**: 015 审查发现 10 个问题并修复后的**第二次审查**，检查当前代码是否还有其他问题

## 架构上下文

### 相关 ADR
- `docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md`（decided）
- `docs/adr/2026-07-17-conflict-failure-policy.md`（decided）
- `docs/adr/2026-07-17-data-backup-strategy.md`（decided）
- `docs/adr/2026-07-17-backup-sync-decoupled-scope.md`（decided）

### 相关 Spec
- `docs/coding-rules/backend-error-handling.md`：异常处理规范
- `docs/coding-rules/backend-core-rules.md`：Service 实例化规范
- `docs/coding-rules/test-rules.md`：测试覆盖规范

## 审查结果

Found 8 issues（置信度 ≥ 80）：

### Issue 1: `_initial_push_db` 对 httpx 调用使用了过于宽泛的 `except Exception`
- **类型**: Code Quality
- **置信度**: 85
- **位置**: `lifeprism/sync/sync_client.py:425`
- **详情**: `_initial_push_db` 中 httpx.post 调用使用 `except Exception as e`。httpx 有文档化的异常类型（`httpx.HTTPStatusError`、`httpx.RequestError`），应捕获具体类型。代码库中其他类似方法（`_pull_files_check`、`_push_files`、`_pull_files_fetch`、`_verify_and_advance_parent`）都正确捕获了 `(httpx.HTTPStatusError, httpx.RequestError)`，此处不一致。
- **依据**: `docs/coding-rules/backend-error-handling.md` §4.5 "不适用范围——知名框架（FastAPI、httpx 等有文档化的异常）"

### Issue 2: `_resolve_conflicts` 中 `except TimeoutError` 是死代码
- **类型**: Code Quality
- **置信度**: 85
- **位置**: `lifeprism/sync/sync_client.py:1891`
- **详情**: `except TimeoutError` 捕获内置 `TimeoutError`，但该异常的来源 `future.result(timeout=600)` 在 `llm_caller()` 闭包中，而闭包在 `resolve_conflict_blocks()` 内部被调用。`resolve_conflict_blocks` 在 L593 用 `except Exception` 捕获了所有异常（含 `concurrent.futures.TimeoutError`），触发重试，3 次失败后正常返回。因此 `TimeoutError` 永远无法传播到 L1891。该分支是死代码。
- **依据**: Python 异常继承体系：`concurrent.futures.TimeoutError`（Python 3.11+ = `builtins.TimeoutError`）继承自 `OSError` → `Exception`，被 L593 的 `except Exception` 捕获

### Issue 3: 备份调度机制文档描述启动补偿与代码实际行为不符
- **类型**: Documentation
- **置信度**: 85
- **位置**: `templates/docs/lifewatch/06-数据备份与恢复.md:537`
- **详情**: 文档 A.1 节写道"启动补偿：错过 03:00 时启动后异步执行一次"。但实际代码 `schedule_service.py:134-136` 注释明确写 "skip_compensation=True：备份是周期性任务，无需启动补偿"，且两个备份任务均设置 `"skip_compensation": True`（L145、L152），APScheduler 的 `_add_system_jobs` 逻辑（L286-291）在 `skip_compensation=True` 时会跳过整个补偿块。文档描述与代码实现矛盾。
- **依据**: `schedule_service.py` L134-136 注释 + L145/L152 `skip_compensation: True` + L286-291 跳过逻辑

### Issue 4: `_resolve_conflicts` 中 `except Exception` 缺少 LEGITIMATE 注释
- **类型**: Code Quality
- **置信度**: 80
- **位置**: `lifeprism/sync/sync_client.py:1896`
- **详情**: `_resolve_conflicts` 在 `for file_path in conflict_paths` 循环内使用 `except Exception` 捕获单文件异常，防止一个文件失败导致整个批次崩溃。这是合法的"辅助操作兜底"场景，但违反 §4.5 要求 3——必须在注释中说明为何使用 `except Exception`。同一代码库中其他类似场景（`conflict_resolution.py:374`、`:594`、`:739`）均有 `# LEGITIMATE:` 注释，此处不一致。
- **依据**: `docs/coding-rules/backend-error-handling.md` §4.5 要求 3："必须在注释中说明为何使用 `except Exception`"

### Issue 5: `test_parse_wrong_field_types_returns_none` 使用了非确定性断言
- **类型**: Testing
- **置信度**: 85
- **位置**: `test/core/unit/sync/test_conflict_json_parse.py:138-140`
- **详情**: 该测试方法名声称"字段类型错误返回 None"，但断言使用 `if result is not None:` 条件包裹，仅做了弱验证。测试在 `result is None`（正确行为）时通过，在 `result is not None` 时也只做了 `assert int(result["conflict_id"]) == 1 or result["conflict_id"] == 1` 的软断言。应改为直接的 `assert result is None`。
- **依据**: 测试目的与断言强度不匹配

### Issue 6: `test_fetch_remote_base_content.py` 未测试 OSError 异常处理路径
- **类型**: Testing
- **置信度**: 80
- **位置**: `test/core/unit/sync/test_fetch_remote_base_content.py`
- **详情**: `_fetch_remote_base_content` 实现中有 `except OSError` 处理（读取备份文件失败时跳过该备份继续下一个），但测试未覆盖此路径。需验证 OSError（如权限不足、文件损坏）时跳过备份且不中断整体查找流程。
- **依据**: `sync_client.py:1672-1678` `except OSError` 分支未被任何测试覆盖

### Issue 7: `parse_conflict_blocks` 的错误恢复路径无直接测试
- **类型**: Testing
- **置信度**: 80
- **位置**: `test/core/unit/sync/test_conflict_json_parse.py` / `lifeprism/sync/conflict_resolution.py:193-200`、`:218-225`
- **详情**: `parse_conflict_blocks` 有两条错误恢复路径：(1) `=======` 分隔符缺失时跳过该冲突块 (2) `>>>>>>>` 结束标记缺失时跳过该冲突块。这两个分支仅在函数内 `logger.warning` 记录日志，无任何测试覆盖。
- **依据**: `conflict_resolution.py` L193-200 和 L218-225 的异常恢复分支

### Issue 8: `match_markers` 的模糊匹配逻辑无直接测试
- **类型**: Testing
- **置信度**: 80
- **位置**: `test/core/unit/sync/test_conflict_json_parse.py` / `lifeprism/sync/conflict_resolution.py:257-333`
- **详情**: `match_markers` 的模糊匹配逻辑（`_normalize_marker` → 去除所有空白后比较）仅在 `resolve_conflict_blocks` 的集成测试中间接覆盖，无直接测试。无法单独验证精确匹配、模糊匹配（含额外空格）、完全不匹配、空文件等场景。
- **依据**: `conflict_resolution.py:276-333` 的 `match_markers` 函数无专门测试类

## 变更摘要

本次审查覆盖 8 个 issue 的全部实现代码（feature commit `11230c56` + fix commit `6a95eb4f`），是 015 审查修复后的第二次审查。

**15 审查已修复**：10 个问题全部修复并在当前代码中验证通过（死代码已删除、LazySingleton 已使用、except Exception 已修复、ADR 引用已修正、过时注释已更新、文档错误已修正）。

**本次新发现**：8 个问题，均为低严重度：
- 3 个 Code Quality（httpx 异常类型与项目其他同类方法不一致、TimeoutError 死代码、except Exception 缺 LEGITIMATE 注释）
- 1 个 Documentation（备份启动补偿描述与实际不符）
- 4 个 Testing（非确定性断言、OSError 恢复路径未测试、parse_conflict_blocks 恢复路径未测试、match_markers 模糊匹配无直接测试）
