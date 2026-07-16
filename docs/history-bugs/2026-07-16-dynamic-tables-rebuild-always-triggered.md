# 动态表同步每次触发无意义重建 — 快照对比方向错误 + 兜底条件永真

## 元信息

- **发生时间**: 2026-07-16（通过日志发现，具体引入时间未考据）
- **发现时间**: 2026-07-16
- **修复状态**: ⏳ 待修复（已决策方案，见 ADR `2026-07-16-dynamic-tables-sync-definition-comparison.md`）
- **影响范围**: 动态表同步流程 — 每次 sync_once 都触发无意义的云端重建请求
- **bug 类型**: 逻辑设计缺陷 — 触发条件方向错误 + 兜底条件永真
- **严重程度**: 一般（P2）— 功能无实际损坏（端点幂等走 skipped 分支），但产生无意义的 HTTP 往返和日志噪音，掩盖了真正的检测逻辑问题

## 触发规则

在以下场景时阅读此文档：
- 排查"每次同步都出现 重建动态表请求开始 / 重建动态表完成 / skipped"日志
- 修改 `sync_client.py` 中 `sync_once` 的动态表重建触发逻辑
- 修改 `get_custom_record_types_snapshot` / `_rebuild_remote_dynamic_tables` 调用链
- 排查动态表同步触发条件相关的问题
- 讨论"快照对比方向错误"或"兜底条件永真"类设计缺陷

## Bug 简述

`sync_once` 中判断是否触发云端动态表重建的条件由两部分 OR 组成：
- 条件 A：比较 pull 前后本地 `custom_record_types` 的快照变化
- 条件 B（兜底）：`or dynamic_tables`（本地存在任何 `custom_*` 数据表则触发）

条件 A 检测的是"云端→本地"方向的变化（pull 把云端定义拉下来导致本地变化），但 rebuild 的方向是"本地→云端"（把本地定义发给云端建表），**方向反了**——本地主动新增动态表时条件 A 永远不成立。

条件 B 本意是兜底"首次同步"场景，但写成了"本地有动态表就触发"的永真条件。只要本地存在任何 `custom_xxx` 数据表，每次 sync_once 都触发重建请求。

## 复现场景

1. 本地有 3 个动态表（reading_log / diet_log / dream_log）
2. 触发 `sync_once`（无论是否有实际数据变更）
3. 观察日志：

```
2026-07-16 09:14:35,110 INFO sync_cloud_api.py func:sync_rebuild_dynamic_tables line 313 : 重建动态表请求开始: types=3
2026-07-16 09:14:35,111 INFO sync_repository.py func:rebuild_dynamic_tables line 1003 : 重建动态表完成: [{'slug': 'reading_log', 'action': 'skipped'}, {'slug': 'diet_log', 'action': 'skipped'}, {'slug': 'dream_log', 'action': 'skipped'}]
2026-07-16 09:14:35,111 INFO sync_cloud_api.py func:sync_rebuild_dynamic_tables line 328 : 重建动态表完成: results=[...], 耗时=0.59ms
```

4. 每次同步都重复出现上述日志，云端全部走 `skipped` 分支（表已存在且字段一致，无实际建表操作）

## 根因分析

### 问题代码位置

`lifeprism/sync/sync_client.py` 第 291-313 行：

```python
# pull 前记录 custom_record_types 的 id 快照
snapshot_before = self.sync_repository.get_custom_record_types_snapshot()

# 数据库同步：Pull -> Push
self.pull_from_remote(remote_url, api_key, last_sync_time, tables)

# pull 后判断是否需要触发云端动态表重建
snapshot_after = self.sync_repository.get_custom_record_types_snapshot()
dynamic_tables = [
    t
    for t in tables
    if t.startswith("custom_") and t not in ("custom_record_types", "custom_record_fields")
]
if snapshot_before != snapshot_after or dynamic_tables:    # 条件A            # 条件B
    self._rebuild_remote_dynamic_tables(remote_url, api_key)
```

### 条件 A 的方向错误

- `snapshot_before`：pull 前本地 `custom_record_types` 的 `(id, updated_at)` 集合
- `snapshot_after`：pull 后本地 `custom_record_types` 的 `(id, updated_at)` 集合
- 两者比较只能检测"**pull 是否改变了本地 meta 表**"——也就是"云端→本地"方向的变化
- 但 `_rebuild_remote_dynamic_tables` 是把**本地定义发给云端**建表，方向是"本地→云端"
- 本地主动新增动态表时，pull 不会改变本地 meta，`snapshot_before == snapshot_after`，条件 A 不成立

### 条件 B 的永真问题

- `dynamic_tables` 列表非空即 `True`
- 本地有 `custom_reading_log`、`custom_diet_log`、`custom_dream_log` 三张表 → 列表非空 → `True`
- 这个条件永远成立，导致每次 sync_once 都触发重建
- 代码注释写的是"兜底首次同步"，但实际语义是"本地有动态表就触发"，两者不等价

### 两个问题的掩盖关系

条件 A 的方向错误导致"本地新增动态表"这个场景无法被正确检测，只能靠条件 B 的永真兜底。条件 B 虽然永真，但因为 `rebuild_dynamic_tables` 端点幂等（走 skipped 分支无副作用），表面上功能正常，掩盖了条件 A 的根本设计缺陷。

## 修复方案

采用"新增端点拉取云端定义，本地 slug 对比"方案，详见 ADR `docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md`。

核心改动：
1. 新增 `GET /api/sync/dynamic-tables-definitions` 端点，返回云端 `custom_record_types` + `custom_record_fields` 两张 meta 表的完整内容
2. 在 pull 之前调用该端点，本地用 slug 集合对比，触发双向建表（本地建表 + 云端建表）
3. 删除 `get_all_sync_tables`，动态表列表由建表步骤产出（云端 slug ∪ 本地 slug）
4. 本地建表只执行 DDL（复用 `generate_create_table_ddl`），不写 meta 数据，让 pull 统一同步

## 设计教训

- **检测方向必须与操作方向一致**：检测"是否需要让云端重建"时，检测的方向应该是"本地定义相比云端是否有变化"（本地→云端方向），而不是"pull 是否改变了本地"（云端→本地方向）
- **兜底条件必须有时效性**：兜底"首次同步"的条件应该能在首次之后失效，不能写成永久成立的条件。如果无法区分"首次"和"无变化"，应该引入持久化状态（如 last_synced_snapshot）来区分
- **永真条件会掩盖其他 bug**：条件 B 的永真性掩盖了条件 A 的方向错误。如果条件 B 不存在，条件 A 的问题会立即暴露（本地新增动态表时无法触发重建）。设计兜底条件时应该考虑"如果其他条件都失效，这个兜底会掩盖什么问题"
- **幂等不等于无成本**：虽然 `rebuild_dynamic_tables` 端点幂等无副作用，但每次触发都产生 HTTP 往返、数据库查询、日志噪音。幂等性不能作为"触发条件可以宽松"的理由
