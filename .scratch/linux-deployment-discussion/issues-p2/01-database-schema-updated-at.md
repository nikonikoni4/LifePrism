# 数据库 Schema 准备 - 添加 updated_at 字段 + 同步约束

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

为 9 个缺少 `updated_at` 字段的表添加此字段，并创建索引以支持增量同步查询。

**需要修改的表**（已确认 `database.py` 的实际配置）：
- `behavior_analysis` - 当前 `"update_at": False`，需改为 `True`
- `category` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`
- `category_map_cache` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`
- `goal` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`
- `mood_entries` - 当前 `"update_at": False`，需改为 `True`
- `sub_category` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`
- `timeline_custom_block` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`
- `todo_list` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`
- `user_app_behavior_log` - 当前缺失 `update_at` 字段（仅有 `"timestamps": True`），需添加 `"update_at": True`

**验证已有配置的表**（无需修改，仅验证）：
- `diary` - 已有 `"update_at": True`，验证即可
- `habits` - 已有 `"update_at": True`，验证即可
- `multi_purpose_map_cache` - 已有 `"update_at": True`，验证即可
- `single_purpose_map_cache` - 已有 `"update_at": True`，验证即可

**实现端到端**：
1. 修改 `lifeprism/config/database.py` 的 `TABLE_CONFIGS`，为这 9 个表添加或修改 `"update_at": True`
2. 创建数据库迁移脚本（`lifeprism/storage/migrations/`），为现有数据添加 `updated_at` 字段，初始值设为当前时间
3. 为每个表创建索引：`CREATE INDEX IF NOT EXISTS idx_{table}_updated_at ON {table}(updated_at)`
4. 验证查询性能：执行 `SELECT * FROM {table} WHERE updated_at > ? ORDER BY updated_at ASC` 测试，确保 9 个表总耗时 < 100ms
5. **为 `timeline_custom_block` 添加 UNIQUE 约束**（同步依赖）：
   - 该表当前主键是 `id AUTOINCREMENT`，无 UNIQUE 约束，无法支持 `INSERT OR REPLACE` 同步判重
   - 在 `TABLE_CONFIGS` 的 `table_constraints` 中添加 `"UNIQUE(start_time)"`
   - 迁移脚本中执行：`CREATE UNIQUE INDEX IF NOT EXISTS idx_timeline_custom_block_start_time_unique ON timeline_custom_block(start_time)`
   - 添加前需检查现有数据是否有 `start_time` 重复，如有则保留最新一条
   - 详见 Issue #05 Category C 说明

---

## Acceptance criteria

- [ ] 9 个表的 `TABLE_CONFIGS` 配置已更新为 `"update_at": True`
- [ ] 数据库迁移脚本已创建，现有数据的 `updated_at` 字段已填充当前时间
- [ ] 9 个表的 `updated_at` 索引已创建
- [ ] 增量查询性能验证通过（9 个表总耗时 < 100ms）
- [ ] 单元测试通过（测试 `updated_at` 字段在 INSERT/UPDATE 时自动更新）
- [ ] `timeline_custom_block` 的 `UNIQUE(start_time)` 约束已添加（TABLE_CONFIGS + 迁移脚本）
- [ ] 添加 UNIQUE 约束前已清理重复 `start_time` 数据

---

## Blocked by

None - can start immediately
