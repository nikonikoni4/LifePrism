# Code Review Report

**审查范围**: deletion-sync-02a-statistical PRD 相关工作区变更（未提交）
**审查时间**: 2026-07-23
**PRD 参考**: `.scratch/deletion-sync-02a-statistical/prd.md`
**变更文件**: 7 个核心源码 + 5 个新测试文件

## 架构上下文

### 相关 ADR
- `docs/adr/2026-07-12-migrate-to-utc-timezone.md` — UTC 迁移决策（相关：时区转换上移到 Service 层）
- `docs/adr/2026-07-12-time-conversion-layering.md` — 时间转换职责分层（相关：Provider 不收 date 参数）
- `docs/adr/2026-07-13-date-to-utc-conversion-boundary.md` — 日期到 UTC 转换边界（相关：build_utc_time_range 在 Service 层调用）

### 相关 Spec
- `docs/specs/2026-07-06-repository-core-spec.md` — Repository 数据访问层核心规格
- `docs/specs/2026-07-16-data-sync-core-spec.md` — 数据同步核心规格（墓碑写入机制）

### 相关编码规则
- `docs/coding-rules/repository-module-rules.md` — Repository 三层架构 + 导入纪律 + 反模式清单
- `docs/coding-rules/time-handling-rules.md` — 时区处理内外分离原则
- `docs/coding-rules/backend-core-rules.md` — Provider 单一职责 + 禁止在非 repository 位置写 SQL

### 决策覆盖
- 7/7 变更文件有编码规则/ADR/Spec 关联
- PRD 定义了 24 个 User Stories + 5 个上移点 + 10 个方法迁移路径

## 审查结果

Found 8 issues:

### Issue 1: `update_log_category` / `batch_update_log_category` 使用 `update_by_filter` 而非 PRD 指定的专用方法
- **类型**: Architecture
- **置信度**: 88
- **位置**: `lifeprism/server/services/activity_service.py:180-195` (update_log_category), `:198-214` (batch_update_log_category)
- **详情**: PRD User Story 13 明确要求 `update_log_category` "改用 `ComputerUsageProvider.update_computer_usage(record_id, {"category_id":..., "sub_category_id":...})`"，User Story 16 要求 `batch_update_log_category` "改用 `ComputerUsageProvider.batch_update_computer_usage(record_ids, data)`"。但实际实现使用了 `update_by_filter` + `{"id": log_id}` / `{"id IN": log_ids}`。这导致三个连带问题：
  1. **绕过 `_generic_update` 的自动 `updated_at` 管理**：`update_computer_usage` 走基类 `_generic_update` 会自动设置 `updated_at`（因 `user_app_behavior_log` 配置了 `update_at: True`），但 `update_by_filter` 不走基类，Service 层被迫手动传 `updated_at: get_utc_now_iso()`（line 191）。
  2. **DSL 泄露到 Service 层**：Service 层需要知道 `"id IN"` 字符串语法才能批量操作。
  3. **已有方法被绕过**：`update_computer_usage` 和 `batch_update_computer_usage` 已存在且语义匹配，但被绕过。

  **选择 `update_by_filter` 的可能原因**：`update_computer_usage` 对 `None` 值的语义是"跳过不修改"（line 138），而 `update_log_category` 需要 `sub_category_id=None` 表示"清除为 NULL"。`update_by_filter` 的 `None` = SET NULL 语义满足了这一需求。但这说明接口设计有问题——应该扩展 `update_computer_usage` 支持 None 清除语义（如使用 sentinel 值），而非绕过整个方法。

- **依据**: PRD User Story 13 & 16；repository-module-rules.md Provider 单一职责原则；`lw_base_data_provider.py:1248-1254` `_generic_update` 自动加 `updated_at` 的逻辑

### Issue 2: `update_by_filter` 在 Provider 层引入查询 DSL，破坏语义化接口
- **类型**: Architecture
- **置信度**: 85
- **位置**: `lifeprism/repository/providers/computer_usage_provider.py:240-342`
- **详情**: `update_by_filter` 引入了 `_WHERE_OPERATOR_SUFFIXES`（`>=`, `<=`, `>`, `<`, `!=`, `IN`，line 243）和 `_parse_where_key` 解析器（line 330-342），在 Provider 层构建了一个 mini 查询 DSL。调用方需要知道 `"start_time >="`、`"id IN"` 等 DSL 语法，底层实现细节泄漏到 Service 层。这与 Provider 应提供语义明确的领域方法（`update_computer_usage`、`batch_update_computer_usage` 等）的设计原则冲突。此外：
  - `update_by_filter` 不经过 `_generic_update`，因此不会自动管理 `updated_at`
  - `batch_update_computer_usage` 和 `update_by_filter` 有大量重复的逻辑（动态 SET 子句构建、参数绑定、白名单校验），应抽取共享方法
- **依据**: repository-module-rules.md §1.1 "子类定义元数据即可获得完整单表增删改查能力"；后端核心规范 "Provider 只做数据库操作，不包含业务逻辑"

### Issue 3: 同一类中三个更新方法对 `None` 有两种相反语义
- **类型**: Code Quality
- **置信度**: 90
- **位置**: `lifeprism/repository/providers/computer_usage_provider.py:138` (update_computer_usage), `:195` (batch_update_computer_usage), `:311-312` (update_by_filter)
- **详情**: 
  - `update_computer_usage` 和 `batch_update_computer_usage`：`{k: v for k, v in data.items() if v is not None}` — **None = 跳过，不修改该字段**
  - `update_by_filter`：`set_params = list(set_fields.values())`（不过滤 None）— **None = 将字段设为 SQL NULL**
  
  虽然代码注释在 `activity_service.py:272` 标注了此差异，但同一类中两种相反的 None 语义极易导致 bug：调用方在方法之间切换时可能不察觉语义变化。例如，如果将来有人将 `update_log_category` 从 `update_by_filter` 改为 `update_computer_usage`（就像 PRD 要求的那样），`sub_category_id=None` 会从"清除字段"变为"静默跳过"。
- **依据**: 代码自身不一致（line 138 vs line 311）；多个审查 Agent 独立发现
- **建议**: 使用 sentinel 对象（如 `_UNSET = object()`）区分"不修改"和"设为 NULL"，统一三个方法的 None 语义

### Issue 4: `habit_providers.py` 中 Provider 之间互相调用，违反编码规则
- **类型**: Architecture
- **置信度**: 90
- **位置**: `lifeprism/repository/providers/habit_providers.py:209-215`
- **详情**: `HabitProvider.delete_habit()` 直接实例化并调用 `HabitChallengeProvider()` 和 `HabitCheckinProvider()`：
  ```python
  challenge_provider = HabitChallengeProvider()
  challenge_provider.delete_by_habit_id(habit_id)   # line 211
  checkin_provider = HabitCheckinProvider()
  checkin_provider.delete_by_habit_id(habit_id)      # line 215
  ```
  `repository-module-rules.md` §2.2 和反模式表（§5）明确禁止 "Provider 之间不应互相 import" 和 "Provider 之间互相调用"。级联删除（一个操作影响多张表）是 Aggregator 的典型职责。项目已有 `HabitAggregator`（`repository/__init__.py:51` 导出为 `habit_repository`），级联逻辑应上移到该 Aggregator。

  **上下文说明**：此变更是 review 020 中识别的 "L3 级联删除修复已就绪待提交" 的实现。修复的方向正确（从原始 DELETE 改为走 `_generic_*` 通道写墓碑），但实现位置应在 Aggregator 而非 Provider。
- **依据**: repository-module-rules.md §2.2 导入纪律 + §5 常见反模式表

### Issue 5: `batch_update_computer_usage` 和 `update_by_filter` 绕过 `_generic_update`，不自动管理 `updated_at`
- **类型**: Architecture / Data Integrity
- **置信度**: 85
- **位置**: `lifeprism/repository/providers/computer_usage_provider.py:173-223` (batch_update), `:240-328` (update_by_filter)
- **详情**: 基类 `_generic_update`（`lw_base_data_provider.py:1248-1254`）为配置了 `update_at: True` 的表自动注入 `updated_at = get_utc_now_iso()`。但 `batch_update_computer_usage` 和 `update_by_filter` 都构建自己的 SQL UPDATE，不经过 `_generic_update`。虽然 Service 层（`activity_service.py:191, 212`）手动传入了 `updated_at`，但：
  1. 这导致 `updated_at` 管理路径分裂：`update_computer_usage` 走自动路径，`batch_update`/`update_by_filter` 走手动路径
  2. `update_logs_by_app_title`（`activity_service.py:273-297`）通过 `update_by_filter` 更新但**未传入** `updated_at`，这意味着这些修改不会触发 LWW 同步
  3. 为弥补此缺口引入的 `_SYSTEM_UPDATE_FIELDS = {"updated_at"}`（line 171）本质上绕过了基类的白名单设计
- **依据**: `lw_base_data_provider.py:1248-1254` `_generic_update` 逻辑；data-sync-core-spec LWW 同步依赖 `updated_at` 字段

### Issue 6: `update_logs_by_app_title` 未设置 `updated_at`，LWW 同步可能丢失
- **类型**: Data Integrity
- **置信度**: 82
- **位置**: `lifeprism/server/services/activity_service.py:273-279`
- **详情**: `update_logs_by_app_title` 构建的 `set_fields` 不包含 `updated_at`：
  ```python
  set_fields: dict = {
      "category_id": category_id,
      "sub_category_id": sub_category_id,
  }
  ```
  而同一文件中 `update_log_category`（line 191）和 `batch_update_log_category`（line 212）都明确传入了 `updated_at: get_utc_now_iso()`。通过此路径修改的记录不会更新 `updated_at` 时间戳，其他设备上的旧数据可能在 LWW 同步时覆盖此修改。这是从旧 `ServerLWDataProvider.update_logs_by_app_title` 继承的已有行为（旧 SQL 也未更新 `updated_at`），但在新架构中此不一致性更加明显。
- **依据**: data-sync-core-spec LWW 冲突解决依赖 `updated_at`；同文件 line 191 和 line 212 的对比

### Issue 7: S3 端到端集成测试缺失
- **类型**: Testing
- **置信度**: 85
- **位置**: `test/core/integration/test_activity_api.py`（不存在）
- **详情**: PRD Testing Decisions §S3 明确要求创建端到端行为等价测试：
  - `/activity/logs/{id}` 返回字段一致（含 `category_name` / `sub_category_name`）
  - `/activity/logs` 批量删除后记录消失 + `deletion_log` 有墓碑
  - `/activity/stats` 返回数据结构一致
  该文件在 git status 中既不是 tracked 也不是 untracked，完全不存在。S1（Provider 单元测试）和 S2（Service 单元测试）已就绪，但 PRD 要求的 S3 集成测试缺失。没有集成测试，迁移前后的 API 行为等价性无法在系统层面验证。
- **依据**: PRD Testing Decisions §S3；git status 确认文件不存在

### Issue 8: `_SYSTEM_UPDATE_FIELDS` 绕过基类白名单机制
- **类型**: Architecture
- **置信度**: 80
- **位置**: `lifeprism/repository/providers/computer_usage_provider.py:171`
- **详情**: `_SYSTEM_UPDATE_FIELDS = {"updated_at"}` 允许 `updated_at` 被显式传入 `batch_update_computer_usage` 和 `update_by_filter`。但 `updated_at` 不在 `_UPDATE_FIELDS` 中的设计意图是：该字段由系统自动管理（`_generic_update` 自动设置），调用方不可手动操作。引入 `_SYSTEM_UPDATE_FIELDS` 在技术上是解决 `batch_update`/`update_by_filter` 绕过 `_generic_update` 的变通方案，但它在概念上破坏了白名单的完整性——如果 `updated_at` 可以通过扩展白名单来手动设置，那 `created_at` 为什么不能？这为未来的字段管理分裂埋下伏笔。
- **依据**: repository-core-spec LWBaseDataProvider `_UPDATE_FIELDS` 设计意图；`lw_base_data_provider.py:1248-1254`

## 变更摘要

本次变更是 deletion-sync-02a-statistical PRD 的实现，将 `statistical_data_providers.py` 中的 10 个业务方法迁移到 `ComputerUsageProvider`/`ComputerUsageAggregator`/Service 层：

1. **统计文件标记废弃**：`statistical_data_providers.py` 标记为 DEPRECATED，删除 11 个死代码方法 + `__main__` 块，保留 10 个业务方法作为基线测试对照
2. **Provider 新增方法** (+243 行)：`computer_usage_provider.py` 新增 `batch_update_computer_usage`、`batch_delete_computer_usage`、`update_by_filter`、`get_total_duration`、`get_top_groups_by_duration` 5 个方法
3. **Aggregator 透传** (+26 行)：`computer_usage_aggregator.py` 新增 5 个透传方法
4. **Service 层迁移** (+100 行)：`activity_service.py` 6 处调用迁移 + 业务逻辑上移；`activity_stats_builder.py` 5 处调用迁移
5. **级联删除墓碑修复**：`habit_providers.py` + `custom_record_aggregator.py` 级联删除改用 `_generic_*` 通道写墓碑
6. **测试覆盖**：5 个新测试文件覆盖 Provider 方法 + Service 业务逻辑 + 基线对照

### 关键设计决策
- **时区转换上移**：所有 `build_utc_time_range` 调用从 Provider 移到 Service 层，符合 time-handling-rules "Provider 不收 date 参数"
- **Python 层时区分组**：`build_activity_summary` 复用 `_add_local_date_column` 做时区分组（非 SQL `DATE()`），保留跨时区边界正确性
- **goal_id 三态语义上移**：`None`=不修改 / `""`=清除 / `"goal-xxx"`=设置，在 Service 层处理
- **墓碑写入**：delete 操作统一走 `_generic_delete` / `_generic_batch_delete`，为 PRD 3 的墓碑同步做准备

### 正向发现
- 所有 SQL 字段名拼接均通过白名单（`_UPDATE_FIELDS`、`_FILTER_FIELDS`）严格校验，无 SQL 注入风险
- `IN` 子句对空列表做了 `1=0` 保护，避免 SQL 语法错误
- 操作符后缀解析顺序正确（长后缀优先，`>=` 不会被误解析为 `>`）
- 所有用户数据通过参数化 `?` 占位符传递
- 注释合规检查全部通过：26 个检查点中注释与实现一致，DEPRECATED 警告完整，时区约束被正确遵守
- 墓碑写入验证覆盖到位：deletion_log 的 `record_id` 使用 `hash_id`、`source` 字段正确
