# 自定义记录类型管理 - LLM 通道端到端

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD.md`

## What to build

实现自定义记录模块的类型管理功能，从存储层到 LLM tool 端到端打通。完成后，用户可以通过 AI 对话创建自定义记录类型（如"体育活动"），AI 调用 tool 完成 meta 表写入和动态数据表 DDL 建表，并可列出已有类型、硬删类型。

端到端行为：
1. 用户在对话中说"我想记录体育活动，字段是日期和锻炼内容"
2. AI 解析意图，调用 `create_custom_record_type` tool
3. 后端写入 `custom_record_types` 和 `custom_record_fields` meta 表，并在同一事务内执行 `CREATE TABLE custom_<slug>` DDL
4. AI 在对话内展示解析结果，用户确认后类型创建成功
5. 用户问"我现在有哪些记录类型"，AI 调用 `list_custom_record_types` 返回完整列表（含 fields）
6. 用户说"删除运动类型"，AI 引导用户走前端删除（AI 无删除工具）

### 存储层

- **Meta 表（静态表，需在 `lifeprism/config/database.py` 的 `TABLE_CONFIGS` 中定义，由 `init_database()` 创建）**：
  - `custom_record_types`：`id` (TEXT PK, `crt-{uuid[:8]}`)、`name` (TEXT)、`slug` (TEXT UNIQUE)、`description` (TEXT)、`created_at` (TEXT)、`updated_at` (TEXT)
  - `custom_record_fields`：`id` (TEXT PK, `crf-{uuid[:8]}`)、`type_id` (TEXT FK)、`field_name` (TEXT)、`field_key` (TEXT)、`field_type` (TEXT, P1 仅 `text`)、`sort_order` (INTEGER)、`created_at` (TEXT)
  - 约束：`(type_id, field_key)` 联合唯一
- **动态数据表 `custom_<slug>`**：每张表统一包含 `id` (TEXT PK, `cre-{uuid[:8]}`)、`created_at` (TEXT)、`updated_at` (TEXT)，外加 `custom_record_fields` 定义的列（P1 均为 TEXT 类型）

### Repository 层

- **`CustomRecordRepository` 独立实现**，不继承 LWBaseDataProvider（豁免 `docs/coding-rules/create-table-rules.md` 中"provider 必须继承 LWBaseDataProvider"的约束）
- 内部直接使用 `lw_db_manager` 执行参数化 SQL
- **核心方法**：
  - `create_type(name, slug, fields)` — 写 meta 表 + DDL 同事务
  - `list_types()` — 返回所有类型（含 fields）
  - `get_type_by_id(type_id)` — 单个类型详情（含 fields）
  - `get_type_fields(type_id)` — 仅返回字段定义
  - `delete_type(type_id)` — DROP 表 + 删 meta 同事务
- **事务策略**：SQLite 支持 DDL 在事务内执行，meta 表写入与 DDL 在同一 `get_connection()` 上下文内完成，任一失败则整体回滚
- **slug 校验**：
  - 格式：正则 `^[a-z][a-z0-9_]*$`（防 SQL 注入和非法表名）
  - 唯一性：依赖 `custom_record_types.slug` UNIQUE 约束，冲突抛 `DuplicateEntityError`
  - 格式错误抛 `ValidationError`
- **field_key 校验**：
  - 格式：正则 `^[a-z][a-z0-9_]*$`
  - 唯一性：`(type_id, field_key)` 联合唯一
  - 格式错误抛 `ValidationError`
- **fields 为空校验**：fields 数组不能为空，至少 1 个字段，否则抛 `ValidationError`
- **导出位置**：在 `lifeprism/repository/__init__.py` 中导出 `custom_record_repository` 实例（参考 `mood_repository` 的导出方式）

### LLM Tool 层

- **2 个 tool**（直接调用 `custom_record_repository`，不经过 service）：
  1. `list_custom_record_types` — 无参数，返回 `[{id, name, slug, fields: [{field_key, field_name, field_type}]}]`
  2. `create_custom_record_type` — 参数 `{name, slug, fields: [{field_name, field_key, field_type}]}`，返回 `{type_id}`
- **注册位置**：在 `lifeprism/llm/agent/loop.py` 的 `_process_msg()` CHAT 分支中注册（参考现有第 425-441 行的 `self._tool_registry.register(...)` 模式）
- **Tool 返回类型**：遵循 `lifeprism/llm/agent/tools/CLAUDE.md`，所有 `execute()` 返回 `str`（成功用 `json.dumps(ensure_ascii=False)`，失败用 `f"{ERROR}..."`）
- **AI 无删除工具**：删除走前端，prompt 中写明流程

### Prompt 设计

- 在 `templates/agent/chat/tool.md`（或合适的 prompt 文件）中追加"自定义记录"段落
- 说明：当用户表达"想记录某类内容"时，调用 `create_custom_record_type`
- 说明：录入前先调 `list_custom_record_types` 获取 schema
- 说明：删除类型走前端，AI 无此能力

### 测试

- **测试 seam**：Repository 层（`test/core/unit/repository/test_custom_records_repository.py`）
- 参考 `test/core/unit/storage/test_base_provider_generic_methods.py` 的测试模式
- 测试覆盖：
  - 创建类型（含字段定义）→ 断言返回 type_id 且 meta 表有记录且数据表存在
  - slug 冲突 → 断言抛 `DuplicateEntityError`
  - slug 格式错误（如 `Wrong-Slug`）→ 断言抛 `ValidationError`
  - field_key 格式错误 → 断言抛 `ValidationError`
  - field_key 同类型唯一性 → 断言抛 `ValidationError`
  - fields 为空 → 断言抛 `ValidationError`
  - 列出类型 → 断言返回含 fields 的完整列表
  - 硬删类型 → 断言 meta 表记录删除且数据表 DROP

## Acceptance criteria

- [ ] meta 表（`custom_record_types`、`custom_record_fields`）在 `TABLE_CONFIGS` 中定义，启动后端后表自动创建
- [ ] `CustomRecordRepository` 在 `lifeprism/repository/__init__.py` 中导出为 `custom_record_repository`
- [ ] 通过 AI 对话创建类型：meta 表写入 + DDL 建表成功，返回 type_id
- [ ] slug 冲突时返回 `DuplicateEntityError`，slug/field_key 格式错误时返回 `ValidationError`
- [ ] fields 为空时返回 `ValidationError`
- [ ] 通过 AI 对话列出所有类型，返回完整 schema（含 fields）
- [ ] 硬删类型时 meta 表记录和数据表同时删除（同事务）
- [ ] 2 个 LLM tool 在 `loop.py` CHAT 分支注册
- [ ] prompt 中追加"自定义记录"段落
- [ ] Repository 层测试全部通过
- [ ] 遵循 `lifeprism/CLAUDE.md`（日志用 %s 格式、API 层不写 try/except、错误处理规则）

## Blocked by

None - 可以立即开始
