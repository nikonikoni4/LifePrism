# 云端初始化种子数据被同步到本地导致数据重复

## 元信息

- **发生时间**: 同步系统设计初期已存在
- **发现时间**: 2026-07-17
- **修复状态**: ⏳ 待修复
- **影响范围**: 6 张初始化种子数据表（category、sub_category、goal、plan_doc、mood_types、mood_impacts），其中 category 影响最严重
- **bug 类型**: 设计缺陷 — 同步范围包含了初始化种子数据表，而两端各自独立初始化相同数据
- **严重程度**: 中（P2）— category 表影响自动分类管线；mood_impacts 靠 UNIQUE 约束兜底防重复但脆弱

## 触发规则

在以下场景时阅读此文档：
- 排查"本地多了不属于自己的分类"问题
- 排查自动分类结果出现意料之外的分类
- 排查 mood_impacts 表出现重复数据
- 修改 `data_initializer.py` 中的默认数据定义
- 修改 `sync_client.py` 中的 `SYNC_TABLES` 同步范围
- 讨论初始化种子数据与同步机制的关系

## Bug 简述

项目在 `data_initializer.py` 中定义了启动时的初始化种子数据（4 个默认分类、7 种心情类型、18 个影响因素、2 个示例目标等），在数据库表为空时自动写入。问题在于：**这些初始化表全部在同步范围 `SYNC_TABLES` 中**，云端部署后云端独立初始化一份种子数据，本地部署后也独立初始化一份。同步时两端种子数据互相传播，造成以下问题：

1. **概念问题**：种子数据是"安装时本地创建"的数据，不应该参与跨端同步
2. **不必要的 LWW 冲突**：两端种子数据虽然内容相同，但 `updated_at` 时间戳不同，触发无意义的冲突判断
3. **AUTOINCREMENT 表风险**：`mood_impacts` 使用 AUTOINCREMENT PK，同步时 id 被剥离，全靠 `name` 的 UNIQUE 约束防止重复——这是脆弱的兜底
4. **分类表影响最严重**：category/sub_category 直接参与自动分类管线（Monitor → CacheMatcher → LLM 分类 → 持久化），云端分类侵入本地会影响本地数据的分类结果

## 初始化种子数据 × 同步范围对照

| 表名 | 种子记录数 | PK 类型 | ID 策略 | 在 SYNC_TABLES? | 重复风险 |
|------|-----------|---------|---------|-----------------|----------|
| `category` | 4 | TEXT PK | 固定 ID（`cat-work`, `cat-study`, `cat-entertainment`, `cat-other`） | ✅ 第70行 | 低（同 ID 靠 INSERT OR REPLACE 合并），但云端用户自建分类（随机 ID `cat-{uuid4()[:8]}`）会同步到本地 |
| `sub_category` | 4 | TEXT PK | 固定 ID（`subcat-work-other` 等） | ✅ 第71行 | 低（同上） |
| `goal` | 2 | TEXT PK | 固定 ID（`goal-example`, `goal-daily`） | ✅ 第57行 | 低（同上） |
| `plan_doc` | 2 | TEXT PK | 固定 ID（`示例-planDoc`, `每日目标-docs`） | ✅ 第59行 | 低（同上） |
| `mood_types` | 7 | TEXT PK | 固定 ID（`joy`, `calm` 等） | ✅ 第72行 | 低（同上） |
| `mood_impacts` | 18 | AUTOINCREMENT PK | 自增，name UNIQUE | ✅ 第73行 | **中** — 同步时 id 被剥离，完全依赖 UNIQUE(name) 防重复 |

## 复现场景

### 场景 1：分类表（影响自动分类）

1. 云端部署 → `data_initializer.py` 执行 → 创建 4 个默认分类（`cat-work` 等）
2. 本地部署 → `data_initializer.py` 执行 → 创建同样的 4 个默认分类
3. 用户在云端通过 UI 创建新分类"阅读" → ID 为随机 `cat-a1b2c3d4`
4. 同步 Pull → 本地不存在 `cat-a1b2c3d4` → `local_updated_at is None` → 直接写入
5. **结果：本地出现云端用户创建的分类，LLM 自动分类管线会使用这个"外来"分类**

### 场景 2：mood_impacts 表（AUTOINCREMENT 风险）

1. 云端初始化 → 18 条 mood_impacts（id=1~18）
2. 本地初始化 → 18 条 mood_impacts（id=1~18，因为是全新 DB）
3. 同步 Pull → `upsert_rows()` 检测到 AUTOINCREMENT 表 → **剥离 id 字段** → `INSERT OR REPLACE INTO mood_impacts (name, sort_order, ...) VALUES (...)`
4. UNIQUE(name) 匹配 → REPLACE 而非 INSERT → **侥幸无重复**
5. **风险：如果未来有人修改 `DEFAULT_MOOD_IMPACTS` 内容或移除 UNIQUE 约束，立刻产生重复数据**

## 根因分析

### 代码位置

- 种子数据定义：[lifeprism/repository/data_initializer.py:13-26](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/data_initializer.py#L13-L26) — `DEFAULT_CATEGORIES` 等常量
- 种子数据写入：[lifeprism/repository/data_initializer.py:239-295](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/data_initializer.py#L239-L295) — `_initialize_default_categories()` / `_initialize_default_sub_categories()`
- 空表检查：[lifeprism/repository/data_initializer.py:219-237](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/data_initializer.py#L219-L237) — `_is_table_empty()` 仅在表为空时写入
- 同步表范围：[lifeprism/sync/sync_client.py:52-91](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L52-L91) — `SYNC_TABLES` 包含所有初始化表
- LWW 冲突解决：[lifeprism/sync/sync_client.py:523-559](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L523-L559) — `pull_from_remote()` 中本地不存在则直接写入
- AUTOINCREMENT id 剥离：[lifeprism/repository/sync_repository.py:396-397](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/sync_repository.py#L396-L397) — `upsert_rows()` 对 AUTOINCREMENT 表剥离 id
- UI 创建分类（随机 ID）：[lifeprism/server/services/category_service.py:483](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/services/category_service.py#L483) — `category_id = f"cat-{str(uuid.uuid4())[:8]}"`

### 设计根因

同步机制把"运行时用户数据"和"安装时种子数据"同等对待。两端各自独立初始化，但同步不做区分：

```
云端: data_initializer → 种子数据 → sync → 传播到本地
本地: data_initializer → 种子数据 → sync → 传播到云端
```

`_is_table_empty()` 的幂等保护仅在"表完全为空"时生效，一旦有任何数据写入（包括同步写入），该保护就失效。对于固定 ID 的表，`INSERT OR REPLACE` 掩盖了这个问题；对于 AUTOINCREMENT 表，UNIQUE 约束侥幸兜底。但设计上这是不正确的——种子数据不应该进入同步通道。

## 候选修复方案

| 方案 | 改动量 | 风险 |
|------|--------|------|
| **方案 A：种子数据标记字段** — 在 category/sub_category/goal/mood_types/mood_impacts 表中增加 `is_seed` 列（DEFAULT 0），种子数据标记为 1，同步时过滤掉 `is_seed=1` 的记录 | 中（改 6 张表 DDL + data_initializer + sync push/pull 查询） | 低 — 改动集中在同步层和初始化层 |
| **方案 B：固定 ID 白名单过滤** — 在 sync push/pull 时，对 category 等表按固定种子 ID 列表过滤，不传播种子记录 | 小（仅改 sync push/pull + 添加种子 ID 常量） | 中 — 新增默认分类时需同步更新白名单 |
| **方案 C：种子数据从 SYNC_TABLES 移除** — 直接将 category、mood_types、mood_impacts 等纯种子表移出同步范围 | 小（改 SYNC_TABLES 列表） | **高** — 用户在这些表上创建的自定义数据（如自定义分类、自定义心情）也将失去同步能力 |
| **方案 D：首次同步标记** — 增加"是否已完成首次初始化同步"标记，首次同步时跳过种子数据表的 pull | 中（新增配置项 + 修改 sync 逻辑） | 中 — 仅解决首次同步问题，后续种子数据变更仍会传播 |

## 复用场景

- 任何包含种子数据/初始化数据的同步系统设计 — 必须区分"安装时数据"和"运行时数据"
- AUTOINCREMENT 表参与同步 — 必须显式处理 id 冲突，不能依赖 UNIQUE 约束兜底
- 分类/标签等影响下游管线（自动分类、统计）的元数据表 — 同步策略需特别谨慎
