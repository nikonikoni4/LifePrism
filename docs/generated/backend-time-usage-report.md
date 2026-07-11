# 后端时间使用报告

生成时间: 2026-07-12

## 第一章：时区问题（P0 优先级）

### 问题描述
时区问题是**核心同步 bug**，与时间格式无关。使用 `datetime.now()` 生成的是 naive datetime（无时区信息），不同设备的本地时间不一致会导致数据同步失败。

### 正确使用时区的代码（✅）

以下代码正确使用了 UTC 时区：

**同步模块**：
- `lifeprism/sync/sync_client.py:167,170` - 同步计时使用 UTC
- `lifeprism/sync/sync_client.py:230` - 当前时间戳使用 UTC
- `lifeprism/sync/heartbeat_manager.py:49,64,84` - 心跳时间使用 UTC

**API 层**：
- `lifeprism/server/api/sync_cloud_api.py:185,220,262,384,468` - 所有同步接口返回 UTC 时间

**数据提供者**：
- `lifeprism/server/providers/commitment_provider.py:191` - commitment 更新时间使用 UTC
- `lifeprism/server/providers/value_provider.py:135` - value 更新时间使用 UTC
- `lifeprism/repository/base_providers/aw_base_data_provider.py:149` - ActivityWatch 查询使用 UTC

### 使用 naive datetime 的代码（❌ 影响同步）

**数据库更新时间字段**（高优先级）：
1. `lifeprism/repository/aggregators/custom_record_aggregator.py:126,381,603`
   - `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
   - **影响**：custom_record 的 `updated_at` 字段使用本地时间

2. `lifeprism/repository/providers/habit_providers.py:404,558`
   - `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` / `datetime.now().isoformat()`
   - **影响**：habits 表的 `updated_at` 字段使用本地时间

3. `lifeprism/repository/providers/habit_chain_providers.py:376`
   - `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
   - **影响**：habit_chain 的 `updated_at` 字段使用本地时间

4. `lifeprism/repository/providers/goal_providers.py:490`
   - `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
   - **影响**：goal 的 `updated_at` 字段使用本地时间

5. `lifeprism/server/services/goal_service.py:234`
   - `datetime.now().strftime("%Y-%m-%d %H:%M:%S")`
   - **影响**：goal 的 `time_invested_updated_at` 字段使用本地时间

6. `lifeprism/repository/base_providers/lw_base_data_provider.py:1184`
   - `datetime.now().isoformat()`
   - **影响**：通用数据提供者的 `updated_at` 字段使用本地时间

7. `lifeprism/repository/providers/map_cache_providers.py:311,672`
   - `datetime.now().isoformat()`
   - **影响**：map_cache 的 `updated_at` 字段使用本地时间

**业务逻辑时间字段**（中优先级）：
8. `lifeprism/server/services/habit_service.py:225,359,432,462,539,704`
   - `datetime.now().isoformat()`
   - **影响**：habit 的 `finished_at`, `paused_at` 等状态时间使用本地时间

9. `lifeprism/server/services/taskpool_service.py:180`
   - `datetime.now().strftime("%Y-%m-%d")`
   - **影响**：taskpool 的 `actual_finished_at` 使用本地时间

10. `lifeprism/server/services/plandoc_sync_service.py:578,607`
    - `datetime.now().strftime("%Y-%m-%d")`
    - **影响**：plandoc 同步的 `actual_finished_at` 使用本地时间

11. `lifeprism/server/services/goal_service.py:513`
    - `datetime.now().strftime("%Y-%m-%d")`
    - **影响**：milestone 的 `finish_time` 使用本地时间

**非同步场景**（低优先级，不影响数据同步）：
- LLM 会话管理：`lifeprism/llm/session/manager.py:51,400` - 消息时间戳
- LLM 日志：`lifeprism/llm/utils/llm_call_logger.py:158,259,287,334` - 日志文件名和时间戳
- 截图监控：`lifeprism/monitor/windows_monitor/runtime.py:66` - 运行时时间戳
- 业务服务：`lifeprism/server/services/chatbot_service.py:87,88,144,147` - 会话创建/更新时间
- 配置迁移：`lifeprism/config/migrations/config_migrator.py:118` - 备份文件时间戳
- 数据库迁移：`lifeprism/repository/migrations/migration_runner.py:78` - 迁移文件名时间戳
- AI 上下文：`lifeprism/llm/agent/context.py:185` - 显示给用户的当前时间
- 其他服务：`lifeprism/server/services/add_on_service.py:180,239` - 插件创建时间

### 修复建议

**优先级 1（立即修复）**：
将所有数据库 `updated_at` 字段改为 UTC 时间：
```python
# 错误 ❌
data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 正确 ✅
from datetime import timezone
data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```

**优先级 2（重要修复）**：
将所有业务状态时间字段改为 UTC 时间：
```python
# 错误 ❌
"finished_at": datetime.now().isoformat()

# 正确 ✅
"finished_at": datetime.now(timezone.utc).isoformat()
```

**优先级 3（可选）**：
非同步场景可保持本地时间，但建议统一为 UTC 以避免混淆。

---

## 第二章：时间格式不一致问题（P1 优先级）

### 问题描述
格式不一致不是错误，但会导致：
- 同一表的不同记录格式不一致（如 habits 表）
- 字符串比较可能出问题
- 前端解析需要兼容两种格式

### 标准格式（推荐 ✅）

**格式**：`YYYY-MM-DD HH:MM:SS`  
**生成方式**：`.strftime("%Y-%m-%d %H:%M:%S")`

使用标准格式的代码：
- `lifeprism/repository/aggregators/custom_record_aggregator.py:126,381,603`
- `lifeprism/repository/providers/habit_providers.py:404,558`
- `lifeprism/repository/providers/habit_chain_providers.py:376`
- `lifeprism/repository/providers/goal_providers.py:490`
- `lifeprism/server/services/goal_service.py:234`
- `lifeprism/server/services/sync_service.py:47,139,144`
- `lifeprism/repository/base_providers/lw_base_data_provider.py:125,126`
- `lifeprism/monitor/windows_monitor/monitor.py:51`
- `lifeprism/processors/data_clean.py:81,209`
- `lifeprism/processors/components/event_transformer.py:83,160`

**说明**：这是 SQLite TEXT 字段存储时间的标准格式，易读性好，适合数据库查询。

### ISO 格式（不一致 ⚠️）

**格式**：`YYYY-MM-DDTHH:MM:SS` 或 `YYYY-MM-DDTHH:MM:SS.ffffff`  
**生成方式**：`.isoformat()`

使用 ISO 格式的代码：
- `lifeprism/repository/base_providers/lw_base_data_provider.py:1184` - 通用更新时间
- `lifeprism/repository/providers/map_cache_providers.py:311,672` - map_cache 更新时间
- `lifeprism/repository/providers/habit_providers.py:403` - habit 更新时间（与同文件第404行格式不一致）
- `lifeprism/server/services/habit_service.py:225,359,432,462,539,704` - habit 状态时间
- `lifeprism/server/services/chatbot_service.py:87,88,144,147` - 会话时间
- `lifeprism/llm/session/manager.py:51,400` - 消息时间戳
- `lifeprism/sync/sync_client.py:230` - 同步时间（但这是 UTC，格式不影响同步逻辑）
- `lifeprism/server/api/sync_cloud_api.py` - 同步接口返回（UTC，格式一致）

### 实际数据库格式混乱情况

根据实际查询结果：

**格式一致的表（✅）**：
- `multi_purpose_map_cache.updated_at`: `2026-07-10 23:38:18`
- `custom_record_types.updated_at`: `2026-07-10 16:33:56`
- `goal.updated_at`: `2026-07-10 15:42:26`

**格式混乱的表（❌）**：
- `habits.updated_at`:
  - 旧数据：`2026-05-06T20:53:23.675664` （ISO 格式 + 微秒）
  - 新数据：`2026-04-26 04:00:35` （标准格式）
  
**原因分析**：
- `lifeprism/repository/providers/habit_providers.py:403-404` 同时使用了两种格式：
  ```python
  now = datetime.now().isoformat()           # 行403：ISO格式（未使用）
  updated_at = datetime.now().strftime(...)  # 行404：标准格式（实际写入）
  ```
- 历史数据可能由旧代码生成（使用 `.isoformat()`）

### 修复建议

**方案 1：统一为标准格式（推荐）**
```python
# 统一使用
datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
```

**优点**：
- 与现有大部分代码一致
- SQLite 友好，易于查询
- 易读性好

**缺点**：
- 需要修改所有 `.isoformat()` 的地方

**方案 2：统一为 ISO 格式**
```python
# 统一使用
datetime.now(timezone.utc).isoformat()
```

**优点**：
- 国际标准格式
- Python 原生支持
- 包含时区信息（如果使用 timezone.utc）

**缺点**：
- 需要修改所有 `.strftime()` 的地方
- SQLite 查询需要额外处理

**方案 3：数据库迁移**
如果选择统一格式，需要迁移历史数据：
```sql
-- 将 ISO 格式转换为标准格式
UPDATE habits 
SET updated_at = REPLACE(REPLACE(updated_at, 'T', ' '), '.675664', '')
WHERE updated_at LIKE '%T%';
```

---

## 第三章：修复优先级和路线图

### Phase 1：时区问题修复（P0）

**目标**：确保数据同步正确

**步骤**：
1. 修复所有 `updated_at` 字段（11 处代码）
2. 修复所有业务状态时间字段（3 处代码）
3. 运行集成测试，验证多设备同步

**预计工作量**：2-3 小时

### Phase 2：格式统一（P1）

**目标**：统一时间格式，消除数据库混乱

**步骤**：
1. 决定统一格式（标准格式 vs ISO 格式）
2. 修改所有不一致的代码（约 20 处）
3. 编写数据库迁移脚本
4. 运行迁移，验证历史数据

**预计工作量**：4-6 小时

### Phase 3：前端兼容（P2）

**目标**：确保前端能正确解析统一后的格式

**步骤**：
1. 检查前端时间解析代码
2. 统一前端时间格式化逻辑
3. 测试所有时间显示页面

**预计工作量**：2-3 小时

---

## 附录：关键代码位置速查

### 需要修复时区的文件（按影响优先级）
1. `lifeprism/repository/aggregators/custom_record_aggregator.py` - custom_record 更新时间
2. `lifeprism/repository/providers/habit_providers.py` - habits 更新时间
3. `lifeprism/repository/providers/habit_chain_providers.py` - habit_chain 更新时间
4. `lifeprism/repository/providers/goal_providers.py` - goal 更新时间
5. `lifeprism/server/services/goal_service.py` - goal 投入时间更新
6. `lifeprism/repository/base_providers/lw_base_data_provider.py` - 通用更新时间
7. `lifeprism/repository/providers/map_cache_providers.py` - map_cache 更新时间
8. `lifeprism/server/services/habit_service.py` - habit 状态时间
9. `lifeprism/server/services/taskpool_service.py` - taskpool 完成时间
10. `lifeprism/server/services/plandoc_sync_service.py` - plandoc 完成时间

### 需要统一格式的文件
- 所有上述文件 + `lifeprism/server/services/chatbot_service.py`
- `lifeprism/llm/session/manager.py`（会话时间戳）

---

## 总结

1. **时区问题**是数据同步的核心 bug，必须立即修复（P0）
2. **格式不一致**不影响功能，但会导致数据混乱，建议尽快统一（P1）
3. 两个问题独立，可以分阶段修复
4. 建议修复顺序：时区问题 → 格式统一 → 前端兼容
