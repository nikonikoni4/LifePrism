---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 从旧 PRD 迁移为正式 spec
abstract: Mind Space 日记界面功能规格，定义日记的存储、API 契约、前端交互设计和模板管理机制
id: mind-space-diary
title: Mind Space 日记界面
status: unstable
module: mind_space/diary
sourc_spec: D:\desktop\软件开发\liferpism多余文档\docs_old\prd\功能需求\mind space\日记界面.md
related_plan: null
code_scope:
  - lifeprism/server/api/diary_api.py
  - lifeprism/server/services/diary_service.py
  - lifeprism/server/providers/diary_provider.py
  - lifeprism/server/schemas/diary_schemas.py
  - lifeprism/config/database.py (DIARY_CONFIG)
contract_refs:
  - lifeprism/server/api/diary_api.py
  - lifeprism/server/schemas/diary_schemas.py
  - lifeprism/config/database.py (DIARY_CONFIG)
---

# Mind Space 日记界面

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 从旧 PRD 迁移为正式 spec，核对代码实现 |

## Overview

日记界面是 Mind Space 模块的核心功能之一，作为用户心理数据的重要来源。用户通过日记记录每日生活、情绪和事件，系统通过心情标签、重要程度标签和自定义标签对日记进行结构化标注，为后续 AI 分析提供数据基础。

核心特性：
- 日记内容以 Markdown 格式存储在文件系统
- 元数据（心情、重要程度、标签等）存储在数据库
- 支持模板系统，用户可创建和管理日记模板
- 提供日历视图所需的日记列表和字数统计

## Scope

本 spec 覆盖：
1. 日记的存储机制（文件 + 数据库混合存储）
2. 日记 CRUD API 契约
3. 日记 AI 总结手动生成 API 契约
4. 模板管理 API 契约
5. 心情和重要程度的枚举值、颜色方案
6. 前端交互设计原则和 UI 组件规格

本 spec 不覆盖：
- 前端具体实现细节（组件树、文件路径）
- 数据插入功能（待办事项、分类数据插入）
- 水墨抽象图样（后续视觉迭代）

## Core Behavior

### 存储机制

**文件存储：**
- 日记内容以 Markdown 格式存储
- 路径结构：`lifeprismData/diary/YYYY/MM/YYYY-MM-DD.md`
- 模板路径：`lifeprismData/diary/template/{name}.md`
- 开发环境：`localData/diary/`

**数据库存储：**
- 仅存储元数据（meta）：日期、心情、重要程度、自定义标签、字数、AI 总结、时间戳
- 日期（YYYY-MM-DD）作为主键
- `custom_tags` 以 JSON 数组格式存储

### 日记生命周期

1. **创建**：用户选择日期后，系统自动创建数据库记录和空 md 文件（若不存在）
2. **编辑**：用户编辑 md 内容，保存时更新文件并同步 `word_count` 到数据库
3. **标注**：用户可随时更新心情、重要程度、自定义标签（独立于内容保存）
4. **查询**：支持单日查询（meta + content）和日期范围查询（仅 meta，用于日历视图）

### 心情标签

5 个等级，冷→暖渐变色系：

| 枚举值 | 标签文本 | 颜色（十六进制） | 语义 |
|--------|---------|-----------------|------|
| `very_bad` | 非常不好 | `#5B6B8A` | 深灰蓝 |
| `bad` | 不太好 | `#8B9DC3` | 雾蓝 |
| `calm` | 平静 | `#A8C4C2` | 青灰 |
| `happy` | 有点开心 | `#B5D89A` | 暖绿 |
| `very_happy` | 非常愉悦 | `#E8C170` | 琥珀 |

### 重要程度标签

3 个等级，表示当日是否发生非平凡事件：

| 枚举值 | 标签文本 | 颜色（十六进制） | 语义 |
|--------|---------|-----------------|------|
| `unimportant` | 平凡 | `#C8C8C8` | 浅灰 |
| `normal` | 一般 | `#B0A08A` | 灰棕 |
| `important` | 重要 | `#C4956A` | 赤金 |

注：重要程度指"是否发生非平凡事件"，而非评价每天的价值。

### 自定义标签

- 用户可添加任意文本标签（如"读书"、"运动"）
- 以 JSON 数组格式存储在数据库
- 前端显示为中性样式（浅灰背景 + 深灰文字），与心情/重要程度标签视觉区分

### 模板系统

- 模板以 `.md` 文件形式存储在 `lifeprismData/diary/template/` 目录
- 文件名即模板名称
- 不经过数据库，直接文件系统操作
- 支持 CRUD 操作

## Technical Contract

### 数据库 Schema

```sql
CREATE TABLE IF NOT EXISTS diary (
    date TEXT PRIMARY KEY NOT NULL,           -- YYYY-MM-DD，唯一标识
    mood TEXT,                                -- 心情: very_happy, happy, calm, bad, very_bad
    importance TEXT,                          -- 平凡程度: important, normal, unimportant
    custom_tags TEXT DEFAULT '[]',            -- 自定义 tag，JSON 数组
    word_count INTEGER DEFAULT 0,             -- 字数统计，用于日历视图展示
    ai_summary TEXT DEFAULT NULL,             -- AI 总结
    created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
    updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime'))
);
```

### API 路由

**路由前缀：** `/diary`

#### 日记 CRUD

| 方法 | 路径 | 说明 | Request Body | Response |
|------|------|------|--------------|----------|
| `GET` | `/diary/{date}` | 获取指定日期日记（meta + content），不存在则自动创建 | - | `DiaryItem` |
| `PATCH` | `/diary/{date}` | 更新日记 meta（心情、重要程度、自定义 tag） | `UpdateDiaryMetaRequest` | `DiaryItem` |
| `PUT` | `/diary/{date}/content` | 保存日记 md 内容，同时更新 word_count | `SaveDiaryContentRequest` | `DiaryItem` |
| `POST` | `/diary/{date}/ai_summary` | 手动生成指定日期日记 AI 总结，成功后覆盖 `ai_summary` | - | `{ content: string }` |
| `GET` | `/diary/list` | 获取日期范围内的日记列表（仅 meta，不含内容） | Query: `start_date`, `end_date` | `DiaryListResponse` |

#### 模板管理

| 方法 | 路径 | 说明 | Request Body | Response |
|------|------|------|--------------|----------|
| `GET` | `/diary/templates` | 获取模板列表（扫描模板目录） | - | `TemplateListResponse` |
| `GET` | `/diary/templates/{name}` | 获取模板内容 | - | `TemplateItem` |
| `POST` | `/diary/templates` | 创建模板 | `CreateTemplateRequest` | `TemplateItem` (201) |
| `PUT` | `/diary/templates/{name}` | 更新模板内容 | `UpdateTemplateRequest` | `TemplateItem` |
| `DELETE` | `/diary/templates/{name}` | 删除模板 | - | `{"message": "..."}` |

### Schema 定义

**DiaryItem（完整日记）：**
```typescript
{
  date: string;              // YYYY-MM-DD
  mood?: string;             // very_happy | happy | calm | bad | very_bad
  importance?: string;       // important | normal | unimportant
  custom_tags: string[];     // 自定义标签数组
  word_count: number;        // 字数统计
  ai_summary?: string;       // AI 总结
  content: string;           // 日记 md 内容
  created_at: string;        // ISO 时间戳
  updated_at?: string;       // ISO 时间戳
}
```

**DiaryMetaItem（仅 meta）：**
```typescript
{
  date: string;
  mood?: string;
  importance?: string;
  custom_tags: string[];
  word_count: number;
  ai_summary?: string;
  created_at: string;
  updated_at?: string;
}
```

**UpdateDiaryMetaRequest：**
```typescript
{
  mood?: string;             // 可选，传 null 清空
  importance?: string;       // 可选，传 null 清空
  custom_tags?: string[];    // 可选，传空数组清空
}
```

**SaveDiaryContentRequest：**
```typescript
{
  content: string;           // 日记 md 内容
}
```

**TemplateItem：**
```typescript
{
  name: string;              // 模板名称（不含 .md）
  content: string;           // 模板内容
}
```

**CreateTemplateRequest：**
```typescript
{
  name: string;              // 模板名称
  content: string;           // 模板内容
}
```

### 路由顺序约束

**关键约束：** `/list` 和 `/templates/*` 路由必须在 `/{date}` 之前注册，否则 FastAPI 会将 "list"/"templates" 误识别为 date 参数。

当前实现已正确处理此约束。

## Interaction / UX Notes

### 设计原则

日记界面遵循 Mind Space 模块的极简和禅意风格，避免过度装饰和复杂交互。

### 核心交互组件

**1. 日期选择器**
- 用户选择日期后，系统自动加载或创建对应日记
- 一个请求完成（`GET /diary/{date}`），无需前端判断存在性

**2. 心情 & 重要程度选择器**
- 入口：日期下方以 tag 形式展示
- 未选择状态：虚线边框 tag `+ 心情` / `+ 重要程度`
- 已选择状态：对应等级彩色背景 + 实线边框 + 文字标签
- 交互：点击弹出滑块选择器弹窗
  - 首次（两个都未选）：点击后先弹心情选择器，确认后自动连续弹出重要程度选择器
  - 已选择状态：点击可重新编辑

**滑块选择器弹窗设计：**
- 中等大小弹窗，居中展示
- 上方：图样区域（当前阶段用对应颜色的色块替代，后续迭代为水墨抽象图样）
- 中间：水平滑块，档位吸附（心情 5 档，重要程度 3 档）
- 下方：当前等级文字标签 + 确认按钮
- 滑块滑动时颜色平滑过渡

**3. 自定义 Tag**
- 位置：日期下方，与心情 tag、重要程度 tag 同行展示
- 样式：中性样式（浅灰背景 + 深灰文字），与心情/重要程度 tag 视觉区分
- 末尾固定一个 `+` 添加按钮（虚线边框 + 浅灰 `+ 标签`）
- 交互：
  - 点击 `+`：弹出 inline 输入框或 popover，输入文字回车添加
  - 点击已有自定义 tag：显示 `×` 删除按钮，点击删除

**4. Markdown 编辑器**
- 复用 `frontend/my-ui-kit/ui-kit/markdownEditor` 组件
- 内容保存独立于 meta 更新（`PUT /diary/{date}/content`）

**5. 设置按钮**
- 位置：底部
- 点击弹出上拉菜单，包含"背景颜色"和"模板管理"两个入口
- 背景颜色：沿用当前已有的颜色选择界面，localStorage 持久化，不走后端

**6. 模板管理界面**
- 入口：设置按钮上拉菜单 →"模板管理"
- 布局：左右分栏（左侧模板列表 + 右侧内容编辑区）
- 左侧：模板列表，顶部标题栏含 `+` 新建按钮
- 右侧：选中模板的内容编辑区，顶部工具栏含模板名称 + 删除按钮
- 交互：
  - 左侧列表：点击切换模板，选中项高亮
  - `+` 按钮：创建新模板，输入模板名后生成空白 .md 文件
  - 删除按钮：删除当前模板（需确认）
  - 编辑区：直接编辑模板 md 内容，自动保存或手动保存

**7. AI 总结卡片**
- 位置：标签栏下方，编辑器上方
- 内容：显示 `ai_summary` 或空状态提示
- 按钮：左上角 `AI 总结`，手动触发生成
- 限制：只读，不可编辑，高度随内容自然撑开

### Tag 显示样式

| 状态 | 样式 |
|------|------|
| 未选择 | 虚线边框 + 浅灰文字（如 `+ 心情`） |
| 已选择（心情/重要程度） | 对应等级颜色浅色背景 + 实线边框 + 文字标签 |
| 已选择（自定义 tag） | 浅灰背景 + 深灰文字 + 实线边框 |

## Acceptance Notes

1. **日记自动创建**：选择任意日期后，系统自动创建数据库记录和空 md 文件（若不存在）
2. **Meta 与内容分离**：心情/重要程度/自定义 tag 的更新不影响 md 内容，反之亦然
3. **字数统计同步**：保存日记内容时，`word_count` 自动更新到数据库
4. **模板文件管理**：模板 CRUD 操作直接操作文件系统，不经过数据库
5. **路由顺序正确**：`/list` 和 `/templates/*` 路由在 `/{date}` 之前注册，避免路径冲突
6. **心情/重要程度枚举值**：前后端严格遵守 `very_happy | happy | calm | bad | very_bad` 和 `important | normal | unimportant`
7. **颜色方案一致性**：前端使用的颜色值与本 spec 定义的颜色方案一致

## Out of Spec

以下内容不在本 spec 长期维护范围：
1. 前端组件树、文件路径、目录结构
2. 具体实现优先级和阶段拆解
3. 水墨抽象图样的 SVG 实现细节（后续视觉迭代）
4. 右侧数据抽屉（待办事项、分类数据插入）的实现细节
5. 前端状态管理、缓存策略等实现细节
