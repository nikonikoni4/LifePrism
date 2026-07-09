# 数据库同步表范围扩展

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-09

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

扩展数据库同步的表范围，从当前的 13 张表扩展到 30 张静态表，并新增动态表（`custom_records_{slug}`）的运行时获取逻辑。

当前 `SYNC_TABLES` 白名单仅包含 13 张表，遗漏了大量用户输入数据表（如 `goal_journal`、`plan_doc`、`daily_focus`、`weekly_focus`、习惯相关的 5 张表、心情相关的 3 张表、价值观相关的 2 张表、自定义记录的 2 张元数据表等）。

**扩展范围**：

**用户输入数据**（15 张）：
- `mood_entries`、`diary`、`todo_list`、`goal`、`goal_journal`、`plan_doc`
- `daily_focus`、`weekly_focus`、`habits`、`habit_challenges`、`habit_checkins`
- `habit_chains`、`habit_chain_nodes`、`timeline_custom_block`、`time_paradoxes`

**元数据**（8 张）：
- `category`、`sub_category`、`mood_types`、`mood_impacts`
- `user_values`、`commitments`、`custom_record_types`、`custom_record_fields`

**Monitor 数据**（3 张）：
- `user_app_behavior_log`、`behavior_analysis`、`raw_behavior_analysis`

**缓存表**（3 张）：
- `multi_purpose_map_cache`、`single_purpose_map_cache`、`category_map_cache`

**统计数据**（1 张）：
- `tokens_usage_log`

**动态表获取逻辑**：

```python
def get_all_sync_tables():
    """获取所有需要同步的表（包括动态表）"""
    static_tables = SYNC_TABLES.copy()
    
    # 查询 custom_record_types 获取 slug 列表
    slugs = db.execute("SELECT slug FROM custom_record_types").fetchall()
    
    # 添加动态表
    for (slug,) in slugs:
        static_tables.append(f"custom_records_{slug}")
    
    return static_tables
```

**实现端到端**：
1. 更新 `lifeprism/sync/sync_client.py` 中的 `SYNC_TABLES` 白名单
2. 新增 `get_all_sync_tables()` 函数，运行时获取动态表
3. `sync_once()` 调用 `get_all_sync_tables()` 替代硬编码的 `SYNC_TABLES`
4. 更新相关测试

---

## Acceptance criteria

- [ ] `SYNC_TABLES` 包含所有 30 张静态表
- [ ] `get_all_sync_tables()` 能动态获取 `custom_records_{slug}` 表
- [ ] `sync_once()` 使用 `get_all_sync_tables()` 获取同步表列表
- [ ] 测试覆盖：同步包含动态表的场景
- [ ] 日志记录：INFO 级别记录同步的表数量（包括动态表）

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/01-database-schema-updated-at.md` - 需要所有表都有 `updated_at` 字段
