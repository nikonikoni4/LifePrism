# P3 Slice 2: 编辑记录全链路（后端 update_entry + 前端 EntryForm edit 模式 + 编辑按钮）

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD-P3.md`

## What to build

在 Slice 1（前端添加记录 / EntryForm create 模式）已建立 `EntryForm` 组件的基础上，补齐"编辑记录"全链路：后端新增 `update_entry` Repository/Service/API 能力（PATCH 语义），前端扩展 EntryForm 支持 edit 模式，并在表格视图和卡片视图添加"编辑"按钮。完成后用户可在 UI 直接编辑已存在的记录值（含事件时间），无需删除重录。

端到端行为：
1. 用户在表格视图每行看到"编辑"按钮（与"删除"按钮并列，hover 显示）
2. 用户在卡片视图每张卡片悬停时看到"编辑"按钮（与"删除"按钮并列）
3. 点击"编辑"后弹出 Modal 表单，所有字段预填当前值
4. Modal 标题为"编辑记录 · {类型名}"
5. "事件时间"输入预填当前记录的 event_time（本地时间 `yyyy-MM-ddTHH:mm` 格式），可修改
6. 用户可只修改部分字段，未修改的字段保持原值（PATCH 语义）
7. 用户可清空某字段值（提交空字符串），后端将其存为 NULL
8. 提交调用 `CustomRecordsAPI.updateEntry(type.id, entry.id, { data, event_time })`：
   - `data` 通过 `buildPayloadData` 构造（空字符串 → null）
   - `event_time` 通过 `toISOStringUTC(new Date(eventTime))` 转换；空字符串传 null 表示不更新
9. 成功后 Modal 关闭、列表刷新、记录字段值/事件时间即时更新
10. 提交失败时保留已填值并显示后端错误消息（如"字段值类型不匹配: weight"）
11. 当用户尝试编辑已被并发删除的记录时，后端返回 404，UI 提示"记录不存在"
12. 编辑成功后 `updated_at` 自动刷新（间接通过列表刷新体现），`id` 和 `created_at` 不变

### 后端 — Repository 层（核心逻辑所在）

新增方法 `update_entry(type_id, entry_id, data, event_time=None) -> bool`（即 `lifeprism/repository/aggregators/custom_record_aggregator.py` 中 `CustomRecordRepository` 类的新方法）：

- 复用 `_get_type_and_table`：获取类型元信息 + 数据表名，类型不存在抛 `EntityNotFoundError(entity_type="CustomRecordType")`
- 复用 `_get_fields_by_type_id`：获取字段定义，构造 valid_keys + field_type_map
- 复用 `field_key` 校验：data 中出现的 key 必须在 valid_keys，否则抛 `ValidationError(code=INVALID_FIELD_KEY)` + `valid_fields` 详情
- 复用 `_coerce_field_value`：**仅对非 None 值**按 field_type 校验/转换；**None 值跳过校验**（表达清空语义，直接作为 SQL 参数写入 NULL），失败抛 `ValidationError(code=INVALID_FIELD_VALUE)` + `invalid_fields` + `valid_fields` 详情
- **不做"空字符串转 NULL"处理**：与项目标准三态语义一致（参考 `value_service.update_value` / `commitment_service.update_commitment`，均无此逻辑）。空字符串就是字符串值 `"x"`，前端用 `null` 表达清空
- PATCH 语义：仅 data 中出现的 key 进入 SET 子句，未出现的字段不参与 UPDATE（前端 diff 已保证）
- entry 存在性校验：UPDATE 前先 `SELECT 1 FROM {data_table} WHERE id = ?`，不存在抛 `EntityNotFoundError(entity_type="CustomRecordEntry", entity_id=entry_id)`
- event_time 处理：`event_time` 为 None 时不更新该列；为字符串时进入 SET 子句（由调用方负责转 UTC ISO 8601）
- updated_at：每次更新自动写入当前 UTC ISO 8601 到 `updated_at` 列
- SQL 构造（动态 SET 子句）：

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

- 事务：`with self.db.get_connection() as conn:` 内执行 SELECT + UPDATE，连接上下文管理器自动 commit/rollback
- 返回值：`bool`（True 表示更新成功；不存在 entry_id 时抛 EntityNotFoundError 而非返回 False，与 `delete_entry` 一致）
- 日志：成功路径 INFO 含 type_id + entry_id；失败路径 ERROR 含完整上下文

### 后端 — Service 层

新增函数 `update_entry(type_id, entry_id, request) -> CustomRecordEntryItem`，遵循项目标准三态模式（参考 `value_service.update_value` / `commitment_service.update_commitment`）：

```python
def update_entry(type_id: str, entry_id: str, request: UpdateCustomRecordEntryRequest) -> CustomRecordEntryItem:
    # 标准 model_dump(exclude_unset=True) 模式
    update_data = request.model_dump(exclude_unset=True)

    # data 字段三态：未传 → 不修改；传 null → 报错；传 dict → 按 dict 内 key 三态处理
    data_dict = update_data.get("data")
    if data_dict is None:
        if "data" in update_data:
            raise ValueError("data 不支持传 null 整体清空，请传 {} 或省略")
        data_dict = {}

    # event_time 字段三态：未传 → 不修改；传 null → 报错；传 str → 更新
    event_time = None
    if "event_time" in update_data:
        if update_data["event_time"] is None:
            raise ValueError("event_time 不允许清空")
        event_time = update_data["event_time"]

    custom_record_repository.update_entry(type_id, entry_id, data_dict, event_time=event_time)

    item = custom_record_repository.get_entry(type_id, entry_id)
    logger.info("更新自定义记录成功: type_id=%s, entry_id=%s", type_id, entry_id)
    return _convert_to_entry_item(item) if item else None
```

### 后端 — Schema 层

`lifeprism/server/schemas/custom_records_schemas.py` 新增：

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

不复用 `CreateCustomRecordEntryRequest`，因为后者不允许 None 值且无 `event_time` 字段。字段类型用 `dict[...] | None` 顶层允许 None 但 Service 层显式拒绝，与 commitment_service 对 status 的处理模式一致。

### 后端 — API 层

`lifeprism/server/api/custom_records_api.py` 新增端点（位于现有 `DELETE /{type_id}/entries/{entry_id}` 之前，避免路径冲突）：

```
PATCH /custom-records/{type_id}/entries/{entry_id}
```

- 请求体：`UpdateCustomRecordEntryRequest`
- 响应：`CustomRecordEntryItem`（更新后的完整记录）
- 错误响应：`EntityNotFoundError` → 404，`ValidationError` → 422（沿用全局异常处理器映射）
- API 层不写 try/except（遵循 lifeprism/CLAUDE.md 错误处理规则）

### 前端 — API 客户端 + 类型

`frontend/apps/custom-records/api.ts` 新增：

```typescript
async updateEntry(typeId: string, entryId: string, req: UpdateCustomRecordEntryRequest): Promise<CustomRecordEntryItem>
```

调用 `PATCH /{typeId}/entries/{entryId}`，错误处理沿用现有 `parseError` 模式。

`frontend/apps/custom-records/types.ts` 新增：

```typescript
export interface UpdateCustomRecordEntryRequest {
  data: Record<string, string | number | null>;
  event_time?: string; // UTC ISO 8601
}
```

### 前端 — EntryForm 扩展 edit 模式

复用 Slice 1 已建立的 `EntryForm` 组件，扩展 `mode === 'edit'` 分支：

- 初始值：`formData[field_key] = entry[field_key] != null ? String(entry[field_key]) : ''`
- `eventTime` 初始：由 `entry.event_time` 转 `yyyy-MM-ddTHH:mm` 本地格式（使用 `parseISOString` + `toLocalDateTimeString`，截取到分钟）
- 提交逻辑（diff 模式，遵循项目标准三态语义）：

```typescript
const payload = buildUpdatePayload(formData, fields, entry, eventTime);
// payload 只包含变化的字段：
//   - 未变化字段 → 不放入 data dict（不修改）
//   - 用户清空字段 → null（清空，写入 NULL）
//   - 用户改值 → 新值（更新）
//   - event_time 未变化 → 不放入 payload（不修改）
//   - event_time 变化 → UTC ISO 8601 字符串（更新）
await CustomRecordsAPI.updateEntry(type.id, entry!.id, payload);
```

### buildUpdatePayload 工具函数

放 `frontend/apps/custom-records/utils/entryFormPayload.ts`（与 Slice 1 的 `buildCreatePayload` 同文件）：

```typescript
export function buildUpdatePayload(
  formData: Record<string, string>,
  fields: FieldDefinition[],
  originalEntry: CustomRecordEntryItem,
  eventTime: string  // 本地时间 yyyy-MM-ddTHH:mm
): UpdateCustomRecordEntryRequest {
  const data: Record<string, string | number | null> = {};

  for (const f of fields) {
    const newVal = formData[f.field_key] ?? '';
    const oldVal = originalEntry[f.field_key];
    const oldStr = oldVal != null ? String(oldVal) : '';

    // 都是空 → 不修改
    if (newVal === '' && oldStr === '') continue;
    // 没变化 → 不修改
    if (newVal === oldStr) continue;

    // 有变化
    if (newVal === '') {
      data[f.field_key] = null; // 用户清空字段 → null（清空语义）
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
    ? toLocalDateTimeString(originalEntry.event_time)
    : '';
  if (eventTime !== oldEventTimeLocal) {
    if (eventTime === '') {
      // edit 模式 event_time 必填，前端不让清空（按钮置灰）
      // 保底：传 null 触发后端报错"event_time 不允许清空"
      result.event_time = null as unknown as string;
    } else {
      result.event_time = toISOStringUTC(new Date(eventTime));
    }
  }
  // 若 eventTime === oldEventTimeLocal，不放入 result → 不修改 event_time

  return result;
}
```

> **重要**：`buildUpdatePayload` 必须实现完整 diff 逻辑，不能简化为"所有字段都放入 data dict"。原因：项目标准三态语义要求"未传=不修改"，前端把所有字段都放入（包括未变化的）会变成"全部覆盖"语义，违反标准。

### 前端 — 编辑入口按钮

**表格视图**（`TypeDetailView` 内 table 渲染）：
- 现有"操作列"只有删除按钮，扩展为"编辑 + 删除"两按钮并列
- 编辑按钮图标 `Pencil`（lucide-react），样式与删除按钮一致（小图标 + hover 显示）

**卡片视图**（`EntryCard`）：
- 现有 `onDelete` prop，新增 `onEdit?: (entryId: string) => void` prop
- 卡片头部右侧"删除"按钮旁新增"编辑"按钮（同一容器，相同 hover 行为）
- 不传 `onEdit` 时退化为现有行为（向后兼容）

### 前端 — TypeDetailView 串联

**重要**：Slice 2 必须修改 Slice 1 已实现的 `handleAddEntry` 和 `handleEntryFormSuccess`，加入 `setEditingEntry(null)` 清理。否则会出现：编辑成功后 `editingEntry` 仍指向旧 entry，下次点击"添加记录"时 `mode` 判断 `editingEntry ? 'edit' : 'create'` 会错误走 edit 模式。

```typescript
const [editingEntry, setEditingEntry] = useState<CustomRecordEntryItem | null>(null);
// 复用 Slice 1 的 showEntryForm state

// Slice 2 必须修改 Slice 1 的 handleAddEntry（加入 setEditingEntry(null)）
const handleAddEntry = () => {
  setEditingEntry(null);  // ← Slice 2 新增：清理 editingEntry，确保走 create 模式
  setShowEntryForm(true);
};

const handleEditEntry = (entry: CustomRecordEntryItem) => {
  setEditingEntry(entry);
  setShowEntryForm(true);
};

// Slice 2 必须修改 Slice 1 的 handleEntryFormSuccess（加入 setEditingEntry(null)）
const handleEntryFormSuccess = () => {
  setShowEntryForm(false);
  setEditingEntry(null);  // ← Slice 2 新增：成功后清理 editingEntry，下次添加走 create 模式
  loadData();
};

// EntryForm 渲染：
{showEntryForm && (
  <EntryForm
    mode={editingEntry ? 'edit' : 'create'}
    type={type}
    entry={editingEntry || undefined}
    onClose={() => { setShowEntryForm(false); setEditingEntry(null); }}
    onSuccess={handleEntryFormSuccess}
  />
)}
```

### 测试覆盖（Repository 层单一 seam）

延续 P1/P2 的测试 seam 原则，在 `test/core/unit/repository/test_custom_records_repository.py` 追加用例：

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

## Acceptance criteria

### 后端
- [ ] Repository: `update_entry` 方法实现并通过全部测试用例（**PATCH 三态语义**：未传=不修改，传 null=清空，传值=更新；None 值跳过 `_coerce_field_value` 校验直接写 NULL；类型校验 + valid_fields 详情 + event_time 可选更新；**不做"空字符串转 NULL"非标准逻辑**）
- [ ] Service: `update_entry` 函数使用 `model_dump(exclude_unset=True)` 处理顶层字段；对 `data` 整体传 null 抛 ValueError；对 `event_time` 传 null 抛 ValueError（不允许清空）；调用 Repository 并返回最新数据
- [ ] Schema: `UpdateCustomRecordEntryRequest` 定义（`data: dict[...] | None = None`，`event_time: str | None = None`，注释明确 dict 内 key 三态语义）
- [ ] API: `PATCH /custom-records/{type_id}/entries/{entry_id}` 端点
- [ ] 后端测试全部通过（见测试覆盖表）

### 前端
- [ ] `frontend/apps/custom-records/api.ts` 新增 `updateEntry` 方法
- [ ] `frontend/apps/custom-records/types.ts` 新增 `UpdateCustomRecordEntryRequest` 类型
- [ ] `EntryForm` 组件扩展 `mode === 'edit'` 分支（预填当前值、eventTime 预填 event_time 本地时间格式）
- [ ] 表格视图每行新增"编辑"按钮（Pencil 图标 + hover 显示，与删除按钮并列）
- [ ] `EntryCard` 新增 `onEdit` 可选 prop + 编辑按钮（向后兼容，不传时退化为现有行为）
- [ ] `TypeDetailView` 串联 EntryForm：`handleEditEntry` 设置 `editingEntry` 后打开 Modal
- [ ] 提交编辑后 Modal 关闭、列表刷新、记录字段值/事件时间即时更新
- [ ] 编辑提交失败时保留已填值并显示后端错误消息
- [ ] 编辑已被并发删除的记录时 UI 提示"记录不存在"

### 人工 UI 验证
- [ ] 在表格视图点击编辑按钮，修改 text 字段值后提交，列表中该字段更新
- [ ] 在卡片视图点击编辑按钮，修改 integer/float 字段值后提交，列表中该字段更新
- [ ] 清空某字段后提交，列表中该字段显示为空（—）
- [ ] 修改 event_time 后提交，列表中事件时间更新
- [ ] 提交时 integer 字段输入非数字，UI 显示后端错误消息

## Blocked by

- `.scratch/custom-records-module/issues/15-frontend-add-entry.md` — 复用 Slice 1 已建立的 `EntryForm` 组件、`buildPayloadData` 工具函数、`TypeDetailView` 的 `showEntryForm` state 串联
