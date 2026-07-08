# Code Review Report

**审查范围**: `.scratch/custom-records-module/issues/01~03`（S1 类型管理 + S2 数据录入查询 + S3 Service/API）
**审查时间**: 2026-07-08
**审查提交**: `4f7a0ea` feat: 实现自定义记录模块 S1-S3（19 文件，+2149/-6 行）
**前次审查**: [001/code-review-2026-07-07.md](../001/code-review-2026-07-07.md)（同提交，已发现 2 个问题并修复）

## 架构上下文

### 相关 ADR
- [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md): SQLite 动态建表 + meta 表方案 (decided)
  - 决策：CustomRecordRepository 独立实现，不继承 LWBaseDataProvider
  - 决策：LLM Tool 直接调用 Repository，不经过 Service

### 相关 Spec
- [custom-records-module](../../docs/specs/custom-records-module.md): 自定义记录模块规格
- [.scratch/custom-records-module/PRD.md](../../.scratch/custom-records-module/PRD.md): 产品规格

### 编码规则
- [backend-core-rules.md](../../docs/coding-rules/backend-core-rules.md): 后端核心规范
- [backend-api-rules.md](../../docs/coding-rules/backend-api-rules.md): API 设计规范
- [create-table-rules.md](../../docs/coding-rules/create-table-rules.md): 数据库接口创建规则
- [lifeprism/CLAUDE.md](../../lifeprism/CLAUDE.md): 后端通用规则
- [lifeprism/llm/agent/tools/CLAUDE.md](../../lifeprism/llm/agent/tools/CLAUDE.md): Agent Tools 规则

### 前次审查已修复问题

| Issue | 状态 |
|-------|------|
| Repository 层 `except Exception as e` → `except sqlite3.Error as e`（8 处） | ✅ 已修复 |
| `delete_entry` 不检查记录存在性 → 抛 `EntityNotFoundError` | ✅ 已修复 |
| TABLE_CONFIGS 缺失 `card_template`/`icon`/`accent_color`/`display_role` 列 | ✅ `b62c3f9` 修复 |

## 审查结果

Found 4 issues:

### Issue 1: LLM Tools 返回格式不一致 — 查询类工具缺少 SUCCESS 前缀

- **类型**: Code Quality / Best Practices
- **置信度**: 85
- **位置**:
  - [custom_records_tool.py:44](../../lifeprism/llm/agent/tools/custom_records_tool.py#L44) — `ListCustomRecordTypesTool.execute()`
  - [custom_records_tool.py:265](../../lifeprism/llm/agent/tools/custom_records_tool.py#L265) — `QueryCustomRecordEntriesTool.execute()`
- **详情**: 4 个 LLM Tool 的 `execute()` 方法成功返回格式不一致：
  - `ListCustomRecordTypesTool`: 返回 `json.dumps(types)` — **无** `SUCCESS` 前缀
  - `QueryCustomRecordEntriesTool`: 返回 `json.dumps(entries)` — **无** `SUCCESS` 前缀
  - `CreateCustomRecordTypeTool`: 返回 `f"{SUCCESS}创建自定义记录类型成功: {json.dumps(result)}"`
  - `CreateCustomRecordEntryTool`: 返回 `f"{SUCCESS}录入自定义记录成功: {json.dumps(result)}"`
- **依据**: 模板 `templates/agent/chat/tool.md` 规定：
  > 成功：以 `"Success: "` 开头
  > 失败：以 `"Error: "` 开头

  `SUCCESS = "Success: "`, `ERROR = "Error: "`（`base.py:12-13`）。查询类工具不加 `SUCCESS` 前缀意味着 LLM 收到纯 JSON，而创建类工具收到 `"Success: ...{json}"` 格式。这种不一致可能导致 LLM 在解析查询结果时行为不同。
- **修复建议**: 统一所有工具的返回格式。推荐方案：查询类工具也加 `SUCCESS` 前缀：
  ```python
  return f"{SUCCESS}{json.dumps(types, ensure_ascii=False)}"
  ```

### Issue 2: `_query_one`/`_query_all` 内部辅助方法不捕获 `sqlite3.Error`

- **类型**: Code Quality / 错误处理一致性
- **置信度**: 75
- **位置**:
  - [custom_record_aggregator.py:195-204](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L195-L204) — `_query_one()`
  - [custom_record_aggregator.py:206-215](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L206-L215) — `_query_all()`
- **详情**: `_query_one` 和 `_query_all` 是 Repository 层的内部辅助方法，直接执行 SQL 但不捕获 `sqlite3.Error`。虽然当前所有调用者（`list_types`、`get_type_by_id`、`create_type`、`create_entry` 等）都在其自身的 try/except 中处理了异常，但公共方法 `get_type_fields()` 直接调用 `_query_all()` 而没有自己的错误处理（[line 288](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L288)）。
- **依据**: [backend-core-rules.md](../../docs/coding-rules/backend-core-rules.md) Section 5：
  > 外部接口层（数据访问层）：捕获外部异常，转换为业务异常并抛出

  如果未来有新调用者直接使用 `_query_one`/`_query_all` 或 `get_type_fields()` 而未包装错误处理，原始 `sqlite3.Error` 将冒泡到上层。
- **修复建议**: 在 `_query_one` 和 `_query_all` 内部添加 `try/except sqlite3.Error` 并转为 `DataAccessError`，与 `list_types`、`get_type_by_id` 等方法保持一致。

### Issue 3: `query_entries` 使用 `dict(row)` 而其他方法使用 `cursor.description + zip`

- **类型**: Code Quality / 一致性
- **置信度**: 60
- **位置**: [custom_record_aggregator.py:464](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L464)
- **详情**: `query_entries()` 在 L464 使用 `rows = [dict(row) for row in cursor.fetchall()]` 构建返回字典，而 `_query_one()`（L204）和 `_query_all()`（L214）使用 `dict(zip(columns, row, strict=True))` 模式。两种模式都正确（因为 `database_manager.py:79` 设置 `row_factory = sqlite3.Row`），但代码路径不一致。
- **依据**: 代码风格一致性。同一文件内的两个模式会让后续维护者困惑哪个是正确的。
- **修复建议**: 统一使用 `cursor.description + zip` 模式（更明确，不依赖 row_factory 的隐式行为）。

### Issue 4: `list_types()` 存在 N+1 查询

- **类型**: Performance
- **置信度**: 50
- **位置**: [custom_record_aggregator.py:227-248](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L227-L248)
- **详情**: `list_types()` 先查询所有类型（1 次查询），然后为每个类型单独调用 `_get_fields_by_type_id()`（N 次查询）。当有 10 个类型时，产生 11 次数据库查询。
- **依据**: 一般性能最佳实践。在类型数量少（< 20）时影响可忽略，但如果未来类型数量增长，可能成为瓶颈。
- **修复建议**: 使用单次 JOIN 查询获取所有类型及其字段：
  ```sql
  SELECT t.*, f.id AS f_id, f.field_name, f.field_key, f.field_type, f.sort_order
  FROM custom_record_types t
  LEFT JOIN custom_record_fields f ON f.type_id = t.id
  ORDER BY t.created_at ASC, f.sort_order ASC
  ```
  然后在 Python 中按 type_id 分组。

## 变更摘要

### 实现覆盖（vs Issue Spec）

| Issue | 要求的文件/功能 | 实现状态 |
|-------|----------------|---------|
| 01 类型管理 | `custom_record_types` + `custom_record_fields` meta 表 | ✅ TABLE_CONFIGS 定义 |
| 01 类型管理 | `CustomRecordRepository` (create_type, list_types, get_type_by_id, get_type_fields, delete_type) | ✅ 全部实现 |
| 01 类型管理 | 2 个 LLM Tool (list, create type) | ✅ 已注册到 loop.py |
| 01 类型管理 | prompt 追加"自定义记录"段落 | ✅ tool.md 已更新 |
| 02 数据录入查询 | create_entry, query_entries, get_entry, delete_entry | ✅ 全部实现 |
| 02 数据录入查询 | field_key 校验 + valid_fields 错误提示 | ✅ 含结构化 JSON |
| 02 数据录入查询 | 2 个 LLM Tool (create_entry, query_entries) | ✅ 已注册 |
| 03 Service/API | CustomRecordService 薄包装 | ✅ 纯函数模块 |
| 03 Service/API | 7 个 REST API 端点 | ✅ + 额外 PATCH 端点(S6) |
| 03 Service/API | 路由挂载到 /api/v2/custom-records | ✅ main.py |

### 安全审查

- **SQL 注入**: ✅ 安全。动态表名 `custom_<slug>` 通过正则 `^[a-z][a-z0-9_]*$` 校验，列名 `field_key` 同理。所有参数值使用参数化查询。
- **DDL 注入**: ✅ slug/field_key 正则校验充分，无法注入恶意 DDL。

### 测试覆盖

- ✅ 24 个 Repository 层测试（创建/列表/校验/删除/录入/查询/分页/日期筛选/配置更新/字段角色）
- ✅ 测试覆盖所有边界情况（空 fields、重复 slug、错误 field_key、空字典 data、缺失字段、不存在的记录）
- ⚠️ 无 LLM Tool 层测试（PRD 未要求）

### 编码规则合规

| 规则 | 状态 |
|------|------|
| API 层不写 try/except | ✅ custom_records_api.py 无 try/except |
| Repository 层捕获 sqlite3.Error → DataAccessError | ⚠️ 公共方法已合规，`_query_one`/`_query_all` 内部方法未捕获 |
| 日志用 %s 格式 | ✅ 全部使用 %s |
| Tool execute() 返回 str | ✅ 全部返回 str |
| 数据库操作仅在 Repository 层 | ✅ Service/API/Tool 层无直接 SQL |
| Server 层 import 用 `as _repository` 后缀 | ⚠️ 使用 `custom_record_repository`（不带后缀），但项目自身 `mood_repository` 等也用同样模式 |
