# PRD: 自定义记录模块（P1）

## Status

ready-for-agent

## Problem Statement

用户希望通过自然语言告诉 AI 想记录什么内容（如体育活动、每日饮食），由 AI 生成数据结构定义并持续把后续自然语言解析成结构化记录。现有模块（mood、diary、habit 等）都是预定义 schema 的固定模块，无法满足"用户自定义记录类型 + 自定义字段"的灵活记录需求。

用户需要：
1. 通过 AI 对话或前端表单创建记录类型（含自定义字段）
2. 通过 AI 对话持续录入数据
3. 前端能查看各类型的记录列表（按日期筛选）
4. 能硬删不再需要的类型

## Solution

采用 SQLite 动态建表 + meta 表元数据驱动方案（见 [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md)）。每个记录类型对应一张数据表 `custom_<slug>`，表结构由两张 meta 表（`custom_record_types`、`custom_record_fields`）驱动动态生成。

P1 范围：仅文本字段 + 文本列表展示，AI 对话式创建/录入 + 前端表单式创建。P2 图表（柱形/折线/饼）暂不做。

## User Stories

### 类型管理（创建/查询/删除）

1. 作为用户，我想通过前端表单创建一个自定义记录类型（含类型名和若干文本字段），以便记录我关心的内容
2. 作为用户，我想在表单中点击"添加字段"按钮动态添加字段行（每行包含字段显示名），像 Navicat 建表那样操作
3. 作为用户，我想在表单中移除已添加的字段行（提交前），以便调整字段设计
4. 作为用户，我想在聊天中告诉 AI"我想记录体育活动，字段是日期和锻炼内容"，AI 自动生成类型定义并在对话内确认后落库
5. 作为用户，我想在前端看到所有自定义记录类型列表，以便知道我有哪些记录类型
6. 作为用户，我想在前端点击某个类型查看其字段定义，以便了解该类型记录什么
7. 作为用户，我想在前端硬删某个不再需要的记录类型（含其所有数据），以便清理空间
8. 作为用户，我想在硬删某个类型后，能用同样的 slug 重新创建同名类型，以便纠正错误设计
9. 作为用户，我想在删除类型前看到确认提示，以防误删
10. 作为用户，当 AI 生成的 slug 与已有类型冲突时，我想让 AI 在对话内重新生成 slug 而不是静默失败
11. 作为用户，当 AI 生成的 field_key 不符合格式（非 snake_case）时，我想让后端拒绝并提示 AI 重新生成
12. 作为用户，当 AI 生成的 field_key 在同一类型内重复时，我想让后端拒绝并提示 AI 重新生成

### 数据录入

13. 作为用户，我想在聊天中说"今天跑了5公里"，AI 解析后展示字段值让我确认，确认后落库
14. 作为用户，当 AI 解析的字段值有误时，我想在对话内修改后再确认落库
15. 作为用户，当 AI 调用录入工具时传入了不存在的 field_key，我想让后端返回错误并附带该类型的正确字段列表，让 AI 重新解析
16. 作为用户，当 AI 调用录入工具时漏传了某些字段，我想让后端正常落库（缺失字段存为 NULL）
17. 作为用户，我想通过 AI 一次对话录入多条记录（如"今天早餐吃了面包，午餐吃了米饭"），AI 批量解析后逐条确认

### 数据查询与展示

18. 作为用户，我想在前端选择某个类型后看到该类型的所有记录列表
19. 作为用户，我想在记录列表中通过日期范围筛选记录
20. 作为用户，我想在记录列表中按创建时间倒序查看记录
21. 作为用户，我想在记录列表中分页查看记录（避免一次加载过多）
22. 作为用户，我想在记录列表中看到每条记录的所有字段值（动态列）
23. 作为用户，我想在记录列表中看到每条记录的创建时间
24. 作为用户，我想删除某条具体记录（不删整个类型）
25. 作为用户，我想在聊天中问 AI"我这周记录了哪些运动"，AI 查询对应类型并返回结果
26. 作为用户，当 AI 查询时传入了不存在的 type_id，我想让后端返回错误并附带当前所有可用类型列表

### AI 工具与提示词

27. 作为 AI agent，我想通过 `list_custom_record_types` 工具获取所有记录类型及其字段定义，以便知道当前可以录入哪些类型
28. 作为 AI agent，我想通过 `create_custom_record_type` 工具创建新类型，参数包含 name、slug、fields 数组
29. 作为 AI agent，我想通过 `create_custom_record_entry` 工具录入一条记录，参数包含 type_id 和 data 字典
30. 作为 AI agent，我想通过 `query_custom_record_entries` 工具按日期范围查询某个类型的记录
31. 作为 AI agent，我不应拥有删除类型或删除记录的工具（删除走前端手动操作）
32. 作为 AI agent，当录入失败时我想收到结构化错误（含正确字段列表），以便重新解析
33. 作为 AI agent，我想在 system prompt 中看到自定义记录模块的职责说明和可用工具列表

### 系统行为

34. 作为系统，当创建类型时，应在同一事务内写入 meta 表并执行 DDL，避免出现 meta 记录存在但数据表不存在的脏状态
35. 作为系统，当硬删类型时，应在同一事务内 DROP 数据表并删除 meta 表记录
36. 作为系统，应为每条记录自动生成 TEXT 格式的 id（`cre-{uuid[:8]}`），全局唯一
37. 作为系统，应为每条记录自动维护 created_at 和 updated_at 字段
38. 作为系统，应将动态表的 schema 完全存于 meta 表，不写入代码中的 TABLE_CONFIGS
39. 作为系统，CustomRecordRepository 应独立实现，不继承 LWBaseDataProvider（动态表名运行时才确定，不符合静态元数据驱动模式）

## Implementation Decisions

### 存储层

- **存储引擎**：SQLite 动态建表（决策见 [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md)）
- **Meta 表 1：`custom_record_types`**：记录类型元数据（**静态表**，需在 `lifeprism/config/database.py` 的 `TABLE_CONFIGS` 中定义，由 `init_database()` 创建）
  - 字段：`id` (TEXT PK, `crt-{uuid[:8]}`)、`name` (TEXT)、`slug` (TEXT UNIQUE)、`description` (TEXT)、`created_at` (TEXT)、`updated_at` (TEXT)
- **Meta 表 2：`custom_record_fields`**：字段定义元数据（**静态表**，同上需在 `TABLE_CONFIGS` 中定义）
  - 字段：`id` (TEXT PK, `crf-{uuid[:8]}`)、`type_id` (TEXT FK)、`field_name` (TEXT)、`field_key` (TEXT)、`field_type` (TEXT, P1 仅 `text`)、`sort_order` (INTEGER)、`created_at` (TEXT)
  - 约束：`(type_id, field_key)` 联合唯一
- **数据表 `custom_<slug>`**：动态表，由 meta 表定义驱动 DDL 动态创建（不写入 `TABLE_CONFIGS`）。每张表统一包含 `id` (TEXT PK, `cre-{uuid[:8]}`)、`created_at` (TEXT)、`updated_at` (TEXT)，外加 `custom_record_fields` 定义的列（P1 均为 TEXT 类型）
- **id 格式**：TEXT 类型 `cre-{uuid[:8]}`，与项目其他表一致（如 mood_entries 的 `mood-{uuid[:8]}`），全局唯一便于前端直接用 entry_id 作 React key

### Repository 层（核心逻辑所在）

- **CustomRecordRepository 独立实现**，不继承 LWBaseDataProvider
  - 原因：LWBaseDataProvider 的元数据是类级静态属性（`_TABLE_NAME` 等），动态表表名运行时才确定，硬套破坏静态契约
  - 内部直接使用 `lw_db_manager` 执行参数化 SQL
  - 豁免 [create-table-rules.md](../../docs/coding-rules/create-table-rules.md) 中"provider 类必须继承自 LWBaseDataProvider"的约束
- **核心方法**：
  - 类型管理：`create_type(name, slug, fields)`、`list_types()`、`get_type_by_id(type_id)`、`get_type_fields(type_id)`、`delete_type(type_id)`
  - 记录管理：`create_entry(type_id, data)`、`query_entries(type_id, date_range, page, page_size)`、`get_entry(type_id, entry_id)`、`delete_entry(type_id, entry_id)`
- **事务策略**：创建类型时 meta 表写入 + DDL 在同一 `get_connection()` 上下文内完成；硬删类型时 DROP + meta 删除在同一事务内
  - SQLite 支持 DDL（CREATE TABLE / DROP TABLE）在事务内执行，可与 DML 在同一事务回滚（不同于 MySQL/PostgreSQL 的 DDL 隐式提交）
  - `lw_db_manager.get_connection()` 上下文管理器（`database_manager.py` 第 136-178 行）正常退出 commit，异常 rollback，保证 meta 表记录与 DDL 的原子性：任一失败则整体回滚
- **slug 冲突检测与校验**：
  - 格式校验：Repository 层正则 `^[a-z][a-z0-9_]*$`（与 field_key 一致，防 SQL 注入和非法表名）
  - 唯一性校验：依赖 `custom_record_types.slug` UNIQUE 约束，冲突时抛 `DuplicateEntityError`
  - 格式错误抛 `ValidationError`
- **field_key 校验**：Repository 层正则 `^[a-z][a-z0-9_]*$` + 同类型内 `(type_id, field_key)` 联合唯一校验
  - 格式错误抛 `ValidationError`，附带错误详情
  - 录入时 data 的 key 不匹配 `custom_record_fields` 中该 type_id 的 field_key，抛 `ValidationError`，details 包含 `valid_fields`（字段 key 与显示名列表）
  - 缺失字段不报错，存为 NULL
- **valid_fields 返回**：Repository 知道字段定义，校验失败时由 Repository 层负责构造 `valid_fields` 列表
- **创建类型时的 fields 校验**：fields 数组不能为空，至少 1 个字段，否则抛 `ValidationError`（空字段表无意义）
- **录入时 data 为空字典**：允许，插入一行全 NULL 的记录（用户可能只想记录"今天发生了某事"但不填具体字段值）
- **date_range 单侧缺失**：可只传 start 或只传 end，缺失侧不加约束（与现有 QueryOptions 模式一致）
- **导出位置**：在 `lifeprism/repository/__init__.py` 中导出 `custom_record_repository` 实例，遵循现有模式（如 `mood_repository` 的导出方式）

### Service 层（API 层薄包装）

- **CustomRecordService** 仅服务 API 层，做参数转换与 repository 调用编排
- **不包含核心业务逻辑**：slug 冲突、field_key 校验、valid_fields 构造等都在 Repository 层
- **LLM Tool 不经过 Service**：遵循现有架构（[lifeprismsystem.py](../../lifeprism/llm/agent/tools/lifeprismsystem.py) 第 6-13 行证明 LLM tool 直接引用 repository），LLM tool 直接调 `custom_record_repository`，避免 `llm → server` 循环引用

### 架构依赖关系

```
API 路由 ──→ Service ──→ Repository (CustomRecordRepository)
                              ↑
LLM Tool ──────────────────────┘  (直接访问，不经过 Service)
```

### API 层

- **路由前缀**：`/custom-records`
- **端点**：
  - `GET /custom-records/types` — 类型列表（含 fields）
  - `GET /custom-records/types/{type_id}` — 单个类型详情（含 fields）
  - `POST /custom-records/types` — 创建类型（body: name, slug, fields: [{field_name, field_key, field_type}]）
  - `DELETE /custom-records/types/{type_id}` — 硬删类型
  - `GET /custom-records/{type_id}/entries` — 查询记录（query: start_date, end_date, page, page_size）
  - `POST /custom-records/{type_id}/entries` — 录入记录（body: data 字典）
  - `DELETE /custom-records/{type_id}/entries/{entry_id}` — 删除单条记录
- **错误响应**：遵循项目全局异常处理器映射（ValidationError → 422，EntityNotFoundError → 404，DuplicateEntityError → 409）
- **API 层不写 try/except**（遵循 [lifeprism/CLAUDE.md](../../lifeprism/CLAUDE.md) 错误处理规则）

### LLM Tool 层（直接调 Repository）

- **4 个 tool**（均注册到 [ToolRegistry](../../lifeprism/llm/agent/tools/registry.py)，直接调用 `custom_record_repository`，不经过 service）：
- **注册位置**：在 `lifeprism/llm/agent/loop.py` 的 `_process_msg()` CHAT 分支中注册 4 个 tool（参考现有第 425-441 行的 `self._tool_registry.register(...)` 模式，如 `UserMoodCreateTool` 的注册方式）
  1. `list_custom_record_types` — 无参数，返回 `[{id, name, slug, fields: [{field_key, field_name, field_type}]}]`
  2. `create_custom_record_type` — 参数 `{name, slug, fields: [{field_name, field_key, field_type}]}`，返回 `{type_id}`
  3. `create_custom_record_entry` — 参数 `{type_id, data: {field_key: value}}`，返回 `{entry_id}`
  4. `query_custom_record_entries` — 参数 `{type_id, date_range?: [start, end], limit?}`，返回 `[{entry}]`
- **AI 无删除工具**：删除走前端，prompt（templates\agent\chat\tool.md文件） 中写明流程
- **Tool 返回类型**：遵循 [lifeprism/llm/agent/tools/CLAUDE.md](../../lifeprism/llm/agent/tools/CLAUDE.md)，所有 `execute()` 返回 `str`（成功用 `json.dumps(ensure_ascii=False)`，失败用 `f"{ERROR}..."`）
- **错误提示契约**：录入时 field_key 错误，tool 捕获 Repository 抛出的 `ValidationError`，返回 JSON 字符串：
  ```json
  {
    "error": "INVALID_FIELD_KEY",
    "message": "字段 'wrong_field' 不存在",
    "valid_fields": [
      {"field_key": "exercise_date", "field_name": "日期"},
      {"field_key": "exercise_content", "field_name": "锻炼内容"}
    ]
  }
  ```
  引导 AI 重新解析（`valid_fields` 由 Repository 层构造，Tool 层仅做 JSON 序列化）

### Prompt 设计

- 在 agent system prompt 中追加"自定义记录模块"段落，说明：
  - 模块职责：用户通过自然语言定义记录类型并录入数据
  - 可用 tool 列表及使用场景
  - 录入流程：解析 → 对话内展示 → 用户确认 → 调用 tool
  - slug 生成规则：英文 snake_case，语义化
  - field_key 生成规则：英文 snake_case，正则 `^[a-z][a-z0-9_]*$`
  - 删除流程：AI 无删除工具，用户走前端

### 前端

- **新增 apps/lifewatch/pages/custom-records/**（或 mindspace 下，按现有布局决定）
- **类型列表页**：展示所有 `custom_record_types`，每项显示 name、字段数、记录数；提供"新建类型"按钮和"删除"操作
- **新建类型页**：表单含类型名称输入 + 动态字段行（"添加字段"按钮加行，每行含字段显示名输入 + 移除按钮）+ slug 输入（或 AI 生成）
- **类型详情页**：动态表格（`fields` 数组驱动表头）+ 日期范围筛选 + 分页 + 行内删除
- **数据驱动渲染**：前端不硬编码列定义，从 API 获取 fields 后用 `fields.map()` 渲染表头与数据列
- **状态管理**：`types` + `selectedTypeId` + `fields` + `entries` 四个独立 state，`useEffect` 串联加载

## Testing Decisions

### 测试原则

- 只测外部行为，不测实现细节
- 单一测试 seam：**Repository 层**（`test/core/unit/repository/test_custom_records_repository.py`）
- 不新增 API 层测试、LLM tool 层测试、Service 层测试、前端测试
  - Repository 是核心逻辑所在（建表、校验、事务、valid_fields 构造）
  - Service 是 Repository 的薄包装，仅服务 API 层
  - LLM Tool 是 Repository 的薄包装 + JSON 序列化
  - API 层是 Service 的薄路由
  - 测 Repository 即覆盖所有核心行为

### 测试覆盖

| 行为 | 测试方法 | 参考 |
|------|---------|------|
| 创建类型（含字段定义） | 直接调用 `custom_record_repository.create_type()`，断言返回 type_id 且 meta 表有记录且数据表存在 | [test_base_provider_generic_methods.py](../../test/core/unit/storage/test_base_provider_generic_methods.py) |
| slug 冲突 | 创建两个相同 slug 的类型，断言第二个抛 `DuplicateEntityError` | 现有 repository 测试模式 |
| field_key 格式校验 | 传入 `Wrong-Key` 等非法格式，断言抛 `ValidationError` | - |
| field_key 同类型唯一性 | 同一类型内两个相同 field_key，断言抛 `ValidationError` | - |
| 录入记录 | 调用 `custom_record_repository.create_entry()`，断言 entry_id 返回且数据表有记录 | - |
| 录入时 field_key 错误 | 传入不存在的 field_key，断言抛 `ValidationError` 且 details 含 `valid_fields` | - |
| 录入时字段缺失 | 漏传部分字段，断言落库成功且缺失字段为 NULL | - |
| 查询记录（日期筛选） | 创建多条记录，按日期范围查询，断言返回正确子集 | - |
| 硬删类型 | 删除后断言 meta 表无记录且数据表已 DROP | - |
| 删除单条记录 | 删除后断言数据表无该记录但其他记录不受影响 | - |

### 不测的内容

- LLM tool 的参数解析与 JSON 序列化（ToolRegistry 已有通用逻辑）
- Service 层（Repository 的薄包装，无业务逻辑）
- API 路由的请求转发（FastAPI 已有保证）
- 前端渲染（人工验证）
- 迁移系统（动态表不走迁移系统）

## Out of Scope

### P1 不做

- **Schema 演进**：字段定义后不可变，要改只能新建类型 + 硬删旧类型
- **图表展示**：柱形图、折线图、饼图暂不做，仅文本列表
- **字段类型扩展**：P1 仅支持 `text` 类型字段，`number`/`date` 类型留作枚举位但不实现
- **AI skill 动态注入**：P1 直接给 LLM tool，P3 才考虑把 schema 动态注入 skill
- **记录类型间的关联查询**：各类型独立，不做跨表 JOIN
- **数据导出**：不支持导出为 CSV/JSON
- **软删/归档**：仅硬删，不可恢复
- **草稿状态**：AI 录入在对话内确认，不存 draft 中间态
- **AI 删除工具**：AI 无删除权限，删除走前端

### 未来可能（不在本 PRD 范围）

- P2：图表展示（需字段类型扩展为 number/date）
- P3：AI skill 动态注入 schema
- Schema 演进（ALTER TABLE 支持增删改字段）
- 软删/归档机制
- 跨类型关联查询

## Further Notes

### 相关文档

- [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md) — 存储方案决策
- [CONTEXT.md](../../CONTEXT.md) — 自定义记录模块术语表
- [repository-core-spec](../../docs/specs/2026-07-06-repository-core-spec.md) — Repository 数据访问层核心契约
- [llm-agent-spec](../../docs/specs/2026-07-06-llm-agent-spec.md) — Agent 执行引擎规格（tool 注册机制）
- [mood-module-spec](../../docs/specs/2026-05-20-mood-module-spec.md) — 近亲模块参考（用户自定义类型 + CRUD + 日期查询）

### 关键设计决策汇总

| 维度 | 决策 |
|------|------|
| 存储 | SQLite 动态建表 + 2 张 meta 表 |
| AI 职责 | schema 生成 + 持续录入（对话内确认） |
| 字段类型 | P1 仅 text |
| Schema 演进 | P1 不支持 |
| 类型删除 | 用户走前端硬删，AI 无删除工具，slug 可复用 |
| field_key | AI 生成 + 正则校验 + 同类型唯一性 |
| 记录 id | TEXT `cre-{uuid[:8]}`，全局唯一 |
| Repository | 独立实现，不继承 LWBaseDataProvider，核心逻辑所在 |
| LLM Tool | 直接调 Repository，不经过 Service（避免循环引用） |
| 测试 seam | Repository 层单一 seam |
