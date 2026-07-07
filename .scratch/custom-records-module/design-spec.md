# 自定义记录模块 · 前端设计规格

> 对应原型: `.scratch/custom-records-module/prototype.html` (v4)
> 状态: `ready-for-implementation`

## 设计目标

解决「字段从后端动态加载，卡片样式如何设计」的核心问题：
- 字段不确定 → 不能写死 CSS 选择器
- 用户不懂 CSS → 不能暴露样式属性
- 需要兼顾自动化与可控性 → 三层分层架构

## 核心原则

**用户永远不直接写 CSS。** 所有展示控制通过语义层（字段角色）和视觉层（模板预设）间接表达，由系统自动转换为具体样式。

---

## 三层自适应架构

```
┌─────────────────────────────────────────────────────────────┐
│  L3 视觉模板预设 (Visual Templates)                          │
│  5 套预设皮肤 → 一键切换整个类型的卡片风格                      │
├─────────────────────────────────────────────────────────────┤
│  L2 字段角色配置 (Field Roles)                               │
│  每个字段指定语义角色 → title / main / chip / hidden / auto   │
├─────────────────────────────────────────────────────────────┤
│  L1 智能布局引擎 (Heuristic Layout Engine)                   │
│  自动识别字段角色 + 自动选择布局模式 (note/compact/tight)     │
└─────────────────────────────────────────────────────────────┘
```

### L1: 智能布局引擎（自动层，覆盖 80%）

**输入**: `fields[]` (字段定义) + `data{}` (单条记录数据) + `overrides{}` (用户覆盖)
**输出**: `{ layout, title, main, subtitle, chips, hidden }`

#### 字段角色识别规则（按优先级）

1. **用户覆盖优先**: `overrides[field_key]` 为 `title/main/chip/hidden` 时直接采用
2. **关键词匹配**:
   - TITLE_KEYWORDS: `title`, `name`, `book_name`, `movie_name`, `game`, `place`, `destination`, `dream_theme` + 中文对应词
   - MAIN_KEYWORDS: `note`, `review`, `content`, `desc`, `description`, `text`, `detail`, `body`, `diary`, `log`, `dream`, `thought`, `feeling` + 中文对应词
   - HIDDEN_KEYWORDS: `id`, `created_at`, `updated_at`, `slug`, `type_id`
3. **内容长度启发**:
   - 长度 > 25 且无其他主体 → 标记为 `main`
   - 长度 <= 20 → 标记为 `chip`
   - 长度 20-25 且无主体 → 标记为 `main`

#### 布局模式决策

| 条件 | 布局 | 特征 |
|------|------|------|
| 有 `main` 字段 | **note** | 标题(如有) + 大段正文 + 底部chips |
| 无 `main` 但 `chips` 全短(<12字) | **tight** | 纯标签云，只显示值 |
| 无 `main` 但有中长字段 | **compact** | 键值对列表 |

### L2: 字段角色配置（语义层，覆盖 15%）

用户通过弹窗为每个字段指定语义角色：

| 角色 | 语义 | 卡片中表现 |
|------|------|-----------|
| `auto` | 自动（默认） | 由 L1 引擎决定 |
| `title` | 标题 | 卡片标题，加粗大字 |
| `main` | 主体内容 | 卡片正文，较大字号 |
| `chip` | 标签/属性 | 底部彩色小标签 |
| `hidden` | 隐藏 | 卡片中不显示 |

**交互**: 类型详情页 → "字段展示设置" 按钮 → 弹窗中每个字段 5 选 1 → 保存。

### L3: 视觉模板预设（皮肤层，覆盖 5%）

5 套预设卡片皮肤。模板只改变视觉层（背景、边框、圆角、间距、字重、chips 样式），不改变数据结构和字段语义。

| 模板 | 风格 | 适合场景 |
|------|------|---------|
| **clean** (默认) | 白底圆角 + 左侧 accent 竖条 | 通用百搭 |
| **paper** | 暖米色 + 衬线字体 + 虚线分割 | 日记、读后感、长文本 |
| **minimal** | 去卡片化 + 细线分割 | 沉浸式阅读、列表浏览 |
| **bold** | accent 色渐变填充 + 白字 | 视觉强调、重要记录 |
| **metric** | chips 变网格指标卡 | 数字型记录、运动、饮食 |

**模板 CSS 架构**: 每个模板对应一组 CSS 类名前缀 `.tpl-{name}`，控制以下视觉属性：
- `background`, `border`, `border-radius`, `box-shadow`
- `.tpl-title`: 字号、字重、颜色
- `.tpl-main`: 字号、行高、颜色、字体族
- `.tpl-chip`: 圆角、padding、背景、边框
- `.tpl-divider`: 分隔线样式、margin
- `.tpl-time`: 时间戳样式
- `.tpl-accent`: 强调色元素位置和样式

---

## 字段配色方案

**不依赖后端配置。** 使用稳定哈希算法从 `field_key` 派生颜色：

```typescript
const FIELD_COLORS = [
  { bg:'bg-cyan-50', text:'text-cyan-700', border:'border-cyan-100', dot:'bg-cyan-400', solid:'bg-cyan-500' },
  { bg:'bg-violet-50', ... },
  // 10 色循环
];

const hashStr = (s) => { let h=0; for(let i=0;i<s.length;i++){ h=((h<<5)-h)+s.charCodeAt(i); h|=0; } return Math.abs(h); };
const getFieldColor = (fieldKey) => FIELD_COLORS[hashStr(fieldKey) % FIELD_COLORS.length];
```

同一 `field_key` 永远获得同一颜色，新增字段自动分配，无需预设。

---

## 数据流与状态分层

### 后端持久化（跨设备一致）

存储在 `custom_record_types` 和 `custom_record_fields` 表中：

| 配置项 | 存储位置 | 字段名 |
|--------|---------|--------|
| 卡片视觉模板 | `custom_record_types` | `card_template` (TEXT, DEFAULT 'clean') |
| 类型图标 | `custom_record_types` | `icon` (TEXT, DEFAULT 'fileText') |
| 强调色 | `custom_record_types` | `accent_color` (TEXT, DEFAULT 'blue') |
| 字段展示角色 | `custom_record_fields` | `display_role` (TEXT, DEFAULT 'auto') |

### 前端本地状态（仅当前设备）

```typescript
type LocalPrefs = {
  [typeId: string]: {
    lastView?: 'card' | 'table' | 'chart';  // 上次使用的视图
    dateRange?: [string, string];           // 上次筛选日期
    sortBy?: 'created_at';
    sortOrder?: 'desc' | 'asc';
  }
};
// 存储于 localStorage
```

---

## 模块架构

自定义记录模块是**顶级独立模块**，与 `goals`/`habits`/`mindspace`/`settings`/`lifewatch` 同层级，通过顶部 `ModuleDock` 切换进入。

### 注册位置（4 处硬编码）

参考 habits 模块的注册模式：

1. **`frontend/shell/types.ts`** — `ModuleId` 联合类型增加 `'custom-records'`
2. **`frontend/shell/ModuleDock.tsx`** — `MODULES` 常量数组增加自定义记录项（icon: database, color: cyan）
3. **`frontend/shell/AppShell.tsx`** — 增加 `CustomRecordsApp` 导入和 `currentModule === 'custom-records'` 条件渲染
4. **`frontend/shell/AppShell.tsx`** — `handleModuleChange` 和 `useEffect` 路径判断中增加 `/custom-records` 映射

### 代码位置

```
frontend/apps/custom-records/
├── CustomRecordsApp.tsx          # 模块入口（Provider 包裹 + 状态路由）
├── CustomRecordsAppContent.tsx   # 主内容（状态切换：列表/新建/详情）
├── components/
│   ├── TypeListView.tsx          # 类型列表视图
│   ├── CreateTypeView.tsx        # 新建类型视图
│   ├── TypeDetailView.tsx        # 类型详情视图
│   ├── EntryCard.tsx             # 自适应卡片组件
│   ├── EntryTable.tsx            # 动态表格组件
│   ├── TemplatePicker.tsx        # 模板选择器
│   ├── FieldRoleModal.tsx        # 字段角色配置弹窗
│   └── DateRangeFilter.tsx       # 日期范围筛选
├── api.ts                        # API 封装
├── types.ts                      # 类型定义
└── utils/
    ├── cardLayoutEngine.ts       # L1 启发式布局引擎
    └── fieldColors.ts            # 字段配色工具
```

### 视图切换模式

模块内部**不使用 React Router**（参考 habits 的 `HabitsAppContent` 模式），所有视图通过本地状态切换：

```typescript
type ViewState =
  | { view: 'list' }
  | { view: 'create' }
  | { view: 'detail'; typeId: string };
```

- **list** → 类型列表页（模块默认视图）
- **create** → 新建类型表单
- **detail** → 类型详情页（含卡片/表格/模板对比 Tab）

### 各视图行为

**TypeListView（列表视图）**
- 加载 `GET /custom-records/types`
- 展示类型卡片（名称、字段数、记录数、最近记录时间）
- "新建类型"按钮 → 切换到 create 视图
- 点击类型卡片 → 切换到 detail 视图

**CreateTypeView（新建视图）**
- 类型名称输入
- 动态字段行：字段显示名 + 字段 key + 字段类型（P1仅text）
- "添加字段"/"移除字段"按钮
- 提交 → `POST /custom-records/types` → 成功后切回 list 视图

**TypeDetailView（详情视图）**
- **Header**: 类型名称、icon、accent色、记录数、模板选择器、字段角色设置按钮
- **字段chips**: 展示该类型所有字段定义
- **Tab栏**: 卡片视图 / 表格视图 / 模板对比(DEMO)
- **筛选栏**: 日期范围(start_date/end_date)
- **内容区**:
  - 卡片视图: 按日期分组 → EntryCard 组件网格
  - 表格视图: 动态表头表格
  - 模板对比: 同一条数据在5种模板下并排展示

---

## 组件层级

```
AppShell
├── ModuleDock（顶部导航栏：lifewatch / goals / habits / mindspace / custom-records / settings）
└── 条件渲染（由 currentModule 状态决定）
    ├── LifeWatchApp      ← currentModule === 'lifewatch'
    ├── HabitsApp         ← currentModule === 'habits'
    ├── GoalsApp          ← currentModule === 'goals'
    ├── MindSpaceApp      ← currentModule === 'mindspace'
    └── CustomRecordsApp  ← currentModule === 'custom-records'
        └── CustomRecordsAppContent（状态驱动视图切换）
            ├── TypeListView
            │   └── TypeCard
            ├── CreateTypeView
            │   └── DynamicFieldRow
            └── TypeDetailView
                ├── TemplatePicker
                ├── FieldRoleModal
                ├── DateRangeFilter
                ├── EntryCard (核心组件)
                │   ├── L1: analyzeCardLayout()
                │   └── L3: tpl-{template} CSS
                ├── EntryTable
                └── TemplateCompareShowcase
```

---

## API 对接点

### 已有端点（Slice 3 已完成）

| 方法 | 端点 | 用途 |
|------|------|------|
| GET | `/api/v2/custom-records/types` | 类型列表 |
| POST | `/api/v2/custom-records/types` | 创建类型 |
| GET | `/api/v2/custom-records/types/{type_id}` | 类型详情（含 fields） |
| DELETE | `/api/v2/custom-records/types/{type_id}` | 删除类型 |
| GET | `/api/v2/custom-records/{type_id}/entries` | 记录列表（含分页、日期筛选） |
| POST | `/api/v2/custom-records/{type_id}/entries` | 创建记录 |
| DELETE | `/api/v2/custom-records/{type_id}/entries/{entry_id}` | 删除记录 |

### 需新增端点（Slice 6）

| 方法 | 端点 | 用途 |
|------|------|------|
| PATCH | `/api/v2/custom-records/types/{type_id}` | 更新类型配置（template/icon/accent） |
| PATCH | `/api/v2/custom-records/types/{type_id}/fields/{field_id}` | 更新字段 display_role |

---

## 原型参考

完整交互原型见: `.scratch/custom-records-module/prototype.html`

该原型用纯 HTML+React CDN 实现，包含：
- 三层架构演示（L1自动布局 + L2字段角色弹窗 + L3模板切换）
- 5 种模板实时切换效果
- 同数据多模板对比展示
- 完整的页面流程（类型列表 → 详情 → 设置）

实现时请将原型中的设计决策转译为项目前端技术栈（React 19 + TypeScript + Tailwind v4），保持交互逻辑和视觉层次一致。
