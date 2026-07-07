# 自定义记录模块前端实现

**Triage labels**: `completed`
**Parent**: `.scratch/custom-records-module/PRD.md`
**Status**: `completed`（TDD 完成，18 个 API 测试通过，UI 人工验证通过）
**UI 原型**: `.scratch/custom-records-module/prototype.html`（用浏览器直接打开即可预览交互）

## What to build

在 Slice 3（Service + API 层）已就位、UI 原型设计完成后，实现自定义记录模块的前端页面。采用数据驱动渲染模式：前端不硬编码列定义，从 API 动态获取字段定义，然后渲染动态表格。

端到端行为：
1. 用户进入"自定义记录"页面，看到所有类型的卡片列表
2. 用户点击"新建类型"，填写类型名 + 动态添加字段行（类似 Navicat 建表），点击创建
3. 用户点击某类型进入详情页，看到动态表格（fields 驱动表头）+ 日期筛选 + 分页
4. 用户可以删除单条记录或删除整个类型

### 模块定位

自定义记录模块是**顶级独立模块**，与 `goals`/`habits`/`mindspace`/`settings`/`lifewatch` 同层级，通过顶部 `ModuleDock` 切换进入，**不是** `lifewatch` 的子页面。

需要在以下 4 处注册（参考 habits 模块模式）：
1. `frontend/shell/types.ts` — `ModuleId` 联合类型增加 `'custom-records'`
2. `frontend/shell/ModuleDock.tsx` — `MODULES` 数组增加自定义记录项
3. `frontend/shell/AppShell.tsx` — 增加 `CustomRecordsApp` 导入和条件渲染
4. `frontend/index.tsx` 路由层面 — `/custom-records` 路径前缀映射到该模块

代码位置：`frontend/apps/custom-records/`（与 `frontend/apps/habits/` 同层级）

### 页面结构

模块内部**不使用 React Router**，所有视图通过组件状态切换（参考 habits 的 `HabitsAppContent` 模式）。

**视图 1：类型列表页（模块默认视图）**
- 模块加载 → `GET /custom-records/types` → 渲染类型卡片列表
- 点击"新建类型"按钮 → 切换到新建表单视图
- 填写表单后点击"创建" → `POST /custom-records/types` → 成功后切回列表视图
- 点击某类型的"删除"按钮 → 弹出确认对话框 → 确认后 `DELETE /custom-records/types/{type_id}` → 刷新列表
- 点击某类型卡片 → 切换到类型详情视图

**视图 2：新建类型表单**
- 类型名称输入框
- 字段定义区域：
  - "添加字段"按钮动态加行（类似 Navicat 建表方式）
  - 每行包含：字段名（显示名）+ 字段 key（列名）+ 字段类型（P1 只有 text）
  - 可删除已添加的字段行
- 创建按钮 → `POST /custom-records/types`（body: `{name, slug, fields: [{field_name, field_key, field_type}]}`）

**视图 3：类型详情页**
- 进入视图 → `GET /custom-records/types/{type_id}` → 获取字段定义
- 同时 → `GET /custom-records/{type_id}/entries` → 获取记录列表（默认无日期筛选）
- 日期筛选：start_date + end_date 输入 → `GET /custom-records/{type_id}/entries?start_date=...&end_date=...`
- 分页：page + page_size → `GET /custom-records/{type_id}/entries?...&page=2&page_size=20`
- 动态表格：
  - 表头：`fields.map(f => <th>{f.field_name}</th>)` + "创建时间"列
  - 数据行：`entries.map(entry => fields.map(f => <td>{entry[f.field_key]}</td>))`
- 删除记录：行内"删除"按钮 → `DELETE /custom-records/{type_id}/entries/{entry_id}` → 刷新列表

### 数据驱动渲染（核心模式）

```tsx
// 类型列表
const [types, setTypes] = useState([]);
useEffect(() => {
  fetch('/api/v2/custom-records/types').then(r => r.json()).then(setTypes);
}, []);

// 字段定义（进入详情页时加载）
const [fields, setFields] = useState([]);
useEffect(() => {
  fetch(`/api/v2/custom-records/types/${typeId}`).then(r => r.json()).then(data => setFields(data.fields));
}, [typeId]);

// 记录列表
const [entries, setEntries] = useState([]);
useEffect(() => {
  fetch(`/api/v2/custom-records/${typeId}/entries?${params}`).then(r => r.json()).then(setEntries);
}, [typeId, dateRange, page]);

// 动态表格渲染
<table>
  <thead>
    <tr>
      {fields.map(f => <th key={f.field_key}>{f.field_name}</th>)}
      <th>创建时间</th>
    </tr>
  </thead>
  <tbody>
    {entries.map(entry => (
      <tr key={entry.id}>
        {fields.map(f => <td key={f.field_key}>{entry[f.field_key]}</td>)}
        <td>{entry.created_at}</td>
      </tr>
    ))}
  </tbody>
</table>
```

### 关键点

- **`fields.map()` 驱动表头**：遍历字段定义生成 `<th>`
- **`entry[f.field_key]` 取值**：用 field_key 作为 key 从 entry 对象取值
- **状态分离**：`types`、`fields`、`entries` 三个状态独立管理
- **API 契约固定**：前端不关心表名是什么，只关心 `type_id` 和 `field_key`
- **使用项目现有 UI 框架**：参考项目现有的 React 组件结构和样式系统

### 不测的内容

- 前端渲染（人工验证）
- API 调用逻辑（API 层已由 Slice 3 覆盖）

## Acceptance criteria

- [x] 类型列表页：加载时调用 `GET /custom-records/types`，展示所有类型卡片
- [x] 新建类型表单：类型名 + 动态字段行（"添加字段"按钮加行，可删除行）
- [x] 新建类型：`POST /custom-records/types` 成功后刷新列表（API 层测试覆盖，UI 流程已实现）
- [x] 删除类型：确认对话框 → `DELETE /custom-records/types/{type_id}` → 刷新列表
- [x] 类型详情页：`GET /custom-records/types/{type_id}` 获取字段定义
- [x] 动态表格：`fields.map()` 驱动表头，`entry[field_key]` 驱动数据列
- [x] 日期筛选：start_date + end_date → `GET /custom-records/{type_id}/entries?...`
- [x] 分页：page + page_size 切换
- [x] 删除记录：行内删除 → `DELETE /custom-records/{type_id}/entries/{entry_id}` → 刷新
- [x] 错误处理：slug 冲突、field_key 格式错误等在 UI 上有提示（表单校验已验证）
- [x] 模块在 `ModuleDock` 中正确注册，点击图标可切换到自定义记录模块
- [x] 模块代码位于 `frontend/apps/custom-records/`，与 habits/goals 同层级
- [x] 遵循项目前端规范（HashRouter、Vite base: './'、camelCase API 字段）

## Blocked by

- `.scratch/custom-records-module/issues/03-service-api.md`
- `.scratch/custom-records-module/design-spec.md`

## Comments

> 2026-07-07: 本 issue 已被细化为两个子 issue，聚焦于"基础前端实现"（类型列表 + 新建 + 表格详情）。卡片视图、自适应布局引擎、模板系统将在子 issue 中实现。
>
> 子 issue:
> - `05-frontend-card-view.md` — 卡片视图 + L1 启发式布局引擎
> - `06-frontend-config-system.md` — 配置持久化 + L2/L3 模板系统
