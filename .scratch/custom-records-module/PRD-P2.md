# PRD: 自定义记录模块（P2）— 数值字段类型 + 折线图

## Status

ready-for-agent

## Problem Statement

P1 自定义记录模块仅支持 `text` 字段类型 + 文本列表/卡片展示，无法满足"数值型记录 + 趋势可视化"场景。用户希望记录运动里程、体重、心率、消费金额、学习时长等数值数据，并直观看到这些数值随时间的变化趋势。

具体痛点：
1. 字段类型单一：所有字段只能是文本，数值数据只能以字符串形式存储，无法做数值聚合（SUM/AVG）
2. 无可视化：仅有卡片/表格/模板对比三种视图，看不到数值随时间的变化趋势
3. AI 无法生成数值字段：LLM tool 的 `field_type` enum 写死为 `["text"]`，AI 创建类型时无法选择数值类型

## Solution

在 P1 基础上扩展两方面能力：

1. **字段类型扩展**：在 `field_type` 枚举中增加 `integer`、`float` 两种数值类型。DDL 严格按 `field_type` 建列（TEXT/INTEGER/REAL），录入时 Repository 层严格校验值类型，LLM tool 支持 `text`/`integer`/`float` 三种取值并在 prompt 中提供类型选择指导。

2. **折线图视图**：在类型详情页新增"图表"Tab，使用项目已有的 recharts 库，以 `TimeDistributionChart.tsx` 为样式参考。支持"按数据点"和"按天聚合（求和）"两种切换模式，自动选择所有 integer/float 字段绘制多线图，并提供字段可见性 toggle。

## User Stories

### 字段类型扩展 — 类型创建

1. 作为用户，我想在新建类型表单中选择字段类型为"整数"，以便记录步数、次数等整型数据
2. 作为用户，我想在新建类型表单中选择字段类型为"浮点数"，以便记录体重、心率、温度等浮点数据
3. 作为用户，我想在字段类型下拉框中看到"文本/整数/浮点数"三个清晰选项，以便快速选择
4. 作为用户，当我在前端表单中切换字段类型时，下拉框应实时反映可选类型

### 字段类型扩展 — AI 通道

5. 作为 AI agent，我想在 system prompt 中看到字段类型选择指导（金额/次数/步数用 integer，心率/体重/里程用 float，文本内容用 text），以便生成合理的字段定义
6. 作为 AI agent，当我调用 `create_custom_record_type` 时，`field_type` 参数应支持 `text`/`integer`/`float` 三种取值
7. 作为 AI agent，当我生成的 `field_type` 不在枚举内时，后端应拒绝并提示可用类型

### 字段类型扩展 — 数据录入与校验

8. 作为用户，当我在前端录入 integer 字段时传了非数值（如 "abc"），后端应返回 422 错误并提示期望类型
9. 作为用户，当我在前端录入 float 字段时传了非数值（如 "xyz"），后端应返回 422 错误并提示期望类型
10. 作为 AI agent，当我调用录入工具时 integer 字段传了非数值，应收到结构化错误（含 valid_fields + 期望类型），以便重新解析
11. 作为 AI agent，当我调用录入工具时 float 字段传了字符串形式的数值（如 "65.5"），应能正常落库（兼容字符串数字）
12. 作为系统，当创建含 integer 字段的类型时，DDL 应将该列建为 INTEGER（而非 TEXT）
13. 作为系统，当创建含 float 字段的类型时，DDL 应将该列建为 REAL（而非 TEXT）
14. 作为系统，录入 integer 字段时，值必须是 int 或可解析为 int 的字符串（不含小数点），否则抛 ValidationError
15. 作为系统，录入 float 字段时，值必须是 int/float 或可解析为 float 的字符串，否则抛 ValidationError
16. 作为系统，ValidationError 的 details 应包含 `valid_fields` 列表和 `expected_types` 映射，引导调用方重新录入

### 字段类型扩展 — 数据查询与展示

17. 作为用户，我想在表格视图中看到 integer/float 字段的值正确显示（数值而非字符串）
18. 作为用户，我想在卡片视图中看到数值字段以 chip 形式显示具体数值
19. 作为系统，查询记录时应保留数值字段的原始类型（integer 返回 int，float 返回 float），不强制转字符串

### 折线图 — 入口与显示

20. 作为用户，我想在类型详情页看到"图表"Tab，进入后展示该类型所有数值字段随时间变化的折线图
21. 作为用户，当类型没有任何 integer/float 字段时，"图表"Tab 应隐藏（不显示）
22. 作为用户，当类型有数值字段但无任何记录时，图表区域应显示空状态提示"暂无记录"
23. 作为用户，图表应复用现有的日期范围筛选器（startDate/endDate），筛选后图表数据同步更新

### 折线图 — 视图模式

24. 作为用户，我想在图表 Tab 内通过 Toggle 按钮切换"按数据点"和"按天聚合"两种视图模式
25. 作为用户，在"按数据点"模式下，每条记录对应图表上的一个数据点，X 轴显示"日期 + 时分"（如 07-13 14:30）
26. 作为用户，在"按数据点"模式下，同一天多条记录应显示为多个独立数据点
27. 作为用户，在"按天聚合"模式下，X 轴显示日期（如 07-13），同一天多条记录的值求和
28. 作为用户，X 轴应按时间升序排列（从左到右时间递增，符合趋势图阅读习惯）

### 折线图 — 多字段与交互

29. 作为用户，当类型有多个 integer/float 字段时，图表应同时展示多条线
30. 作为用户，我想通过 toggle 按钮切换各数值字段的可见性，以便聚焦关注特定字段
31. 作为用户，当所有数值字段都被隐藏时，至少应保留一个可见（不允许全隐藏）
32. 作为用户，图表 Tooltip 应显示当前数据点的日期、各字段名与值
33. 作为用户，图表样式应与项目内 `TimeDistributionChart.tsx` 保持一致（白底卡片 + recharts + 自定义 Tooltip + category toggle）

### 系统行为

34. 作为系统，图表数据应从已有的 `GET /custom-records/{type_id}/entries` 接口获取，前端完成聚合，不新增后端聚合 API
35. 作为系统，P1 已创建的类型（全 TEXT 列）保持不变，P2 类型扩展仅作用于新创建的类型
36. 作为系统，不应为 P2 执行任何数据迁移脚本（P1 明确不支持 schema 演进）
37. 作为用户，进入类型详情页时，时间筛选器应默认填充"最近一周"（今天往前 7 天），以便快速看到近期数据
38. 作为用户，当我手动清除时间筛选器后，应加载全部记录（恢复 P1 行为）
39. 作为 AI agent，创建类型时我应将单位以括号形式写入 field_name（如"体重(kg)"），以便前端显示时带单位
40. 作为 AI agent，录入百分比数据时我应按"百分点"存储（85% 存为 85），不写小数形式（0.85）
41. 作为用户，integer 字段值应显示为整数，float 字段值应固定显示 1 位小数

## Implementation Decisions

### Schema 层

- `FieldDefinition.field_type`：从 `str` 改为 `Literal["text", "integer", "float"]`，在 Pydantic 层强制枚举校验
- `CreateCustomRecordEntryRequest.data`：类型从 `dict[str, str]` 改为 `dict[str, str | int | float]`，允许数值类型传入
- `CustomRecordEntryItem`：保持 `model_config = {"extra": "allow"}`，动态字段值类型由 SQLite 列类型决定

### Repository 层（核心逻辑所在）

#### DDL 列类型映射

`create_type` 的 DDL 生成逻辑改为按 `field_type` 映射 SQLite 列类型：

| field_type | SQLite 列类型 |
|------------|---------------|
| text       | TEXT          |
| integer    | INTEGER       |
| float      | REAL          |

映射通过模块级常量字典实现，未知 `field_type` 抛 `ValidationError(code=INVALID_FIELD_TYPE)`。

#### 录入类型校验

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

`query_entries` / `get_entry` 返回的字典中，数值字段的值应保留 SQLite 返回的原始类型（int/float），不强制转字符串。SQLite 在列类型为 INTEGER/REAL 时会自动按数值类型返回 Python 的 int/float。

### LLM Tool 层

- `CreateCustomRecordTypeTool.parameters.fields.items.field_type.enum` 从 `["text"]` 改为 `["text", "integer", "float"]`
- description 中"P1 仅 text"改为"可选 text/integer/float"
- `CreateCustomRecordEntryTool` 的错误处理兼容新的 `INVALID_FIELD_VALUE` 错误码，返回结构化 JSON 引导 AI 重新解析

### Prompt 设计

在 agent system prompt 的"自定义记录模块"段落中增加字段类型选择指导：

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

此约定仅作为 prompt 指导，后端不强制校验百分比格式（无法区分 0.85 和 85 谁是百分比）。

### API 层

- 路由不变，仍为 `/api/v2/custom-records/*`
- `POST /custom-records/{type_id}/entries` 的请求体 `data` 字段允许数值类型值
- 错误响应：`INVALID_FIELD_VALUE` → 422，遵循现有全局异常处理器映射
- API 层不写 try/except（遵循 lifeprism/CLAUDE.md）

### 前端 — 类型创建

- `CreateTypeView` 字段类型下拉框选项从单一的"文本"扩展为三个：
  - 文本（value: text）
  - 整数（value: integer）
  - 浮点数（value: float）
- 下拉框样式保持不变

### 前端 — 类型详情页

`TypeDetailView` 的 Tab 栏从 3 个扩展为条件性 4 个：

- 当类型含至少 1 个 integer/float 字段时，显示 4 个 Tab：卡片 / 表格 / 图表 / 模板对比
- 当类型全为 text 字段时，显示 3 个 Tab：卡片 / 表格 / 模板对比（与 P1 一致）

`activeTab` 的 ViewTab 类型扩展为 `'card' | 'table' | 'chart' | 'compare'`，默认仍为 'card'。

#### 默认时间范围（影响 P1 行为）

进入类型详情页时，若 `startDate/endDate` 均为空，自动填充默认值：
- `endDate` = 今天
- `startDate` = 今天往前 7 天

此默认值作用于整个详情页（所有 Tab 共享），影响 P1 现有行为（P1 默认加载全部记录）。用户可手动清除筛选器恢复"加载全部"。

理由：自定义记录以 AI/人工录入为主，每天 2-3 条，一周内数据量可控（≤30 条），默认展示最近一周符合主要使用场景。

### 前端 — 折线图组件

新增 `EntryChart` 组件，结构如下：

```
EntryChart
├── 卡片外壳（bg-white rounded-2xl shadow-sm border border-gray-100 p-6）
├── Header
│   ├── icon（TrendingUp）+ title + subtitle（时间范围）
│   └── 视图模式 Toggle 按钮组（按数据点 / 按天聚合）
├── 字段可见性 Toggle 按钮组（右上角，每个数值字段一个按钮）
└── LineChart（recharts）
    ├── X 轴
    │   ├── 按数据点模式：MM-DD HH:MM
    │   └── 按天聚合模式：MM-DD
    ├── Y 轴（数值，无单位后缀）
    ├── 多 Line：每个数值字段一条线，颜色来自 field_key 哈希
    └── 自定义 Tooltip（白底卡片，显示字段名 + 值）
```

#### 数据流

1. 复用 `TypeDetailView` 已加载的 `entries` 数据（来自 `GET /custom-records/{type_id}/entries`）
2. 从 `localFields` 中筛选 `field_type` 为 `integer` 或 `float` 的字段作为图表 series
3. 按当前 Toggle 模式聚合：
   - **按数据点**：每条记录一个数据点，X = `event_time` 转本地时间 `MM-DD HH:MM`
   - **按天聚合**：按 `event_time` 的本地日期分组，同日多记录对每个数值字段求和，X = `MM-DD`
4. X 轴升序排列（与 card/table 的 DESC 相反，趋势图需要时间从左到右）

#### 样式参考

以 `TimeDistributionChart.tsx` 为基础：
- recharts `LineChart` + `ResponsiveContainer`
- `CartesianGrid` 虚线网格
- `XAxis` / `YAxis` 隐藏轴线，浅色 tick
- `Line` 使用 `type="monotone"`、`strokeWidth=2`、`dot r=3`
- 自定义 Tooltip 白底卡片
- 字段颜色使用 `getFieldColor(field_key)` 与 EntryCard 保持一致

#### 数值格式化

前端统一数值显示格式：
- **integer 字段**：显示原值，不格式化（如 `5` 显示为 `5`）
- **float 字段**：固定 1 位小数（如 `65.5` 显示为 `65.5`，`65` 显示为 `65.0`）
- **text 字段**：直接显示字符串

格式化通过工具函数实现，应用于：EntryChart（Tooltip + Y 轴）、EntryTable（数值列）、EntryCard（chip）。千分位、自定义小数位等留作 P3。

### 空状态处理

- **类型无数值字段**：图表 Tab 隐藏（TypeDetailView 的 Tab 列表中不包含 'chart'）
- **有数值字段但无记录**：图表区域显示空状态提示"暂无记录"（参考现有表格空状态样式）
- **所有字段被 toggle 隐藏**：至少保留一个可见（与 TimeDistributionChart 一致）

### 架构依赖关系

延续 P1 的架构，不引入新的依赖方向：

```
API 路由 ──→ Service ──→ Repository (CustomRecordRepository)
                              ↑
LLM Tool ──────────────────────┘  (直接访问，不经过 Service)

前端 TypeDetailView ──→ EntryChart（新组件）──→ recharts（已有依赖）
                  ──→ CustomRecordsAPI.getEntries（复用现有接口）
```

## Testing Decisions

### 测试原则

延续 P1 的"Repository 层单一 seam"原则：
- 只测外部行为，不测实现细节
- 单一测试 seam：**Repository 层**（`test/core/unit/repository/test_custom_records_repository.py`）
- 不新增 API 层测试、LLM tool 层测试、Service 层测试、前端测试

### 测试覆盖

| 行为 | 测试方法 |
|------|---------|
| 创建含 integer 字段的类型 | 调 `create_type` 传 `field_type=integer`，断言返回 type_id 且数据表该列为 INTEGER 类型 |
| 创建含 float 字段的类型 | 调 `create_type` 传 `field_type=float`，断言数据表该列为 REAL 类型 |
| 创建含未知 field_type | 调 `create_type` 传 `field_type=unknown`，断言抛 `ValidationError(code=INVALID_FIELD_TYPE)` |
| 录入 integer 字段正确 int 值 | 调 `create_entry` 传 `{"count": 5}`，断言落库成功且值为 5 |
| 录入 integer 字段正确字符串数字 | 调 `create_entry` 传 `{"count": "5"}`，断言落库成功 |
| 录入 integer 字段错误值 | 调 `create_entry` 传 `{"count": "abc"}`，断言抛 `ValidationError(code=INVALID_FIELD_VALUE)` 且 details 含 valid_fields + expected_types |
| 录入 integer 字段浮点字符串 | 调 `create_entry` 传 `{"count": "5.5"}`，断言抛 `ValidationError`（integer 不接受小数） |
| 录入 float 字段正确 float 值 | 调 `create_entry` 传 `{"weight": 65.5}`，断言落库成功 |
| 录入 float 字段正确 int 值 | 调 `create_entry` 传 `{"weight": 65}`，断言落库成功（int 兼容 float） |
| 录入 float 字段错误值 | 调 `create_entry` 传 `{"weight": "abc"}`，断言抛 `ValidationError` |
| 查询 integer 字段返回类型 | 创建+录入后查询，断言返回值为 Python int 类型 |
| 查询 float 字段返回类型 | 创建+录入后查询，断言返回值为 Python float 类型 |
| text 字段保持原行为 | 调 `create_entry` 传字符串，断言落库成功（回归测试） |

### Prior Art

- 字段类型相关测试参考 P1 的 `test_custom_records_repository.py` 中 `field_key` 校验测试模式
- DDL 列类型断言参考现有 `test_base_provider_generic_methods.py` 的表结构验证方式

### 不测的内容

- 前端图表渲染（人工验证，参考 TimeDistributionChart 的现有模式）
- LLM tool 的参数解析与 JSON 序列化（ToolRegistry 已有通用逻辑）
- API 路由的请求转发（FastAPI 已有保证）
- Schema 层的 Literal 校验（Pydantic 已有保证）
- 迁移系统（动态表不走迁移系统，P2 不执行任何迁移）

## Out of Scope

### P2 不做

- **后端聚合 API**：图表数据聚合在前端完成，不新增后端聚合端点（大数据量场景留作 P3）
- **图表类型扩展**：仅折线图，柱形图/饼图留作 P3
- **Schema 演进**：仍不支持 ALTER TABLE 增删改字段（P1 明确不做，P2 延续）
- **聚合策略可选**：按天聚合仅支持 sum，avg/max/min 留作 P3
- **数值字段格式化**：千分位、单位、小数位数控制留作 P3
- **图表交互**：不支持点击数据点跳转、不支持缩放、不支持导出
- **数据迁移**：P1 已创建的类型（全 TEXT 列）保持不变，不执行任何迁移脚本
- **跨类型关联查询**：各类型独立，不做跨表 JOIN
- **草稿状态**：AI 录入仍在对话内确认，不存 draft 中间态
- **AI 删除工具**：AI 无删除权限，删除走前端

### 未来可能（P3）

- 后端聚合 API（支持大数据量、复杂聚合）
- 柱形图、饼图
- 聚合策略可选（sum/avg/max/min）
- 数值字段格式化（千分位、自定义小数位）
- 图表点击数据点跳转到对应记录
- Schema 演进（ALTER TABLE 增删改字段）
- AI skill 动态注入 schema

## Further Notes

### 相关文档

- [PRD.md](PRD.md) — P1 自定义记录模块 PRD（本 PRD 的前置基础）
- [design-spec.md](design-spec.md) — 前端设计规格（三层自适应架构、字段配色、模板预设）
- [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md) — 存储方案决策
- [CONTEXT.md](../../CONTEXT.md) — 自定义记录模块术语表
- [repository-core-spec](../../docs/specs/2026-07-06-repository-core-spec.md) — Repository 数据访问层核心契约
- [llm-agent-spec](../../docs/specs/2026-07-06-llm-agent-spec.md) — Agent 执行引擎规格

### 关键设计决策汇总

| 维度 | 决策 |
|------|------|
| 字段类型 | P2 扩展为 text/integer/float |
| DDL 列类型 | 严格按 field_type 映射（TEXT/INTEGER/REAL） |
| 录入校验 | Repository 层严格校验，类型不匹配抛 INVALID_FIELD_VALUE |
| 数据迁移 | 无（P1 不支持 schema 演进，旧表保持 TEXT） |
| 字段单位 | 写入 field_name（如"体重(kg)"），不新增 unit 字段 |
| 百分比存储 | 按百分点存（85% 存为 85），仅 prompt 指导，后端不校验 |
| 图表库 | recharts（已有依赖） |
| 图表位置 | TypeDetailView 新增"图表"Tab（条件性显示） |
| 图表模式 | 按数据点 + 按天聚合（sum），Tab 内 Toggle 切换 |
| 图表样式 | 以 TimeDistributionChart.tsx 为基础 |
| 图表数据 | 复用 GET /entries 接口，前端聚合，不新增后端 API |
| 默认时间范围 | 进入详情页默认最近一周（今天往前 7 天），所有 Tab 共享，影响 P1 行为 |
| 数值格式化 | integer 显示原值，float 固定 1 位小数 |
| LLM Prompt | 增加字段类型选择指导 + 单位约定 + 百分比约定 |
| 测试 seam | Repository 层单一 seam（延续 P1） |

### 影响 P1 已有功能

- **P1 类型（全 text 字段）**：不受影响，图表 Tab 隐藏；但进入详情页默认时间范围变为最近一周（原为加载全部）
- **P1 已有数据**：不受影响，不执行迁移
- **P1 API 契约**：仅 `data` 字段值类型扩展（str → str|int|float），向后兼容
- **P1 LLM Tool**：`field_type` enum 扩展，向后兼容（text 仍可用）
- **P1 前端筛选器**：默认值从"空（加载全部）"改为"最近一周"，用户可手动清除恢复"加载全部"
