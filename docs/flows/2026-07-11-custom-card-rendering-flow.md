---
created: 2026-07-11
tags: [flow, custom-records, card-rendering, layout-engine, frontend]
---

# 自定义记录卡片渲染 Flow

## Flow 对象

`CardLayoutResult`（卡片布局分析结果）

卡片渲染是自定义记录模块的前端核心管线。它将原始的字段定义 + 记录数据 + 用户配置，经过三层布局引擎（L1 启发式 → L2 用户覆盖 → L3 模板预设）转换为最终的可视化卡片 DOM。

管线输入：
- `fields[]`：字段定义列表（含 display_role 用户配置）
- `entry`：单条记录数据（动态字段键值对）
- `card_template`：类型的模板 ID（clean/paper/minimal/bold/metric）

管线输出：
- 一个渲染完成的卡片 React 元素（EntryCard）

相关 Spec：[custom-records-module-spec](../specs/custom-records-module.md)
相关 Flow：[记录 CRUD Flow](2026-07-11-custom-entry-crud-flow.md)（数据来源）

## 关键约束

1. **空值过滤优先**：无论字段配置什么角色，空值（空字符串/纯空白/null/undefined）一律跳过不渲染
2. **标题唯一**：title 角色有且仅有一个。第一个非空 title 候选成为标题，其余降级为 chip
3. **正文可叠加**：main 角色支持多个，所有非空 main 字段按字段定义顺序（sort_order）依次收集，渲染为独立段落
4. **三级优先级**：空值过滤 > L2 用户覆盖（display_role）> L1 关键词匹配 > L1 内容长度启发
5. **布局模式由 mains[] 决定**：mains 非空 → note；mains 为空 + chips 全短 → tight；否则 → compact
6. **纯前端纯函数**：布局分析在浏览器端完成，不依赖后端计算，同一条记录在不同数据内容下可选择不同布局
7. **确定性着色**：field_color 基于 field_key 哈希计算，同一字段始终使用同一颜色
8. **模板与布局正交**：L3 模板控制视觉样式（CSS 类名），L1/L2 控制内容结构，两者可自由组合（5×3=15 种形态）

## 反常设计

- **布局由数据内容驱动而非类型固定**：同类型的不同记录可能因字段值长度不同而选择不同布局（note/tight/compact）。这意味着同一列表中的卡片可能呈现不同形态，这是有意为之——"长得像什么就用什么布局"。
- **L2 overrides 从 fields 的 display_role 字段构建**：不是从单独的配置对象传入，而是 EntryCard 组件在渲染时遍历 fields，将非 auto 的 display_role 提取为 overrides 对象传给 analyzeCardLayout。
- **L1 关键词包含中英文混合**：TITLE 和 MAIN 关键词列表同时包含英文（title/name/note/content）和中文（标题/名称/笔记/内容），覆盖用户创建字段时的中英文命名习惯。
- **布局引擎不读取 template 配置**：analyzeCardLayout 只输出结构（layout/title/mains/chips），不涉及任何视觉样式。模板 CSS 类名由 getTemplatePreset 独立计算，EntryCard 将两者组合。
- **字段颜色在 chip 渲染时动态计算**：getFieldColor(field_key) 在渲染每个 chip 时调用，而非预计算。颜色仅影响 chip 标签的背景/文字/边框色。
- **EntryCard 不处理空 chips/mains 边界**：因为 analyzeCardLayout 已在源头过滤空值，EntryCard 可以安全地 mains.map() 和 chips.map() 而无需额外空值检查。

## 链路 1：布局分析（analyzeCardLayout 核心管线）

### 触发场景

EntryCard 组件每次渲染时调用，是卡片渲染的核心数据转换步骤。

### 5类节点分析

- **状态变化节点**：原始 fields + data → 结构化 CardLayoutResult（title/mains/chips/hidden 分配）
- **分支节点**：5 层判断（空值 → L2 override → L1 关键词 → L1 长度启发 → title 竞争）
- **集合点**：titleCandidates 收集后统一分配（第一个为标题，其余降级）；mains 和 chips 数组最终组装
- **跨层节点**：逻辑层（纯函数计算）→ 表现层（EntryCard 渲染），无 IO、无副作用
- **持久化节点**：无（纯内存计算）

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│              布局分析（analyzeCardLayout 管线）                   │
└─────────────────────────────────────────────────────────────────┘

输入: fields[], data{}, overrides{}
        │
        ▼
┌─ 初始化 ───────────────────────────────────────────────────────┐
│  title = null                                                   │
│  mains = []                                                     │
│  chips = []                                                     │
│  hidden = []                                                    │
│  titleCandidates = []  // 收集所有 title 候选，最后竞争          │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 逐字段处理循环 ───────────────────────────────────────────────┐
│  for each field in fields:                                     │
│                                                                 │
│  ① 提取值: rawValue = data[field.field_key]                    │
│     value = rawValue ?? ""                                     │
│                                                                 │
│  ② 空值过滤: isEmpty(value)?                                   │
│     （空串/纯空白/null/undefined）                              │
│     ├─ Yes → continue（跳过该字段，不进入任何角色）              │
│     └─ No  → 继续                                               │
│                                                                 │
│  ③ resolveRole(field, overrides, value):                       │
│     ├─ overrides[field_key] 存在且非 "auto" → 使用 override    │
│     ├─ 匹配 HIDDEN 关键词 → "hidden"                           │
│     ├─ 匹配 TITLE 关键词 → "title"                             │
│     ├─ 匹配 MAIN 关键词 → "main"                               │
│     ├─ value.length > 25 → "main"                              │
│     ├─ value.length <= 20 → "chip"                             │
│     └─ 20-25 字 → "main"                                       │
│                                                                 │
│  ④ 根据 role 分配:                                             │
│     ├─ "title"  → titleCandidates.push({value, ...})           │
│     ├─ "main"   → mains.push({value, ...})                     │
│     ├─ "hidden" → hidden.push(field_key)                       │
│     └─ "chip"   → chips.push({value, ...})                     │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 标题竞争分配 ─────────────────────────────────────────────────┐
│  if titleCandidates.length > 0:                                │
│    title = titleCandidates[0].value  ← 第一个非空候选为标题     │
│    for i = 1 to end:                                            │
│      chips.push(titleCandidates[i])  ← 其余降级为 chip          │
│  else:                                                          │
│    title = null  ← 无标题                                      │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─ 布局模式决策 ─────────────────────────────────────────────────┐
│  if mains.length > 0:                                          │
│    layout = "note"  // 有正文 → 笔记模式                       │
│  else if chips.every(c => c.value.length < 12):                │
│    layout = "tight" // 无正文 + 全短标签 → 速记模式             │
│  else:                                                          │
│    layout = "compact" // 无正文 + 有中长字段 → 条目模式         │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
输出: { layout, title, mains, chips, hidden }
```

<key_function>
- frontend/apps/custom-records/utils/cardLayoutEngine.ts:analyzeCardLayout:100
- frontend/apps/custom-records/utils/cardLayoutEngine.ts:resolveRole:（内部函数）
- frontend/apps/custom-records/utils/cardLayoutEngine.ts:isEmpty:（内部函数）
</key_function>

## 链路 2：L2 overrides 构建

### 触发场景

EntryCard 组件在调用 analyzeCardLayout 之前，需要从 fields 定义中提取用户配置的 display_role 构建 overrides 对象。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                  L2 overrides 构建                               │
└─────────────────────────────────────────────────────────────────┘

fields[] (FieldDefinition，含 display_role)
        │
        ▼
┌─ EntryCard 组件初始化 ─────────────────────────────────────────┐
│  const overrides: Overrides = {}                               │
│                                                                 │
│  for each field in fields:                                     │
│    if field.display_role && field.display_role !== "auto":     │
│      overrides[field.field_key] = field.display_role           │
│    // auto 和空值不加入 overrides，让 L1 启发式决定             │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
overrides{} 传入 analyzeCardLayout(fields, data, overrides)
```

<key_function>
- frontend/apps/custom-records/components/EntryCard.tsx:EntryCard:34
</key_function>

## 链路 3：L3 模板预设解析

### 触发场景

EntryCard 组件渲染时独立调用 getTemplatePreset 获取 CSS 类名。模板解析与布局分析完全独立。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                  L3 模板预设解析                                 │
└─────────────────────────────────────────────────────────────────┘

templateId (card_template: "clean"/"paper"/"minimal"/"bold"/"metric")
        │
        ▼
┌─ getTemplatePreset(templateId) ────────────────────────────────┐
│  switch (templateId):                                          │
│    "paper"  → { cardClass, accentBarClass, ..., chipClass }    │
│    "minimal"→ { ... }                                          │
│    "bold"   → { ... }                                          │
│    "metric" → { ... }                                          │
│    default/"clean" → clean 预设（白底青条）                     │
│                                                                 │
│  返回 TemplatePreset 对象:                                      │
│  {                                                             │
│    cardClass,       // 卡片容器 CSS 类                         │
│    titleClass,      // 标题 CSS 类                             │
│    mainClass,       // 正文 CSS 类                             │
│    chipClass,       // 标签默认 CSS 类                         │
│    accentBarClass,  // 左侧强调条 CSS 类                       │
│    timestampClass, // 时间戳 CSS 类                            │
│    label           // 模板显示名                               │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
tpl 对象传入 EntryCard JSX，作为 className 拼接
```

<key_function>
- frontend/apps/custom-records/utils/templatePresets.ts:getTemplatePreset:79
</key_function>

## 链路 4：EntryCard 渲染（三布局分支）

### 触发场景

analyzeCardLayout 返回结果 + getTemplatePreset 返回 tpl 对象后，EntryCard 根据 layout 模式选择渲染分支。

### 5类节点分析

- **状态变化节点**：CardLayoutResult + TemplatePreset → DOM 元素
- **分支节点**：layout 三选一（note/compact/tight）
- **跨层节点**：逻辑计算结果 → React JSX → DOM
- **持久化/集合点**：无（纯渲染）

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                  EntryCard 渲染                                  │
└─────────────────────────────────────────────────────────────────┘

{ layout, title, mains, chips } + tpl (TemplatePreset)
        │
        ▼
┌─ 卡片外壳 ─────────────────────────────────────────────────────┐
│  <div className={tpl.cardClass}>                               │
│    <!-- 左侧 accent 竖条 -->                                   │
│    <div className={tpl.accentBarClass} />                      │
│                                                                 │
│    <!-- 头部：时间戳 + 布局标签 + 删除按钮 -->                  │
│    <div>Clock icon + formatDate(entry.created_at)              │
│         + <span class={tpl.chipClass}>{layoutLabel}</span>     │
│         + 删除按钮(hover显示, onClick→onDelete) </div>          │
│                                                                 │
│    <!-- 主体：根据 layout 三选一渲染 -->                        │
│    ┌─────────────────────────────────────────────────────────┐ │
│    │ layout === "note" ?                                     │ │
│    │   ┌─ note 模式 ──────────────────────────────────────┐  │ │
│    │   │  {title && <h3 class={tpl.titleClass}>{title}</h3>}  │ │
│    │   │  {mains.map(m =>                                 │  │ │
│    │   │    <p class={tpl.mainClass}>{m.value}</p>         │  │ │
│    │   │  )}  ← 多正文叠加，每个 <p> 一段                   │  │ │
│    │   │  {chips.length > 0 && (                          │  │ │
│    │   │    <div class="flex flex-wrap">                   │  │ │
│    │   │      {chips.map(c => (                            │  │ │
│    │   │        <span class={`${tpl.chipClass}             │  │ │
│    │   │          ${getFieldColor(c.field_key).bg}         │  │ │
│    │   │          ${getFieldColor(c.field_key).text}       │  │ │
│    │   │          border ...`}>                            │  │ │
│    │   │          {c.value}                                │  │ │
│    │   │        </span>                                    │  │ │
│    │   │      ))}                                          │  │ │
│    │   │    </div>                                         │  │ │
│    │   │  )}                                               │  │ │
│    │   └───────────────────────────────────────────────────┘  │ │
│    │                                                         │ │
│    │ layout === "compact" ?                                  │ │
│    │   ┌─ compact 模式 ───────────────────────────────────┐  │ │
│    │   │  {title && <h3 class={tpl.titleClass}>{title}</h3>}  │ │
│    │   │  {chips.map(c => (                                │  │ │
│    │   │    <div>                                          │  │ │
│    │   │      <span class="opacity-40">{c.field_name}</span>│  │ │
│    │   │      <span class={getFieldColor(c.field_key).text}>│  │ │
│    │   │        {c.value}                                  │  │ │
│    │   │      </span>                                      │  │ │
│    │   │    </div>                                         │  │ │
│    │   │  ))}  ← 键值对列表（字段名: 值）                  │  │ │
│    │   └───────────────────────────────────────────────────┘  │ │
│    │                                                         │ │
│    │ layout === "tight" ?                                    │ │
│    │   ┌─ tight 模式 ─────────────────────────────────────┐  │ │
│    │   │  <div class="flex flex-wrap">                     │  │ │
│    │   │    {chips.map(c => (                              │  │ │
│    │   │      <span class={`${tpl.chipClass}               │  │ │
│    │   │        ${getFieldColor(c.field_key).bg}...`}>     │  │ │
│    │   │        {c.value}                                  │  │ │
│    │   │      </span>                                      │  │ │
│    │   │    ))}  ← 纯标签云                                │  │ │
│    │   │  </div>                                           │  │ │
│    │   └───────────────────────────────────────────────────┘  │ │
│    └─────────────────────────────────────────────────────────┘ │
│  </div>                                                         │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
DOM 元素 → React 提交到浏览器渲染
```

<key_function>
- frontend/apps/custom-records/components/EntryCard.tsx:EntryCard:34
- frontend/apps/custom-records/utils/fieldColors.ts:getFieldColor
</key_function>

## 链路 5：字段颜色确定性分配

### 触发场景

每个 chip 渲染时调用 getFieldColor(field_key)，为标签分配背景色、文字色和边框色。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                  字段颜色分配                                    │
└─────────────────────────────────────────────────────────────────┘

field_key (如 "exercise_content", "mood")
        │
        ▼
┌─ getFieldColor(field_key) ────────────────────────────────────┐
│  1. 对 field_key 计算哈希值（简单字符哈希）                     │
│  2. hash % paletteSize 取模                                    │
│  3. 从预定义颜色调色板中取对应色组                              │
│     { bg: "bg-xxx-50", text: "text-xxx-700",                  │
│       border: "border-xxx-200" }                               │
│  返回: { bg, text, border }                                    │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
同一 field_key → 同一哈希 → 同一颜色（确定性）
不同 field_key → 均匀分布在调色板上
```

<key_function>
- frontend/apps/custom-records/utils/fieldColors.ts:getFieldColor
</key_function>

## 链路 6：日期分组（TypeDetailView 列表渲染前置）

### 触发场景

TypeDetailView 卡片视图获取到记录列表后，在渲染 EntryCard 列表之前，按日期分组。

### 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                  日期分组                                        │
└─────────────────────────────────────────────────────────────────┘

entries[] (CustomRecordEntryItem[])
        │
        ▼
┌─ 按 created_at 日期部分分组 ───────────────────────────────────┐
│  groupKey = entry.created_at.slice(0, 10)  // YYYY-MM-DD       │
│  groups = { "2026-07-11": [entries...], ... }                  │
│                                                                 │
│  对每个分组，生成显示标签:                                      │
│  ├─ 今天 → "今天"                                              │
│  ├─ 昨天 → "昨天"                                              │
│  ├─ 前天 → "前天"                                              │
│  └─ 其他 → "M月D日"（如 "7月8日"）                             │
│                                                                 │
│  按日期倒序排列分组                                             │
└────────────────────────────────────────────────────────────────┘
        │
        ▼
渲染:
  每个分组 → 日期标题 + 组内 entries.map(EntryCard)
```

<key_function>
- frontend/apps/custom-records/components/TypeDetailView.tsx:（日期分组逻辑在组件内）
</key_function>

## 完整渲染管线端到端

```
┌─────────────────────────────────────────────────────────────────┐
│              卡片渲染端到端管线                                   │
└─────────────────────────────────────────────────────────────────┘

GET /{type_id}/entries 返回 entries[]
        │
        ▼
TypeDetailView 接收 { items, total }
        │
        ▼
按日期分组（今天/昨天/M月D日）
        │
        ▼
每组内 entries.map(entry =>
        │
        ▼
  EntryCard 组件接收 { fields, entry, templateId, onDelete }
        │
        ├──────────────────────────────┐
        ▼                              ▼
  构建 data{}                    构建 overrides{}
  (entry动态字段→字典)           (fields.display_role非auto→映射)
        │                              │
        └──────────┬───────────────────┘
                   ▼
         analyzeCardLayout(fields, data, overrides)  ← L1+L2
                   │
                   ├─ 空值过滤
                   ├─ 角色解析（override→关键词→长度）
                   ├─ 标题竞争分配
                   └─ 布局模式决策
                   │
                   ▼
         { layout, title, mains, chips }
                   │
          ┌────────┴────────┐
          ▼                 ▼
  getTemplatePreset     getFieldColor (每个chip)
  (templateId→CSS类名)   (field_key→颜色)
          │                 │
          └────────┬────────┘
                   ▼
         JSX 渲染（三布局分支）
                   │
                   ▼
         React DOM → 浏览器绘制
```

## 耦合关系

| 耦合对象 | 耦合方式 |
|---------|---------|
| `CustomRecordType` | card_template 决定 L3 模板预设；fields 定义提供 display_role（L2 overrides）和 field_key（着色、数据提取） |
| `CustomRecordEntry` | 记录数据是布局引擎的输入，entry[field_key] 提供字段值 |
| `TypeDetailView` | 消费记录列表，做日期分组后批量渲染 EntryCard；管理模板切换 debounce 保存和字段角色配置 |
| `TemplatePreset`（templatePresets.ts） | getTemplatePreset 独立计算 CSS 类名，与布局分析正交 |
| `FieldColor`（fieldColors.ts） | getFieldColor 基于 field_key 哈希确定性分配颜色，仅影响 chip 标签视觉 |
| `React` | EntryCard 是 React 函数组件，使用 hooks 和 JSX |
| `lucide-react` | 使用 Trash2（删除）、Clock（时间戳）图标 |
| `tailwindcss` | 所有样式通过 Tailwind CSS 类名实现 |
