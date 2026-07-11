# Backend Timezone Issues Report

> **生成时间**: 2026-07-12  
> **目的**: 全面检查后端所有时间字段的时区使用情况，按优先级分类问题并提供修复建议

---

## 第一部分：时区使用统计

### 1.1 总体统计

| 分类 | 数量 | 时区 | 格式 |
|------|------|------|------|
| **SQLite DEFAULT 自动生成** | 48 个表的 created_at | 本地时间 | `datetime('now', 'localtime')` → `YYYY-MM-DD HH:MM:SS` |
| **SQLite DEFAULT 自动生成** | 35 个表的 updated_at | 本地时间 | `datetime('now', 'localtime')` → `YYYY-MM-DD HH:MM:SS` |
| **旧迁移遗留（UTC）** | 3 个字段 | UTC | `CURRENT_TIMESTAMP` → `YYYY-MM-DD HH:MM:SS` |
| **Python 代码写入（本地时间）** | ~30 处 | 本地时间 | `datetime.now().isoformat()` 或 `.strftime()` |
| **Python 代码写入（UTC）** | 12 处 | UTC | `datetime.now(timezone.utc).isoformat()` |
| **业务时间字段** | 35 个字段 | 混合 | 取决于代码写入逻辑 |

### 1.2 时区使用分布

#### 本地时间（Naive Datetime）使用位置
- **SQLite DEFAULT**: 48 个表使用 `datetime('now', 'localtime')`
- **Python 代码**: 约 30 处使用 `datetime.now()` 写入数据库字段

#### UTC 时间使用位置
- **同步相关**: `sync_client.py`, `heartbeat_manager.py` (心跳时间戳)
- **API 响应**: `sync_cloud_api.py` (返回 sync_time、server_time)
- **特定字段**: `commitments.created_at`, `user_values.created_at` (显式写入 UTC)
- **旧迁移遗留**: `todo_list.created_at`, `timeline_custom_block.created_at/updated_at`

#### 格式不一致问题
| 来源 | 格式 | 示例 |
|------|------|------|
| SQLite DEFAULT | `YYYY-MM-DD HH:MM:SS` | `2026-07-12 00:29:54` |
| `.isoformat()` | `YYYY-MM-DDTHH:MM:SS.ffffff` | `2026-07-12T00:29:54.123456` |
| `.strftime()` | `YYYY-MM-DD HH:MM:SS` | `2026-07-12 00:29:54` |

---

## 第二部分：时区不一致问题

### P0: 参与数据同步的字段，时区不一致（必须立即修复）

#### 问题 1: 旧迁移遗留使用 CURRENT_TIMESTAMP（UTC）

| 表名.字段名 | 当前时区 | SQLite DEFAULT | 是否参与同步 | 代码写入位置 |
|------------|---------|----------------|------------|-------------|
| `todo_list.created_at` | **UTC** | `CURRENT_TIMESTAMP` | ✅ 是 | 无手动写入（SQLite 自动） |
| `timeline_custom_block.created_at` | **UTC** | `CURRENT_TIMESTAMP` | ✅ 是 | 无手动写入（SQLite 自动） |
| `timeline_custom_block.updated_at` | **UTC** | `CURRENT_TIMESTAMP` | ✅ 是 | 无手动写入（SQLite 自动） |

**影响**:
- 这 3 个字段使用 UTC 时间，其他 45 个表使用本地时间
- 数据同步时可能因时区不一致导致冲突判断错误
- 显示时间比其他表早 8 小时（UTC+8 时区）

**根本原因**: 旧迁移脚本遗留，未使用 `datetime('now', 'localtime')`

**修复建议**:
```sql
-- 迁移步骤：
-- 1. 修改 DEFAULT 为 localtime
ALTER TABLE todo_list ...
ALTER TABLE timeline_custom_block ...

-- 2. 转换历史数据（UTC → 本地时间）
UPDATE todo_list 
SET created_at = datetime(created_at, '+8 hours') 
WHERE created_at IS NOT NULL;

UPDATE timeline_custom_block 
SET created_at = datetime(created_at, '+8 hours'),
    updated_at = datetime(updated_at, '+8 hours')
WHERE created_at IS NOT NULL;
```

#### 问题 2: Python 代码写入格式不一致（带 T vs 不带 T）

**位置 1**: `lw_base_data_provider.py:1184`
```python
# ❌ 问题：使用 .isoformat()，格式为 "2026-07-12T00:29:54.123456"
data["updated_at"] = datetime.now().isoformat()
```
- **影响范围**: 所有继承 `LwBaseDataProvider` 的表手动更新 `updated_at` 时
- **参与同步**: ✅ 是（约 35 个表）
- **格式冲突**: SQLite DEFAULT 为 `YYYY-MM-DD HH:MM:SS`（不带 T），Python 为 `YYYY-MM-DDTHH:MM:SS.ffffff`（带 T）

**位置 2**: `map_cache_providers.py:311, 672`
```python
# ❌ 问题：批量更新时使用 .isoformat()
data["updated_at"] = datetime.now().isoformat()
```
- **影响范围**: `category_map_cache`, `multi_purpose_map_cache`, `single_purpose_map_cache`
- **参与同步**: ✅ 是
- **格式冲突**: 同上

**位置 3**: `habit_providers.py:403-404`
```python
# ❌ 问题：同一位置使用两种格式
now = datetime.now().isoformat()  # "2026-07-12T00:29:54.123456"
updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # "2026-07-12 00:29:54"
```
- **影响范围**: `habit_challenges` 表
- **参与同步**: ✅ 是
- **格式冲突**: 同一函数内使用两种不同格式

**位置 4**: `chatbot_service.py:87-88, 144, 147`
```python
# ❌ 问题：chat_session 使用 .isoformat()
created_at=metadata.get("created_at", datetime.now().isoformat())
updated_at=metadata.get("updated_at", datetime.now().isoformat())
```
- **影响范围**: `chat_session` 表（虽然 timestamps=False，但手动写入）
- **参与同步**: ❌ 否
- **格式问题**: 使用 `.isoformat()` 格式

**修复建议**:
```python
# 方案 1: 统一改为 .strftime()（推荐）
data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 方案 2: 在 LwBaseDataProvider 中封装统一方法
class LwBaseDataProvider:
    @staticmethod
    def _get_timestamp() -> str:
        """返回与 SQLite DEFAULT 一致的时间戳格式"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def update(self, record_id, data):
        if self._TABLE_NAME in self._TABLES_WITH_UPDATE_AT and "updated_at" not in data:
            data["updated_at"] = self._get_timestamp()
```

#### 问题 3: 业务时间字段写入时区不一致

**位置**: `goal_service.py:234`
```python
# ❌ 问题：goal.time_invested_updated_at 使用本地时间
item["time_invested_updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```
- **影响范围**: `goal.time_invested_updated_at` 字段
- **参与同步**: ✅ 是
- **时区**: 本地时间（与其他字段一致，但应明确记录）

**位置**: `habit_service.py:225, 359, 432, 462, 539, 704`
```python
# ❌ 问题：多处使用 .isoformat()
"finished_at": datetime.now().isoformat()
"paused_at": datetime.now().isoformat()
now_str = datetime.now().isoformat()
```
- **影响范围**: `habits.paused_at`, `habit_challenges.finished_at`, `habit_checkins.completed_at`
- **参与同步**: ✅ 是
- **格式冲突**: 使用 `.isoformat()` 格式（带 T）

**位置**: `taskpool_service.py:180`, `plandoc_sync_service.py:578, 607`
```python
# ✅ 正确：使用 .strftime()
updates["actual_finished_at"] = datetime.now().strftime("%Y-%m-%d")
update_data["actual_finished_at"] = datetime.now().strftime("%Y-%m-%d")
```
- **影响范围**: `todo_list.actual_finished_at`
- **参与同步**: ✅ 是
- **格式**: 正确（YYYY-MM-DD，仅日期）

---

### P1: 不参与同步，但影响业务逻辑的字段

#### 问题 4: custom_record_aggregator 使用本地时间但未明确标注

**位置**: `custom_record_aggregator.py:126, 381, 603`
```python
# ⚠️ 潜在问题：隐式使用本地时间
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```
- **影响范围**: `custom_record_types.created_at`, `custom_record_fields.created_at`
- **参与同步**: ✅ 是（custom_record_types），❌ 否（custom_record_fields）
- **时区**: 本地时间（但应在代码注释中明确）

**位置**: `habit_providers.py:558`, `habit_chain_providers.py:376`
```python
# ⚠️ 潜在问题：update 操作使用 .strftime()
now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```
- **影响范围**: `habit_challenges`, `habit_chains`, `habit_chain_nodes`
- **参与同步**: ✅ 是
- **格式**: 正确（但与 habit_providers.py:403 的 `.isoformat()` 不一致）

#### 问题 5: sync_service 使用本地时间处理数据同步

**位置**: `sync_service.py:139, 144`
```python
# ⚠️ 潜在问题：数据同步时使用本地时间
analysis_start_time = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
analysis_end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
```
- **影响范围**: 行为分析数据同步逻辑
- **参与同步**: ❌ 否（内部逻辑）
- **时区**: 本地时间（但与云端时区可能不一致）

---

### P2: 仅用于显示或内部逻辑的字段

#### 问题 6: 日志记录和临时变量使用本地时间

以下位置使用 `datetime.now()` 但**不写入数据库时间字段**，**优先级最低**：

| 位置 | 用途 | 是否需要修复 |
|------|------|------------|
| `monitor.py:47, 121` | 监控开始时间 | ❌ 否（内部变量） |
| `data_clean.py:581` | 数据清理结束时间 | ❌ 否（内部变量） |
| `config_migrator.py:118` | 迁移脚本时间戳 | ❌ 否（文件名） |
| `migration_runner.py:78` | 迁移脚本时间戳 | ❌ 否（文件名） |
| `llm_call_logger.py:158, 259, 287, 334` | LLM 调用日志 | ❌ 否（日志记录） |
| `helpers.py:43, 48` | 辅助函数（获取当前时间字符串）| ❌ 否（显示用） |
| `context.py:185` | Agent 上下文显示 | ❌ 否（日志显示） |
| `prompt_loader.py:178` | Prompt 使用统计 | ❌ 否（内部统计） |
| `session.py:24, 51, 53, 337, 364, 400` | Session 管理（名称、消息时间戳）| ❌ 否（内存对象） |
| `category_service.py:168, 1499` | 服务层内部时间变量 | ❌ 否（内部逻辑） |
| `data_processing_service.py:836, 837` | 数据处理时间窗口 | ❌ 否（内部逻辑） |
| `timeline_builder.py:599` | Timeline 构建起始时间 | ❌ 否（内部逻辑） |
| `schedule_service.py:34, 102, 184, 222, 267, 365` | 定时任务时间计算 | ⚠️ 可能（需验证与数据库字段关系）|
| `report_service.py:135, 230, 333` | 报告生成当前日期 | ⚠️ 可能（需验证是否用于查询）|
| `goal_service.py:114, 210, 513` | 目标服务内部逻辑 | ⚠️ 可能（需验证）|
| `habit_aggregator.py:94` | 习惯聚合结束日期 | ❌ 否（查询参数）|
| `add_on_service.py:180, 239` | 扩展目录 created_at | ❌ 否（不参与同步）|
| `agent_schedule_job.py:455, 466, 569, 574` | Agent 定时任务逻辑 | ❌ 否（内部逻辑）|

#### 问题 7: UTC 时间使用（正确）

以下位置使用 `datetime.now(timezone.utc)`，用于**同步相关功能**，**时区正确**：

| 位置 | 用途 | 时区 | 是否正确 |
|------|------|------|---------|
| `sync_client.py:167, 170, 230` | 同步客户端时间戳 | UTC | ✅ 正确 |
| `heartbeat_manager.py:49, 64, 84` | 心跳管理时间戳 | UTC | ✅ 正确 |
| `sync_cloud_api.py:185, 220, 262, 384, 468` | API 响应 sync_time/server_time | UTC | ✅ 正确 |
| `commitment_provider.py:191` | commitments.created_at | UTC | ⚠️ 需验证（其他表用本地时间）|
| `value_provider.py:135` | user_values.created_at | UTC | ⚠️ 需验证（其他表用本地时间）|
| `aw_base_data_provider.py:149` | ActivityWatch 数据查询 | UTC | ✅ 正确（外部系统）|

**⚠️ 特别注意**: `commitment_provider.py:191` 和 `value_provider.py:135` 显式写入 UTC 时间到 `created_at` 字段，而其他 47 个表使用本地时间。这可能导致时区不一致。

---

## 第三部分：修复优先级

### P0 清单（必须立即修复）

| 问题 | 表名.字段名 | 当前问题 | 影响范围 | 修复难度 |
|------|-----------|---------|---------|---------|
| 1 | `todo_list.created_at` | CURRENT_TIMESTAMP（UTC） | 参与同步 | 中（需迁移历史数据）|
| 1 | `timeline_custom_block.created_at` | CURRENT_TIMESTAMP（UTC） | 参与同步 | 中（需迁移历史数据）|
| 1 | `timeline_custom_block.updated_at` | CURRENT_TIMESTAMP（UTC） | 参与同步 | 中（需迁移历史数据）|
| 2 | `lw_base_data_provider.py:1184` | `.isoformat()` 格式不一致 | 35 个表 | 低（单处修改）|
| 2 | `map_cache_providers.py:311, 672` | `.isoformat()` 格式不一致 | 3 个 map_cache 表 | 低（2 处修改）|
| 2 | `habit_providers.py:403` | `.isoformat()` 格式不一致 | habit_challenges | 低（1 处修改）|
| 3 | `habit_service.py` 多处 | `.isoformat()` 格式不一致 | habits, habit_challenges, habit_checkins | 低（6 处修改）|

**P0 修复步骤**:

1. **立即修复格式不一致**（低风险，高收益）:
   ```python
   # 1. 修改 lw_base_data_provider.py:1184
   - data["updated_at"] = datetime.now().isoformat()
   + data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   
   # 2. 修改 map_cache_providers.py:311, 672
   - data["updated_at"] = datetime.now().isoformat()
   + data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   
   # 3. 修改 habit_providers.py:403
   - now = datetime.now().isoformat()
   + now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   
   # 4. 修改 habit_service.py 所有 .isoformat()
   - "finished_at": datetime.now().isoformat()
   + "finished_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
   ```

2. **创建迁移脚本修复旧迁移遗留**（需谨慎）:
   ```python
   # lifeprism/storage/migrations/migrate_timezone_fix_v1.py
   
   def upgrade(db: Database):
       # 1. 修改 DEFAULT 为 localtime
       db.execute("""
           CREATE TABLE todo_list_new AS SELECT * FROM todo_list;
           DROP TABLE todo_list;
           CREATE TABLE todo_list (
               ...,
               created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
               ...
           );
           INSERT INTO todo_list SELECT * FROM todo_list_new;
           DROP TABLE todo_list_new;
       """)
       
       # 2. 转换历史数据（UTC → 本地时间，假设 UTC+8）
       db.execute("""
           UPDATE todo_list 
           SET created_at = datetime(created_at, '+8 hours') 
           WHERE created_at IS NOT NULL;
       """)
       
       # 3. 同样处理 timeline_custom_block
       ...
   ```

### P1 清单（尽快修复）

| 问题 | 位置 | 当前问题 | 影响范围 | 修复难度 |
|------|------|---------|---------|---------|
| 4 | `custom_record_aggregator.py` | 隐式本地时间 | custom_record 相关表 | 低（加注释）|
| 4 | `habit_providers.py:558` | 格式不一致（同文件内）| habit_challenges | 低（1 处修改）|
| 5 | `sync_service.py:139, 144` | 本地时间用于同步逻辑 | 行为分析同步 | 中（需验证）|
| 7 | `commitment_provider.py:191` | UTC 时间（其他表用本地时间）| commitments.created_at | 中（需统一策略）|
| 7 | `value_provider.py:135` | UTC 时间（其他表用本地时间）| user_values.created_at | 中（需统一策略）|

**P1 修复建议**:
- 统一 `commitment_provider` 和 `value_provider` 的时区策略（要么全 UTC，要么全本地时间）
- 验证 `sync_service` 中使用本地时间是否会导致多设备同步时时区混乱
- 在所有时间写入位置添加明确注释标注时区

### P2 清单（可延后）

| 问题 | 位置 | 当前问题 | 影响范围 | 修复难度 |
|------|------|---------|---------|---------|
| 6 | 各服务层内部变量 | 隐式本地时间 | 日志、显示 | 低（加注释）|
| - | `schedule_service.py` | 需验证是否影响数据库字段 | 定时任务 | 中（需分析）|
| - | `report_service.py` | 需验证是否用于查询条件 | 报告生成 | 中（需分析）|

---

## 第四部分：根本原因分析

### 4.1 为什么会出现时区不一致？

1. **历史遗留**:
   - `todo_list`, `timeline_custom_block` 使用旧迁移脚本，未统一为 `datetime('now', 'localtime')`
   - 早期代码未明确时区策略

2. **Python vs SQLite 格式差异**:
   - SQLite DEFAULT: `datetime('now', 'localtime')` → `YYYY-MM-DD HH:MM:SS`
   - Python `.isoformat()`: `datetime.now().isoformat()` → `YYYY-MM-DDTHH:MM:SS.ffffff`
   - 开发者习惯使用 `.isoformat()`，但不知道格式不一致

3. **缺少统一封装**:
   - 各文件自行写 `datetime.now().isoformat()` 或 `.strftime()`
   - 没有统一的时间生成方法

4. **UTC vs 本地时间混用**:
   - 同步相关代码正确使用 UTC（`sync_client`, `sync_cloud_api`）
   - 但 `commitment_provider`, `value_provider` 也用 UTC，而其他 47 个表用本地时间
   - 缺少明确的时区策略文档

### 4.2 潜在风险

1. **数据同步冲突**:
   - 格式不一致（带 T vs 不带 T）可能导致云端判断为"需要更新"
   - 时区不一致（UTC vs 本地时间）会导致时间比对错误

2. **时间显示错误**:
   - `todo_list.created_at` 使用 UTC，其他表用本地时间，前端显示时会早 8 小时

3. **业务逻辑错误**:
   - 如果按 `created_at` 排序，UTC 时间的记录会排在前面

---

## 第五部分：长期改进建议

### 5.1 建立时区策略文档

在 `docs/coding-rules/backend-timezone-rules.md` 中明确：
1. **存储策略**: 数据库统一使用本地时间（`datetime('now', 'localtime')`）
2. **Python 代码**: 写入时间字段统一使用 `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
3. **UTC 例外**: 仅同步相关代码使用 UTC（明确标注）
4. **格式要求**: 禁止 `.isoformat()`，必须 `.strftime("%Y-%m-%d %H:%M:%S")`

### 5.2 封装统一时间生成方法

```python
# lifeprism/repository/base_providers/lw_base_data_provider.py

class LwBaseDataProvider:
    @staticmethod
    def _get_local_timestamp() -> str:
        """返回本地时间戳，格式: YYYY-MM-DD HH:MM:SS
        
        ⚠️ 用于数据库时间字段写入，与 SQLite DEFAULT (datetime('now', 'localtime')) 格式一致
        """
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def _get_utc_timestamp() -> str:
        """返回 UTC 时间戳（ISO 格式），仅用于同步相关字段
        
        ⚠️ 仅用于 sync_client, heartbeat, cloud_api 等同步相关代码
        """
        return datetime.now(timezone.utc).isoformat()
```

### 5.3 添加静态检查

在 CI 中添加检查，禁止在 Repository/Provider 层使用 `.isoformat()`:

```python
# scripts/check_timezone.py

def check_timezone_usage():
    bad_patterns = [
        (r'datetime\.now\(\)\.isoformat\(\)', '禁止使用 .isoformat()，应使用 .strftime("%Y-%m-%d %H:%M:%S")'),
        (r'CURRENT_TIMESTAMP', '禁止使用 CURRENT_TIMESTAMP，应使用 datetime(\'now\', \'localtime\')'),
    ]
    
    for pattern, message in bad_patterns:
        if found in ['repository', 'server/services']:
            raise ValueError(f'{message} at {file}:{line}')
```

### 5.4 前端时区处理

如果需要支持多时区用户，应该：
1. 后端统一存储 UTC 时间
2. 前端根据用户时区转换显示
3. **当前系统不需要**（单用户本地应用）

---

## 附录：代码位置汇总

### 需要修复的代码位置（按优先级）

#### P0（立即修复）
```
lifeprism/repository/base_providers/lw_base_data_provider.py:1184
lifeprism/repository/providers/map_cache_providers.py:311
lifeprism/repository/providers/map_cache_providers.py:672
lifeprism/repository/providers/habit_providers.py:403
lifeprism/server/services/habit_service.py:225
lifeprism/server/services/habit_service.py:359
lifeprism/server/services/habit_service.py:432
lifeprism/server/services/habit_service.py:462
lifeprism/server/services/habit_service.py:539
lifeprism/server/services/habit_service.py:704
```

#### P1（尽快修复）
```
lifeprism/repository/providers/habit_providers.py:558
lifeprism/server/services/sync_service.py:139
lifeprism/server/services/sync_service.py:144
lifeprism/server/providers/commitment_provider.py:191
lifeprism/server/providers/value_provider.py:135
```

### 不需要修复的代码位置（内部逻辑/日志）
```
lifeprism/monitor/windows_monitor/monitor.py:47, 121
lifeprism/config/migrations/config_migrator.py:118
lifeprism/processors/data_clean.py:581
lifeprism/llm/agent/context.py:185
lifeprism/llm/session/manager.py:24, 51, 53, 337, 364, 400
lifeprism/llm/utils/llm_call_logger.py:158, 259, 287, 334
lifeprism/llm/utils/helpers.py:43, 48
lifeprism/llm/prompts/prompt_loader.py:178
lifeprism/server/services/category_service.py:168, 1499
lifeprism/server/services/data_processing_service.py:836, 837
lifeprism/server/services/timeline_builder.py:599
lifeprism/repository/aggregators/habit_aggregator.py:94
lifeprism/server/services/add_on_service.py:180, 239
lifeprism/llm/function/agent_schedule_job.py:455, 466, 569, 574
```

---

## 总结

### 关键发现

1. **旧迁移遗留**: 3 个字段使用 `CURRENT_TIMESTAMP`（UTC），与其他 83 个字段（本地时间）不一致
2. **格式不一致**: Python 代码 10+ 处使用 `.isoformat()`（带 T），与 SQLite DEFAULT 格式冲突
3. **时区混用**: `commitment_provider`, `value_provider` 使用 UTC，其他 47 个表用本地时间
4. **缺少规范**: 无明确的时区策略文档和统一封装方法

### 修复优先级

- **P0**: 10 处代码修改（格式统一）+ 1 个迁移脚本（修复旧迁移遗留）
- **P1**: 5 处代码修改（时区策略统一）
- **P2**: 文档化 + 静态检查

### 预期收益

- ✅ 消除数据同步冲突风险
- ✅ 修复时间显示错误（UTC vs 本地时间）
- ✅ 建立明确的时区处理规范
- ✅ 防止未来引入新的时区问题
