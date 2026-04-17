---
version: 1.0
created_at: 2026-04-16
updated_at: 2026-04-16
last_updated: 从 docs/temp/old_docs/user_guide.md 提取分类管理规格
abstract: >
  分类管理模块规格文档。定义 LifePrism 系统中分类层级的管理规则、Map Cache 映射管理、
  分类状态切换规则、以及 Goal 与分类的绑定机制。本 spec 与 AI 数据分类流程 spec（classify-spec）
  共同构成完整的分类体系：classify-spec 侧重技术实现与 AI 分类管道，本 spec 侧重用户可配置的管理规则。
id: category-spec
title: 分类管理模块
status: draft
module: lifeprism/server/services/category_service, lifeprism/processors/components
sourc_spec: docs/temp/old_docs/user_guide.md
related_plan: ""
code_scope:
  - lifeprism/server/services/category_service.py
  - lifeprism/server/api/category_api.py
  - lifeprism/server/schemas/category_schemas.py
  - lifeprism/processors/components/category_cache.py
  - lifeprism/server/providers/goal_provider.py
contract_refs:
  - lifeprism/server/schemas/category_schemas.py
  - lifeprism/server/api/category_api.py
---

# 分类管理模块

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

分类管理模块负责维护 LifePrism 系统的分类层级结构和应用-分类映射关系。用户通过该模块管理主分类、子分类，配置应用与分类的映射规则（Map Cache），以及绑定 Goal 与分类的关联关系。

整个分类体系分为两层规范：

1. **本 spec（category-spec）**：定义用户可配置的管理规则，包括分类 CRUD、Map Cache 管理、分类状态切换、Goal 绑定
2. **classify-spec**：定义 AI 数据分类的技术实现与分类管道

两者关系：classify-spec 中的分类缓存命中逻辑依赖本 spec 定义的 Map Cache 数据结构；Goal 绑定对 AI 分类的影响也在本 spec 中定义。

## Scope

**在范围内：**

- 主分类与子分类的层级结构管理（CRUD）
- 分类颜色配置规则
- 分类启用/禁用状态及其级联影响
- Map Cache（应用-分类映射）管理界面
- Map Cache 与分类状态的同步规则
- Goal 与分类的绑定及对 AI 分类的优先级影响
- Data Review 数据审核功能

**不在范围内：**

- AI 分类管道的具体实现（见 classify-spec）
- 分类统计数据的计算逻辑
- Goal 的创建与任务管理（见 goals 相关 spec）
- Map Cache 的技术索引结构（见 classify-spec）

## Core Behavior

### 1. 分类层级结构

分类系统采用两级层级结构：

```
主分类（Category）
  └── 子分类（SubCategory）
```

- 主分类代表活动的大类（如工作、学习、娱乐）
- 子分类属于特定主分类，代表更细的活动类型（如编程、阅读、视频）
- 分类名称要求：语义明确、分类间互斥、名称不重复

### 2. 分类 CRUD

#### 2.1 创建分类

**创建主分类：**
- 输入：分类名称、主分类颜色（十六进制格式）
- 系统生成唯一分类 ID（格式：`cat-xxxxxxxx`）
- 子分类颜色由系统自动生成同色系衍生色，无需单独设置

**创建子分类：**
- 输入：所属主分类 ID、子分类名称
- 子分类继承主分类的衍生色系
- 系统生成唯一子分类 ID（格式：`sub-xxxxxxxx`）

#### 2.2 更新分类

**更新主分类：**
- 可修改名称和颜色
- 子分类颜色不受影响

**更新子分类：**
- 可修改名称
- 颜色继承主分类，不可单独修改

#### 2.3 删除分类

**删除主分类：**
- 关联的行为日志记录被重新分配到指定分类（默认 `other`）
- 该主分类下的所有子分类通过 CASCADE 自动删除

**删除子分类：**
- 关联的行为日志记录的子分类被重置为 `untracked`
- 子分类本身被删除

### 3. 分类颜色规则

| 分类类型 | 颜色配置 | 规则 |
|---------|---------|------|
| 主分类 | 用户自由选择 | 十六进制格式，如 `#5B8FF9` |
| 子分类 | 系统自动衍生 | 继承主分类颜色，生成同色系浅色 |

### 4. 分类状态管理

分类状态（`state`）用于控制分类是否参与自动分类：

- `state = 1`：启用，分类参与自动分类
- `state = 0`：禁用，分类不参与自动分类，历史数据保留

#### 4.1 禁用分类的级联影响

当主分类或子分类被禁用时：

| 影响范围 | 禁用主分类 | 禁用子分类 |
|---------|----------|-----------|
| Map Cache 记录 | 该分类下所有记录 `state=0` | 该子分类下所有记录 `state=0` |
| Goal 分类流程 | 绑定该分类的 Goal 不参与分类 | 绑定该子分类的 Goal 不参与分类 |
| 历史数据 | 保留不变 | 保留不变 |

#### 4.2 启用分类的恢复规则

当分类从禁用恢复启用时：

**恢复条件：** 主分类启用 **且** 关联的子分类也启用

**冲突处理机制：**
- 如果在禁用期间，同一应用/标题产生了新的分类记录（被归入其他类别）
- 启用时会**自动删除**这些在禁用期间产生的较新缓存记录
- 优先恢复原有分类设置

**示例时间轴：**

```
T1 (正常): App A 被归类为「工作」（缓存有效）
T2 (操作): 用户禁用「工作」分类 → T1 缓存失效
T3 (运行): App A 再次运行，因「工作」禁用，AI 将其归类为「其他」（产生新缓存）
T4 (恢复): 用户重新启用「工作」分类
           → 系统删除 T3 产生的「其他」缓存
           → 恢复 T1 的「工作」缓存
```

### 5. Map Cache 管理

Map Cache（分类映射缓存）存储应用与分类的映射关系，供 classify-spec 中的缓存匹配阶段使用。

#### 5.1 单用途与多用途

| 类型 | 匹配键 | 说明 |
|-----|-------|------|
| 单用途 | `app` | 同一应用始终使用相同分类（如 VS Code → 开发） |
| 多用途 | `app + title` | 同一应用不同标题可有不同分类（如 Chrome + github.com → 工作，Chrome + bilibili.com → 娱乐） |

#### 5.2 Map Cache 记录结构

每条 Map Cache 记录包含：

- `app`：应用名称（如 `chrome.exe`）
- `title`：窗口标题（多用途应用使用，单用途为空）
- `app_description`：应用用途描述（AI 生成或手动填写）
- `title_analysis`：标题分析结果（AI 生成，仅多用途长活动）
- `category_id` / `sub_category_id`：映射的目标分类
- `link_to_goal_id`：关联的 Goal ID（可选）
- `is_multipurpose_app`：是否为多用途应用
- `state`：记录状态（1=有效，0=无效）

#### 5.3 Map Cache 操作

| 操作 | 说明 |
|-----|------|
| 查看 | 分页展示，支持搜索（匹配 app 或 title）、按状态/类型筛选 |
| 更新 | 修改分类、应用描述、标题分析、关联 Goal |
| 批量更新 | 批量修改多条记录的分类 |
| 删除 | 删除单条映射记录 |
| 批量删除 | 批量删除多条映射记录 |

**同步到日志：** 修改 Map Cache 后，可选择将修改同步到所有匹配的历史 `user_app_behavior_log` 记录。

### 6. Goal 分类绑定

#### 6.1 绑定规则

Goal 可绑定到一个主分类（必选）和一个子分类（可选）。

绑定时指定：
- `link_to_category_id`：主分类 ID
- `link_to_sub_category_id`：子分类 ID（可选）

#### 6.2 对 AI 分类的影响

根据 classify-spec，AI 分类采用三级优先级：

| 优先级 | 来源 | 说明 |
|-------|------|------|
| 第 0 级 | 缓存命中 | 已在 CacheMatcher 完成，无需 LLM |
| 第 1 级 | Goal 匹配 | 活动与绑定了分类的 Goal 相关时，优先使用 Goal 的分类 |
| 第 2 级 | AI 纯分类 | 依据 app 用途 / title 语义进行分类 |

**Goal 参与分类的条件（`get_active_goals_for_classify`）：**

1. Goal 状态为 `active`
2. `track_time_automatically = 1`（开启自动时间追踪）
3. 必须绑定了主分类（`link_to_category_id IS NOT NULL`）
4. 关联的主分类未被禁用（`category.state != 0`）
5. 关联的子分类未被禁用（`sub_category.state != 0` 或未绑定子分类）

#### 6.3 Goal 绑定对时间统计的影响

当用户在 Map Cache 中为应用设置了 `link_to_goal_id`：
- 该软件的使用时间会被统计到对应的 Goal 中
- 同一时间段内，一个应用只能绑定一个 Goal

### 7. Data Review（数据审核）

Data Review 用于审核和修正 AI 的自动分类结果。

| 操作 | 范围 | 效果 |
|-----|------|------|
| 单条修改 | 当前记录 | 仅影响当前记录，不修改 Map Cache |
| 批量修改 | 多条选中记录 | 批量修改分类或批量删除 |

**建议：** 若同一应用/标题后续仍可能分类错误，应到 Map Cache 页面修改映射关系，确保后续数据自动使用正确分类。

## Technical Contract

### 核心数据模型

```python
# lifeprism/server/schemas/category_schemas.py

class CategoryTreeItem(BaseModel):
    id: str                    # 分类唯一标识符
    name: str                  # 分类名称
    color: str                 # 分类颜色（十六进制格式）
    state: int                 # 分类状态（1: 启用, 0: 禁用）
    subcategories: list[SubCategoryTreeItem] | None = None

class SubCategoryTreeItem(BaseModel):
    id: str                    # 子分类唯一标识符
    name: str                  # 子分类名称
    color: str                 # 分类颜色（系统衍生）
    state: int                 # 分类状态（1: 启用, 0: 禁用）

class CategoryMapCacheItem(BaseModel):
    id: str                    # 记录唯一标识（格式：m-xxx 或 s-xxx）
    app: str                    # 应用程序名称
    app_description: str | None
    title: str                 # 窗口标题
    title_analysis: str | None
    category: str | None       # 主分类名称（通过 ID 映射）
    sub_category: str | None   # 子分类名称（通过 ID 映射）
    category_id: str | None
    sub_category_id: str | None
    link_to_goal_id: str | None
    link_to_goal: str | None
    is_multipurpose_app: bool
    state: int                 # 记录状态（1: 有效, 0: 无效）
    created_at: str | None
```

### API 契约

#### 分类结构接口

```
GET /category/tree?depth=2
Response: CategoryTreeResponse {
    data: list[CategoryTreeItem]
}
```

#### 分类管理接口（CRUD）

| 方法 | 路径 | 说明 |
|-----|------|------|
| POST | `/category/manage` | 创建主分类 |
| PUT | `/category/manage/{category_id}` | 更新主分类 |
| DELETE | `/category/manage/{category_id}` | 删除主分类 |
| POST | `/category/manage/{parent_id}/sub` | 添加子分类 |
| PUT | `/category/manage/{parent_id}/sub/{sub_id}` | 更新子分类 |
| DELETE | `/category/manage/{parent_id}/sub/{sub_id}` | 删除子分类 |

#### 分类状态切换接口

```
PATCH /category/manage/{category_id}/state
Request: ToggleCategoryStateRequest { state: 1 | 0 }

PATCH /category/manage/{parent_id}/sub/{sub_id}/state
Request: ToggleCategoryStateRequest { state: 1 | 0 }
```

#### Map Cache 接口

| 方法 | 路径 | 说明 |
|-----|------|------|
| GET | `/category/category_map` | 获取映射列表（分页、筛选） |
| PUT | `/category/category_map/{record_id}` | 更新单条映射 |
| PUT | `/category/category_map/batch` | 批量更新映射 |
| DELETE | `/category/category_map/{record_id}` | 删除单条映射 |
| DELETE | `/category/category_map/batch` | 批量删除映射 |

**Map Cache 记录 ID 格式：**
- `m-xxxxxxxx`：多用途应用记录（multi-purpose）
- `s-xxxxxxxx`：单用途应用记录（single-purpose）

### Map Cache 状态同步规则

#### 禁用分类时的同步

```sql
-- 禁用主分类时
UPDATE multi_purpose_map_cache SET state = 0 WHERE category_id = ?
UPDATE single_purpose_map_cache SET state = 0 WHERE category_id = ?

-- 禁用子分类时
UPDATE multi_purpose_map_cache SET state = 0 WHERE sub_category_id = ?
UPDATE single_purpose_map_cache SET state = 0 WHERE sub_category_id = ?
```

#### 启用分类时的恢复

```sql
-- 恢复条件：主分类 AND 子分类都启用
-- 冲突处理：删除同 (app, title/app) 中 created_at 更晚的记录
```

### Goal 分类参与条件

```sql
-- goal_provider.get_active_goals_for_classify()
SELECT g.id, g.name, g.link_to_category_id, g.link_to_sub_category_id
FROM goal g
INNER JOIN category c ON g.link_to_category_id = c.id
LEFT JOIN sub_category sc ON g.link_to_sub_category_id = sc.id
WHERE g.status = 'active'
  AND g.track_time_automatically = 1
  AND g.link_to_category_id IS NOT NULL
  AND c.state != 0
  AND (sc.state IS NULL OR sc.state != 0)
```

## Interaction / UX Notes

### 分类设置建议

推荐分类方案：
- **四分法**：工作、学习、娱乐、其他
- **三分法**：工作/学习、娱乐、其他（适合工作学习边界模糊的用户）

自定义分类要求：
1. 分类之间界限明确，避免语义重叠
2. 分类名称清晰无歧义，使用常见词汇
3. 各分类名称不能重复或过于相似

### Map Cache 编辑

- 修改 Map Cache 后，后续匹配该应用/标题的数据自动使用新分类
- 若需修正历史数据，点击"同步到日志"批量回填

### Data Review vs Map Cache

| 场景 | 使用 Data Review | 使用 Map Cache |
|-----|-----------------|---------------|
| 修正单条历史记录 | ✅ | ❌ |
| 修正同一应用的未来分类 | ❌ | ✅ |
| 批量修正 | ✅（选中多条） | ✅（同步到日志） |

## Acceptance Notes

- [ ] 主分类可自由选择颜色，子分类自动生成衍生色
- [ ] 删除主分类时，关联记录重新分配到指定分类，子分类 CASCADE 删除
- [ ] 禁用分类时，该分类的 Map Cache 记录同步禁用
- [ ] 禁用分类时，绑定该分类的 Goal 不参与 AI 分类流程
- [ ] 启用分类时，恢复原有 Map Cache 记录，删除冲突的新记录
- [ ] 单用途应用按 `app` 匹配，多用途应用按 `app + title` 匹配
- [ ] Map Cache 修改后可通过"同步到日志"回填历史数据
- [ ] Data Review 单条修改仅影响当前记录，不修改 Map Cache
- [ ] Goal 绑定分类需 `track_time_automatically=1` 且分类启用才参与分类

## Out of Spec

- AI 分类管道的具体实现（见 `classify-spec`）
- 分类统计数据的计算逻辑与展示格式
- Goal 的创建、任务管理、里程碑等完整功能（见 goals 相关 spec）
- Map Cache 的内部索引结构和缓存匹配算法（见 `classify-spec`）
- ActivityWatch 数据采集与同步机制
