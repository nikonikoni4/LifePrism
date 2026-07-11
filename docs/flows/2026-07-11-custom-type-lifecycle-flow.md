---
created: 2026-07-11
tags: [flow, custom-records, type-lifecycle, meta-table, ddl]
---

# 自定义记录类型生命周期 Flow

## Flow 对象

`CustomRecordType`（自定义记录类型）+ `CustomRecordField`（字段定义）

类型是自定义记录模块的元数据核心。每个类型拥有：
- 一条 `custom_record_types` 表中的 meta 记录
- 多条 `custom_record_fields` 表中的字段定义记录
- 一张动态创建的数据表 `custom_<slug>`

类型生命周期包含：创建 → 查询 → 配置更新 → 字段角色更新 → 删除。

相关 Spec：[custom-records-module-spec](../specs/custom-records-module.md)

## 关键约束

1. **slug 全局唯一**：创建时 check-then-insert + UNIQUE 约束兜底，冲突返回 409
2. **slug/field_key 格式**：必须匹配 `^[a-z][a-z0-9_]*$`（小写字母开头，含小写字母/数字/下划线）
3. **同类型 field_key 唯一**：同一类型内字段标识不可重复
4. **fields 至少 1 个**：创建类型时必须有至少 1 个字段
5. **字段定义后不可变**：`field_key`/`field_type`/`field_name` 创建后不可修改，仅 `display_role` 可变（属展示配置）
6. **事务一致性**：创建类型的三步（INSERT types → INSERT fields → CREATE TABLE）和删除类型的三步（DROP TABLE → DELETE fields → DELETE types）必须在同一事务中完成
7. **动态表名拼接**：数据表名由 `custom_` + slug 拼接，slug 已通过正则白名单校验，不存在 SQL 注入风险
8. **删除不可恢复**：硬删除（DROP TABLE + DELETE meta），无软删除/回收站机制

## 反常设计

- **LLM Tool 绕过 Service 层**：`CreateCustomRecordTypeTool` 直接调用 Repository，不走 Service 层。原因是 Service 层依赖 Pydantic schema 做响应转换，Tool 层需要返回 SUCCESS/ERROR 前缀字符串；且 Tool 注册在 Agent 模块，直接依赖 Service 会形成循环引用。
- **Repository 不继承 LWBaseDataProvider**：动态表名运行时才确定，无法在类定义时写死 `_TABLE_NAME`，且涉及 DDL（CREATE/DROP TABLE），超出静态 CRUD 模板能力。
- **删除顺序与创建顺序相反**：创建时先写 meta 再建表；删除时先 DROP 表再删 meta。防止删 meta 后表成为孤儿表。
- **update_type_config 动态拼接 SET 子句**：三个配置字段（card_template/icon/accent_color）均为可选，仅传入非 None 的字段才会被更新，始终追加 updated_at。

## 链路 1：创建类型

### 触发场景

用户通过前端表单（CreateTypeView）提交新类型，或通过 ChatPanel AI 对话调用 `create_custom_record_type` tool。

### 5类节点分析

- **跨模块节点**：前端表单/AI Tool → API/Service → Repository → DatabaseManager（事务）
- **持久化节点**：3 次写入（INSERT types、INSERT fields、CREATE TABLE DDL）
- **分支节点**：4 层校验（slug 格式 → fields 非空 → field_key 格式 → field_key 唯一 → slug 唯一），任一层失败提前返回错误
- **集合点**：事务提交前三步必须全部成功，任一失败整体回滚
- **状态变化**：无 → 新类型（meta 记录 + 字段定义 + 空数据表）

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        创建类型                                  │
└─────────────────────────────────────────────────────────────────┘

用户/AI 提交 { name, slug, fields[], description? }
        │
        ▼
┌─ API: POST /types ─────────────────────────────────────────────┐
│  Pydantic 校验 CreateCustomRecordTypeRequest                    │
│  - name min_length=1                                            │
│  - slug min_length=1                                            │
│  - fields min_length=1                                          │
│  ─→ 校验失败 → 422 ValidationError                              │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: create_type() ───────────────────────────────────────┐
│  调用 repository.create_type()                                  │
│  返回 _convert_to_type_item() 转为 CustomRecordTypeItem         │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: create_type() ────────────────────────────────────┐
│                                                                 │
│  1. slug 格式校验 (regex ^[a-z][a-z0-9_]*$)                    │
│     └─ 失败 → ValidationError(INVALID_SLUG_FORMAT)             │
│                                                                 │
│  2. fields 非空校验                                             │
│     └─ 失败 → ValidationError(EMPTY_FIELDS)                    │
│                                                                 │
│  3. 每个 field_key 格式校验                                     │
│     └─ 失败 → ValidationError(INVALID_FIELD_KEY_FORMAT)        │
│                                                                 │
│  4. field_key 同类型唯一性校验                                  │
│     └─ 失败 → ValidationError(DUPLICATE_FIELD_KEY)             │
│                                                                 │
│  5. slug 唯一性查询 (SELECT FROM custom_record_types)           │
│     └─ 已存在 → DuplicateEntityError → 409                     │
│                                                                 │
│  6. 生成 type_id = "crt-" + uuid[:8]                            │
│     data_table = "custom_" + slug                               │
│                                                                 │
│  7. ┌─ 事务开始 ──────────────────────────────────────────────┐ │
│     │                                                         │ │
│     │  7a. INSERT INTO custom_record_types                    │ │
│     │      (id, name, slug, description, created_at,          │ │
│     │       updated_at, card_template='clean',                │ │
│     │       icon='fileText', accent_color='blue')             │ │
│     │                                                         │ │
│     │  7b. 循环 INSERT INTO custom_record_fields              │ │
│     │      每个字段生成 field_id = "crf-" + uuid[:8]           │ │
│     │      (id, type_id, field_name, field_key, field_type,   │ │
│     │       sort_order, created_at)                           │ │
│     │                                                         │ │
│     │  7c. DDL: CREATE TABLE custom_<slug> (                  │ │
│     │        id TEXT PRIMARY KEY,                             │ │
│     │        <field_key_1> TEXT,                              │ │
│     │        <field_key_2> TEXT, ...,                         │ │
│     │        created_at TEXT, updated_at TEXT                 │ │
│     │      )                                                  │ │
│     │                                                         │ │
│     └─ 事务提交 ──────────────────────────────────────────────┘ │
│                                                                 │
│  异常处理:                                                       │
│  - sqlite3.IntegrityError → DuplicateEntityError (UNIQUE 兜底)  │
│  - sqlite3.Error → DataAccessError                              │
│                                                                 │
│  返回: type_id                                                  │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  REST 路径: 201 Created + CustomRecordTypeItem                  │
│  AI Tool 路径: "SUCCESS {type_id, name, slug}"                  │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:create_custom_record_type:38
- lifeprism/server/services/custom_records_service.py:create_type:83
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.create_type:53
- lifeprism/llm/agent/tools/custom_records_tool.py:CreateCustomRecordTypeTool.execute:115
</key_function>

## 链路 2：查询类型列表

### 触发场景

前端 TypeListView 加载，或 AI 调用 `list_custom_record_types` tool 获取所有类型及字段定义。

### 5类节点分析

- **跨模块节点**：前端/AI Tool → API/Service → Repository → DB
- **持久化节点**：1 次 SELECT types + N 次 SELECT fields（N = 类型数量）
- **分支节点**：无（查询不改变数据，无校验分支）
- **集合点**：每个类型的 fields 列表附加到类型对象上，组装完整响应
- **状态变化**：无（只读）

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                        查询类型列表                              │
└─────────────────────────────────────────────────────────────────┘

GET /types (REST) / list_custom_record_types tool (AI)
        │
        ▼
┌─ API: GET /types ──────────────────────────────────────────────┐
│  无请求参数，直接调用 Service                                    │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: get_types() ─────────────────────────────────────────┐
│  调用 repository.list_types()                                   │
│  转换为 CustomRecordTypeListResponse { items: [...] }           │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: list_types() ─────────────────────────────────────┐
│                                                                 │
│  1. SELECT id, name, slug, description, card_template, icon,   │
│        accent_color, created_at, updated_at                    │
│     FROM custom_record_types ORDER BY created_at ASC           │
│                                                                 │
│  2. 对每个类型，查询其字段:                                      │
│     SELECT id, field_name, field_key, field_type, sort_order,  │
│            display_role                                        │
│     FROM custom_record_fields WHERE type_id = ?                │
│     ORDER BY sort_order ASC                                    │
│     → 附加到 t["fields"]                                        │
│                                                                 │
│  返回: 类型列表（含 fields）                                     │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  200 OK + { items: [CustomRecordTypeItem, ...] }               │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:get_custom_record_types:30
- lifeprism/server/services/custom_records_service.py:get_types:64
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.list_types:227
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository._get_fields_by_type_id:217
- lifeprism/llm/agent/tools/custom_records_tool.py:ListCustomRecordTypesTool.execute:41
</key_function>

## 链路 3：查询单个类型详情

### 触发场景

前端 TypeDetailView 加载时（Promise.all 并行加载类型详情和记录数据）。

### 流程图

```
GET /types/{type_id}
        │
        ▼
┌─ API: GET /types/{type_id} ────────────────────────────────────┐
│  路径参数 type_id                                               │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: get_type(type_id) ───────────────────────────────────┐
│  调用 repository.get_type_by_id(type_id)                        │
│  返回 None → 抛 EntityNotFoundError → 404                      │
│  转换为 CustomRecordTypeItem                                    │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: get_type_by_id(type_id) ──────────────────────────┐
│                                                                 │
│  1. SELECT ... FROM custom_record_types WHERE id = ?           │
│     └─ 不存在 → return None                                     │
│                                                                 │
│  2. SELECT fields FROM custom_record_fields WHERE type_id = ?  │
│     → 附加到 t["fields"]                                        │
│                                                                 │
│  返回: 类型详情（含 fields）或 None                              │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  存在: 200 OK + CustomRecordTypeItem                            │
│  不存在: 404 EntityNotFoundError                                │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:get_custom_record_type:50
- lifeprism/server/services/custom_records_service.py:get_type:71
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.get_type_by_id:250
</key_function>

## 链路 4：更新类型展示配置

### 触发场景

用户在 TypeDetailView 中切换卡片模板、图标或强调色。模板切换带 600ms debounce 自动保存。

### 5类节点分析

- **跨模块节点**：前端 debounce → API → Service → Repository → DB
- **持久化节点**：1 次 UPDATE（动态 SET 子句）
- **分支节点**：三个配置字段均可选，非 None 的才加入 SET 子句；无字段更新时直接返回 True
- **集合点**：无
- **状态变化**：类型展示配置更新，updated_at 刷新

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                    更新类型展示配置                               │
└─────────────────────────────────────────────────────────────────┘

PATCH /types/{type_id}
Body: { card_template?, icon?, accent_color? }
        │
        ▼
┌─ API: PATCH /types/{type_id} ──────────────────────────────────┐
│  Pydantic 校验 UpdateTypeConfigRequest（三字段均可选）           │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: update_type_config() ────────────────────────────────┐
│  调用 repository.update_type_config()                           │
│  重新查询类型（get_type_by_id）返回更新后的数据                  │
│  转换为 CustomRecordTypeItem                                    │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: update_type_config() ─────────────────────────────┐
│                                                                 │
│  1. 动态构建 SET 子句:                                          │
│     - card_template != None → "card_template = ?"              │
│     - icon != None → "icon = ?"                                │
│     - accent_color != None → "accent_color = ?"                │
│     - 始终追加 "updated_at = ?"                                 │
│                                                                 │
│  2. 无字段需更新 → return True（不执行 SQL）                     │
│                                                                 │
│  3. UPDATE custom_record_types SET <clauses> WHERE id = ?      │
│     └─ rowcount == 0 → EntityNotFoundError → 404               │
│                                                                 │
│  返回: True                                                     │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  200 OK + 更新后的 CustomRecordTypeItem                         │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:update_custom_record_type_config:67
- lifeprism/server/services/custom_records_service.py:update_type_config:164
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.update_type_config:560
</key_function>

## 链路 5：更新字段展示角色

### 触发场景

用户在 TypeDetailView 点击"配置角色"弹出 FieldRoleModal，为某个字段选择 display_role。前端乐观更新 + 后端持久化，失败回滚。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                     更新字段展示角色                              │
└─────────────────────────────────────────────────────────────────┘

PATCH /types/{type_id}/fields/{field_id}
Body: { display_role: "auto"|"title"|"main"|"chip"|"hidden" }
        │
        ▼
┌─ 前端: TypeDetailView.handleFieldRoleChange() ─────────────────┐
│  1. 本地乐观更新 setLocalFields（立即更新 UI）                   │
│  2. 调用 API.updateFieldRole()                                  │
│  3. 失败 → 回滚本地状态 + 显示错误提示                           │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ API: PATCH /types/{type_id}/fields/{field_id} ────────────────┐
│  Pydantic 校验 UpdateFieldRoleRequest（display_role 必填）      │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: update_field_role() ─────────────────────────────────┐
│  调用 repository.update_field_role()                            │
│  返回 {"success": true}                                         │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: update_field_role() ──────────────────────────────┐
│                                                                 │
│  UPDATE custom_record_fields                                    │
│  SET display_role = ?                                           │
│  WHERE id = ? AND type_id = ?                                   │
│  （双条件 WHERE 防止跨类型误更新）                                │
│                                                                 │
│  └─ rowcount == 0 → EntityNotFoundError → 404                  │
│                                                                 │
│  返回: True                                                     │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  200 OK + { "success": true }                                   │
│  前端持久化成功 → 保留乐观更新状态                                │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:update_custom_record_field_role:80
- lifeprism/server/services/custom_records_service.py:update_field_role:181
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.update_field_role:627
- frontend/apps/custom-records/components/TypeDetailView.tsx:handleFieldRoleChange
</key_function>

## 链路 6：删除类型

### 触发场景

用户在 TypeListView 点击类型卡片右上角删除按钮，确认"不可撤销"警告后提交。

### 5类节点分析

- **跨模块节点**：前端确认弹窗 → API → Service → Repository → DB
- **持久化节点**：3 次操作（DROP TABLE DDL + DELETE fields + DELETE types），顺序与创建相反
- **分支节点**：类型不存在 → EntityNotFoundError → 404
- **集合点**：事务内三步必须全部成功
- **状态变化**：类型 + 字段 meta 记录 + 数据表 + 所有记录数据 → 全部永久删除

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                         删除类型                                 │
└─────────────────────────────────────────────────────────────────┘

DELETE /types/{type_id}
（前端需先弹出确认弹窗，警告"不可撤销"）
        │
        ▼
┌─ API: DELETE /types/{type_id} ─────────────────────────────────┐
│  路径参数 type_id                                               │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Service: delete_type() ───────────────────────────────────────┐
│  调用 repository.delete_type()                                  │
│  返回 {"success": true}                                         │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ Repository: delete_type() ────────────────────────────────────┐
│                                                                 │
│  1. SELECT slug FROM custom_record_types WHERE id = ?          │
│     └─ 不存在 → EntityNotFoundError → 404                      │
│                                                                 │
│  2. data_table = "custom_" + slug                               │
│                                                                 │
│  3. ┌─ 事务开始 ──────────────────────────────────────────────┐ │
│     │                                                         │ │
│     │  3a. DROP TABLE IF EXISTS custom_<slug>  ◄── 先删表！   │ │
│     │      （防止删 meta 后表成为孤儿表）                       │ │
│     │                                                         │ │
│     │  3b. DELETE FROM custom_record_fields                   │ │
│     │      WHERE type_id = ?                                  │ │
│     │                                                         │ │
│     │  3c. DELETE FROM custom_record_types                    │ │
│     │      WHERE id = ?                                       │ │
│     │                                                         │ │
│     └─ 事务提交 ──────────────────────────────────────────────┘ │
│                                                                 │
│  返回: True                                                     │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 响应 ─────────────────────────────────────────────────────────┐
│  200 OK + { "success": true }                                   │
│  前端: refreshKey++ 强制刷新类型列表                             │
│  注意: 删除后 slug 可被新类型复用                                │
└────────────────────────────────────────────────────────────────┘
```

<key_function>
- lifeprism/server/api/custom_records_api.py:delete_custom_record_type:58
- lifeprism/server/services/custom_records_service.py:delete_type:101
- lifeprism/repository/aggregators/custom_record_aggregator.py:CustomRecordRepository.delete_type:290
</key_function>

## 耦合关系

| 耦合对象 | 耦合方式 |
|---------|---------|
| `DatabaseManager` | 通过 `self.db.get_connection()` 获取连接，执行 DML + DDL，使用事务上下文管理器 |
| `SyncRepository` | `custom_record_types` 和 `custom_record_fields` 列入静态同步白名单；动态生成的 `custom_<slug>` 表通过运行时查询 types 表的 slug 列表进行同步 |
| `LLM Agent Loop` | `CreateCustomRecordTypeTool` 和 `ListCustomRecordTypesTool` 直接调用 Repository（绕过 Service），返回 SUCCESS/ERROR 字符串供 Agent 解析 |
| `CustomRecordEntry` | 类型删除时级联删除数据表中的所有记录（DROP TABLE 直接销毁）；记录录入/查询依赖类型的字段定义进行 field_key 校验和动态 SQL 拼接 |
| `前端 TypeListView` | 调用 GET /types 展示类型卡片网格，调用 DELETE /types 删除类型 |
| `前端 CreateTypeView` | 调用 POST /types 创建类型，前端做 slug/field_key 预校验 |
| `前端 TypeDetailView` | 调用 GET /types/{type_id} 加载详情，调用 PATCH 更新配置和字段角色 |
