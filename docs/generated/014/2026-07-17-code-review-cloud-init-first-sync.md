# Code Review Report

**审查范围**: 云端首次同步全清覆盖方案（7 个文件 git diff 变更）
**审查时间**: 2026-07-17
**变更文件**:
- `lifeprism/config/database.py`（MOOD_IMPACTS_CONFIG id 回滚）
- `lifeprism/repository/providers/mood_providers.py`（方法签名回滚）
- `lifeprism/repository/sync_repository.py`（新增 query_all + delete_all_rows）
- `lifeprism/server/api/sync_cloud_api.py`（新增 3 个端点）
- `lifeprism/server/bootstrap.py`（agent_only 跳过）
- `lifeprism/sync/constants.py`（常量迁移 + 新增 timeout 常量）
- `lifeprism/sync/sync_client.py`（首次同步分支 + 5 个新方法）

## 架构上下文

### 相关 ADR
- ADR 2026-07-17: 云端初始化与首次同步策略：全清覆盖替代黑名单过滤 (decided)

### 相关编码规则
- `docs/coding-rules/backend-core-rules.md` — 后端核心规范
- `docs/coding-rules/backend-api-rules.md` — API 设计规范
- `docs/coding-rules/repository-module-rules.md` — Repository 数据访问层规范
- `docs/coding-rules/time-handling-rules.md` — 时间处理规则

### 决策覆盖
- 7/7 变更文件有 ADR 关联

## 审查结果

共发现 12 个置信度 >= 50 的问题，其中 10 个已直接修复，2 个需要用户决策。

### 已修复的问题（10 个）

#### Issue 1: N+1 查询（P0，置信度 85）
- **类型**: Performance
- **位置**: `lifeprism/sync/sync_client.py:485-536`（`_advance_local_parent_after_initial_sync`）
- **详情**: 对每个文件路径循环调用 `get_state` + `upsert_state`，导致 2N 次数据库往返
- **修复**: 改用 `batch_get_states` + `batch_upsert_states` 批量操作（单次查询 + 单次事务）

#### Issue 2: 重复扫描文件目录（P0，置信度 65）
- **类型**: Performance
- **位置**: `lifeprism/sync/sync_client.py:441-483`（`_initial_push_files`）
- **详情**: 先调用 `_scan_sync_files` 扫描，再调用 `_refresh_current_hashes`（内部再次扫描），同一批目录被扫描两次
- **修复**: 复用 `_refresh_current_hashes` 的返回值（已返回文件路径列表）

#### Issue 3: 跨层访问私有方法（P1，置信度 80）
- **类型**: Architecture
- **位置**: `lifeprism/sync/sync_client.py:422`（`_initial_push_db`）
- **详情**: 直接访问 `SyncRepository._is_dynamic_table` 私有方法，破坏封装边界
- **修复**: 在 SyncRepository 新增公共方法 `is_dynamic_table`，保留 `_is_dynamic_table` 私有别名向后兼容

#### Issue 4: 抛出 RuntimeError 而非 LWBaseError 子类（P1，置信度 75）
- **类型**: Code Quality
- **位置**: `lifeprism/sync/sync_client.py:432-439`
- **详情**: 直接抛出 Python 内置 `RuntimeError`，未纳入 LWBaseError 异常体系
- **修复**: 改用 `ExternalServiceError`（含 code 和 details）

#### Issue 5: 魔法数字硬编码（P1，置信度 60）
- **类型**: Code Quality
- **位置**: `lifeprism/sync/sync_client.py` 多处 timeout 和 batch_size
- **修复**: 提取 5 个常量到 `constants.py`：`DB_PUSH_BATCH_SIZE`、`INITIALIZATION_STATUS_TIMEOUT`、`FULL_CLEAR_TIMEOUT`、`MARK_INITIALIZED_TIMEOUT`、`PUSH_ENDPOINT_TIMEOUT`

#### Issue 6: 未告警未完全推进的文件（P1，置信度 70）
- **类型**: Code Quality
- **位置**: `lifeprism/sync/sync_client.py:528-536`
- **详情**: 部分文件 state 为 None 时仅记 INFO，会导致下次同步 CONFLICT 误判
- **修复**: 添加 WARNING 日志告警未推进的文件数

#### Issue 7: API 层 except Exception 过于宽泛（P1，置信度 70）
- **类型**: Code Quality
- **位置**: `lifeprism/server/api/sync_cloud_api.py:982-986, 989-992`
- **详情**: `except Exception` 会吞掉编程错误（NameError、AttributeError 等）
- **修复**: 缩小为 `except DataAccessError`，添加 ADR 例外注释说明这是前提 7 的明确要求

#### Issue 8: 空目录未清理（P2，置信度 55）
- **类型**: Code Quality
- **位置**: `lifeprism/server/api/sync_cloud_api.py:1006-1022`
- **修复**: 文件删除后添加 `os.walk(topdown=False)` + `rmdir()` 清理空目录

#### Issue 9: docstring 与代码行为不符（P2，置信度 60）
- **类型**: Documentation
- **位置**: `lifeprism/sync/sync_client.py:323`
- **修复**: 修正 `_full_sync_to_cloud` tables 参数描述为"保留参数仅为兼容 sync_once 调用签名"

#### Issue 10: 注释表述易误解 + docstring 不一致（P2，置信度 55/50）
- **类型**: 代码注释合规
- **位置**: `sync_cloud_api.py:962-964`、`sync_client.py:275-278`、`bootstrap.py:42-45`
- **修复**: 修正 full-clear "保留范围" → "未清空范围"；修正 `_check_cloud_initialized` docstring 控制流描述；bootstrap.py 补充 `initialize_category_colors` 空表行为说明

### 需要用户决策的问题（2 个）

#### Issue 11: 新增方法完全无测试覆盖（置信度 95）
- **类型**: Testing
- **位置**: 8 个核心方法（5 个 SyncClient 方法 + 2 个 SyncRepository 方法 + 3 个 API 端点）
- **详情**: 首次同步全清流程涉及数据销毁/同步操作，完全没有单元测试或集成测试覆盖
- **依据**: AGENTS.md 核心规则 5「Bug 先测试」；CLAUDE.md 核心规则 4
- **决策点**: 测试补全范围与优先级

#### Issue 12: SyncClient 类职责膨胀（置信度 50）
- **类型**: Architecture
- **位置**: `lifeprism/sync/sync_client.py`（整体）
- **详情**: SyncClient 现在承担首次同步 + 增量同步两条差异显著的流程，类规模超 1780 行
- **决策点**: 是否重构为独立的 `InitialSyncService` 类

## 变更摘要

本次实现依据 ADR 2026-07-17 完成"云端首次同步全清覆盖"方案：
1. Phase A: bootstrap.py agent_only 跳过资源/种子数据初始化
2. Phase B: 3 个 API 端点 + 2 个 Repository 方法
3. Phase C: sync_once 首次同步分支 + 5 个首次同步方法
4. Phase D: 共享常量集中化
5. 回滚: mood_impacts 配置回 INTEGER AUTOINCREMENT

审查后修复了 10 个问题（2 个 P0 + 5 个 P1 + 3 个 P2），主要涉及性能优化（N+1 查询、重复扫描）、架构合规（封装、异常体系）、代码质量（魔法数字、告警、异常范围）。
