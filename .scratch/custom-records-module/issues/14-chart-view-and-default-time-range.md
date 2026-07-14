# P2 Slice 2: 折线图视图 + 默认时间范围

**Triage labels**: `ready-for-agent`
**Parent**: `.scratch/custom-records-module/PRD-P2.md`

## What to build

在 Slice 1（数值字段类型扩展）已就位的基础上，为类型详情页新增折线图视图和默认时间范围。完成后用户进入类型详情页时默认看到最近一周的数据，当类型含数值字段时可切换到"图表"Tab 查看折线图，支持"按数据点 / 按天聚合"两种视图模式。

端到端行为：
1. 用户进入类型详情页时，时间筛选器自动填充"最近一周"（`endDate=今天`、`startDate=今天-7天`），所有 Tab 共享此筛选
2. 用户手动清除筛选器后，加载全部记录（恢复 P1 行为）
3. 当类型含至少 1 个 integer/float 字段时，Tab 栏显示"图表"选项；全 text 字段时隐藏（与 P1 一致）
4. 进入图表 Tab 后展示折线图，自动选择所有 integer/float 字段绘制多线图
5. 图表 Tab 内有 Toggle 按钮切换"按数据点"和"按天聚合"两种模式
6. "按数据点"模式：每条记录一个数据点，X 轴显示"MM-DD HH:MM"
7. "按天聚合"模式：同一天多条记录对每个数值字段求和，X 轴显示"MM-DD"
8. X 轴按时间升序排列（与 card/table 的 DESC 相反）
9. 多数值字段时提供 toggle 按钮切换各字段可见性（至少保留一个可见）
10. 图表 Tooltip 显示当前数据点的日期、各字段名与值
11. 图表数据复用已加载的 entries（来自 `GET /custom-records/{type_id}/entries`），前端完成聚合，不新增后端 API
12. 有数值字段但无记录时显示空状态提示"暂无记录"

### 默认时间范围（影响 P1 行为）

进入类型详情页时，若 `startDate/endDate` 均为空，自动填充默认值：
- `endDate` = 今天
- `startDate` = 今天往前 7 天

此默认值作用于整个详情页（所有 Tab 共享），影响 P1 现有行为（P1 默认加载全部记录）。用户可手动清除筛选器恢复"加载全部"。

### 前端 — 类型详情页 Tab

`TypeDetailView` 的 Tab 栏从 3 个扩展为条件性 4 个：
- 当类型含至少 1 个 integer/float 字段时，显示 4 个 Tab：卡片 / 表格 / 图表 / 模板对比
- 当类型全为 text 字段时，显示 3 个 Tab：卡片 / 表格 / 模板对比（与 P1 一致）

`activeTab` 的 ViewTab 类型扩展为 `'card' | 'table' | 'chart' | 'compare'`，默认仍为 'card'。

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

图表中的数值显示复用 Slice 1 的格式化工具函数：
- integer 字段：显示原值
- float 字段：固定 1 位小数

### 空状态处理

- **类型无数值字段**：图表 Tab 隐藏（TypeDetailView 的 Tab 列表中不包含 'chart'）
- **有数值字段但无记录**：图表区域显示空状态提示"暂无记录"（参考现有表格空状态样式）
- **所有字段被 toggle 隐藏**：至少保留一个可见（与 TimeDistributionChart 一致）

### 架构依赖关系

无后端改动，纯前端实现：

```
前端 TypeDetailView ──→ EntryChart（新组件）──→ recharts（已有依赖）
                  ──→ CustomRecordsAPI.getEntries（复用现有接口）
```

### 不测的内容

- 前端图表渲染（人工验证，参考 TimeDistributionChart 的现有模式）
- 默认时间范围的填充逻辑（人工验证）

## Acceptance criteria

- [ ] 进入类型详情页时，时间筛选器默认填充"最近一周"（endDate=今天、startDate=今天-7天）
- [ ] 默认时间范围作用于所有 Tab（卡片/表格/图表/模板对比）
- [ ] 用户手动清除筛选器后，加载全部记录（恢复 P1 行为）
- [ ] 当类型含至少 1 个 integer/float 字段时，Tab 栏显示"图表"选项
- [ ] 当类型全为 text 字段时，Tab 栏不显示"图表"选项（与 P1 一致）
- [ ] 进入图表 Tab 后展示折线图，自动选择所有 integer/float 字段
- [ ] 图表 Tab 内有 Toggle 按钮切换"按数据点"和"按天聚合"两种模式
- [ ] "按数据点"模式：X 轴显示"MM-DD HH:MM"，同一天多条记录显示多个独立点
- [ ] "按天聚合"模式：X 轴显示"MM-DD"，同一天多条记录对每个数值字段求和
- [ ] X 轴按时间升序排列
- [ ] 多数值字段时提供 toggle 按钮切换各字段可见性
- [ ] 至少保留一个字段可见（不允许全隐藏）
- [ ] 图表 Tooltip 显示当前数据点的日期、各字段名与值
- [ ] 图表样式与 TimeDistributionChart.tsx 一致（白底卡片 + recharts + 自定义 Tooltip + category toggle）
- [ ] 图表数据复用已加载的 entries，前端聚合，不新增后端 API
- [ ] 有数值字段但无记录时显示空状态提示"暂无记录"
- [ ] 图表数值格式化：integer 显示原值，float 固定 1 位小数（复用 Slice 1 工具函数）
- [ ] 图表复用现有的日期范围筛选器（startDate/endDate），筛选后图表数据同步更新

## Blocked by

- `.scratch/custom-records-module/issues/13-field-type-extension.md`（图表依赖数值字段类型存在）
