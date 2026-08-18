# Code Review Report

**审查范围**: 工作区未提交变更（"当前的修改"）
**审查时间**: 2026-08-18
**变更文件**: 
- 新增: `lifeprism/llm/agent/tools/habit_tool.py`, `test/core/integration/llm/agent/tools/test_habit_tool.py`
- 修改: `lifeprism/llm/agent/loop.py`, `lifeprism/llm/agent/tools/__init__.py`, `lifeprism/repository/providers/habit_providers.py`, `frontend/src/config/env.ts`, `frontend/package.json`, `frontend/.env.demo`, `pyproject.toml`
- 文档: 多个 specs/flows/history-bugs 文档
- 排除: `scripts/code_search/ast_scan_result.json`（自动生成）、`frontend/package-lock.json`（锁文件）、`scripts/docs_update/.last_sync_time`（自动生成）

## 架构上下文

### 相关 ADR
- `docs/adr/2026-07-22-habit-chain-tables-not-synced.md` — 习惯链条表不参与同步（accepted）
- `docs/adr/2026-07-22-hash-id-sync-only-identifier.md` — hash_id 仅作同步标识（accepted）
- `docs/adr/2026-05-03-llm-tool-separation-for-detail-query.md` — LLM 工具分离查询（accepted）
- `docs/adr/2026-06-30-tool-call-chain-logging.md` — 工具调用链日志（accepted）

### 相关 Spec
- `docs/specs/2026-07-06-llm-agent-spec.md` — Agent 执行引擎核心规格，定义工具注册与安全沙箱
- `docs/specs/2026-04-15-habit-system.md` — 习惯系统规格，定义打卡/补签/挑战/Streak 业务规则
- `docs/specs/2026-07-06-repository-core-spec.md` — Repository 数据访问层规格

### 决策覆盖
- 2/4 代码文件有 ADR 关联（habit_tool.py 涉及 LLM 工具分离 ADR；habit_providers.py 涉及 hash_id ADR）
- 文件头注释明确约定"不直连 repository"（见 Issue 1）

### 相关 CLAUDE.md 规则
- `lifeprism/llm/agent/tools/CLAUDE.md`: 所有工具 execute() 必须返回 str
- `lifeprism/CLAUDE.md`: 类型注解禁止 Any 返回类型、错误处理分层规则、日志记录规范
- `docs/coding-rules/repository-module-rules.md`: 导入纪律——外部调用方只能从 `lifeprism.repository` 导入

## 审查结果

Found 2 issues:

### Issue 1: backfill_checkin 绕过 Service 层直接调用 repository
- **类型**: Architecture
- **置信度**: 85
- **位置**: [habit_tool.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/habit_tool.py#L124-L129) 第 124-129 行
- **详情**: `backfill_checkin` 函数在第 124 行直接调用 `habit_repository.get_current_challenge(habit_id)` 获取当前挑战，违反了文件头注释（第 4-6 行）明确声明的约定：
  ```
  调用 HabitService（延迟导入，见 _get_habit_service 说明），不直连 repository--
  打卡/补签涉及挑战 completed_count 更新、结算判定、Streak 计算，
  绕过 service 会跳过业务规则导致挑战状态错乱。
  ```
  虽然 `get_current_challenge` 是只读查询，但 Tool 层直接访问 Repository 破坏了 Tool → Service → Repository 的分层架构。正确做法应让 HabitService 暴露获取当前挑战的方法，或让 `backfill_checkin` 的 service 方法自行查找 challenge_id。
- **依据**: 
  - 文件头注释（第 4-6 行）
  - `docs/coding-rules/repository-module-rules.md` 第 2.2 节导入纪律：外部调用方（含 llm/）只能从 `lifeprism.repository` 导入 `xxx_repository`，但 Tool 层应调用 Service 而非 Repository
  - `docs/specs/2026-07-06-llm-agent-spec.md` 工具实现规范

### Issue 2: except sqlite3.IntegrityError 变成死代码
- **类型**: Code Quality
- **置信度**: 85
- **位置**: [habit_providers.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/providers/habit_providers.py#L600-L602) 第 600-602 行
- **详情**: 修改后的 `create_checkin` 方法将 `_generic_insert(insert_data)` 改为 `_generic_insert(insert_data, on_conflict="ignore")`。根据 `_generic_insert` 实现（[lw_base_data_provider.py:1186-1211](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/base_providers/lw_base_data_provider.py#L1186-L1211)）：
  1. `on_conflict="ignore"` 生成 `INSERT OR IGNORE INTO ...`，UNIQUE 冲突时 `cursor.rowcount == 0`，返回 None（不抛异常）
  2. 其他 sqlite3 错误（含 IntegrityError）被 `_generic_insert` 内部 `except sqlite3.Error`（IntegrityError 父类）捕获并转换为 `DataAccessError` 抛出
  
  因此，第 600 行的 `except sqlite3.IntegrityError` 永远不会被触发，成为死代码。且其日志消息"打卡记录已存在"现在已不准确（真要触发只会是其他完整性约束错误，而非 UNIQUE(habit_id, date) 冲突）。
- **依据**:
  - `_generic_insert` 实现确认 `INSERT OR IGNORE` 不抛 IntegrityError
  - `sqlite3.IntegrityError` 是 `sqlite3.Error` 子类，已被内部捕获
  - 用户修改了 try 块逻辑（新增 `on_conflict="ignore"` + `if result is None` 分支），导致 except 块语义改变

## 变更摘要

本次变更新增习惯打卡模块的 4 个 LLM Agent 工具（QueryUserHabitsTool / CheckinHabitTool / CancelCheckinHabitTool / BackfillCheckinTool），并修复 HabitCheckinProvider 重复打卡被静默替换的 bug（将 `on_conflict` 从默认 `replace` 改为 `ignore`）。

**正向评价**:
- 工具返回类型全部为 str，符合 `lifeprism/llm/agent/tools/CLAUDE.md` 规范
- 使用 SUCCESS/ERROR 常量前缀，便于 LLM 解析
- 延迟导入 `_get_habit_service()` 正确解决循环导入问题
- 参数校验完整（status 枚举校验、habit_id 非空校验、dates 列表校验）
- 错误处理分层清晰：ConflictError/ValidationError/NotFoundError 分别捕获并返回对应错误提示
- 测试覆盖主要场景（查询/打卡/重复打卡/取消/补签/边界/不存在）
- 时间处理遵循 time-handling-rules（本地日期用于习惯，UTC 用于时间戳）
- bug 修复有清晰的注释说明原因（replace 导致重复打卡计入完成数）
- 新增 history-bug 文档记录该 bug
- 版本号从 0.1.3 升级到 0.2.0，4 处版本号同步更新
