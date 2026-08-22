# PRD: 自定义记录模块（P3）— 前端记录 CRUD（新增/编辑记录）

## Status

ready-for-agent

## Problem Statement

P1 + P2 让自定义记录模块具备了"AI 对话录入 + 前端查看/删除"的能力，但前端缺失两个核心 CRUD 操作：

1. **添加记录**：用户在前端无法直接录入一条新记录。当前只能通过 AI 对话录入，对话流程慢、需要确认，对"快速记一条"场景不友好（如刚跑完步想立刻记里程）。
2. **修改内容**：用户在前端无法编辑已存在的记录值（例如打错字、记错数字、想补充内容）。当前只能删除重录，对已有 event_time 和 id 造成无谓浪费。

> "添加表"和"删除表/删除记录"在 P1 已实现（见 `TypeListView` / `TypeDetailView`），P3 不重复。

P3 在不引入字段定义（schema）演进的前提下，让前端补齐"C"+"U"两环，使自定义记录模块在前端能完整 CRUD（仅字段定义不可改）。

## Solution

**前端**：在 `TypeDetailView` 新增"添加记录"按钮（位于 Tab 栏右侧），点击弹出 Modal 表单。表格视图与卡片视图的每条记录新增"编辑"按钮，点击弹出同一 Modal（预填当前值）。

**后端**：Repository 新增 `update_entry` 方法（PATCH 语义：仅更新 `data` 中出现的字段，缺失字段保持原值），Service 与 API 薄包装，新增 `PATCH /custom-records/{type_id}/entries/{entry_id}` 端点。

**字段定义不可改**：本 PRD 明确不做字段定义（schema）的增/删/改。前端表单的输入控件由当前类型的 `fields` 动态渲染，不存在"修改字段"入口。

## User Stories

### 添加记录 — 入口与表单

1. 作为用户，我想在类型详情页看到"添加记录"按钮，以便直接从 UI 录入新数据
2. 作为用户，点击"添加记录"后应弹出表单 Modal，按当前类型字段定义动态生成输入控件
3. 作为用户，表单应按字段类型生成对应输入控件：text 用单行输入框（短文本）或多行 textarea（长文本），integer 用整数输入框，float 用浮点输入框
4. 作为用户，表单应允许我留空某些字段（不填值，落库为 NULL）
5. 作为用户，表单应提供"事件时间"输入（datetime-local 控件），留空时默认使用当前时间
6. 作为用户，提交表单后 Modal 关闭，新记录出现在列表顶部（按 event_time 倒序）并刷新总数
7. 作为用户，提交失败时表单保留我已填的值，并在顶部显示后端返回的错误消息
8. 作为用户，我可以点击 Modal 外部或"取消"按钮关闭表单不保存

### 添加记录 — 字段类型适配

9. 作为用户，当我录入 text 字段时，可以输入任意字符串
10. 作为用户，当我录入 integer 字段时，输入框应阻止非数字字符；若我输入小数，提交时应被后端拒绝并提示"期望整数"
11. 作为用户，当我录入 float 字段时，可以输入小数（如 65.5）
12. 作为用户，表单中控件应显示字段显示名（含单位，如"体重(kg)"）作为 label
13. 作为用户，表单上方应显示当前类型名称，以便确认我录入到了正确的类型

### 编辑记录 — 入口与表单

14. 作为用户，在表格视图中每行应有"编辑"按钮（与"删除"按钮并列）
15. 作为用户，在卡片视图中每张卡片悬停时应显示"编辑"按钮（与"删除"按钮并列）
16. 作为用户，点击"编辑"后应弹出 Modal 表单，所有字段预填当前值
17. 作为用户，编辑表单中的"事件时间"应预填当前记录的 event_time（本地时间格式），可修改
18. 作为用户，提交编辑后 Modal 关闭，列表中该记录的字段值/事件时间应即时更新
19. 作为用户，编辑时我可以只修改部分字段，未修改的字段保持原值（PATCH 语义）
20. 作为用户，编辑时我可以清空某字段值（提交空字符串），后端应将其存为 NULL

### 编辑记录 — 边界与一致性

21. 作为用户，当我想修改一条已被删除的记录时（多窗口/多设备并发），后端应返回 404 并在 UI 提示"记录不存在"
22. 作为用户，编辑表单提交成功后应能看到 updated_at 已变化（间接通过列表刷新体现）
23. 作为用户，编辑提交时若某 integer 字段被我改成了非数字，后端应返回 422 并提示具体字段

### AI 通道

24. 作为 AI agent，我的现有工具（`create_custom_record_entry` 等）不受 P3 影响
25. 作为 AI agent，P3 不为我新增"更新记录"工具（编辑走前端，与 P1 删除决策一致：AI 仅负责写入与查询，不负责编辑与删除）

### 系统行为

26. 作为系统，`update_entry` 应遵循 PATCH 语义：`data` 中出现的字段才更新，未出现的字段保持原值
27. 作为系统，`update_entry` 应复用 `create_entry` 的字段校验逻辑（field_key 校验 + 类型校验 + valid_fields 构造）
28. 作为系统，`update_entry` 应自动更新 `updated_at`，不修改 `id` / `created_at`
29. 作为系统，`update_entry` 应支持可选更新 `event_time`（独立于 data 字段）
30. 作为系统，前端表单提交 `null` 值时 Repository 应写入 NULL（与"清空字段"语义一致，遵循项目标准三态语义：未传=不修改，传 null=清空，传值=更新）

## Implementation Decisions

### 三态语义对齐项目标准

P3 的 PATCH 严格遵循 [backend-api-rules.md](../../docs/coding-rules/backend-api-rules.md) 的三态语义（参考 `value_service.update_value` / `commitment_service.update_commitment` 实现）：

| 前端传值 | 含义 | 后端行为 |
|---------|------|---------|
| 字段/key 不在请求 JSON 中 | 不修改 | 跳过该字段 |
| `"field": null` | 清空 | 写入 NULL |
| `"field": value` | 更新为新值 | 写入新值 |

由于 custom_record 的字段是动态的（按 type 不同而不同），无法预先定义 Schema 字段名，因此采用 `data: dict[str, ...]` 包装动态字段。dict 内 key 的三态语义遵循同样规则：

| dict 内 key 状态 | 含义 | 后端行为 |
|-----------------|------|---------|
| key 不在 data dict 中 | 不修改 | 跳过该字段 |
| `"key": null` | 清空该字段 | 写入 NULL |
| `"key": value` | 更新为新值 | 写入新值 |

> **设计偏离说明**：backend-api-rules 要求 Service 层用 `model_dump(exclude_unset=True)` 实现三态语义。该模式对**顶层固定字段**（如 `event_time`）有效，但对 `data` 这种 dict 字段内部 key 无法直接区分"未传"和"传了 null"——因为 Pydantic 只能区分"data 字段是否传了"，无法区分"data 中某个 key 是否传了"。
>
> **本 PRD 的折中方案**：Service 层仍使用 `model_dump(exclude_unset=True)` 处理顶层字段（`data` / `event_time`），dict 内 key 的三态语义由前端 `buildUpdatePayload` 通过 diff 实现（仅把变化的字段放入 data dict，未变化的字段不放入），后端 Repository 层遍历 data.items() 时只看到"要更新"的 key，None 值表达"清空"。
>
> 这是与项目标准的精神一致（前端显式表达"未传/传 null/传值"三态），实现路径不同（前端 diff 而非 model_dump）。审查者不应误以为遗漏三态语义。

### Repository 层（核心逻辑所在）

新增方法 `update_entry(type_id, entry_id, data, event_time=None) -> bool`，与 `create_entry` 共用校验逻辑：

- **复用 `_get_type_and_table`**：获取类型元信息 + 数据表名，类型不存在抛 `EntityNotFoundError`
- **复用 `_get_fields_by_type_id`**：获取字段定义，构造 valid_keys + field_type_map
- **复用 `field_key` 校验**：data 中出现的 key 必须在 valid_keys，否则抛 `ValidationError(code=INVALID_FIELD_KEY)` + `valid_fields` 详情
- **复用 `_coerce_field_value`**：仅对**非 None** 的值按 field_type 校验/转换；**None 值跳过校验**（表达清空语义，直接作为 SQL 参数写入 NULL），失败抛 `ValidationError(code=INVALID_FIELD_VALUE)` + `invalid_fields` + `valid_fields` 详情
- **不做"空字符串转 NULL"处理**：与项目标准三态语义一致（`value_service` / `commitment_service` 均无此逻辑）。空字符串就是字符串值 `"x"`，不应被解释为清空；前端用 `null` 表达清空
- **PATCH 语义**：仅 data 中出现的 key 进入 SET 子句，未出现的字段不参与 UPDATE（前端 diff 已保证）
- **entry 存在性校验**：UPDATE 前先 `SELECT 1 FROM {data_table} WHERE id = ?`，不存在抛 `EntityNotFoundError(entity_type="CustomRecordEntry", entity_id=entry_id)`
- **event_time 处理**：`event_time` 参数为 None 时不更新该列；为字符串时进入 SET 子句（由调用方负责转 UTC ISO 8601，与 `create_entry` 一致）
- **updated_at**：每次更新自动写入当前 UTC ISO 8601 时间到 `updated_at` 列
- **SQL 构造**：
  ```python
  set_clauses = []
  params = []
  if event_time is not None:
      set_clauses.append("event_time = ?")
      params.append(event_time_val)
  for key, value in data.items():
      set_clauses.append(f"{key} = ?")
      params.append(value)  # None 直接作为 SQL 参数，自动写为 NULL
  set_clauses.append("updated_at = ?")
  params.append(now)
  params.append(entry_id)
  sql = f"UPDATE {data_table} SET {', '.join(set_clauses)} WHERE id = ?"
  ```
- **事务**：`with self.db.get_connection() as conn:` 内执行 SELECT + UPDATE，连接上下文管理器自动 commit/rollback
- **返回值**：`bool`（True 表示更新成功；不存在 entry_id 时抛 EntityNotFoundError 而非返回 False，与 `delete_entry` 一致）
- **日志**：成功路径 INFO 日志，含 type_id + entry_id；失败路径 ERROR 日志，含完整上下文

> **Repository 类定位**：即 `lifeprism/repository/aggregators/custom_record_aggregator.py` 中的 `CustomRecordRepository` 类（沿用 P1/P2 命名约定）。

### Service 层

新增函数 `update_entry(type_id, entry_id, request) -> CustomRecordEntryItem`，遵循项目标准三态模式：

```python
def update_entry(type_id: str, entry_id: str, request: UpdateCustomRecordEntryRequest) -> CustomRecordEntryItem:
    # 标准 model_dump(exclude_unset=True) 模式（参考 value_service.update_value）
    update_data = request.model_dump(exclude_unset=True)

    # data 字段三态：
    #   未传 data → 不修改任何字段值（用空 dict 表达）
    #   传 data=null → 报错（不支持整体清空，避免误操作）
    #   传 data={} → 仅刷 updated_at
    #   传 data={key: null/val} → 按 dict 内 key 三态处理
    data_dict = update_data.get("data")
    if data_dict is None:
        if "data" in update_data:
            # 显式传 null，不支持
            raise ValueError("data 不支持传 null 整体清空，请传 {} 或省略")
        # 未传 data 字段，视为空 dict
        data_dict = {}

    # event_time 字段三态：
    #   未传 event_time → 不修改 event_time
    #   传 event_time=null → 报错（event_time 不允许清空，必填字段）
    #   传 event_time="value" → 更新 event_time
    event_time = None
    if "event_time" in update_data:
        if update_data["event_time"] is None:
            raise ValueError("event_time 不允许清空")
        event_time = update_data["event_time"]

    custom_record_repository.update_entry(type_id, entry_id, data_dict, event_time=event_time)

    # 返回更新后的完整记录（与 create_entry 模式一致）
    item = custom_record_repository.get_entry(type_id, entry_id)
    logger.info("更新自定义记录成功: type_id=%s, entry_id=%s", type_id, entry_id)
    return _convert_to_entry_item(item) if item else None
```

- 使用 `model_dump(exclude_unset=True)` 区分顶层字段"未传/传 null/传值"三态（项目标准）
- 对不可清空字段（`data` 整体、`event_time`）做显式 null 校验抛 `ValueError`（参考 `commitment_service` 对 `status` 的处理模式）
- 对 dict 内 key 的三态语义：由前端 diff 保证（dict 中只放要更新的 key，None 表达清空）

### Schema 层

新增 `UpdateCustomRecordEntryRequest`：

```python
class UpdateCustomRecordEntryRequest(BaseModel):
    """更新自定义记录（PATCH 三态语义）

    顶层字段三态语义（model_dump(exclude_unset=True) 区分）：
      - data 未传 → 不修改任何字段值
      - data 传 null → 报错（不支持整体清空）
      - data 传 dict → 按 dict 内 key 三态处理
      - event_time 未传 → 不修改 event_time
      - event_time 传 null → 报错（不允许清空）
      - event_time 传 str → 更新

    dict 内 key 三态语义（前端 diff 实现）：
      - key 不在 data 中 → 不修改该字段
      - key 在 data 中，值为 null → 清空该字段（写入 NULL）
      - key 在 data 中，值为具体值 → 更新该字段为新值
    """
    data: dict[str, str | int | float | None] | None = Field(
        default=None,
        description="待更新字段值字典。未传=不修改任何字段；传 null=报错；传 dict=按 dict 内 key 三态处理"
    )
    event_time: str | None = Field(
        default=None,
        description="事件时间 UTC ISO 8601。未传=不修改；传 null=报错（不允许清空）；传 str=更新"
    )
```

- 不复用 `CreateCustomRecordEntryRequest`，因为后者不允许 None 值且无 `event_time` 字段
- 字段类型用 `dict[...] | None` 顶层允许 None 但 Service 层显式拒绝，与 commitment_service 对 status 的处理模式一致（不可清空字段传 null 时抛错）

### API 层

新增端点（位于 `custom_records_api.py` 现有 `DELETE /{type_id}/entries/{entry_id}` 之前，避免路径冲突）：

```
PATCH /custom-records/{type_id}/entries/{entry_id}
```

- 请求体：`UpdateCustomRecordEntryRequest`
- 响应：`CustomRecordEntryItem`（更新后的完整记录）
- 错误响应：`EntityNotFoundError` → 404，`ValidationError` → 422（沿用全局异常处理器映射）
- API 层不写 try/except（遵循 lifeprism/CLAUDE.md 错误处理规则）

### 前端 — API 客户端

`frontend/apps/custom-records/api.ts` 新增：

```typescript
async updateEntry(typeId: string, entryId: string, req: UpdateCustomRecordEntryRequest): Promise<CustomRecordEntryItem>
```

调用 `PATCH /{typeId}/entries/{entryId}`，错误处理沿用现有 `parseError` 模式。

`frontend/apps/custom-records/types.ts` 新增 `UpdateCustomRecordEntryRequest` 类型：

```typescript
export interface UpdateCustomRecordEntryRequest {
  data: Record<string, string | number | null>;
  event_time?: string; // UTC ISO 8601
}
```

### 前端 — 入口按钮

`TypeDetailView` 在 Tab 栏 + 筛选栏所在的工具条区域新增"添加记录"按钮：

- 位置：日期筛选器右侧（或 Tab 栏最右端，按视觉层级决定）
- 样式：与 `TypeListView` 的"新建类型"按钮风格一致（cyan-teal 渐变 + Plus 图标），但更小尺寸（适配详情页工具条）
- 显示条件：所有 Tab（card/table/chart/compare）都显示该按钮（添加记录不依赖具体视图）
- 图表 Tab 下点击"添加记录"也允许（用户可能想先加数据再看图表）

### 前端 — EntryForm 组件

新增 `frontend/apps/custom-records/components/EntryForm.tsx`：

**Modal 结构**（参考 `TypeListView` 删除确认 Modal 的视觉风格）：

```
EntryForm (Modal)
├── 遮罩层 bg-slate-900/40 backdrop-blur-sm
└── Modal 卡片 bg-white rounded-2xl shadow-2xl
    ├── Header
    │   ├── 标题（"添加记录" / "编辑记录" + 类型名）
    │   └── 关闭按钮 X（右上角）
    ├── 错误提示区（条件渲染，红色背景）
    ├── 表单主体
    │   ├── 事件时间输入（datetime-local，label="事件时间"，留空=当前时间）
    │   └── 动态字段列表（按 fields 数组顺序渲染）
    │       每行：label(field_name) + 输入控件
    │       - text + 长度 <=50: <input type="text">
    │       - text + 长度 >50: <textarea rows={3}>  ← 按字段名启发（如含 note/content/review 等）
    │       - integer: <input type="number" step="1">
    │       - float: <input type="number" step="any">
    └── Footer
        ├── 取消按钮
        └── 提交按钮（添加/编辑，渐变 cyan-teal）
```

**Props**：

```typescript
interface EntryFormProps {
  mode: 'create' | 'edit';
  type: CustomRecordTypeItem;       // 当前类型（含字段定义）
  entry?: CustomRecordEntryItem;   // edit 模式必填，create 模式不传
  onClose: () => void;
  onSuccess: () => void;            // 成功回调（用于触发父组件刷新）
}
```

**表单状态**：

- `formData: Record<field_key, string>` —— 所有字段值以字符串形式管理，提交时按字段类型转换
- `eventTime: string` —— 本地时间 `yyyy-MM-ddTHH:mm` 格式；create 模式初始为空，edit 模式初始预填 entry.event_time 的本地时间
- `submitting: boolean`、`error: string`

**初始值**：

- create 模式：`formData` 全部为空字符串，`eventTime` 为空
- edit 模式：`formData[field_key] = entry[field_key] != null ? String(entry[field_key]) : ''`，`eventTime` 由 `entry.event_time` 转 `yyyy-MM-ddTHH:mm` 本地格式

**提交逻辑**：

- create 模式：
  ```typescript
  const data = buildCreatePayload(formData, fields); // 留空字段不放入 data
  await CustomRecordsAPI.createEntry(type.id, { data });
  ```
  > **明确不做**：P3 不扩展 `CreateCustomRecordEntryRequest` 加 `event_time` 字段。create 通道沿用 P1 行为：后端使用当前 UTC 时间作为 event_time。前端 EntryForm 在 create 模式下即使渲染了"事件时间"控件（为统一 UI 体验），提交时也**忽略该字段**（不传给后端）。
  >
  > 理由：P1 已规定 AI 录入走当前时间，前端 create 也保持一致；用户事后可通过编辑记录修改 event_time。这避免修改 P1 schema 引入回归风险。

- edit 模式（diff 模式，仅传变化字段）：
  ```typescript
  const payload = buildUpdatePayload(formData, fields, entry, eventTime);
  // payload 只包含变化的字段，未变化字段不放入 data dict
  // 清空字段 → null；改值 → 新值
  await CustomRecordsAPI.updateEntry(type.id, entry.id, payload);
  ```

**buildCreatePayload 函数**（前端工具，放 `utils/entryFormPayload.ts`）：

> create 模式不需要 diff，所有可见字段都放入 data dict；留空字段不放入（避免后端把 NULL 当作"清空"处理，因为 create 时不存在"清空"概念）。

```typescript
function buildCreatePayload(
  formData: Record<string, string>,
  fields: FieldDefinition[]
): Record<string, string | number> {
  const data: Record<string, string | number> = {};
  for (const f of fields) {
    const raw = formData[f.field_key];
    if (raw == null || raw === '') {
      continue; // 留空字段不放入（后端默认 NULL）
    }
    if (f.field_type === 'integer') {
      data[f.field_key] = Number.isInteger(Number(raw)) ? Number(raw) : raw;
    } else if (f.field_type === 'float') {
      data[f.field_key] = isNaN(Number(raw)) ? raw : Number(raw);
    } else {
      data[f.field_key] = raw;
    }
  }
  return data;
}
```

**buildUpdatePayload 函数**（前端工具，diff 模式，遵循项目标准三态语义）：

> edit 模式采用 diff：仅把变化的字段放入 data dict（未变化 → 不放入 = 不修改）；用户清空字段 → null（清空）；用户改值 → 新值（更新）。

```typescript
function buildUpdatePayload(
  formData: Record<string, string>,
  fields: FieldDefinition[],
  originalEntry: CustomRecordEntryItem,
  eventTime: string  // 本地时间 yyyy-MM-ddTHH:mm
): UpdateCustomRecordEntryRequest {
  const data: Record<string, string | number | null> = {};
  let hasChanges = false;

  for (const f of fields) {
    const newVal = formData[f.field_key] ?? '';
    const oldVal = originalEntry[f.field_key];
    const oldStr = oldVal != null ? String(oldVal) : '';

    // 都是空 → 不修改
    if (newVal === '' && oldStr === '') continue;
    // 没变化 → 不修改
    if (newVal === oldStr) continue;

    // 有变化
    hasChanges = true;
    if (newVal === '') {
      // 用户清空字段 → null（清空语义）
      data[f.field_key] = null;
    } else if (f.field_type === 'integer') {
      data[f.field_key] = Number.isInteger(Number(newVal)) ? Number(newVal) : newVal;
    } else if (f.field_type === 'float') {
      data[f.field_key] = isNaN(Number(newVal)) ? newVal : Number(newVal);
    } else {
      data[f.field_key] = newVal;
    }
  }

  // event_time diff：与原 event_time 比较后再传
  const result: UpdateCustomRecordEntryRequest = { data };

  const oldEventTimeLocal = originalEntry.event_time
    ? toLocalDateTimeString(originalEntry.event_time)  // 转本地 yyyy-MM-ddTHH:mm
    : '';
  if (eventTime !== oldEventTimeLocal) {
    if (eventTime === '') {
      // 用户清空 event_time → 不允许清空，前端拦截：按钮置灰或弹提示
      // 实际实现：edit 模式 event_time 必填，前端不让清空
      // 此处保底逻辑：传 null 触发后端报错"event_time 不允许清空"
      result.event_time = null as unknown as string;  // 类型 trick，实际后端会拒绝
    } else {
      result.event_time = toISOStringUTC(new Date(eventTime));
    }
  }
  // 若 eventTime === oldEventTimeLocal，不放入 result → 不修改 event_time

  return result;
}
```

> **注意**：`buildUpdatePayload` 必须实现完整的 diff 逻辑，不能简化为"所有字段都放入"。原因：项目标准三态语义要求"未传=不修改"，如果前端把所有字段都放入 data dict（包括未变化的），会变成"全部覆盖"语义，违反标准。

### 前端 — 编辑入口按钮

**表格视图**（`TypeDetailView` 内 table 渲染）：

- 现有"操作列"只有删除按钮，扩展为"编辑 + 删除"两按钮并列
- 编辑按钮图标 `Pencil` / `Edit2`（lucide-react），样式与删除按钮一致（小图标 + hover 显示）

**卡片视图**（`EntryCard`）：

- 现有 `onDelete` prop，新增 `onEdit?: (entryId: string) => void` prop
- 卡片头部右侧"删除"按钮旁新增"编辑"按钮（同一容器，相同 hover 行为）

**TypeDetailView 串联**：

```typescript
const [editingEntry, setEditingEntry] = useState<CustomRecordEntryItem | null>(null);
const [showEntryForm, setShowEntryForm] = useState(false);

const handleAddEntry = () => {
  setEditingEntry(null);
  setShowEntryForm(true);
};

const handleEditEntry = (entry: CustomRecordEntryItem) => {
  setEditingEntry(entry);
  setShowEntryForm(true);
};

const handleEntryFormSuccess = () => {
  setShowEntryForm(false);
  setEditingEntry(null);
  loadData(); // 刷新当前页
};
```

### 架构依赖关系

延续 P1/P2 的架构，不引入新依赖方向：

```
API 路由 ──→ Service ──→ Repository (CustomRecordRepository.update_entry)
                              ↑
LLM Tool ──────────────────────┘  (不新增 LLM tool，编辑走前端)

前端 TypeDetailView
  ├── EntryForm (新组件，Modal) ──→ CustomRecordsAPI.createEntry / updateEntry
  ├── EntryCard (新增 onEdit prop)
  └── 表格视图 (新增编辑按钮)
```

### 不引入的能力

- **不修改字段定义**：本 PRD 不为 Repository 新增 `update_field_definition` / `add_field` / `delete_field` 方法，不为 API 新增字段定义的 PATCH/POST/DELETE 端点
- **不新增 LLM tool**：AI 不获得编辑能力（与 P1 删除决策一致：编辑/删除走前端，AI 仅负责写入与查询）
- **不引入草稿/版本**：编辑直接覆盖原行，不保留历史版本

## Testing Decisions

### 测试原则

延续 P1/P2 的"Repository 层单一 seam"原则：

- 只测外部行为，不测实现细节
- 单一测试 seam：**Repository 层**（`test/core/unit/repository/test_custom_records_repository.py`，在 P1/P2 已有测试文件中追加用例）
- 不新增 API 层测试、Service 层测试、前端测试

### 测试覆盖

| 行为 | 测试方法 |
|------|---------|
| 更新单字段（text） | 创建类型 + 录入记录 + 调 `update_entry` 传 `{field: "新值"}`，断言仅该字段更新，其他字段保持原值 |
| 更新全部字段 | 创建类型 + 录入记录 + 调 `update_entry` 传所有字段新值，断言全部字段更新 |
| 空字典更新（仅刷 updated_at） | 调 `update_entry` 传 `{}`，断言 updated_at 已变化，字段值全部不变 |
| 清空字段（None 值，三态语义） | 录入记录后调 `update_entry` 传 `{field: None}`，断言该字段为 NULL（验证项目标准三态：传 null=清空） |
| 未传字段（三态语义） | 录入记录后调 `update_entry` 传 `{other_field: "x"}` 不传某字段，断言未传字段保持原值（验证项目标准三态：未传=不修改） |
| 更新 integer 字段正确 int 值 | 传 `{"count": 10}`，断言落库成功 |
| 更新 integer 字段错误值 | 传 `{"count": "abc"}`，断言抛 `ValidationError(code=INVALID_FIELD_VALUE)` 且 details 含 valid_fields |
| 更新 float 字段正确值 | 传 `{"weight": 65.5}`，断言落库成功 |
| 更新 float 字段错误值 | 传 `{"weight": "xyz"}`，断言抛 `ValidationError(code=INVALID_FIELD_VALUE)` |
| 更新不存在的 field_key | 传 `{"unknown_field": "x"}`，断言抛 `ValidationError(code=INVALID_FIELD_KEY)` 且 details 含 valid_fields |
| 更新不存在的 type_id | 调 `update_entry` 传不存在的 type_id，断言抛 `EntityNotFoundError(entity_type="CustomRecordType")` |
| 更新不存在的 entry_id | 类型存在但 entry_id 不存在，断言抛 `EntityNotFoundError(entity_type="CustomRecordEntry")` |
| 更新 event_time | 调 `update_entry` 传 `event_time="2026-08-01T00:00:00+00:00"`，断言 event_time 列已更新，data 字段不变 |
| event_time=None 不更新该列 | 调 `update_entry(data={...}, event_time=None)`，断言 event_time 列保持原值 |
| updated_at 自动刷新 | 记录创建时间 + 等待 1 秒 + 调 `update_entry`，断言 updated_at > created_at 且 updated_at > 原始 updated_at |
| id 与 created_at 不可变 | 更新后断言 id 和 created_at 与原值一致 |
| None 值跳过 _coerce_field_value 校验 | 传 `{"note": None}`，断言 Repository 不调用 `_coerce_field_value`（直接作为 SQL 参数写 NULL），不抛 ValidationError |
| text 字段保持原行为（回归） | 创建+录入+更新 text 字段，断言全流程成功（与 P1 行为一致） |

### Prior Art

- update_entry 测试参考 P1 `test_custom_records_repository.py` 中 `create_entry` 校验测试模式
- "不存在 entry_id 抛 EntityNotFoundError"参考 `delete_entry` 已有测试模式
- "valid_fields 详情构造"参考 P1/P2 的 field_key / field_value 校验测试

### 不测的内容

- 前端 Modal 渲染与表单交互（人工验证，参考 P1 前端验收模式）
- 前端 datetime-local 控件行为（浏览器保证）
- LLM tool 的参数解析与 JSON 序列化（无新增 tool）
- API 路由请求转发（FastAPI 已有保证）
- Schema 层的 Literal 校验（Pydantic 已有保证）
- Service 层（Repository 薄包装，无业务逻辑）
- 迁移系统（动态表不走迁移系统）

## Out of Scope

### P3 不做

- **字段定义（schema）演进**：不新增字段、不删除字段、不修改字段的 field_type / field_name / field_key / display_role。用户要调整字段只能新建类型 + 硬删旧类型（沿用 P1 决策）
- **AI 编辑工具**：AI 不获得"更新记录"工具，编辑走前端（与 P1 删除决策一致）
- **批量编辑**：不支持一次编辑多条记录
- **行内编辑（inline edit）**：编辑统一走 Modal 弹窗，不做表格行内直接编辑（简化实现）
- **草稿/版本控制**：编辑直接覆盖，不保留历史版本
- **冲突检测**：不引入乐观锁（version 字段），多窗口并发编辑以最后提交为准
- **历史回溯**：不记录编辑历史，updated_at 仅反映最后修改时间
- **create 通道的 event_time**：明确不做。P3 不扩展 `CreateCustomRecordEntryRequest` 加 `event_time` 字段，create 通道沿用 P1 行为（后端使用当前 UTC 时间）。前端 EntryForm create 模式即使渲染了"事件时间"控件也忽略提交（仅用于 UI 统一）。用户事后可通过编辑记录修改 event_time
- **图表 Tab 的"添加记录"特殊处理**：图表 Tab 也显示"添加记录"按钮，但不自动切换到卡片/表格 Tab（用户添加后手动切换）

### 未来可能（不在本 PRD 范围）

- 字段定义演进（ALTER TABLE 增删改字段 + meta 表同步）—— 见 P1 / P2 Out of Scope
- AI 编辑工具
- 行内编辑（表格双击单元格直接编辑）
- 批量编辑（多选 + 批量修改）
- 编辑历史/版本控制
- 乐观锁（version 字段，防并发覆盖）

## Further Notes

### 相关文档

- [PRD.md](PRD.md) — P1 自定义记录模块 PRD（本 PRD 的前置基础，提供 create/delete/get_entries 等基础能力）
- [PRD-P2.md](PRD-P2.md) — P2 数值字段类型 + 折线图（提供 text/integer/float 类型校验逻辑，本 PRD 复用）
- [design-spec.md](design-spec.md) — 前端设计规格（三层自适应架构、字段配色、模板预设）
- [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md) — 存储方案决策
- [CONTEXT.md](../../CONTEXT.md) — 自定义记录模块术语表
- [repository-core-spec](../../docs/specs/2026-07-06-repository-core-spec.md) — Repository 数据访问层核心契约
- [llm-agent-spec](../../docs/specs/2026-07-06-llm-agent-spec.md) — Agent 执行引擎规格

### 关键设计决策汇总

| 维度 | 决策 |
|------|------|
| 更新语义 | PATCH 三态语义（对齐项目标准 backend-api-rules.md） |
| 三态实现 | 顶层用 `model_dump(exclude_unset=True)`（参考 value_service）；dict 内 key 由前端 diff 保证 |
| 清空表达 | 前端传 `null` → Repository 写入 NULL（与 value_service/commitment_service 一致，不做"空字符串转 NULL"） |
| event_time 更新 | 独立于 data 字段，可选；未传=不修改，传 null=报错，传 str=更新 |
| event_time 字段可空性 | 不允许清空（必填字段，传 null 时 Service 抛 ValueError） |
| data 字段可空性 | 不允许整体清空（传 null 时 Service 抛 ValueError，传 {} 仅刷 updated_at） |
| create 通道 event_time | 明确不做（沿用 P1 行为，后端使用当前 UTC 时间） |
| 字段定义（schema）演进 | 不支持（沿用 P1 决策） |
| AI 编辑工具 | 不提供（沿用 P1 删除决策） |
| 前端编辑入口 | Modal 弹窗（不复用独立 view 切换，避免破坏现有视图架构） |
| 前端添加入口 | Tab 栏 + 筛选栏区域新增"添加记录"按钮 |
| 前端 create 提交 | `buildCreatePayload`：留空字段不放入 data dict |
| 前端 edit 提交 | `buildUpdatePayload`：diff 模式，仅把变化字段放入 data dict（未变化不放入=不修改，清空=null，改值=新值） |
| 表单字段类型适配 | text→input/textarea, integer→number step=1, float→number step=any |
| LLM Tool | 无新增（不新增 update tool） |
| API 端点 | PATCH /custom-records/{type_id}/entries/{entry_id} |
| 测试 seam | Repository 层单一 seam（延续 P1/P2） |

### 影响 P1/P2 已有功能

- **P1 API 契约**：仅新增 PATCH 端点，不动现有 POST/GET/DELETE
- **P1 Repository**：新增 `update_entry` 方法，不动现有方法
- **P1/P2 前端**：`TypeDetailView` 新增按钮和 Modal，`EntryCard` 新增可选 `onEdit` prop（不传时退化为现有行为，向后兼容）
- **P1 测试**：无破坏性变更，原有测试不受影响
- **P2 字段类型校验**：`update_entry` 完整复用 `_coerce_field_value`，integer/float 字段的更新校验与录入校验行为一致

### 验收清单（Implementation 完成后）

- [ ] 后端 Repository: `update_entry` 方法实现并通过全部测试用例
- [ ] 后端 Service: `update_entry` 函数薄包装
- [ ] 后端 Schema: `UpdateCustomRecordEntryRequest` 定义
- [ ] 后端 API: `PATCH /custom-records/{type_id}/entries/{entry_id}` 端点
- [ ] 前端 API 客户端: `CustomRecordsAPI.updateEntry` 方法
- [ ] 前端 types.ts: `UpdateCustomRecordEntryRequest` 类型
- [ ] 前端 EntryForm 组件: Modal + 动态字段 + add/edit 双模式
- [ ] 前端 TypeDetailView: "添加记录"按钮 + EntryForm 集成
- [ ] 前端表格视图: 编辑按钮 + onEdit 回调
- [ ] 前端 EntryCard: `onEdit` prop + 编辑按钮
- [ ] 人工 UI 验证: 添加记录、编辑记录、清空字段、event_time 修改、错误提示
