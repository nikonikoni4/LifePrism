---
version: 1.0
created_at: 2026-05-20
updated_at: 2026-05-20
last_updated: 创建心情模块 spec 初稿
abstract: >
  心情模块规格文档。定义 Mind Space 中心情追踪系统的核心功能，包括心情类型管理、
  心情记录 CRUD、影响因素管理。本模块为独立模块，不依赖其他业务模块。
id: mood-module-spec
title: 心情模块
status: draft
module: lifeprism/server/services/mood_service, lifeprism/server/api/mood_api
sourc_spec: ""
related_plan: ""
code_scope:
  - lifeprism/server/api/mood_api.py
  - lifeprism/server/services/mood_service.py
  - lifeprism/server/schemas/mood_schemas.py
  - lifeprism/repository/mood_repository.py
contract_refs:
  - lifeprism/server/schemas/mood_schemas.py
  - lifeprism/server/api/mood_api.py
  - lifeprism/config/database.py
---

# 心情模块

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

心情模块是 Mind Space 的核心子模块之一，提供心情状态的记录与追踪功能。用户可以通过选择预设或自定义的心情类型来记录当前心情状态，并添加文字描述和影响因素标签。

本模块采用独立设计，不依赖其他业务模块（如分类、Goal 等），数据完全自包含。

## Scope

**在范围内：**

- 心情类型（Mood Types）的 CRUD 管理
- 心情记录（Mood Entries）的 CRUD 管理
- 影响因素（Mood Impacts）的管理
- 按日期范围查询心情记录

**不在范围内：**

- 心情数据的统计分析与可视化展示
- 心情与日记（Diary）的关联逻辑
- 心情与行为数据的关联分析
- AI 对心情数据的分析与总结

## Core Behavior

### 1. 心情类型管理

心情类型定义了用户可选择的心情状态，每种类型包含以下属性：

- **名称**：心情的语义标签（如"喜悦"、"宁静"），最长 4 字符
- **图标**：Lucide 图标库中的图标名
- **颜色**：十六进制颜色值，用于前端展示
- **评分**：0-100 的数值，用于心情趋势图的 Y 轴计算
- **深色标识**：是否为深色主题（影响前端文字颜色）
- **排序权重**：控制在列表中的展示顺序

#### 1.1 预设类型与自定义类型

- 系统预设的心情类型使用固定 ID（如 `joy`, `calm`）
- 用户自定义的心情类型使用 `mood-type-{uuid[:8]}` 格式的 ID
- 自定义类型与预设类型享有相同的管理能力

#### 1.2 删除约束

- 删除心情类型前，需检查是否有关联的心情记录
- 若存在关联记录，禁止删除并返回关联记录数量
- 若无关联记录，允许删除

### 2. 心情记录管理

心情记录是用户在特定时间点的心情快照。

#### 2.1 记录结构

每条心情记录包含：
- 关联的心情类型（决定评分）
- 用户输入的文字内容（可选）
- 影响因素标签列表（可选）

#### 2.2 评分自动获取

创建或更新心情记录时，评分从关联的心情类型自动获取，无需用户手动输入。

#### 2.3 查询能力

- 支持按日期范围过滤（start_date, end_date）
- 返回结果按创建时间排序

### 3. 影响因素管理

影响因素是用于标记心情成因的标签（如"工作"、"健康"、"社交"）。

#### 3.1 唯一性约束

- 影响因素名称全局唯一
- 创建时若名称已存在，返回错误

#### 3.2 排序权重

- 通过 sort_order 控制展示顺序
- 数值越大越靠前

## Technical Contract

### 数据库表结构

#### mood_types（心情类型表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY, NOT NULL | 心情类型 ID，预设用固定 id，自定义用 mood-type-{uuid[:8]} |
| name | TEXT | NOT NULL | 心情名称，最长 4 字符 |
| icon | TEXT | NOT NULL | Lucide 图标名 |
| color | TEXT | NOT NULL | 十六进制颜色值 |
| score | INTEGER | NOT NULL | 心情评分权重 0-100 |
| is_dark | INTEGER | NOT NULL, DEFAULT 0 | 是否深色主题 |
| sort_order | INTEGER | NOT NULL, DEFAULT 0 | 排序权重，越大越靠前 |
| created_at | TEXT | 自动添加 | 创建时间 |

#### mood_entries（心情记录表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PRIMARY KEY, NOT NULL | 心情记录 ID，格式 mood-{uuid[:8]} |
| mood_type_id | TEXT | NOT NULL | 关联 mood_types.id |
| score | INTEGER | NOT NULL | 心情评分（冗余存储，取自 mood_type 的 score） |
| content | TEXT | - | 用户输入的文字内容 |
| factors | TEXT | - | JSON 数组，影响因素标签列表 |
| created_at | TEXT | 自动添加 | 创建时间 |

#### mood_impacts（影响因素表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 自增 ID |
| name | TEXT | NOT NULL, UNIQUE | 因素名称 |
| sort_order | INTEGER | NOT NULL, DEFAULT 0 | 排序权重 |
| created_at | TEXT | 自动添加 | 创建时间 |

### API 契约

#### 心情类型接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/mood/types` | 获取所有心情类型列表 |
| POST | `/mood/types` | 创建心情类型 |
| PATCH | `/mood/types/{mood_type_id}` | 更新心情类型（部分更新） |
| DELETE | `/mood/types/{mood_type_id}` | 删除心情类型 |

**创建心情类型请求体：**

```json
{
  "name": "string (1-4字符)",
  "icon": "string (Lucide图标名)",
  "color": "string (十六进制颜色)",
  "score": "integer (0-100)",
  "is_dark": "integer (0或1)",
  "sort_order": "integer"
}
```

**删除心情类型错误响应：**

- 400: 该心情类型下有 N 条记录，无法删除

#### 影响因素接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/mood/impacts` | 获取所有影响因素列表 |
| POST | `/mood/impacts` | 创建影响因素 |
| DELETE | `/mood/impacts/{impact_id}` | 删除影响因素 |

**创建影响因素请求体：**

```json
{
  "name": "string",
  "sort_order": "integer"
}
```

**创建影响因素错误响应：**

- 400: 影响因素名称已存在

#### 心情记录接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/mood/entries` | 获取心情记录列表（支持日期过滤） |
| GET | `/mood/entries/{entry_id}` | 获取单条心情记录 |
| POST | `/mood/entries` | 创建心情记录 |
| PATCH | `/mood/entries/{entry_id}` | 更新心情记录（部分更新） |
| DELETE | `/mood/entries/{entry_id}` | 删除心情记录 |

**查询参数：**

- `start_date` (可选): 开始日期 YYYY-MM-DD
- `end_date` (可选): 结束日期 YYYY-MM-DD

**创建心情记录请求体：**

```json
{
  "mood_type_id": "string",
  "content": "string (可选)",
  "factors": ["string"] // 可选，影响因素标签列表
}
```

**创建心情记录错误响应：**

- 400: 无效的心情类型 ID

### 业务规则

#### 评分同步规则

- 创建心情记录时，score 从 mood_types 表自动获取
- 更新心情记录的 mood_type_id 时，score 同步更新
- score 字段在 API 请求中不可直接设置

#### 删除级联规则

- 删除心情类型：检查 mood_entries 是否有引用，有则禁止删除
- 删除心情记录：直接删除，无级联影响
- 删除影响因素：直接删除，不影响已记录的 factors 标签

## Acceptance Notes

- [ ] 心情类型支持 CRUD 操作，名称限制 4 字符
- [ ] 创建心情记录时自动从 mood_type 获取 score
- [ ] 更新心情记录的 mood_type_id 时 score 同步更新
- [ ] 删除心情类型时检查关联记录，有记录则禁止删除
- [ ] 影响因素名称全局唯一，重复创建返回错误
- [ ] 心情记录支持按日期范围过滤查询
- [ ] factors 字段以 JSON 数组格式存储和返回

## Out of Spec

- 心情数据的统计分析与图表展示（属于 report 模块）
- 心情与日记的关联逻辑（属于 Mind Space 整合层）
- 心情趋势的 AI 分析与建议
- 心情数据的导出功能
