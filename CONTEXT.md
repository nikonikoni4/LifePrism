# Project Glossary

> 项目核心域语言与概念定义。当 issue、提案、测试名、spec 引用这些概念时，使用此处定义的术语，避免漂移到同义词。
> 由 `/grill-with-docs` 在术语实际被解决时懒创建。

## 跨平台部署（Cross-Platform Deployment）

LifePrism 支持三种运行形态，对应三个独立启动入口：

### 运行形态（Runtime Variants）

1. **Windows 桌面完整版**（`main.py`）
   - FastAPI 服务 + Electron 前端 + Agent + Monitor
   - 本地数据采集与完整功能
   - 主要使用场景

2. **Linux Web Demo**（`main_web_demo.py`）
   - FastAPI 服务 + 静态前端 + Agent（无 Monitor）
   - 通过 Nginx 反向代理对外暴露
   - 用于演示与远程访问

3. **Linux Agent Only**（`main_agent_only.py`）
   - 仅 Agent Loop + Channel（无 FastAPI，无前端，无 Monitor）
   - 通过微信渠道提供对话服务
   - 服务器后台运行，本地关机也可用

### 数据同步（Data Sync）— P2 计划，本期未实现

> 以下为 P2 规划的设计方向，当前代码库中尚未实现。P1 部署不包含数据同步功能。

**使用模式**：主备模式（不同时使用多端）

**同步策略**：按需同步（启动时拉取 + 可选定时拉取）

- **同步方向**：双向（Windows ↔ Linux）
- **同步时机**：启动时 + 可选的定时拉取（如每 10 分钟）
- **冲突解决**：最后写入胜出（Last-Write-Wins），因主备模式冲突概率极低
- **ID 生成**：`{prefix}-{uuid.uuid4().hex[:8]}`，全局唯一，冲突概率 ~1/42亿
- **同步范围**：
  - Windows → Linux：Monitor 采集数据 + 桌面版手动输入
  - Linux → Windows：微信对话输入的数据（心情/备注/自定义记录）

**不存在的概念**：实时同步、冲突仲裁机制（主备模式不需要）

## 自定义记录模块（Custom Records Module）

让用户通过自然语言告诉 AI 想记录什么，AI 生成数据结构定义并持续把后续自然语言解析成结构化记录写入的系统。P1 仅支持文本字段 + 文本列表展示，P2 图表（柱形/折线/饼）暂不做。

### Custom Record Type（自定义记录类型）

用户定义的一类记录，如"体育活动"、"每日饮食"。每个类型对应一张数据表 `custom_<slug>`。

- 由 AI 解析用户自然语言生成
- 创建时 AI 生成 slug（语义化标识，用作表名后缀）
- P1 字段定义后不可变，要改只能新建类型 + 硬删旧类型
- 删除走前端手动操作，AI 无删除工具

### Custom Record Field（自定义记录字段）

记录类型下的字段定义，存于 `custom_record_fields` meta 表。一个类型有多个字段（1:N）。

- `field_name`：显示名（如"锻炼内容"）
- `field_key`：数据库列名（如 `exercise_content`），AI 生成，正则 `^[a-z][a-z0-9_]*$` 校验 + 同类型内唯一性校验
- `field_type`：P1 只有 `text`，保留 `number`/`date` 枚举位供未来扩展

### Custom Record Entry（自定义记录条目）

一条具体的记录数据，存于对应类型的 `custom_<slug>` 数据表。每条记录统一带 `id`、`created_at`、`updated_at`，外加字段定义的列。

### Meta Table（元数据表）

存储动态表结构定义的两张表：

- `custom_record_types`：记录类型元数据（name、slug、description）
- `custom_record_fields`：字段定义元数据（type_id、field_name、field_key、field_type、sort_order）

运行时 AI 与前端都从 meta 表读 schema，**动态数据表（`custom_<slug>`）的结构完全不写在代码里**。`TABLE_CONFIGS` 不包含动态数据表。`CustomRecordRepository` 独立实现，不继承 [LWBaseDataProvider](lifeprism/repository/base_providers/lw_base_data_provider.py)（因为 LWBaseDataProvider 的 `_TABLE_NAME` 等元数据是类级静态属性，动态表名运行时才确定，无法套用）。

注意：meta 表本身（`custom_record_types`、`custom_record_fields`）是**静态表**，需在 `lifeprism/config/database.py` 的 `TABLE_CONFIGS` 中定义，由 `init_database()` 创建。

### Data Table（数据表）

`custom_<slug>` 命名的实际数据表，由 meta 表定义驱动 DDL 动态创建。每张表结构：

```
id TEXT PRIMARY KEY,
<field_key> TEXT,  -- 由 custom_record_fields 定义
created_at TEXT,
updated_at TEXT
```

### Slug

记录类型的语义化标识，用作数据表名后缀。

- 创建时 AI 生成，全局唯一（`custom_record_types.slug` UNIQUE 约束）
- 硬删类型后 slug 可被新类型复用
- 不使用 `xxx-01` 这类编号命名——它解决的是不存在的问题（SQLite 有 `sqlite_master` 可查表名，且 meta 表已提供类型列表）

### AI 录入流程（AI Entry Flow）

1. 用户在对话中说"今天跑了5公里"
2. AI 根据 meta 表中该类型的字段定义，解析自然语言为字段值
3. AI 在对话内输出解析结果（不存中间 draft 状态）
4. 用户在对话内确认或修改
5. 确认后 AI 调用写入 tool 落库

不存在的概念：`draft` 状态、草稿表。解析失败=对话内重新解析，不产生持久化中间态。
