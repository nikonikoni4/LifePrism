---
created: 2026-07-11
tags: [flow, custom-records, entry-crud, dynamic-sql, ai-tool]
---

# 自定义记录条目 CRUD Flow

## Flow 对象

`CustomRecordEntry`（自定义记录条目）

记录是用户存储在动态数据表 `custom_<slug>` 中的实际数据行。每条记录拥有：
- 一个 `cre-{uuid[:8]}` 格式的 ID
- 动态字段值（由类型的 field_key 决定列名，全为 TEXT 类型）
- `created_at` 和 `updated_at` 时间戳

记录的生命周期包含：录入（REST/AI 双通道）→ 分页查询 → 删除。P1 不支持记录更新。

相关 Spec：[custom-records-module-spec](../specs/custom-records-module.md)
相关 Flow：[类型生命周期 Flow](2026-07-11-custom-type-lifecycle-flow.md)（类型是记录的前置依赖）

## 关键约束

1. **field_key 白名单校验**：录入时 data 中的 key 必须匹配类型的 field_key 集合，未知 key 返回 422 + valid_fields 列表
2. **缺失字段存 NULL**：data 中未出现的字段在 INSERT 时不出现，数据库列存 NULL
3. **空字典允许**：data={} 时插入全 NULL 行（仅 id + created_at + updated_at）
4. **类型必须存在**：所有记录操作前通过 `_get_type_and_table()` 验证 type_id，不存在抛 EntityNotFoundError → 404
5. **动态 SQL 拼接**：表名、列名来自 meta 表（已通过正则白名单校验），值使用参数化查询（? 占位符），无 SQL 注入风险
6. **按 created_at DESC 排序**：查询始终按创建时间倒序
7. **分页双查询**：查询记录时先 COUNT 获取总数，再 SELECT 获取当前页数据
8. **AI Tool 绕过 Service**：CreateCustomRecordEntryTool 和 QueryCustomRecordEntriesTool 直接调用 Repository
9. **AI 智能重试**：field_key 错误时 Tool 返回包含 valid_fields 的结构化 JSON 错误，引导 AI 重新解析用户输入后重试
10. **删除不可恢复**：硬删除（DELETE），无软删除

## 反常设计

- **AI Tool 直连 Repository（双通道架构）**：REST API 走 API → Service → Repository 三层；AI Tool 走 Tool → Repository 两层。原因：Tool 返回 SUCCESS/ERROR 前缀字符串而非 HTTP 响应，不需要 Pydantic 转换；且 Tool 在 llm 模块中注册，依赖 Service 会形成 `server → llm → server` 循环引用。
- **INSERT 动态列拼接**：只插入 data 中出现的字段列，而非所有字段。缺失字段由数据库默认值（NULL）填充。这避免了将未填写字段强制设为空字符串。
- **COUNT + SELECT 双查询**：分页查询需要执行两次 SQL（COUNT 获取总数用于分页元数据，SELECT LIMIT/OFFSET 获取当前页数据），两次查询在同一连接中顺序执行。
- **query_entries 返回 tuple**：返回 `(rows, total_count)` 而非包含 items/total 的对象，Service 层负责包装为 CustomRecordEntryListResponse。
- **AI 查询不分页**：QueryCustomRecordEntriesTool 默认 page=1，page_size=limit（默认 50），一次拿够数据，不支持翻页。AI 场景下记录量通常不大。
- **delete_entry 异常抛出位置**：EntityNotFoundError 在 with 块外抛出（连接归还池后），避免连接以未提交/未回滚状态归还连接池。

## 链路 1：录入记录（REST API 路径）

### 触发场景

用户通过前端表单或其他 REST 客户端提交记录数据。当前 P1 前端卡片视图主要依赖 AI 录入，但 POST 端点已完整实现供未来表单录入使用。

### 5类节点分析

- **跨模块节点**：前端 → API → Service → Repository → DB
- **持久化节点**：1 次动态 INSERT
- **分支节点**：类型不存在 → 404；field_key 错误 → 422 + valid_fields
- **集合点**：动态列名和值组装成 INSERT 语句后执行
- **状态变化**：无 → 新记录行

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    录入记录（REST 路径）                          │
└─────────────────────────────────────────────────────────────────┘

POST /{type_id}/entries
Body: { data: { field_key: value, ... } }
        │
        ▼
┌─ API: POST /{type_id}/entries ─────────────────────────────────┐
│  Pydantic 校验 CreateCustomRecordEntryRequest                   │
│  - data 默认 {}（允许空字典）                                    │
│  路径参数 type_id                                               │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: create_entry() ──────────────────────────────────────┐
│  调用 repository.create_entry(type_id, request.data)            │
│  返回 _convert_to_entry_item() 转为 CustomRecordEntryItem       │
│  Repository 返回 None（类型不存在）→ EntityNotFoundError → 404  │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: create_entry() ───────────────────────────────────┐
│                                                                 │
│  1. _get_type_and_table(type_id):                              │
│     SELECT id, name, slug FROM custom_record_types WHERE id=?  │
│     └─ 不存在 → EntityNotFoundError                             │
│     data_table = "custom_" + slug                               │
│                                                                 │
│  2. _get_fields_by_type_id(type_id) 获取字段定义                │
│     valid_keys = { f.field_key for f in fields }               │
│                                                                 │
│  3. 校验 data 的 key:                                            │
│     invalid_keys = data.keys() - valid_keys                     │
│     └─ 有无效 key → ValidationError(INVALID_FIELD_KEY)          │
│         details 含 valid_fields 列表                            │
│                                                                 │
│  4. 生成 entry_id = "cre-" + uuid[:8]                           │
│     now = 当前时间                                               │
│                                                                 │
│  5. 构造动态 INSERT:                                            │
│     columns = ["id", "created_at", "updated_at"]                │
│     placeholders = ["?", "?", "?"]                              │
│     values = [entry_id, now, now]                               │
│     for key in data:                                            │
│       columns.append(key)  ← 只插入 data 中出现的字段           │
│       placeholders.append("?")                                  │
│       values.append(data[key])                                  │
│                                                                 │
│     SQL: INSERT INTO custom_<slug> (cols...) VALUES (?...?)    │
│                                                                 │
│  6. 执行 INSERT（参数化查询，值用 ? 占位符）                     │
│                                                                 │
│  异常: sqlite3.Error → DataAccessError                          │
│                                                                 │
│  返回: entry_id                                                 │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  201 Created + CustomRecordEntryItem                            │
│  422 + { valid_fields: [...] }（field_key 错误）                 │
│  404 EntityNotFoundError（类型不存在）                           │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:create_custom_record_entry:122
- lifeprism/server/services/custom_records_service.py:create_entry:139
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.create_entry:343
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository._get_type_and_table:332
</key_function>

## 链路 2：录入记录（AI Tool 路径）

### 触发场景

用户通过 ChatPanel 用自然语言描述要记录的内容，AI 解析后调用 `create_custom_record_entry` tool。若 field_key 错误，AI 收到 valid_fields 反馈后自动纠正重试。

### 5类节点分析

- **跨模块节点**：ChatPanel → LLM Agent → Tool → Repository → DB
- **持久化节点**：1 次动态 INSERT（与 REST 路径相同的 Repository 方法）
- **分支节点**：参数缺失/类型错误 → ERROR 字符串；field_key 错误 → ERROR + valid_fields JSON；成功 → SUCCESS JSON
- **集合点**：Tool 返回字符串结果，Agent Loop 根据 SUCCESS/ERROR 前缀决定下一步（继续对话或重试）
- **状态变化**：无 → 新记录行

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                 录入记录（AI Tool 路径）                          │
└─────────────────────────────────────────────────────────────────┘

用户自然语言输入（ChatPanel）
        │
        ▼
┌─ LLM Agent 解析 ───────────────────────────────────────────────┐
│  1. AI 根据对话上下文理解用户意图                                │
│  2. 若未确认类型字段定义，先调用 list_custom_record_types       │
│  3. 从用户输入中提取字段值，构造 data {}                        │
│  4. 调用 create_custom_record_entry tool                       │
│     参数: { type_id, data: { field_key: value } }              │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Tool: CreateCustomRecordEntryTool.execute() ──────────────────┐
│                                                                 │
│  1. 参数校验:                                                   │
│     - type_id 为空 → "ERROR参数缺失：type_id 必填"              │
│     - data 非字典 → "ERROR参数错误：data 必须是字典"             │
│                                                                 │
│  2. 直接调用 custom_record_repository.create_entry()            │
│     （绕过 Service 层）                                         │
│                                                                 │
│  3. 结果处理:                                                   │
│     ├─ 成功 → "SUCCESS" + json.dumps({entry_id, type_id})      │
│     ├─ ValidationError → "ERROR" + json.dumps({                │
│     │     error: e.code,                                        │
│     │     message: e.message,                                   │
│     │     valid_fields: e.details.valid_fields                  │
│     │   })  ← 结构化错误供 AI 重试                              │
│     └─ 其他异常 → "ERROR录入自定义记录失败: {e}"                │
│                                                                 │
│  返回: 字符串（SUCCESS/ERROR 前缀）                              │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: create_entry() ───────────────────────────────────┐
│  （同链路 1 的 Repository 逻辑）                                 │
│  - _get_type_and_table → 校验类型存在                           │
│  - _get_fields_by_type_id → 获取有效字段                        │
│  - 校验 invalid_keys → ValidationError(含 valid_fields)        │
│  - 动态 INSERT → 返回 entry_id                                  │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Agent Loop 处理结果 ──────────────────────────────────────────┐
│  ├─ SUCCESS → AI 向用户确认录入成功                             │
│  └─ ERROR + valid_fields → AI 根据 valid_fields 重新解析       │
│     用户输入，纠正 field_key 后自动重试                          │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/llm/agent/tools/custom_records_tool.py:CreateCustomRecordEntryTool.execute:174
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.create_entry:343
</key_function>

## 链路 3：分页查询记录

### 触发场景

前端 TypeDetailView 加载（卡片/表格/模板对比三个 Tab 都需要数据），用户切换日期筛选或翻页。

### 5类节点分析

- **跨模块节点**：前端（Promise.all 并行加载类型+记录）→ API → Service → Repository → DB
- **持久化节点**：2 次 SELECT（COUNT + SELECT LIMIT/OFFSET）
- **分支节点**：日期范围可选（start/end 任一或两者）；类型不存在 → 404
- **集合点**：COUNT 结果和 SELECT 结果在 Repository 中合并为 tuple(rows, total)，Service 包装为响应对象
- **状态变化**：无（只读）

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                     分页查询记录                                  │
└─────────────────────────────────────────────────────────────────┘

GET /{type_id}/entries?start_date=&end_date=&page=1&page_size=20
        │
        ▼
┌─ 前端: TypeDetailView.loadData() ──────────────────────────────┐
│  Promise.all([                                                  │
│    API.getTypeById(typeId),    // 并行加载类型详情               │
│    API.getEntries({ typeId, startDate, endDate, page, pageSize })│
│  ])                                                             │
│  记录到达后:                                                     │
│  1. 按日期分组（今天/昨天/前天/M月D日）                          │
│  2. 传递给 EntryCard 渲染                                       │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ API: GET /{type_id}/entries ──────────────────────────────────┐
│  查询参数:                                                      │
│  - start_date: 可选，格式 YYYY-MM-DD                           │
│  - end_date: 可选，格式 YYYY-MM-DD                             │
│  - page: 默认 1                                                 │
│  - page_size: 默认 20（前端）                                   │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: get_entries() ───────────────────────────────────────┐
│  调用 repository.query_entries(type_id, date_range, page, page_size)│
│  结果 (rows, total_count):                                      │
│  - rows → _convert_to_entry_item_list()                         │
│  - 包装为 CustomRecordEntryListResponse { items, total }        │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: query_entries() ──────────────────────────────────┐
│                                                                 │
│  1. _get_type_and_table(type_id)                                │
│     └─ 不存在 → EntityNotFoundError                             │
│                                                                 │
│  2. 动态构建 WHERE 子句:                                        │
│     where_clauses = []                                          │
│     params = []                                                 │
│     if start_date: where_clauses.append("created_at >= ?")     │
│     if end_date:   where_clauses.append("created_at <= ?")     │
│     where_sql = "WHERE ..." 或 ""                               │
│                                                                 │
│  3. offset = (page - 1) * page_size                             │
│                                                                 │
│  4. COUNT 查询（总记录数）:                                     │
│     SELECT COUNT(*) FROM custom_<slug> {where_sql}             │
│     → total_count                                               │
│                                                                 │
│  5. 数据查询（当前页）:                                         │
│     SELECT * FROM custom_<slug> {where_sql}                    │
│     ORDER BY created_at DESC LIMIT ? OFFSET ?                  │
│     → rows (list[dict])                                         │
│                                                                 │
│  两次查询在同一连接中顺序执行                                    │
│                                                                 │
│  返回: (rows, total_count)                                      │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  200 OK + { items: CustomRecordEntryItem[], total: int }       │
│  total 用于前端分页组件计算总页数                                │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:get_custom_record_entries:99
- lifeprism/server/services/custom_records_service.py:get_entries:113
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.query_entries:413
</key_function>

## 链路 4：AI 查询记录

### 触发场景

用户通过 ChatPanel 询问"最近记录了什么"、"这周看了哪些电影"等查询问题，AI 调用 `query_custom_record_entries` tool。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                   AI 查询记录                                    │
└─────────────────────────────────────────────────────────────────┘

用户自然语言查询
        │
        ▼
┌─ Tool: QueryCustomRecordEntriesTool.execute() ─────────────────┐
│                                                                 │
│  1. 参数处理:                                                   │
│     - type_id 必填，为空 → ERROR                                │
│     - date_range: [start, end] → (start, end)                  │
│       空串/null 表示该侧不限制                                   │
│       两侧都无 → date_range = None（不筛选）                    │
│     - limit: 默认 50，范围 [1, 500]                             │
│                                                                 │
│  2. 直接调用 repository.query_entries(                          │
│       type_id, date_range, page=1, page_size=limit              │
│     )  ← 固定 page=1，用 limit 控制条数                         │
│                                                                 │
│  3. 结果处理:                                                   │
│     ├─ 成功 → "SUCCESS" + json.dumps((rows, total))            │
│     │  注意：返回的是 tuple [rows_array, total_int]             │
│     └─ 异常 → "ERROR查询自定义记录失败: {e}"                    │
│                                                                 │
│  返回: 字符串                                                   │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Agent Loop 处理结果 ──────────────────────────────────────────┐
│  SUCCESS → AI 解析记录列表，用自然语言向用户总结/回答            │
│  注意：AI 场景默认拿 50 条不分页，足够回答大多数查询             │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/llm/agent/tools/custom_records_tool.py:QueryCustomRecordEntriesTool.execute:243
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.query_entries:413
</key_function>

## 链路 5：删除记录

### 触发场景

用户在卡片视图或表格视图点击某条记录的删除按钮（Trash2 图标，hover 显示）。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        删除记录                                  │
└─────────────────────────────────────────────────────────────────┘

DELETE /{type_id}/entries/{entry_id}
        │
        ▼
┌─ API: DELETE /{type_id}/entries/{entry_id} ────────────────────┐
│  路径参数 type_id + entry_id                                    │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: delete_entry() ──────────────────────────────────────┐
│  调用 repository.delete_entry(type_id, entry_id)                │
│  返回 {"success": true}                                         │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: delete_entry() ───────────────────────────────────┐
│                                                                 │
│  1. _get_type_and_table(type_id)                                │
│     └─ 类型不存在 → EntityNotFoundError                         │
│                                                                 │
│  2. 执行 DELETE:                                                │
│     DELETE FROM custom_<slug> WHERE id = ?                     │
│     deleted = cursor.rowcount > 0                               │
│                                                                 │
│  3. with 块结束（连接归还池）后检查:                             │
│     └─ not deleted → EntityNotFoundError（记录不存在）          │
│        （在 with 外抛异常，避免连接状态异常）                     │
│                                                                 │
│  返回: True                                                     │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  成功: 200 OK + { "success": true }                             │
│  类型不存在: 404                                                │
│  记录不存在: 404                                                │
│  前端: 从本地状态中移除该记录，刷新列表                          │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:delete_custom_record_entry:140
- lifeprism/server/services/custom_records_service.py:delete_entry:152
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.delete_entry:510
</key_function>

## 耦合关系

| 耦合对象 | 耦合方式 |
|---------|---------|
| `CustomRecordType` | 所有记录操作前需通过 `_get_type_and_table()` 验证类型存在并获取表名；录入时通过 `_get_fields_by_type_id()` 获取有效字段列表用于 field_key 校验 |
| `DatabaseManager` | 通过 `get_connection()` 获取连接，执行动态 SQL（表名/列名来自白名单校验过的 meta 数据，值用参数化查询） |
| `LLM Agent Loop` | Create/Query Tool 返回 SUCCESS/ERROR 字符串；ValidationError 携带 valid_fields 触发 Agent 自动重试循环 |
| `ChatPanel（前端）` | 用户自然语言输入入口，集成在 CustomRecordsApp 右下角，通过 LLM Tools 完成录入和查询 |
| `CardLayout Engine` | 查询返回的 records 数据作为 `analyzeCardLayout()` 的输入，决定每条记录的渲染方式 |
| `前端 TypeDetailView` | Promise.all 并行加载类型和记录；日期筛选 + 分页；按日期分组；传递给 EntryCard/表格/模板对比三个 Tab |
| `前端 EntryCard` | 消费单条 entry + fields 数据，调用 cardLayoutEngine 分析布局后渲染 |
