# P2 Slice 1: 数值字段类型扩展（integer + float）端到端

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD-P2.md`

## What to build

在 P1 仅支持 `text` 字段类型的基础上，端到端扩展 `integer` 和 `float` 两种数值字段类型。完成后用户（通过 AI 对话或前端表单）能创建含数值字段的自定义记录类型，数据按正确的 SQLite 列类型（INTEGER/REAL）存储，录入时校验值类型，查询返回值保留原始类型，前端正确显示数值。

端到端行为：
1. AI 在对话中创建类型时，能选择 `text`/`integer`/`float` 三种字段类型，prompt 提供类型选择指导 + 单位约定（写入 field_name）+ 百分比约定（按百分点存）
2. 前端新建类型表单的字段类型下拉框提供"文本/整数/浮点数"三个选项
3. 后端 Schema 层用 `Literal["text","integer","float"]` 强制枚举校验
4. Repository 层 `create_type` 按 `field_type` 映射 DDL 列类型（TEXT/INTEGER/REAL）
5. Repository 层 `create_entry` 新增值类型校验：integer 不接受浮点字符串，float 接受 int/float/可解析字符串；不匹配抛 `ValidationError(code=INVALID_FIELD_VALUE)`，details 含 `valid_fields` + `expected_types`
6. 查询返回值保留 SQLite 原始类型（integer 返回 int，float 返回 float）
7. 前端表格/卡片的数值字段按规则格式化：integer 显示原值，float 固定 1 位小数
8. P1 已创建的类型（全 TEXT 列）不受影响，行为完全一致

### Schema 层

- `FieldDefinition.field_type`：从 `str` 改为 `Literal["text", "integer", "float"]`
- `CreateCustomRecordEntryRequest.data`：类型从 `dict[str, str]` 改为 `dict[str, str | int | float]`
- `CustomRecordEntryItem`：保持 `model_config = {"extra": "allow"}`

### Repository 层（核心逻辑所在）

#### DDL 列类型映射

`create_type` 的 DDL 生成逻辑改为按 `field_type` 映射：

| field_type | SQLite 列类型 |
|------------|---------------|
| text       | TEXT          |
| integer    | INTEGER       |
| float      | REAL          |

映射通过模块级常量字典实现，未知 `field_type` 抛 `ValidationError(code=INVALID_FIELD_TYPE)`。

#### 录入值类型校验

`create_entry` 在现有的 field_key 校验之后，增加值类型校验：
- **integer 字段**：值必须是 `int`，或可解析为 int 的字符串（字符串不含小数点且能 `int()` 成功）
- **float 字段**：值必须是 `int` 或 `float`，或可解析为 float 的字符串（能 `float()` 成功）
- **text 字段**：保持现状，任何值都转为字符串存储

类型不匹配抛 `ValidationError(code=INVALID_FIELD_VALUE)`，details 包含：
```python
{
    "invalid_fields": [{"field_key": "count", "value": "abc", "expected_type": "integer"}],
    "valid_fields": [{"field_key": "count", "field_name": "次数", "field_type": "integer"}],
}
```

#### 查询值类型保留

`query_entries` / `get_entry` 返回的字典中，数值字段的值保留 SQLite 返回的原始类型（int/float），不强制转字符串。

### LLM Tool 层

- `CreateCustomRecordTypeTool.parameters.fields.items.field_type.enum` 从 `["text"]` 改为 `["text", "integer", "float"]`
- description 中"P1 仅 text"改为"可选 text/integer/float"
- `CreateCustomRecordEntryTool` 的错误处理兼容新的 `INVALID_FIELD_VALUE` 错误码，返回结构化 JSON 引导 AI 重新解析
- `data` 的 `additionalProperties` 从 `{"type": "string"}` 改为支持 number

### Prompt 设计

在 `templates/agent/chat/tool.md` 的"自定义记录模块"段落中增加：

#### 字段类型选择指导
- **text**：文本内容（如锻炼内容、备注、书名、感想）
- **integer**：整数计数（如次数、金额以元为单位、步数、页数）
- **float**：浮点数值（如心率、体重、温度、里程、时长以小时为单位）

#### 字段单位约定
AI 创建类型时，将单位以括号形式写入 `field_name`，不新增独立 `unit` 字段。示例：
- `field_name="心率(bpm)"`、`field_name="体重(kg)"`、`field_name="里程(km)"`、`field_name="金额(元)"`、`field_name="完成度(%)"`

#### 百分比存储约定
百分比数据按"百分点"单位存储为数值，不写小数形式：
- 正确：完成度 85% → `field_name="完成度(%)"`、`field_type="integer"`、值 `85`
- 错误：完成度 85% → 值 `0.85`

此约定仅作为 prompt 指导，后端不强制校验百分比格式。

### API 层

- 路由不变，仍为 `/api/v2/custom-records/*`
- `POST /custom-records/{type_id}/entries` 的请求体 `data` 字段允许数值类型值
- 错误响应：`INVALID_FIELD_VALUE` → 422，遵循现有全局异常处理器映射
- API 层不写 try/except（遵循 lifeprism/CLAUDE.md）

### 前端 — 类型创建

`CreateTypeView` 字段类型下拉框选项从单一的"文本"扩展为三个：
- 文本（value: text）
- 整数（value: integer）
- 浮点数（value: float）

### 前端 — 数值格式化

新增数值格式化工具函数，应用于 EntryTable（数值列）、EntryCard（chip）：
- **integer 字段**：显示原值，不格式化（如 `5` 显示为 `5`）
- **float 字段**：固定 1 位小数（如 `65.5` 显示为 `65.5`，`65` 显示为 `65.0`）
- **text 字段**：直接显示字符串

### 测试

延续 P1 的"Repository 层单一 seam"原则，在现有 Repository 测试文件中新增数值字段相关测试。

## Acceptance criteria

- [ ] `FieldDefinition.field_type` 改为 `Literal["text", "integer", "float"]`
- [ ] `CreateCustomRecordEntryRequest.data` 类型扩展为 `dict[str, str | int | float]`
- [ ] `create_type` 按 `field_type` 映射 DDL 列类型（text→TEXT、integer→INTEGER、float→REAL）
- [ ] 未知 `field_type` 抛 `ValidationError(code=INVALID_FIELD_TYPE)`
- [ ] `create_entry` 校验 integer 字段值：接受 int 和可解析为 int 的字符串，拒绝浮点字符串（如 "5.5"）和非数值字符串（如 "abc"）
- [ ] `create_entry` 校验 float 字段值：接受 int/float 和可解析为 float 的字符串，拒绝非数值字符串
- [ ] 类型不匹配抛 `ValidationError(code=INVALID_FIELD_VALUE)`，details 含 `valid_fields` + `expected_types`
- [ ] `query_entries` / `get_entry` 返回值保留原始类型（integer 返回 int，float 返回 float）
- [ ] `CreateCustomRecordTypeTool` 的 `field_type` enum 改为 `["text", "integer", "float"]`
- [ ] `CreateCustomRecordEntryTool` 的错误处理兼容 `INVALID_FIELD_VALUE` 错误码
- [ ] `tool.md` 增加字段类型选择指导 + 单位约定 + 百分比约定
- [ ] 前端 `CreateTypeView` 字段类型下拉框提供"文本/整数/浮点数"三个选项
- [ ] 前端数值格式化：integer 显示原值，float 固定 1 位小数
- [ ] P1 已创建的类型（全 text 字段）行为不受影响（回归测试通过）
- [ ] Repository 层测试覆盖：DDL 列类型、录入校验、查询值类型、text 回归
- [ ] 遵循 `lifeprism/CLAUDE.md`（日志用 %s 格式、错误处理规则、API 层不写 try/except）

## Blocked by

None - can start immediately
