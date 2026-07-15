# Code Review Report

**审查范围**: push sync 云端 OOM 修复（分批推送）— 5 个变更文件
**审查时间**: 2026-07-15
**变更文件**:
- `lifeprism/sync/sync_client.py` — 核心修改
- `test/core/integration/sync/test_sync_client.py` — 测试适配
- `test/core/integration/sync/test_sync_client_batch.py` — 新增分批测试
- `test/core/integration/sync/test_sync_client_files.py` — 测试适配
- `test/core/integration/sync/test_sync_timezone_utc.py` — 测试适配

## 架构上下文

### 相关 ADR
- [ADR-2026-07-14-sync-full-sync-strategy](../adr/2026-07-14-sync-full-sync-strategy.md) (decided) — 全量同步策略（方案B：重置按钮）；LWW updated_at 相等跳过
- [ADR-2026-07-14-file-sync-conflict-resolution](../adr/2026-07-14-file-sync-conflict-resolution.md) (decided) — 文件同步 parent_hash + current_hash + 11 状态决策矩阵

### 相关 Spec
- [data-sync-spec](../specs/2026-07-11-data-sync-spec.md) (draft) — 数据同步模块规格：Pull 分批拉取（1000条/批）、Push 增量查询推送、LWW 冲突解决

### 决策覆盖
- 4/5 变更文件有 ADR 或 Spec 关联
- 变更属于实现细节优化（传输层 payload 切分），不引入新的架构决策

---

## 审查结果

**No issues found** above the confidence threshold (≥80).

8 个并行 Agent（Security / Performance / Architecture / Code Quality / Best Practices / Testing / Documentation / 注释合规）审查了全部变更，初始发现 8 个潜在问题。随后 8 个独立评分 Agent 对每个发现进行了置信度评分（0-100），按规范过滤掉分数 < 80 的问题。

---

## 置信度评分详情

### Issue 1: `push_to_remote` 全量加载增量行到内存 → **置信度: 25** ❌ 已过滤

- **类型**: Performance / Architecture
- **位置**: `lifeprism/sync/sync_client.py:522`
- **评分理由**: 这是**预先存在的问题**（旧代码同样全量加载，且多表同时驻留）。新代码逐表处理，峰值内存从"所有表之和"降为"最大单表"，**实际上是轻微改善**。按评分规则忽略预先存在的问题。
- **修复建议**: 改为数据库级分页（`query_incremental` 传入 offset/limit），与 `pull_from_remote` 对齐

### Issue 2: `_push_files` 全量加载文件内容到内存 → **置信度: 0** ❌ 已过滤

- **类型**: Performance
- **位置**: `lifeprism/sync/sync_client.py:892-926`
- **评分理由**: 文件读取/压缩/编码部分（L892-917）**在本次 diff 中完全未被修改**——变更仅涉及 POST 阶段。属于预先存在的问题，按评分规则直接给 0 分。

### Issue 3: `_push_files` 分批逻辑零测试覆盖 → **置信度: 75** ❌ 已过滤

- **类型**: Testing
- **位置**: `test/core/integration/sync/test_sync_client_files.py`（缺失）
- **评分理由**: 这是本次变更新增的代码路径，确实没有测试覆盖。对比 `push_to_remote` 有 `TestPushBatched` 类（3 个测试），`_push_files` 的分批路径是零覆盖。但 test-rules.md 未明确要求"新增功能必须有测试"，且两套分批逻辑的循环结构相似度较高。**未达到 80 阈值**，因为缺少强制性的测试覆盖规则支撑。
- **修复建议**: 新增 `TestPushFilesBatched` 类，至少覆盖跨批（51+ 文件）和失败即停两个场景

### Issue 4: 未使用 `httpx.Client` 复用连接池 → **置信度: 25** ❌ 已过滤

- **类型**: Performance / Best Practices
- **位置**: `lifeprism/sync/sync_client.py:530, 928`
- **评分理由**: 文件中全部 9 处 `httpx.post()` 均使用便捷函数模式，属于**文件一贯的编码风格**。10 分钟同步间隔远超 TCP keep-alive 超时，连接池复用收益仅限于单次同步内部。无 CLAUDE.md 或 coding-rules 要求使用 `httpx.Client`。属于性能优化建议而非规范违反。

### Issue 5: Flow 文档 Push 步骤描述过时 → **置信度: 30** ❌ 已过滤

- **类型**: Documentation
- **位置**: `docs/flows/2026-07-11-data-sync-flow.md`
- **评分理由**: Flow 文档不属于"必须与代码同步"的类型（vs 自动生成的 `docs/generated/`）。docs-rules 中**没有"代码行为变更后必须更新 flow 文档"的明确约束**。实际影响中等——开发者阅读时会被误导，但代码本身是终极真相。无法被 linter/CI 自动检测。

### Issue 6: ADR 未记录分批推送对原子性的影响 → **置信度: 25** ❌ 已过滤

- **类型**: Architecture / Documentation
- **位置**: 文档
- **评分理由**: 不满足 `write-decisions` skill 的四个触发条件。现有 ADR 已明确声明"整体原子性指 `last_sync_time` 更新是原子的，不指数据库事务级别"。分批后 `last_sync_time` 不更新的保护机制未改变。HTTP 单请求级别的"原子性"从来不是设计保证，`last_sync_time` + 幂等重试才是。

### Issue 7: `batch_size = 1000` 局部变量与 `FILE_BATCH_SIZE = 50` 常量不一致 → **置信度: 10** ❌ 已过滤

- **类型**: Code Quality
- **位置**: `lifeprism/sync/sync_client.py:510`
- **评分理由**: 属于**误报**。`FILE_BATCH_SIZE = 50` 是模块级常量（控制文件推送），`batch_size = 1000` 是函数内局部变量（控制数据库记录推送）。两者用途不同、数值不同，局部变量小写命名符合 Python 惯例。`backend-core-rules.md` 的常量全大写规则针对的是模块级常量，不约束局部变量。

### Issue 8: 测试使用通用 `Exception` 而非 `httpx.HTTPStatusError` → **置信度: 45** ❌ 已过滤

- **类型**: Testing
- **位置**: `test/core/integration/sync/test_sync_client_batch.py:433`
- **评分理由**: 确认存在 mock 类型不匹配，但属于低影响问题。测试的核心验证目标（异常传播 + 批次中止）已达成。**整个项目无任何测试使用 `httpx.HTTPStatusError`**——所有 sync 测试文件均使用相同的 `Exception(...)` 模式（`_make_mock_response` 辅助函数），属于项目范围内的既定约定。

---

## 变更摘要

将 `push_to_remote`（数据库推送）和 `_push_files`（文件推送）从单次大 POST 改为分批 POST 策略，避免首次同步时 50-100MB+ payload 导致云端（896Mi 内存）uvicorn OOM 崩溃。

**核心修改** (`sync_client.py`):
- `push_to_remote`: 逐表 + 分批 1000 行/批 POST（从"33张表单次POST"改为逐表逐批）
- `_push_files`: 按 `FILE_BATCH_SIZE=50` 分批 POST（从"全部文件单次POST"改为每批 50 个文件）
- 新增 `FILE_BATCH_SIZE = 50` 模块常量

**测试修改** (4 个测试文件):
- `test_sync_client.py`: 4 个测试适配（插入增量数据使 push 触发、`assert_not_called()` 替代旧断言）
- `test_sync_client_batch.py`: 新增 `TestPushBatched` 类（3 个测试：大表分批、多表独立、失败即停）
- `test_sync_client_files.py`: 1 个测试适配（插入增量数据）
- `test_sync_timezone_utc.py`: 1 个测试适配（`assert_not_called()`）

**不变部分**: 云端 API 端点不改（幂等设计）；`pull_from_remote` 不改（已有分批）；其他轻量端点不改

**测试结果**: 全部 155 个 sync 集成测试通过，零回归
