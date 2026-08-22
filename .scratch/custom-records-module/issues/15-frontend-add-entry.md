# P3 Slice 1: 前端添加记录（EntryForm create 模式 + 添加按钮）

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD-P3.md`

## What to build

在 P1 已有的后端 `createEntry` API 基础上，为前端补齐"添加记录"能力。完成后用户在类型详情页可点击"添加记录"按钮，弹出 Modal 表单按当前类型字段定义动态生成输入控件，填写并提交后新记录出现在列表顶部。

本 slice 不涉及任何后端工作（复用 P1 已有的 `POST /custom-records/{type_id}/entries`），仅在前端建立 `EntryForm` Modal 组件（仅 create 模式）和"添加记录"按钮入口。EntryForm 组件设计需为后续 Slice 2 的 edit 模式预留扩展接口（mode prop 区分 create/edit）。

端到端行为：
1. 用户在 `TypeDetailView` 工具条区域看到"添加记录"按钮（cyan-teal 渐变 + Plus 图标，与 `TypeListView` 的"新建类型"按钮风格一致但更小尺寸）
2. 所有 Tab（card/table/chart/compare）都显示该按钮（添加记录不依赖具体视图）
3. 点击按钮后弹出 Modal 表单，Modal 标题为"添加记录 · {类型名}"
4. Modal 主体包含：
   - 错误提示区（条件渲染，红色背景，显示后端返回的 message）
   - 表单主体：
     - **事件时间输入控件**（`<input type="datetime-local">`，label="事件时间"，位于动态字段列表上方）
       - create 模式初始值为空字符串
       - **create 通道不传 event_time 给后端**（沿用 P1 行为：后端使用当前 UTC 时间）。即使前端渲染了该控件，提交时也忽略（仅用于 UI 统一，为 Slice 2 edit 模式预留）
       - 控件 label 旁注明"(可选，create 不生效)"或在提交时静默忽略
     - 动态字段列表，按当前类型 `fields` 数组顺序渲染
     - 每行：label（field_name，含单位如"体重(kg)"）+ 输入控件
     - text 字段（短） → `<input type="text">`
     - text 字段（长，按字段名启发：含 note/content/review/desc/description/body/detail 等关键词）→ `<textarea rows={3}>`
     - integer 字段 → `<input type="number" step="1">`
     - float 字段 → `<input type="number" step="any">`
   - 字段允许留空（落库为 NULL）
5. 提交按钮调用 `CustomRecordsAPI.createEntry(type.id, { data })`：
   - `data` 通过 `buildCreatePayload(formData, fields)` 构造（**留空字段不放入 data dict**，符合 create 语义——create 时不存在"清空"概念，留空即 NULL）
   - 成功后 Modal 关闭、列表刷新、新记录出现在列表顶部（按 event_time 倒序）+ 总数刷新
6. 提交失败时：
   - Modal 保留已填的值
   - 顶部显示后端返回的错误消息（如"字段值类型不匹配: weight"）
   - 用户可修改后重新提交
7. Modal 可通过点击外部遮罩、右上角 X 按钮、底部"取消"按钮关闭（不保存）
8. **create 通道 event_time 明确不做**：P3 不扩展 `CreateCustomRecordEntryRequest` 加 `event_time` 字段。前端 EntryForm 即使渲染了"事件时间"控件（为 UI 统一），提交时也**忽略该字段**（不传给后端）。用户事后可通过编辑记录修改 event_time

### EntryForm 组件 Props（为 Slice 2 预留扩展接口）

```typescript
interface EntryFormProps {
  mode: 'create' | 'edit';
  type: CustomRecordTypeItem;
  entry?: CustomRecordEntryItem;   // edit 模式必填，create 模式不传
  onClose: () => void;
  onSuccess: () => void;
}
```

本 slice 仅实现 `mode === 'create'` 分支，但 Props 类型按上述完整定义，为 Slice 2 的 edit 模式扩展做好准备。

### buildCreatePayload 工具函数

放 `frontend/apps/custom-records/utils/entryFormPayload.ts`：

> create 模式不需要 diff，所有可见字段都放入 data dict；**留空字段不放入**（避免后端把 null 当作"清空"处理，因为 create 时不存在"清空"概念，留空即 NULL）。

```typescript
export function buildCreatePayload(
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

### TypeDetailView 串联

```typescript
const [showEntryForm, setShowEntryForm] = useState(false);

const handleAddEntry = () => {
  setShowEntryForm(true);
};

const handleEntryFormSuccess = () => {
  setShowEntryForm(false);
  loadData();
};
```

按钮位置：Tab 栏 + 筛选栏所在的工具条区域，紧邻"筛选"按钮。

## Acceptance criteria

- [ ] `TypeDetailView` 新增"添加记录"按钮（cyan-teal 渐变 + Plus 图标）
- [ ] 所有 Tab（card/table/chart/compare）都显示该按钮
- [ ] 点击按钮弹出 Modal，Modal 标题含当前类型名
- [ ] Modal 表单主体首项为"事件时间"`<input type="datetime-local">`（label="事件时间"，create 模式初始为空）
- [ ] create 通道提交时**忽略**事件时间控件（不传 event_time 给后端，沿用 P1 行为）
- [ ] Modal 表单按 `fields` 数组动态渲染输入控件
- [ ] text 字段短文本用 `<input type="text">`，长文本（字段名含 note/content 等关键词）用 `<textarea>`
- [ ] integer 字段用 `<input type="number" step="1">`
- [ ] float 字段用 `<input type="number" step="any">`
- [ ] 字段 label 显示 field_name（含单位）
- [ ] 字段允许留空（**留空字段不放入 data dict**，后端默认 NULL）
- [ ] 提交调用 `CustomRecordsAPI.createEntry`，成功后 Modal 关闭、列表刷新、新记录出现在列表顶部（按 event_time 倒序）+ 总数刷新
- [ ] 提交失败时保留已填值并显示后端错误消息
- [ ] 点击遮罩 / X / 取消按钮可关闭 Modal 不保存
- [ ] `EntryForm` Props 已定义 `mode: 'create' | 'edit'`，为 Slice 2 扩展做好准备
- [ ] `buildCreatePayload` 工具函数实现并放置在 `utils/entryFormPayload.ts`
- [ ] 人工 UI 验证通过：添加 text/integer/float 三种字段类型的记录均成功落库

## Blocked by

None - can start immediately
