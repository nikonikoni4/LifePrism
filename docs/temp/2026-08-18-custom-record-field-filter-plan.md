# 自定义记录 Agent 查询工具：字段级过滤筛选

日期：2026-08-18
状态：已实施完成

## 目标

增强 `query_custom_record_entries` Agent 工具，在现有 `date_range` 时间筛选基础上，新增字段级过滤（如「查心率大于 100 的记录」「锻炼内容包含 跑步 的记录」），减少 AI 拿到全量数据后自行筛选的 token 消耗与出错率。

## 现状

- 工具层：`lifeprism/llm/agent/tools/custom_records_tool.py` 的 `QueryCustomRecordEntriesTool`，目前仅支持 `type_id` / `date_range` / `limit`
- Repository 层：`lifeprism/repository/aggregators/custom_record_aggregator.py` 的 `query_entries`，WHERE 仅拼 event_time 条件，全参数化 SQL
- 值类型校验已有现成机制：`_coerce_field_value`（text/integer/float 三类转换 + 哨兵）
- `create_entry` 已有 INVALID_FIELD_KEY / INVALID_FIELD_VALUE 结构化错误模式（返回 valid_fields 引导 AI 重试），可复用

## 设计

### 1. Repository 层：`query_entries` 新增 `filters` 参数

签名追加 `filters: list[dict[str, Any]] | None = None`，每项 `{"field_key": str, "op": str, "value": Any}`：

- **操作符白名单**（映射到固定 SQL 模板，杜绝注入）：
  - 通用：`eq`(=)、`ne`(!=)、`in`(IN (?,...))
  - 仅 text 字段：`contains`(LIKE '%v%' ESCAPE '\')
  - 仅 integer/float 字段：`gt`、`gte`、`lt`、`lte`
- **校验**（抛 ValidationError，code 与 create_entry 对齐）：
  - field_key 不在类型字段定义 -> `INVALID_FIELD_KEY`（details 含 valid_fields）
  - op 不在该 field_type 允许集合 -> `INVALID_FILTER_OP`（details 含 allowed_ops）
  - value 经 `_coerce_field_value` 转换失败 -> `INVALID_FIELD_VALUE`
  - `in` 的 value 必须是非空数组，逐项转换；`contains` 仅接受字符串
- SQL 构建：过滤条件以 AND 追加进现有 WHERE，COUNT 查询同步生效，参数全占位符
- **向后兼容**：`filters=None` 行为完全不变，`custom_records_service.py` 调用点无需改动

### 2. Tool 层：`QueryCustomRecordEntriesTool` 新增 `filters` 参数

- `parameters` 增加 `filters` 数组（items: `{field_key, op, value}`，op 用 enum 列出全部操作符，value 不限定类型）
- `description` 更新：说明各操作符适用的字段类型、field_key 来自 `list_custom_record_types` 的字段定义、多条件间为 AND
- `execute` 透传 filters；单独捕获 ValidationError 返回结构化 JSON（含 valid_fields / allowed_ops），引导 AI 纠正后重试（复用 CreateCustomRecordEntryTool 的错误模式）

### 3. 测试（`@pytest.mark.core`）

- `test/core/unit/llm/test_custom_records_tool.py`：filters 正确透传（mock repository 断言调用参数）、INVALID_FIELD_KEY / INVALID_FILTER_OP 结构化错误返回
- `test/core/integration/repository/test_custom_records_repository.py`：真实 DB 下 eq / gt / contains / in 结果正确性、多条件 AND 组合、无效 field_key 与 op 报错、value 类型不匹配报错

### 4. 文档

- 更新 `docs/specs/custom-records-module.md`：功能清单（第 122 行）、调用链路、工具接口表（第 343 行）补充 filters 说明
- 写文档前先读 `docs/docs-rules/index.md` + `docs/docs-rules/docs-write-rules.md`

## 任务拆分（超过 3 个文件，分步执行）

1. Repository：`query_entries` 支持 filters + 校验
2. Tool：filters 参数 schema + description + 错误处理
3. 测试：unit + integration，全部通过
4. 文档：spec 更新

## 风险

- **LIKE 通配符**：`contains` 值中的 `%`/`_` 会被当通配符 -> 用 ESCAPE '\' 转义
- **SQL 注入**：op 走白名单模板、field_key 走字段定义校验、value 全参数化，无拼接面
- **兼容性**：filters 为可选参数，service 层与现有调用不受影响
