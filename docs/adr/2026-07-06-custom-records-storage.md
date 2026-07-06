---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated: 创建自定义记录模块存储方案决策初稿
abstract: 决定自定义记录模块采用 SQLite 动态建表 + meta 表元数据驱动方案，否决 JSON 文件方案。AI 负责schema 生成与持续录入，P1 仅支持文本字段，字段定义后不可变。
status: decided
---

# 自定义记录模块存储方案决策

## 版本历史

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿 |

## 问题界定

### 问题简述

新增"自定义记录模块"：用户通过自然语言告诉 AI 想记录什么（如体育活动、每日饮食），AI 生成数据结构定义并持续把后续自然语言解析成结构化记录写入。需要决定数据存储实现方式。

### 讨论范围

- 存储引擎选择（SQLite 动态建表 vs JSON 文件 vs 配置文件 + DB 数据）
- 动态表结构如何管理（表名发现、schema 元数据存储）
- AI 在模块中的职责边界
- Schema 演进策略
- 数据可信度处理
- 记录类型删除策略

### 非讨论范围

- 具体代码实现细节（Provider 类、API 路由）
- LLM prompt 设计
- 前端组件实现
- P2 阶段的图表（柱形/折线/饼）展示

### 问题深度

这是架构设计决策，影响：
- 数据访问层是否引入新的存储范式
- LLM tool 契约设计
- 与现有 [repository-core-spec](../specs/2026-07-06-repository-core-spec.md) 的集成方式
- 未来 schema 演进成本

## 现状分析

### 用户需求

1. 用户通过自然语言定义记录类型（"我想记录体育活动，字段是日期和锻炼内容"）
2. AI 解析生成数据结构
3. 后续用户继续通过自然语言录入数据（"今天跑了5公里"）
4. 支持按日期查询
5. P1 仅文本字段 + 文本列表展示
6. P2 图表（柱形/折线/饼）暂不做

### 现有架构约束

- 项目已有 [LWBaseDataProvider](../../lifeprism/repository/base_providers/lw_base_data_provider.py) 元数据驱动 CRUD 基类，子类定义 `_TABLE_NAME` 等元数据即可获得完整 CRUD
- [mood-module-spec](../specs/2026-05-20-mood-module-spec.md) 是近亲模块：用户自定义类型 + CRUD + 日期查询，但 schema 是静态的
- [llm-agent-spec](../specs/2026-07-06-llm-agent-spec.md) 中 LLM tool 已通过 repository 模式访问数据
- 项目数据库为 SQLite，[lw_db_manager](../../lifeprism/repository/__init__.py) 已支持连接池与 WAL 模式

### 初始方案的两个误区

**误区 1：JSON 文件可部分读取**

初始设想 JSON 文件按日期筛选只读一部分。事实是 JSON 无索引，必须整体加载到内存才能过滤。能做的优化只有按日期分文件或改用 JSONL 流式读取，但仍需遍历。这削弱了 JSON 方案的核心吸引力。

**误区 2：表名用 `xxx-01`/`xxx-02` 编号命名**

初始设想前端通过编号枚举发现表。事实上 SQLite 有 `sqlite_master` 系统表，可 `SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'custom\_%'` 列出所有动态表。但本决策最终采用 meta 表方案，前端通过 meta 表获取类型列表，连 `sqlite_master` 都不需要暴露给前端。编号命名解决的是不存在的问题。

## 可选方案

### 方案 A：JSON 文件

**描述**：
- 每个记录类型一个 JSON 文件（如 `custom_sport.json`、`custom_food.json`）
- 文件内含 schema 定义 + 记录数组
- 全部放在一个文件夹内，搜索文件即可发现类型

**优点**：
- 本地可编辑（任何文本编辑器）
- Schema 演进极轻：改定义即可，旧记录读时补默认值
- 无需建表 DDL

**缺点**：
1. **无索引能力**：按日期查询必须全量加载到内存过滤
2. **写入并发问题**：文件锁需自实现，与现有连接池模式不一致
3. **与现有架构偏离**：需新写一套 file-based provider，[LWBaseDataProvider](../../lifeprism/repository/base_providers/lw_base_data_provider.py) 模式无法复用
4. **LLM tool 契约不一致**：现有 [llm-agent-spec](../specs/2026-07-06-llm-agent-spec.md) 中 tool 通过 repository 访问数据，JSON 方案需新建 file I/O 工具
5. **AI 持续录入场景下"本地可编辑"优势不存在**：录入入口是 AI 不是手动编辑

### 方案 B：SQLite 动态建表 + meta 表（最终方案）

**描述**：
- 两张 meta 表存储所有动态表的 schema 定义
- 每个记录类型对应一张数据表 `custom_<slug>`
- DDL 由 meta 表定义驱动动态生成
- 表结构完全不写在代码里，`TABLE_CONFIGS` 不包含动态表

**优点**：
- ✅ 索引能力：SQLite 天然支持，按日期查询毫秒级
- ✅ 与现有架构一致：复用 [LWBaseDataProvider](../../lifeprism/repository/base_providers/lw_base_data_provider.py) 模式，`_TABLE_NAME` 运行时由 meta 表驱动设置
- ✅ LLM tool 契约统一：tool 直接调 repository，与 [llm-agent-spec](../specs/2026-07-06-llm-agent-spec.md) 一致
- ✅ 写入并发：WAL 模式 + 连接池天然支持
- ✅ Schema 可发现：meta 表提供类型列表与字段定义，前端不接触 `sqlite_master`

**缺点**：
- Schema 演进需 ALTER TABLE，比 JSON 略重（但 P1 决定不支持演进，此缺点不成立）
- 动态 DDL 需编写建表逻辑，比静态 `TABLE_CONFIGS` 多一层

### 方案 C：配置文件（schema）+ DB（数据）

**描述**：
- Schema 定义存 yaml/json 配置文件（类似 [prompt-centralized-management](2026-05-13-prompt-centralized-management.md) 的 prompt 管理）
- 数据存 SQLite

**优点**：
- Schema 可本地编辑
- 数据查询走 DB 有索引

**缺点**：
- Schema 与数据分离，AI 创建类型时需同时写配置文件和建表，事务性差
- 配置文件加载时机与 DB 初始化时序耦合
- 比方案 B 多一层 I/O，无额外收益

## 最终决策

**选择方案 B：SQLite 动态建表 + meta 表元数据驱动**

## 决策原因

### 1. 为什么选 DB 而非 JSON

**核心驱动因素：AI 持续录入**

用户选择"schema + 持续录入都走 AI"，这意味着：
- 写入频繁且经过 LLM，需要稳定的 tool 契约 → DB 更合适
- 需要按日期查询 → DB 有索引，JSON 必须全量加载
- 需要和现有 repository/llm-agent 架构一致 → DB 完胜

JSON 唯一真实优势是"本地可编辑"，但 AI 是录入入口，用户手动编辑场景不存在。此优势在当前需求下不成立。

### 2. 为什么用 meta 表而非配置文件

- AI 创建类型时，schema 与建表必须在同一事务内，meta 表方案天然事务性
- 配置文件方案需协调文件 I/O 与 DB 事务，复杂度上升无收益
- meta 表可被 SQL 查询，前端分页/筛选方便

### 3. 为什么放弃 `xxx-01` 编号命名

`xxx-01` 解决的是"前端如何发现表"，但这个问题已被 meta 表方案解决：前端查 `custom_record_types` 即可拿到所有类型。编号命名是反模式——它意味着"不知道 schema 是什么"，但 schema 必须存在某处，存在 meta 表就该用语义化 slug。

### 4. 为什么 P1 不支持 schema 演进

- 字段定义后不可变，要改只能新建类型 + 硬删旧类型
- 大幅简化 P1 实现：不需要 ALTER TABLE、不需要处理旧记录新字段为 NULL 的兼容
- 用户硬删旧类型后 slug 可复用，新建同名类型无冲突
- 未来若需支持演进，可单独设计迁移机制，不污染 P1

### 5. 为什么 AI 无删除工具

- 删除是破坏性操作，AI 误调用风险高
- 用户走前端手动删除，prompt 中写明流程即可
- AI 仅拥有创建类型、写入记录、查询记录三类工具

## 设计细节

### Meta 表结构

#### `custom_record_types`（记录类型元数据）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK, NOT NULL | `crt-{uuid[:8]}` |
| name | TEXT | NOT NULL | 显示名（如"体育活动"） |
| slug | TEXT | NOT NULL, UNIQUE | 表名后缀（如 `sport`），实际表名 `custom_sport` |
| description | TEXT | - | 描述，给 AI 看 |
| created_at | TEXT | 自动 | 创建时间 |
| updated_at | TEXT | 自动 | 更新时间 |

#### `custom_record_fields`（字段定义元数据）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | TEXT | PK, NOT NULL | `crf-{uuid[:8]}` |
| type_id | TEXT | FK → custom_record_types.id | 关联类型 |
| field_name | TEXT | NOT NULL | 显示名（如"锻炼内容"） |
| field_key | TEXT | NOT NULL | 列名（如 `exercise_content`），AI 生成 |
| field_type | TEXT | NOT NULL | P1 只有 `text`，保留 `number`/`date` 枚举位 |
| sort_order | INTEGER | NOT NULL, DEFAULT 0 | 列顺序 |
| created_at | TEXT | 自动 | 创建时间 |

**约束**：`(type_id, field_key)` 联合唯一，防止同类型内列名重复。

### 数据表结构

`custom_<slug>` 命名，DDL 由 meta 表定义驱动动态生成：

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

### 动态建表流程

```
用户:"我想记录体育活动,字段是日期和锻炼内容"
  ↓
AI 解析 → 生成 type={name:"体育活动", slug:"sport"}
         + fields=[{key:"exercise_date",type:"date"},
                  {key:"exercise_content",type:"text"}]
  ↓
LLM tool 调用 create_custom_record_type
  ↓
1. INSERT custom_record_types (slug 唯一性校验)
2. INSERT custom_record_fields (批量, field_key 正则 + 唯一性校验)
3. DDL: CREATE TABLE custom_sport (...)
  ↓
返回 type_id 给 AI,对话内确认
```

### 前端发现表的流程

```
前端启动 → GET /custom-records/types → 查 custom_record_types
        → 选某类型 → GET /custom-records/types/{type_id}/fields → 查 custom_record_fields
        → GET /custom-records/{type_id}/entries?date_range=... → 查 custom_<slug>
```

所有路径过 meta 表，`sqlite_master` 不暴露给前端。

### AI 录入流程

1. 用户在对话中说"今天跑了5公里"
2. AI 根据 meta 表中该类型的字段定义，解析自然语言为字段值
3. AI 在对话内输出解析结果（**不存中间 draft 状态**）
4. 用户在对话内确认或修改
5. 确认后 AI 调用写入 tool 落库

**不存在的概念**：`draft` 状态、草稿表。解析失败=对话内重新解析，不产生持久化中间态。

### 记录类型删除策略

- 用户通过前端手动硬删（DROP 表 + 删除 meta 记录）
- AI 无删除工具，prompt 中写明删除走前端
- 硬删后 slug 可被新类型复用
- 不可恢复（P1 不做回收站）

### field_key 生成规则

- AI 从用户描述生成 snake_case 列名
- 后端正则校验 `^[a-z][a-z0-9_]*$`，防 SQL 注入
- 同类型内 `field_key` 唯一性校验
- 校验失败要求 AI 重新生成

## 决策影响

### 正面影响

1. **架构一致性**：复用现有 [LWBaseDataProvider](../../lifeprism/repository/base_providers/lw_base_data_provider.py) 模式，无新存储范式
2. **LLM tool 契约统一**：与 [llm-agent-spec](../specs/2026-07-06-llm-agent-spec.md) 一致，tool 调 repository
3. **查询性能**：SQLite 索引支持按日期高效查询
4. **schema 可发现**：meta 表提供类型列表，前端不接触系统表
5. **P1 实现简化**：不支持 schema 演进，无 ALTER TABLE 复杂度

### 潜在风险

1. **动态 DDL 需编写建表逻辑**：比静态 `TABLE_CONFIGS` 多一层，需在 LWTableManager 之外单独管理
2. **slug 冲突需运行时校验**：依赖 `custom_record_types.slug` UNIQUE 约束 + AI 生成时的重试逻辑
3. **未来 schema 演进需补设计**：P1 不支持，P2 若需支持要单独设计迁移机制

### 风险缓解

- 动态建表逻辑封装在 `CustomRecordRepository` 中，不污染现有 `LWTableManager`
- slug 生成失败时 AI 在对话内重新生成，不自动加后缀
- schema 演进留作未来 ADR 单独决策

## 经验教训

### 关于 JSON 部分读取的误区

**教训**：JSON 文件无法只读一部分，必须整体加载才能按字段过滤。

**原因**：JSON 是无索引的纯文本结构。能做的优化只有按日期分文件或改用 JSONL 流式读取，但仍需遍历。

**改进**：评估存储方案时，先确认查询模式（是否需要索引、是否需要按字段过滤），再选引擎。需要索引的场景直接排除 JSON。

### 关于编号命名的反模式

**教训**：`xxx-01`/`xxx-02` 这类编号命名是反模式，它解决的是不存在的问题。

**原因**：编号命名意味着"不知道 schema 是什么"，但 schema 必须存在某处。存在 meta 表就该用语义化 slug，存在 `sqlite_master` 就该用 LIKE 查询。SQLite 系统表完全能列出所有表名。

**改进**：遇到"如何发现 X"的问题，先查目标存储引擎是否提供系统目录/元数据查询能力，再决定是否需要自定义命名约定。

### 关于 AI 持续录入对存储选择的影响

**教训**：录入入口决定存储方案。AI 持续录入场景下，JSON"本地可编辑"优势不存在。

**原因**：用户不手动编辑文件，编辑入口是 AI。此时 JSON 相比 DB 的唯一优势消失，而 DB 的索引、事务、并发、架构一致性优势全部成立。

**改进**：评估存储方案时，先明确"数据的生产者是谁"。生产者是 AI/程序时优先 DB；生产者是人类手动编辑时才考虑 JSON/yaml。

## 后续行动

1. 编写自定义记录模块 spec（`docs/specs/`）
2. 实现 `CustomRecordRepository`（meta 表 CRUD + 动态建表）
3. 实现相关 LLM tool（create_custom_record_type、create_entry、query_entries）
4. 前端实现类型列表 + 文本列表展示
5. P2 阶段单独决策图表展示与字段类型扩展
