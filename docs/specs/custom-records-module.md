---
version: 1.1
created_at: 2026-07-07
updated_at: 2026-07-11
last_updated: 补充多正文叠加、空字段过滤、ChatPanel集成、表格/模板对比视图；修正API端点表和布局引擎描述；更新Functional Checklist为已验证状态
abstract: 自定义记录模块是顶级独立模块，允许用户通过自然语言创建任意结构化数据类型。采用 SQLite 动态建表 + meta 表元数据驱动方案，L1/L2/L3 三层布局引擎实现自适应卡片展示，支持多个正文叠加和空字段自动过滤，集成 ChatPanel AI 对话录入。
---

# 自定义记录模块 Spec

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建 spec 初稿 |
| 1.1  | 修正布局引擎输出结构（main→mains[] 支持多正文叠加）；补充空字段过滤规则和 title fallback 机制；补充 ChatPanel AI 集成、表格视图、模板对比视图、FieldRoleModal 交互说明；补充 GET /types/{type_id} 端点到主表；补充分页 total 字段说明；Functional Checklist 标记已验证功能；更新 key_function 行号 |

## Overview

**业务问题**：用户有记录任意结构化内容的需求（如体育活动、每日饮食、读书笔记、观影记录），但这些需求无法预先穷举，也不适合为每类内容建一张固定表。需要一个灵活机制让用户通过自然语言告诉 AI 想记录什么，AI 生成数据结构定义并持续把后续自然语言解析成结构化记录写入。

**核心职责**：

- **类型管理**：用户通过 AI 或表单创建记录类型（定义名称、slug、字段列表），系统动态建表
- **记录录入**：AI 解析自然语言为字段值或用户手动表单录入，写入对应的动态数据表
- **记录查询**：按类型 + 日期范围查询记录，支持分页
- **展示配置**：用户可调整类型展示配置（卡片模板/图标/强调色）和字段展示角色
- **自适应展示**：L1/L2/L3 三层布局引擎自动选择最优卡片布局，支持多正文叠加
- **AI 对话集成**：ChatPanel 侧边栏面板，支持自然语言创建类型和录入数据

**模块定位**：自定义记录是 LifePrism 的**顶级独立模块**，与 habits（习惯系统）、goals（目标管理）同层级。它不依赖任何业务模块，仅依赖底层 repository 基础设施。

## Scope

### 范围内

- 记录类型的创建、查询、删除（meta 表 + 动态 DDL）
- 记录的录入、查询、删除（动态数据表）
- 类型展示配置更新（card_template / icon / accent_color）
- 字段展示角色更新（display_role）
- L1 启发式布局引擎（关键词匹配 + 内容长度启发）
- L2 用户覆盖（字段角色手动指定）
- L3 模板预设（5 套视觉模板）
- 多正文叠加渲染（多个 main 字段依次渲染为段落）
- 空字段自动过滤（无论何种角色，空值不渲染）
- AI LLM tool（创建类型 / 录入记录 / 查询记录 / 列出类型）
- ChatPanel AI 侧边栏集成（自然语言录入入口）
- 前端三种视图（卡片/表格/模板对比）

### 范围外

- 记录更新（P1 不支持，用户需删除后重新录入）
- Schema 演进（字段定义后不可变，要改只能新建类型 + 硬删旧类型）
- 字段类型扩展（P1 仅 text，number/date 留枚举位）
- 图表展示（柱形/折线/饼，P2 阶段）
- 记录间关联（如"这条运动记录关联到某个目标"）
- 前端表单手动创建类型时的 AI 辅助（当前仅 ChatPanel 支持 AI 创建，表单为纯手动）

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 类型管理

- [x] 用户通过 AI 对话创建记录类型，AI 生成 name/slug/fields 并调用 tool 建表
- [x] 用户通过前端表单手动创建记录类型（CreateTypeView）
- [x] slug 格式校验（`^[a-z][a-z0-9_]*$`），格式错误返回 422
- [x] slug 全局唯一，冲突返回 409
- [x] field_key 格式校验（`^[a-z][a-z0-9_]*$`）+ 同类型内唯一性校验
- [x] fields 至少 1 个，空列表返回 422
- [x] 前端 GET /types 返回所有类型（含字段定义），按创建时间正序
- [x] 前端 GET /types/{type_id} 返回单个类型详情（含字段定义）
- [x] 删除类型时同事务 DROP 数据表 + 删除 meta 记录
- [x] 删除后 slug 可被新类型复用
- [x] 类型列表页卡片展示类型名、slug、字段数量、创建日期

### 记录管理

- [x] AI 解析自然语言为字段值，调用 tool 录入记录
- [x] data 中的 key 必须匹配类型的 field_key，错误返回 422 + valid_fields 列表
- [x] 缺失字段存为 NULL，空字典允许（插入全 NULL 行）
- [x] 查询记录按 created_at 倒序，支持 start_date/end_date 日期筛选 + 分页（page/page_size）
- [x] 查询响应包含 total 字段（满足筛选条件的总记录数）
- [x] 删除单条记录，记录不存在返回 404
- [x] 记录列表按日期分组显示（今天/昨天/前天/M月D日）

### 展示配置

- [x] PATCH /types/{type_id} 更新 card_template/icon/accent_color，不存在返回 404
- [x] PATCH /types/{type_id}/fields/{field_id} 更新 display_role，字段不存在返回 404
- [x] display_role 可在 auto/title/main/chip/hidden 之间切换，不影响已存储数据
- [x] 模板切换带 600ms debounce 自动保存，保存状态提示
- [x] 字段角色配置弹窗（FieldRoleModal）支持逐字段设置角色，本地乐观更新+后端持久化

### 布局引擎

- [x] L1 启发式引擎根据关键词自动识别 title/main/chip/hidden 字段角色
- [x] L1 根据是否存在 main 字段自动选择 note/compact/tight 布局
- [x] L2 用户覆盖优先于 L1 启发式，display_role 非 auto 时覆盖自动判断
- [x] L3 模板预设根据 card_template 切换卡片 CSS 样式（clean/paper/minimal/bold/metric）
- [x] 布局引擎对同一条记录在不同数据下可能选择不同布局（内容长度驱动）
- [x] **正文（main）支持多个叠加**：所有配置为 main 且非空的字段按字段顺序依次渲染为段落
- [x] **空字段过滤**：无论字段配置为什么角色，值为空（空字符串/纯空白/null/undefined）时不渲染
- [x] **Title fallback**：配置为 title 的字段为空时，自动取第一个非空 title 候选作为标题，其余降级为 chip
- [x] 基于 field_key 哈希的确定性字段着色（同一字段始终同一颜色）

### 前端视图

- [x] 类型列表页（TypeListView）：卡片网格展示所有类型
- [x] 创建类型页（CreateTypeView）：动态字段表单，可添加/删除字段行
- [x] 类型详情页（TypeDetailView）：三个 Tab（卡片视图/表格视图/模板对比）
- [x] 卡片视图：EntryCard 自适应渲染，按日期分组
- [x] 表格视图：传统 HTML 表格展示，列=字段，行=记录
- [x] 模板对比视图：5 套模板并排预览同一条数据，一键应用
- [x] ChatPanel AI 侧边栏：右下角浮动按钮切换，大屏响应式右边距

### AI 工具

- [x] list_custom_record_types：列出所有类型及字段定义
- [x] create_custom_record_type：创建新类型，slug/field_key 校验失败返回结构化错误
- [x] create_custom_record_entry：录入记录，field_key 错误返回 valid_fields 引导重试
- [x] query_custom_record_entries：按日期范围查询记录，支持 limit 控制返回条数
- [x] AI Tool 直接调用 Repository 层（绕过 Service），返回 SUCCESS/ERROR 前缀字符串

## Technical Contract

### API 层

<key_function>
- lifeprism/server/api/custom_records_api.py
  - custom_records_api.get_custom_record_types:30
  - custom_records_api.create_custom_record_type:38
  - custom_records_api.get_custom_record_type:50
  - custom_records_api.delete_custom_record_type:58
  - custom_records_api.update_custom_record_type_config:67
  - custom_records_api.update_custom_record_field_role:80
  - custom_records_api.get_custom_record_entries:99
  - custom_records_api.create_custom_record_entry:122
  - custom_records_api.delete_custom_record_entry:140
</key_function>

### Service 层

<key_function>
- lifeprism/server/services/custom_records_service.py
  - custom_records_service.get_types:64
  - custom_records_service.get_type:71
  - custom_records_service.create_type:83
  - custom_records_service.delete_type:101
  - custom_records_service.get_entries:113
  - custom_records_service.create_entry:139
  - custom_records_service.delete_entry:152
  - custom_records_service.update_type_config:164
  - custom_records_service.update_field_role:181
</key_function>

### Repository 层

<key_function>
- lifeprism/repository/aggregators/custom_record_aggregator.py
  - custom_record_aggregator.CustomRecordRepository.create_type:53
  - custom_record_aggregator.CustomRecordRepository.list_types:227
  - custom_record_aggregator.CustomRecordRepository.get_type_by_id:250
  - custom_record_aggregator.CustomRecordRepository.delete_type:290
  - custom_record_aggregator.CustomRecordRepository.create_entry:343
  - custom_record_aggregator.CustomRecordRepository.query_entries:413
  - custom_record_aggregator.CustomRecordRepository.delete_entry:510
  - custom_record_aggregator.CustomRecordRepository.update_type_config:560
  - custom_record_aggregator.CustomRecordRepository.update_field_role:627
</key_function>

### LLM Tool 层

<key_function>
- lifeprism/llm/agent/tools/custom_records_tool.py
  - custom_records_tool.ListCustomRecordTypesTool.execute:41
  - custom_records_tool.CreateCustomRecordTypeTool.execute:115
  - custom_records_tool.CreateCustomRecordEntryTool.execute:174
  - custom_records_tool.QueryCustomRecordEntriesTool.execute:243
</key_function>

### 前端核心

<key_function>
- frontend/apps/custom-records/utils/cardLayoutEngine.ts
  - cardLayoutEngine.analyzeCardLayout:100
- frontend/apps/custom-records/utils/templatePresets.ts
  - templatePresets.getTemplatePreset:79
- frontend/apps/custom-records/components/EntryCard.tsx
  - EntryCard:34
</key_function>

### 数据模型

#### Meta 表：`custom_record_types`（记录类型元数据）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK, NOT NULL | `crt-{uuid[:8]}` |
| name | TEXT | NOT NULL | 显示名（如"体育活动"） |
| slug | TEXT | NOT NULL, UNIQUE | 表名后缀（如 `sport`），实际表名 `custom_sport` |
| description | TEXT | - | 描述，给 AI 看 |
| card_template | TEXT | NOT NULL, DEFAULT 'clean' | 卡片模板（clean/paper/minimal/bold/metric） |
| icon | TEXT | NOT NULL, DEFAULT 'fileText' | 图标名 |
| accent_color | TEXT | NOT NULL, DEFAULT 'blue' | 强调色 |
| created_at | TEXT | 自动 | 创建时间 |
| updated_at | TEXT | 自动 | 更新时间 |

#### Meta 表：`custom_record_fields`（字段定义元数据）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK, NOT NULL | `crf-{uuid[:8]}` |
| type_id | TEXT | FK → custom_record_types.id | 关联类型 |
| field_name | TEXT | NOT NULL | 显示名（如"锻炼内容"） |
| field_key | TEXT | NOT NULL | 列名（如 `exercise_content`），正则 `^[a-z][a-z0-9_]*$` |
| field_type | TEXT | NOT NULL | P1 仅 `text`，保留 `number`/`date` 枚举位 |
| sort_order | INTEGER | NOT NULL, DEFAULT 0 | 列顺序 |
| display_role | TEXT | NOT NULL, DEFAULT 'auto' | 展示角色（auto/title/main/chip/hidden），属展示配置可变 |
| created_at | TEXT | 自动 | 创建时间 |

**约束**：`(type_id, field_key)` 联合唯一，防止同类型内列名重复。

> **display_role 不违反"字段定义后不可变"约束**：`field_key`/`field_type`/`field_name` 等结构定义一旦创建不可修改，而 `display_role` 属于展示层配置（决定字段在卡片中的渲染角色），与数据结构无关，用户可随时通过 PATCH 端点调整。

#### 动态数据表：`custom_<slug>`

DDL 由 meta 表定义驱动动态生成：

```sql
CREATE TABLE IF NOT EXISTS custom_<slug> (
    id TEXT PRIMARY KEY NOT NULL,
    <field_key_1> TEXT,
    <field_key_2> TEXT,
    ...
    created_at TEXT,
    updated_at TEXT
)
```

- 表名由 `custom_` 前缀 + slug 拼接（如 `custom_sport`）
- 每个字段一列，类型均为 TEXT（P1）
- 记录 ID 格式：`cre-{uuid[:8]}`
- 不在 `TABLE_CONFIGS` 中注册（完全动态，由 CustomRecordRepository 管理）

### API 端点

路由前缀：`/api/v2/custom-records`

共 9 个端点，覆盖类型 CRUD + 记录 CRUD + PATCH 配置 + PATCH 字段角色：

| # | 方法 | 路径 | 说明 | 状态码 |
|---|------|------|------|--------|
| 1 | GET | `/types` | 获取所有类型列表（含字段定义） | 200 |
| 2 | POST | `/types` | 创建记录类型（含字段定义 + 动态建表） | 201 / 409(slug冲突) / 422(格式错误) |
| 3 | GET | `/types/{type_id}` | 获取单个类型详情（含字段定义） | 200 / 404 |
| 4 | DELETE | `/types/{type_id}` | 硬删类型（DROP 表 + 删 meta） | 200 / 404 |
| 5 | PATCH | `/types/{type_id}` | 更新类型展示配置（card_template/icon/accent_color） | 200 / 404 |
| 6 | PATCH | `/types/{type_id}/fields/{field_id}` | 更新字段展示角色（display_role） | 200 / 404 |
| 7 | GET | `/{type_id}/entries` | 查询记录（日期筛选 + 分页） | 200 / 404 |
| 8 | POST | `/{type_id}/entries` | 录入记录 | 201 / 404 / 422(field_key错误) |
| 9 | DELETE | `/{type_id}/entries/{entry_id}` | 删除单条记录 | 200 / 404 |

#### Request/Response Schemas

**FieldDefinition**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 否 | 字段 ID（`crf-{uuid[:8]}`），创建时为空 |
| field_name | string | 是 | 字段显示名 |
| field_key | string | 是 | 列名，正则 `^[a-z][a-z0-9_]*$` |
| field_type | string | 否 | 字段类型，默认 `text` |
| display_role | enum | 否 | `auto`/`title`/`main`/`chip`/`hidden`，默认 `auto` |

**CustomRecordTypeItem**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 类型 ID |
| name | string | 类型显示名 |
| slug | string | 语义化标识 |
| description | string | 类型描述 |
| fields | FieldDefinition[] | 字段定义列表 |
| card_template | enum | `clean`/`paper`/`minimal`/`bold`/`metric`，默认 `clean` |
| icon | string | 图标名，默认 `fileText` |
| accent_color | string | 强调色，默认 `blue` |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |

**CreateCustomRecordTypeRequest**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| name | string | 是 | 类型显示名（min_length=1） |
| slug | string | 是 | 语义化标识（min_length=1） |
| fields | FieldDefinition[] | 是 | 字段定义列表（min_length=1） |
| description | string | 否 | 类型描述 |

**CreateCustomRecordEntryRequest**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| data | dict<string, string> | 否 | 字段值字典 `{field_key: value}`，允许空字典 |

**CustomRecordEntryItem**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 记录 ID |
| created_at | string | 创建时间 |
| updated_at | string | 更新时间 |
| [field_key] | string | 动态字段（model_config extra=allow） |

**CustomRecordEntryListResponse**

| 字段 | 类型 | 说明 |
|------|------|------|
| items | CustomRecordEntryItem[] | 当前页记录列表 |
| total | int | 满足筛选条件的总记录数（用于分页计算） |

**UpdateTypeConfigRequest**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| card_template | enum | 否 | `clean`/`paper`/`minimal`/`bold`/`metric` |
| icon | string | 否 | 图标名 |
| accent_color | string | 否 | 强调色 |

**UpdateFieldRoleRequest**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| display_role | enum | 是 | `auto`/`title`/`main`/`chip`/`hidden` |

### LLM Tool 契约

| Tool 名 | 参数 | 返回 | 说明 |
|---------|------|------|------|
| `list_custom_record_types` | 无 | 类型列表 JSON | 列出所有类型及字段定义 |
| `create_custom_record_type` | name, slug, fields[], description? | `SUCCESS {type_id, name, slug}` / `ERROR ...` | 创建类型，校验失败返回结构化错误 |
| `create_custom_record_entry` | type_id, data{} | `SUCCESS {entry_id, type_id}` / `ERROR ...` | 录入记录，field_key 错误返回 valid_fields 引导重试 |
| `query_custom_record_entries` | type_id, date_range?, limit? | 记录列表 JSON | 查询记录，按 created_at 倒序，AI 场景默认 50 条 |

> **Tool 返回格式**：所有 Tool 的 `execute()` 返回字符串，以 `SUCCESS` 或 `ERROR` 前缀标识结果状态。错误时返回结构化 JSON 供 Agent 解析重试。

### 布局引擎设计（L1/L2/L3）

自定义记录的卡片展示采用三层布局引擎，从数据结构到视觉呈现逐层细化：

#### L1 启发式引擎（自动布局选择）

**输入**：字段定义列表 + 单条记录数据 + L2 overrides
**输出**：布局模式（note/compact/tight）+ 字段角色分配结果

**字段角色识别优先级**（在 L2 未覆盖时）：

1. **空值过滤**（最优先）：值为空字符串、纯空白、null、undefined 的字段直接跳过，不参与任何角色分配
2. **关键词匹配**：
   - TITLE 关键词：`title`/`name`/`book_name`/`movie_name`/`game`/`place`/`destination`/`dream_theme`/`标题`/`名称`/`书名`/`片名`/`游戏`/`地点`/`目的地` → 角色为 `title`
   - MAIN 关键词：`note`/`review`/`content`/`desc`/`description`/`text`/`detail`/`body`/`diary`/`log`/`dream`/`thought`/`feeling`/`笔记`/`评论`/`内容`/`描述`/`正文`/`日记`/`日志`/`感想`/`感受`/`详情` → 角色为 `main`
   - HIDDEN 关键词：`id`/`created_at`/`updated_at`/`slug`/`type_id` → 角色为 `hidden`
3. **内容长度启发**（关键词未命中时）：
   - value 长度 > 25 → `main`
   - value 长度 <= 20 → `chip`
   - 20-25 → `main`

**角色分配规则**：

| 角色 | 数量规则 | 渲染方式 |
|------|---------|---------|
| `title` | 有且仅有一个：第一个非空 title 候选成为标题，其余降级为 chip | 卡片标题（h3） |
| `main` | **支持多个叠加**：所有非空 main 字段按字段顺序依次收集 | 每个字段渲染为独立段落（p） |
| `chip` | 无数量限制 | 标签/胶囊或键值对 |
| `hidden` | 不渲染 | 完全隐藏 |

**Title fallback 机制**：若用户指定的 title 字段（L2 override）或关键词匹配的 title 字段值为空，引擎自动选取第一个非空的 title 候选字段作为标题；若所有 title 候选均为空，则不渲染标题区域。

**布局模式决策**：

| 条件 | 布局模式 | 渲染方式 |
|------|---------|---------|
| mains[] 非空（至少一个正文） | `note` | 标题 + 多个正文段落（依次排列） + chips 标签区 |
| mains[] 为空，chips 全短（<12 字） | `tight` | 纯标签云 |
| mains[] 为空，有中长字段 | `compact` | 键值对列表（字段名: 值） |

#### L2 用户覆盖（字段角色手动指定）

用户可通过 PATCH 端点或 FieldRoleModal 为每个字段手动指定 `display_role`，**优先于 L1 启发式判断**。

| display_role | 含义 | 覆盖效果 |
|-------------|------|---------|
| `auto` | 使用 L1 启发式自动判断（默认） | 不覆盖 |
| `title` | 字段作为标题展示 | 覆盖 L1，参与 title 候选竞争 |
| `main` | 字段作为主要内容展示 | 覆盖 L1，加入 mains[] 数组 |
| `chip` | 字段作为标签/胶囊展示 | 覆盖 L1 |
| `hidden` | 字段隐藏不展示 | 覆盖 L1 |

**优先级规则**：空值过滤 > L2 覆盖 > L1 关键词匹配 > L1 内容长度启发

**覆盖传递**：`display_role` 非 `auto` 时，布局引擎跳过 L1 的关键词和长度判断，直接使用用户指定角色。但空值过滤始终生效（即使字段被配置为 title/main，值为空时仍不渲染）。布局模式仍由最终角色分配结果决定（mains[] 是否为空）。

#### L3 模板预设（视觉风格切换）

用户可通过 PATCH 端点或模板对比视图为类型指定 `card_template`，切换卡片的 CSS 样式预设。

| 模板 ID | 名称 | 视觉风格 | 适用场景 |
|---------|------|---------|---------|
| `clean` | 简洁 | 白底卡片，cyan 强调条 | 默认，大多数场景 |
| `paper` | 纸张 | 暖色调纸张质感，amber 强调 | 笔记、日记 |
| `minimal` | 极简 | 无边框纯文字，slate 强调 | 克制展示 |
| `bold` | 粗体 | 强对比大字标题，slate-800 边框 | 展示型数据 |
| `metric` | 数据 | 深色底 + 等宽字体，cyan-400 强调 | 数值、指标 |

**模板与布局的关系**：L3 模板控制视觉样式（颜色/字体/边框/阴影），L1/L2 控制内容布局（哪些字段当标题/正文/标签）。两者正交，可自由组合（5 模板 × 3 布局 = 15 种渲染形态）。

**代码位置**：
- L1 + L2 引擎：`frontend/apps/custom-records/utils/cardLayoutEngine.ts` → `analyzeCardLayout()`
- L3 模板预设：`frontend/apps/custom-records/utils/templatePresets.ts` → `getTemplatePreset()`
- 卡片渲染：`frontend/apps/custom-records/components/EntryCard.tsx`

## Design Rationale

**为什么用 meta 表驱动而非 JSON 文件？**

AI 持续录入场景下，写入频繁且需要稳定的 tool 契约。DB 有索引支持按日期查询，JSON 必须全量加载。JSON 唯一优势"本地可编辑"在 AI 录入入口下不存在。详见 [ADR](../adr/2026-07-06-custom-records-storage.md)。

**为什么 CustomRecordRepository 独立实现，不继承 LWBaseDataProvider？**

动态表名 `custom_<slug>` 运行时才确定，无法在类定义时写死 `_TABLE_NAME`。同一个 Repository 实例需操作多张动态表，且涉及 DDL（CREATE/DROP TABLE），超出了 LWBaseDataProvider 的静态 CRUD 模板能力。详见 [ADR 实现偏差说明](../adr/2026-07-06-custom-records-storage.md#实现偏差说明)。

**为什么 P1 不支持 Schema 演进？**

字段定义后不可变，要改只能新建类型 + 硬删旧类型。大幅简化 P1 实现：不需要 ALTER TABLE、不需要处理旧记录新字段为 NULL 的兼容。未来若需支持演进，可单独设计迁移机制。

**为什么 AI 无删除工具？**

删除是破坏性操作，AI 误调用风险高。用户走前端手动删除，prompt 中写明流程即可。AI 仅拥有创建类型、写入记录、查询记录、列出类型四类工具。

**为什么 display_role 可变但不违反"字段定义后不可变"？**

`display_role` 属于展示层配置，决定字段在卡片中的渲染角色，与数据结构（`field_key`/`field_type`/`field_name`）无关。修改 display_role 不影响已存储数据的完整性，只是改变展示方式。

**为什么正文（main）支持多个叠加？**

用户的记录内容往往包含多个正文性质的字段（如"感想"+"感受"、"优点"+"缺点"、"正文"+"补充说明"），将它们合并为单个正文会丢失语义结构，而全部降级为标签又失去可读性。多正文叠加允许每个正文段落独立呈现，同时保留字段间的语义区分。

**为什么空字段无论什么角色都不渲染？**

用户可能创建了多个字段但某次记录只填了部分字段，如果空字段仍以标签或占位符形式渲染，会产生视觉噪音（空方框、`—` 占位符）。空值过滤是展示层的通用规则，不影响上层角色配置——配置决定"有值时在哪里显示"，空值过滤决定"没值时不显示"，两者职责分离不冲突。

**为什么 LLM Tool 绕过 Service 层直接调用 Repository？**

Service 层依赖 Pydantic schema 做参数校验和响应转换，而 Tool 层需要灵活的字符串返回格式（SUCCESS/ERROR 前缀 + JSON），且 Tool 注册在 Agent 模块中，直接依赖 Service 会形成循环引用（server → llm → server）。Tool 层自行处理参数校验和错误格式化，与 Service 层共享 Repository 作为唯一数据访问入口。

**相关 ADR**：
- [自定义记录模块存储方案决策](../adr/2026-07-06-custom-records-storage.md)

## Interaction / UX Notes

### 前端模块结构

自定义记录前端位于 `frontend/apps/custom-records/`，作为顶级 app 与 lifewatch/goals/habits/mindspace 同级。

```
custom-records/
├── CustomRecordsApp.tsx      # 入口：状态驱动视图切换 + ChatPanel 集成
├── api.ts                    # 后端 API 封装
├── types.ts                  # TypeScript 类型定义
├── api.test.ts               # API 层测试
├── components/
│   ├── TypeListView.tsx      # 类型列表页（卡片网格）
│   ├── CreateTypeView.tsx    # 创建类型页（动态字段表单）
│   ├── TypeDetailView.tsx    # 类型详情页（3 Tab + 筛选 + 配置）
│   ├── EntryCard.tsx         # 自适应卡片组件
│   ├── FieldRoleModal.tsx    # 字段角色配置弹窗
│   └── TemplatePicker.tsx    # 模板选择器
└── utils/
    ├── cardLayoutEngine.ts   # L1+L2 布局引擎
    ├── cardLayoutEngine.test.ts
    ├── templatePresets.ts    # L3 模板预设
    ├── templatePresets.test.ts
    ├── fieldColors.ts        # 字段确定性着色
    └── fieldColors.test.ts
```

### 卡片渲染流程

```
类型配置 (card_template)          字段定义 (display_role)
  ↓                                 ↓
L3 模板预设                        L2 用户覆盖
  ↓                                 ↓
getTemplatePreset(templateId)      overrides[field_key] = display_role
  ↓                                 ↓
  CSS 类名                          字段角色映射
  ↓                                 ↓
  ┌─────────────────────────────────┐
  │     analyzeCardLayout(          │
  │       fields, data, overrides   │  ← L1 启发式引擎
  │     )                           │    （空值过滤 → 角色分配 → 布局决策）
  └─────────────────────────────────┘
  ↓
  { layout, title, mains[], chips[] }
  ↓
  EntryCard 组件根据 layout + template 渲染
  ├─ note 模式：title + mains.map(段落) + chips
  ├─ compact 模式：title + 键值对列表
  └─ tight 模式：纯标签云
```

### 视图导航

```
TypeListView（类型列表）
  ├─ 点击"新建类型" → CreateTypeView
  ├─ 点击类型卡片 → TypeDetailView
  └─ 右下角浮动按钮 → ChatPanel（AI 侧边栏）

CreateTypeView（创建类型）
  └─ 提交成功 → 返回 TypeListView（强制刷新）

TypeDetailView（类型详情）
  ├─ Tab 1: 卡片视图（默认）→ 按日期分组 + EntryCard 渲染
  ├─ Tab 2: 表格视图 → HTML 表格，列=字段
  └─ Tab 3: 模板对比 → 5 套模板并排预览 + 一键应用
```

### 类型列表页

- 响应式卡片网格（1-3 列），每张卡片显示：类型名、slug、字段数量 chip、创建日期、字段名标签
- 右上角删除按钮（hover 显示）+ 删除确认弹窗（不可撤销警告）
- 空状态引导文案 + 新建按钮
- 右下角浮动 AI 按钮（MessageCircle 图标）

### 创建类型页

- 动态字段表单：可添加/删除字段行，至少保留 1 个
- 每个字段行：显示名（中文）+ field_key（英文标识，自动从显示名生成建议）+ 类型下拉（目前只有"文本"）
- 前端校验：name/slug 非空、slug/field_key 正则校验、field_key 不重复
- 提交后回列表并通过 refreshKey 强制刷新

### 类型详情页

- 顶部并行加载类型详情和记录数据（`Promise.all`）
- 日期范围筛选器 + 分页（每页 20 条，滚动加载或翻页）
- **卡片视图**（默认 Tab）：按日期分组（今天/昨天/前天/M月D日），EntryCard 渲染
- **表格视图**：传统 HTML 表格，每列一个字段，每行一条记录，支持删除
- **模板对比视图**：取第一条记录数据，5 套模板（clean/paper/minimal/bold/metric）并排渲染，点击"应用"切换模板
- 模板切换带 600ms debounce 自动保存，顶部显示"保存中..."/"已保存"状态
- 字段角色配置：点击"配置角色"按钮弹出 FieldRoleModal
- FieldRoleModal：每个字段一行，5 个角色选项（自动/标题/正文/标签/隐藏），本地乐观更新 + 后端持久化，失败回滚
- 字段 chips 展示：非 auto 角色的字段显示角色标签

### ChatPanel AI 集成

- 右下角浮动 MessageCircle 按钮切换 ChatPanel 显示/隐藏
- ChatPanel 以 sidebar 模式显示在右侧
- 大屏（≥1024px）时主内容区自动添加 `marginRight` 为 ChatPanel 留出空间
- 用户通过自然语言与 AI 对话，AI 可调用 4 个 custom_records tool 完成：
  - 列出已有类型和字段定义
  - 创建新记录类型
  - 录入新记录（解析自然语言为字段值）
  - 查询已有记录
- AI 录入时 field_key 错误会收到 valid_fields 反馈，可自动纠正重试

### AI 对话录入流程

1. 用户："我想记录体育活动，字段是日期和锻炼内容"
2. AI 调用 `create_custom_record_type` 创建类型
3. 用户："今天跑了5公里"
4. AI 调用 `list_custom_record_types` 确认字段定义
5. AI 解析为 `{exercise_date: "2026-07-07", exercise_content: "跑步5公里"}`
6. AI 在对话内输出解析结果（不存中间 draft）
7. 用户确认或修改
8. AI 调用 `create_custom_record_entry` 落库

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **存储方案决策**：[ADR](../adr/2026-07-06-custom-records-storage.md) - 存储引擎选择、动态建表流程、删除策略的架构决策
- **Repository 基础设施**：[repository-core-spec](2026-07-06-repository-core-spec.md) - DatabaseManager、LWBaseDataProvider、连接池
- **LLM Agent 工具系统**：[llm-agent-spec](2026-07-06-llm-agent-spec.md) - Tool 注册、安全沙箱、AgentLoop
- **LLM Tool 执行流程**：[llm-tool-execution-flow](../flows/2026-07-06-llm-tool-execution-flow.md) - Tool 通用执行路径、参数校验、错误反馈
- **数据同步**：sync_repository 动态表同步机制 - 自定义记录动态表通过 sync_client 白名单 + 运行时 slug 查询进行同步
- **心情模块（近亲模块）**：[mood-module-spec](2026-05-20-mood-module-spec.md) - 用户自定义类型 + CRUD + 日期查询（静态 schema 版）
