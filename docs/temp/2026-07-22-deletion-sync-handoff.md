# 删除同步方案 Handoff 文档

> 创建时间：2026-07-22
> 状态：方案已确认，待实现
> 用途：交接给新聊天会话继续实现

---

## 一、问题背景

LifeWatch-AI 项目的云端同步系统目前存在一个核心功能缺口：**删除操作无法同步**。

### 问题表现

1. **文件删除**：文件删除不走 LifePrism 同步系统（`plan/` 目录有前端按钮但不同步，其他文件直接在文件系统操作）
2. **数据库数据删除**：在 A 设备删除一条记录后，同步时该记录不在增量集中（`updated_at > last_sync_time` 查不到已删行），云端保留该记录；B 设备下次 pull 会重新拉回该记录，**删除被静默撤销**

### 代码证据

- `lifeprism/repository/sync_repository.py:1091` 注释：「注意：不删除任何表——删除同步需要独立的 tombstone 机制，不属于本方法的职责范围。」
- `lifeprism/server/api/sync_cloud_api.py:327` 注释：「注意：不删除任何表——删除同步需要独立的 tombstone 机制。」
- 代码作者已明确知晓此缺口，但未实现

---

## 二、研究领域成果

### 2.1 同步架构概览

**核心文件**：
- `lifeprism/sync/sync_client.py`（约 2166 行）：主同步客户端，含 `sync_once` 主流程
- `lifeprism/repository/sync_repository.py`（约 1169 行）：Repository 层，含 LWW 逻辑
- `lifeprism/server/api/sync_cloud_api.py`：云端 API 端点
- `lifeprism/server/api/sync_status_api.py`：状态/触发/重置 API
- `lifeprism/sync/constants.py`：SYNC_TABLES 定义
- `lifeprism/config/database.py`：所有表 schema 定义

### 2.2 sync_once 主流程

1. 读取 `remote_url`、`api_key`、`last_sync_time`
2. 检查云端是否已初始化
3. 若未初始化 → `_full_sync_to_cloud`（4 步全量首同步）
4. 否则增量流程：
   - 动态表定义对比
   - 数据库 Pull：`pull_from_remote`
   - 数据库 Push：`push_to_remote`
   - 文件同步全流程
5. 全部成功 → 更新 `last_sync_time`

### 2.3 LWW（Last-Write-Wins）机制

- 所有 SYNC_TABLES 都配置 `update_at: True`，自动维护 `updated_at` 字段
- Pull 阶段：本地与云端 `updated_at` 字符串比较，谁晚谁赢
- Push 阶段：云端 `upsert_rows_with_lww` 做 LWW 过滤后写入

### 2.4 SYNC_TABLES 清单（31 张静态表）

`lifeprism/sync/constants.py:19-58`：

```python
SYNC_TABLES = [
    # 用户输入数据（15张）
    "mood_entries", "diary", "todo_list", "goal", "goal_journal",
    "plan_doc", "daily_focus", "weekly_focus", "habits",
    "habit_challenges", "habit_checkins", "habit_chains",
    "habit_chain_nodes", "timeline_custom_block", "time_paradoxes",
    # 元数据（8张）
    "category", "sub_category", "mood_types", "mood_impacts",
    "user_values", "commitments", "custom_record_types", "custom_record_fields",
    # Monitor 数据（3张）
    "user_app_behavior_log", "behavior_analysis", "raw_behavior_analysis",
    # 缓存表（3张）
    "multi_purpose_map_cache", "single_purpose_map_cache", "category_map_cache",
    # 统计数据（1张）
    "tokens_usage_log",
    # 微信账户状态（1张）
    "wechat_account_state",
]
```

注意：`window_events` 被显式排除。

### 2.5 主键结构分布

#### 类型 A：TEXT PRIMARY KEY + hash_id 格式（18 张）

ID 生成算法（`lifeprism/repository/base_providers/lw_base_data_provider.py:1130-1134`）：

```python
if id_prefix:
    import uuid
    data["id"] = f"{id_prefix}{uuid.uuid4().hex[:8]}"
```

- 格式：`{prefix}{uuid4().hex[:8]}`，8 位十六进制字符（32 bit 熵）
- 按生日悖论，单前缀约 65536 条记录开始有显著碰撞概率
- 个人级使用碰撞风险极低

| 表名 | 前缀 | 示例 ID |
|------|------|---------|
| todo_list | `t-` | `t-a3f8b2c1` |
| goal | `goal-` | `goal-7e9d4f2b` |
| goal_journal | `journal-` | `journal-...` |
| plan_doc | `plandoc-` | `plandoc-...` |
| mood_entries | `mood-` | `mood-...` |
| user_values | `val-` | `val-...` |
| commitments | `cmt-` | `cmt-...` |
| custom_record_types | `crt-` | `crt-...` |
| custom_record_fields | `crf-` | `crf-...` |
| mood_types | `mood-type-` | 或固定 ID |
| habits | TEXT PK | - |
| habit_challenges | TEXT PK | - |
| habit_checkins | TEXT PK | - |
| category | TEXT PK | - |
| sub_category | TEXT PK | - |
| multi_purpose_map_cache | `m-` | `m-...` |
| single_purpose_map_cache | `s-` | `s-...` |
| wechat_account_state | `wechat_user_id` | TEXT PK |
| tokens_usage_log | `session_id` | TEXT PK |

#### 类型 B：INTEGER PRIMARY KEY AUTOINCREMENT（9 张，需新增 hash_id）

| 表名 | 主键 | UNIQUE 约束 | 数据量评估 |
|------|------|------------|-----------|
| `daily_focus` | INTEGER PK AUTO | 列级 `date UNIQUE` | 低频 |
| `weekly_focus` | INTEGER PK AUTO | 表级 `UNIQUE(year, month, week_num)` | 低频 |
| `timeline_custom_block` | INTEGER PK AUTO | 无 | 低频 |
| `time_paradoxes` | INTEGER PK AUTO | `UNIQUE(user_id,mode,version)` | 低频 |
| `mood_impacts` | INTEGER PK AUTO | 列级 `name UNIQUE` | 低频 |
| `habit_chains` | INTEGER PK AUTO | 无 | 低频 |
| `habit_chain_nodes` | INTEGER PK AUTO | 无（有外键） | 低频 |
| `user_app_behavior_log` | INTEGER PK AUTO | 需确认 | **高频（每天500-2000条）** |
| `category_map_cache` | INTEGER PK AUTO | 需确认 | 中等 |

#### 类型 C：自然键主键（3 张）

| 表名 | 主键字段 | 示例 |
|------|---------|------|
| `diary` | `date` | `2026-07-22` |
| `behavior_analysis` | `start_time` | 时间戳 |
| `raw_behavior_analysis` | `start_time` | 时间戳 |

### 2.6 主键字段解析机制

`lifeprism/repository/sync_repository.py:850` 的 `get_primary_key_field(table_name)` 方法：
- 遍历 TABLE_CONFIGS 的 columns，找 constraints 含 `"PRIMARY KEY"` 的列
- 动态表（`custom_{slug}`）固定返回 `"id"`
- **关键：数据库层面主键字段名统一是 `id`**（除自然键表），前端说的"goal-id"、"cat-id"是前端命名习惯

---

## 三、关键发现：AUTOINCREMENT 表的 id 剥离问题

### 3.1 id 剥离是有意设计

`lifeprism/repository/sync_repository.py:514-520`：

```python
# 对 AUTOINCREMENT 表，从行数据副本中移除 id（避免污染 sqlite_sequence）
if self._is_autoincrement_table(table_name):
    rows = [{k: v for k, v in row.items() if k != "id"} for row in rows]
    if not rows or not rows[0]:
        logger.debug("upsert_rows: AUTOINCREMENT 表 %s 剥离 id 后无数据", table_name)
        return 0
    columns = list(rows[0].keys())
```

**原因**：两端独立分配 id 会冲突。如果不剥离，`INSERT OR REPLACE` 按 PK 去重，id 相同就直接覆盖，不关心内容是否同一份数据。

### 3.2 去重机制存在 bug

#### Bug 1：列级 UNIQUE 不被识别

`get_unique_fields()` 只解析 `table_constraints` 中的 `UNIQUE(...)` 格式（`sync_repository.py:877-897`），不解析列定义中的 `UNIQUE` 约束。

受影响表：
- `daily_focus`：列约束 `["NOT NULL", "UNIQUE"]`（date 字段）→ 不被识别
- `mood_impacts`：列约束 `["NOT NULL", "UNIQUE"]`（name 字段）→ 不被识别

#### Bug 2：完全无 UNIQUE 约束的表会重复插入

| 表名 | 有 UNIQUE？ | 后果 |
|------|------------|------|
| `habit_chains` | 无 | 每次同步重复插入 |
| `habit_chain_nodes` | 无 | 每次同步重复插入 |
| `timeline_custom_block` | 无（只有 CHECK） | 每次同步重复插入 |

#### Bug 3：外键引用 id 在两端不同

`habit_chain_nodes` 有外键（`database.py:1325`）：

```python
"FOREIGN KEY (chain_id) REFERENCES habit_chains(id) ON DELETE CASCADE"
```

本地 `habit_chains` 的 id=1，同步到云端后云端分配的 id 可能是 3。`habit_chain_nodes` 的 `chain_id` 字段记录的是本地的 id=1，同步到云端后 `chain_id=1` 指向云端的 id=1（可能是完全不同的链条）—— **外键关系断裂**。

### 3.3 同步时间与重置机制

- `last_sync_time` 存储在 `config.yaml`，通过 `SettingsManager` 管理
- 重置端点：`lifeprism/server/api/sync_status_api.py:119-154` `POST /api/sync/reset-sync-progress`
- 重置只清 `sync.last_sync_time`，不重置 `file_sync_state`

---

## 四、方案讨论过程

### 4.1 成熟方案名称

用户提出的方案在分布式系统领域有成熟名称：
- **Tombstone Pattern（墓碑表模式）**：独立表记录"已死亡"的数据
- 相关概念：CDC（Change Data Capture）、Event Sourcing（事件溯源）

### 4.2 文件删除决策

**结论**：作为已知限制处理。

理由：
1. 文件操作不走 LifePrism 同步管控
2. `plan/` 目录不在 `SYNC_DIRECTORIES` 白名单中
3. 文件同步的 11 状态矩阵只处理"存在/不存在 + hash 变化"，没有"删除传播"状态

### 4.3 数据库删除方案演进

#### 初始方案（用户提出）
新增同步表记录删除行为，字段：表名、hash_id、行为、平台。

#### 反驳与修正
1. **AUTOINCREMENT 表无法用此方案**：id 在两端不同，用 id 删除会删错
2. **自然键表不适用**：没有 hash_id 概念
3. **hash_id 碰撞风险确认**：8 位截断有理论风险（个人使用可忽略）
4. **自增 id 复用风险不成立**：SQLite AUTOINCREMENT 维护 `sqlite_sequence`，删除后不复用
5. **清理策略风险**：多设备场景下清理墓碑会导致删除丢失（但本项目是严格两节点，风险不存在）
6. **删除-更新冲突未处理**：作为已知限制接受

#### 最终方案
为所有 AUTOINCREMENT 表新增 `hash_id` 字段，统一用 hash_id 作同步标识。

---

## 五、最终决策汇总

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 执行策略 | 一次性完成 | 所有 30 张表统一做删除同步 |
| 同步标识字段 | `hash_id` | AUTOINCREMENT 表新增此字段 |
| hash_id 位数 | 新增表用 12 位，现有表保持 8 位 | 12 位支持 1677 万条无碰撞 |
| 节点模型 | 严格两节点 | 本地↔云端，可激进清理墓碑 |
| 冲突策略 | 墓碑 created_at 作 LWW | 墓碑不修改，created_at == updated_at |
| 墓碑清理 | 同步成功后立即清理 | 清理 `created_at <= last_sync_time` 的记录 |
| 文件删除 | 已知限制 | 文档记录，不实现同步 |

### 5.1 hash_id 位数选择依据

| 位数 | 熵 (bit) | 50% 碰撞概率的记录数 | 适用场景 |
|------|----------|-------------------|---------|
| 8 | 32 | 65,536 | < 1万条（当前 TEXT PK 表） |
| 12 | 48 | 16,777,216 | < 1000万条（user_app_behavior_log 10年预估 730万条） |
| 16 | 64 | 4,294,967,296 | < 10亿条 |
| 32 | 128 | 1.8×10¹⁹ | 几乎不可能 |

选择 12 位 + 保持现状的理由：
- `user_app_behavior_log` 每天 2000 条 × 10年 = 730万条，远低于 1677 万阈值
- 现有 TEXT PK 表数据量小，8 位足够
- 长度适中，存储和索引开销可忽略

---

## 六、实现方案

### 6.1 9 张 AUTOINCREMENT 表新增 hash_id 字段

建议前缀：

| 表名 | 建议前缀 | 示例 hash_id |
|------|---------|-------------|
| `daily_focus` | `df-` | `df-a3f8b2c1d4e6` |
| `weekly_focus` | `wf-` | `wf-...` |
| `timeline_custom_block` | `tcb-` | `tcb-...` |
| `time_paradoxes` | `tp-` | `tp-...` |
| `mood_impacts` | `mi-` | `mi-...` |
| `habit_chains` | `hc-` | `hc-...` |
| `habit_chain_nodes` | `hcn-` | `hcn-...` |
| `user_app_behavior_log` | `awbl-` | `awbl-...` |
| `category_map_cache` | `cmc-` | `cmc-...` |

### 6.2 Schema 变更

每张 AUTOINCREMENT 表新增字段：

```python
"hash_id": {
    "type": "TEXT",
    "constraints": ["NOT NULL", "UNIQUE"],
    "comment": "同步用全局唯一标识（12位 hex）",
},
```

文件位置：`lifeprism/config/database.py` 的 `TABLE_CONFIGS`。

### 6.3 ID 生成逻辑

在 `lifeprism/repository/base_providers/lw_base_data_provider.py` 中，对 AUTOINCREMENT 表的插入操作生成 hash_id：

```python
# 新增逻辑（AUTOINCREMENT 表）
if self._is_autoincrement_table(table_name):
    hash_prefix = HASH_ID_PREFIXES.get(table_name)
    if hash_prefix and "hash_id" not in data:
        data["hash_id"] = f"{hash_prefix}{uuid.uuid4().hex[:12]}"
```

建议在 `lifeprism/sync/constants.py` 中新增 `HASH_ID_PREFIXES` 字典。

### 6.4 同步去重逻辑调整

`lifeprism/repository/sync_repository.py` 的 `upsert_rows_with_lww` 方法：

**当前逻辑**（需修改）：
```python
# 对 AUTOINCREMENT 表，从行数据副本中移除 id
if self._is_autoincrement_table(table_name):
    rows = [{k: v for k, v in row.items() if k != "id"} for row in rows]
```

**修改为**：
```python
if self._is_autoincrement_table(table_name):
    # 不再剥离 id，改用 hash_id 作为去重键
    # id 字段仍然剥离（避免污染 sqlite_sequence），但保留 hash_id
    rows = [{k: v for k, v in row.items() if k != "id"} for row in rows]
    # 去重键改为 hash_id
    unique_fields = ["hash_id"]
```

具体实现需要修改：
- `upsert_rows_with_lww`：AUTOINCREMENT 表的去重键改为 `hash_id`
- `_batch_get_existing_updated_at_by_unique`：支持按 `hash_id` 查询
- `get_unique_fields`：对 AUTOINCREMENT 表返回 `["hash_id"]`

### 6.5 墓碑表 schema

新增 `deletion_log` 表：

```python
DELETION_LOG_CONFIG = {
    "table_name": "deletion_log",
    "columns": {
        "id": {
            "type": "TEXT",
            "constraints": ["PRIMARY KEY"],
            "comment": "墓碑ID（dl-+uuid8）",
        },
        "target_table": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "被删记录所在表名",
        },
        "record_id": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "被删记录的主键值或hash_id",
        },
        "source": {
            "type": "TEXT",
            "constraints": ["NOT NULL"],
            "comment": "来源：local/cloud",
        },
    },
    "timestamps": True,
    "update_at": True,  # created_at == updated_at，墓碑不修改
}
```

**注意**：字段名用 `target_table` 避免与列名 `table_name` 冲突。

将 `deletion_log` 加入 `SYNC_TABLES`。

### 6.6 删除同步流程

#### Pull 阶段（新增）
1. 拉取云端墓碑（`created_at > last_sync_time`）
2. 对每条墓碑执行 `DELETE FROM {target_table} WHERE {pk或hash_id} = {record_id}`
3. 写入本地墓碑副本（标记 source=cloud）

#### Push 阶段（新增）
1. 推送本地墓碑（`created_at > last_sync_time` 且 `source=local`）到云端
2. 云端执行删除

#### 清理阶段（同步成功后）
1. 两端清理 `created_at <= last_sync_time` 的墓碑记录

### 6.7 业务层删除拦截

在 `lifeprism/repository/base_providers/lw_base_data_provider.py` 的 `_generic_delete` 中，删除前先写墓碑：

```python
def _generic_delete(self, table_name, pk_field, pk_value):
    # 写墓碑（仅对 SYNC_TABLES）
    if table_name in SYNC_TABLES:
        self._write_tombstone(table_name, pk_value)
    # 执行删除
    # ...
```

### 6.8 数据迁移脚本

为 9 张 AUTOINCREMENT 表的现有数据回填 `hash_id`：

```python
# 迁移脚本伪代码
import uuid

HASH_ID_PREFIXES = {
    "daily_focus": "df-",
    "weekly_focus": "wf-",
    # ...
}

for table_name, prefix in HASH_ID_PREFIXES.items():
    rows = db.execute(f"SELECT id FROM {table_name} WHERE hash_id IS NULL")
    for row in rows:
        hash_id = f"{prefix}{uuid.uuid4().hex[:12]}"
        db.execute(f"UPDATE {table_name} SET hash_id = ? WHERE id = ?", [hash_id, row["id"]])
```

---

## 七、实现步骤

1. **写 ADR 文档**：记录所有决策和方案，放到 `docs/adr/`
2. **Schema 变更**：
   - 9 张 AUTOINCREMENT 表加 `hash_id` 字段
   - 新增 `deletion_log` 表
   - 更新 `TABLE_CONFIGS`
3. **数据迁移脚本**：回填 hash_id
4. **同步逻辑修改**：
   - `upsert_rows_with_lww` 去重键改用 hash_id
   - 不再剥离 id（或仍剥离 id 但保留 hash_id）
   - 修复列级 UNIQUE 不识别的 bug（可选）
5. **墓碑机制实现**：
   - 墓碑表 Provider
   - 墓碑写入逻辑（删除拦截）
   - 删除执行逻辑
   - 同步流程集成（Pull/Push/清理）
6. **测试验证**：
   - 单表删除同步测试
   - 多表删除同步测试
   - 边界情况测试（重置同步时间、全量同步等）

---

## 八、关键文件路径索引

### 同步核心
- `lifeprism/sync/sync_client.py`：主同步客户端
- `lifeprism/sync/constants.py`：SYNC_TABLES 定义
- `lifeprism/sync/hash_utils.py`：文件 hash 计算
- `lifeprism/sync/conflict_resolution.py`：文件冲突解决
- `lifeprism/sync/sync_config.py`：同步配置

### Repository 层
- `lifeprism/repository/sync_repository.py`：同步 Repository
- `lifeprism/repository/base_providers/lw_base_data_provider.py`：基础 Provider（ID 生成在 1130-1134 行）
- `lifeprism/repository/providers/file_sync_state_provider.py`：文件同步状态 Provider

### Schema / 配置
- `lifeprism/config/database.py`：TABLE_CONFIGS（FILE_SYNC_STATE_CONFIG 在 1598 行）
- `lifeprism/config/settings_manager.py`：配置管理

### API 层
- `lifeprism/server/api/sync_cloud_api.py`：云端 Pull/Push/full-clear/mark-initialized
- `lifeprism/server/api/sync_status_api.py`：status/trigger/reset-sync-progress

项目根目录：`D:\desktop\软件开发\LifeWatch-AI`

---

## 九、已知限制（需文档记录）

1. **文件删除不同步**：文件操作不走 LifePrism 同步管控，`plan/` 目录不同步，其他文件删除需用户手动保持两端一致
2. **删除-更新冲突不处理**：一端删除、另一端更新同一条记录时，不自动处理（概率极低，接受）
3. **hash_id 碰撞风险**：8 位截断有理论碰撞概率（个人使用可忽略），12 位支持 1677 万条无碰撞
4. **AUTOINCREMENT 表外键断裂问题**：`habit_chain_nodes.chain_id` 引用 `habit_chains.id`，同步后 id 在两端不同，外键关系可能断裂（本方案不解决，需单独处理）

---

## 十、待确认问题

1. **`user_app_behavior_log` 和 `category_map_cache` 的 UNIQUE 约束**：需确认这两张表是否有 UNIQUE 约束（影响去重逻辑）
2. **外键断裂问题**：`habit_chain_nodes.chain_id` 引用 `habit_chains.id`，是否需要改为引用 `hash_id`？这涉及外键迁移
3. **前端适配**：虽然自增 id 不变，但前端是否需要感知 `hash_id`（如用于删除操作的 API 参数）？
4. **墓碑表字段命名**：`table_name` 是 SQL 保留字，建议用 `target_table` 或 `table_name_field`

---

## 十一、用户偏好提醒

- 通信语言：中文
- 开发：所有修改不能影响正常运行（非 mock 模式）
- 配置管理：偏好简单，consolidating settings into a single file
- 架构设计：清晰分层（Repository 层只做 CRUD，业务逻辑在上层）
- 低频场景：优先手动方案 + 文档化，而非复杂自动化
- 决策方式：充分讨论替代方案，基于具体风险做最终判断
- 研究报告：必须人工审查，将建议转化为可执行验收标准后再分发任务
- 任务执行：需要显式追踪和引用先前的研究发现

---

## 十二、参考资料

- [Tombstone Pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/tombstone)
- [Linear 的同步工程博客](https://linear.app/blog/scaling-linear-sync)
- [SQLite AUTOINCREMENT](https://www.sqlite.org/autoinc.html)
- [生日悖论碰撞计算器](https://www.birthdayproblem.com/)

---

**文档结束**

新聊天会话请从"七、实现步骤"部分开始，先写 ADR 文档，然后按顺序实现。

---

## 十三、数据库操作合法化（前置任务，优先执行）

> 本章节为 2026-07-22 补充，是删除同步方案的前置任务。
> 在实现 hash_id 和墓碑机制之前，必须先解决 repo 模块的遗留不一致问题。

### 13.1 三张弃用表的调查结果

| 表 | 弃用状态 | 证据 |
|---|---|---|
| `daily_focus` | ✅ 确实弃用 | Provider 全注释归档在 `scripts/archived_providers/focus_provider.py`，无 API 端点，无业务读写，仅 demo 脚本和 SYNC_TABLES 残留 |
| `weekly_focus` | ✅ 确实弃用 | 同 daily_focus |
| `category_map_cache` | ✅ 半弃用 | 写入方法 `save_category_map_cache` 在 `lw_base_data_provider.py:642` 已完整注释；`save_category_map_cache_V2` 实际写入的是 `multi_purpose_map_cache` 和 `single_purpose_map_cache`（TEXT PK 表）；service/API 层只有 GET/PUT/DELETE，无 POST 创建接口 |

### 13.2 time_paradoxes 表的调查结果（用户判断有误）

**time_paradoxes 未弃用，完全活跃**。完整链路：

- Provider：`lifeprism/server/providers/being_provider.py`（完全活跃，无注释）
- Service：`lifeprism/server/services/being_service.py`
- API：`lifeprism/server/api/being_api.py`（路由 `/being`，完整 CRUD）
- 路由已注册：`lifeprism/server/api/__init__.py:6, 38`

API 端点清单：
- `GET /being/{mode}` - 获取最新版本
- `GET /being/{mode}/versions` - 版本列表
- `GET /being/{mode}/{version}` - 指定版本
- `POST /being/{mode}` - 创建新版本
- `PUT /being/{mode}/{version}` - 更新
- `DELETE /being/{mode}/{version}` - 删除
- `POST /being/{mode}/{version}/ai-abstract` - AI 总结（预留）

### 13.3 9 张 AUTOINCREMENT 表的写入方式不一致

#### 不一致点 1：写入方式分裂

| 派别 | 表 | 写入方式 |
|---|---|---|
| **A 派（标准）** | `timeline_custom_block`、`user_app_behavior_log` | `_generic_insert` |
| **B 派（遗留）** | `habit_chains`、`habit_chain_nodes`、`mood_impacts`、`time_paradoxes` | 原生 SQL INSERT + `cursor.lastrowid` |

**同一文件 `mood_providers.py` 内部都不一致**：`MoodEntryProvider`（TEXT PK）用 `_generic_insert`，`MoodImpactProvider`（AUTOINCREMENT）用原生 SQL。

#### 不一致点 2：Provider 目录归属混乱

| 目录 | 表 | 状态 |
|---|---|---|
| `repository/providers/`（正确） | 5 张 | ✅ |
| `server/providers/`（错误） | `time_paradoxes` | ❌ 迁移遗留 |
| `scripts/archived_providers/`（归档） | `daily_focus`、`weekly_focus` | 全注释 |
| `repository/base_providers/`（基类） | `category_map_cache` | 写入方法已注释 |

`BeingProvider` 是 repo 模块迁移时漏网的，没有跟着其他 Provider 一起迁移到 `repository/providers/`。

#### 不一致点 3：弃用表仍在 SYNC_TABLES

`daily_focus`、`weekly_focus`、`category_map_cache` 这三张表实际已无写入入口，但仍在 `SYNC_TABLES` 中，每次同步都在传输空数据。

### 13.4 合法化方案（三步分步执行）

#### 第一步：清理三张弃用表

**操作**：
1. 从 `SYNC_TABLES` 中移除 `daily_focus`、`weekly_focus`、`category_map_cache`
   - 文件：`lifeprism/sync/constants.py:19-58`
2. 从 `TABLE_CONFIGS` 中移除对应的 schema 定义（或保留但标记 deprecated）
   - 文件：`lifeprism/config/database.py`
   - 涉及配置：`DAILY_FOCUS_CONFIG`、`WEEKLY_FOCUS_CONFIG`、`CATEGORY_MAP_CACHE_CONFIG`
3. 删除 `scripts/archived_providers/focus_provider.py`（已全注释）
4. 删除 `lw_base_data_provider.py:642` 已注释的 `save_category_map_cache` 方法
5. 清理 demo 脚本中对这三张表的写入代码（`scripts/demo/demo_data_generator.py`）

**理由**：
- 这三张表无写入入口，同步是空操作
- 留在 `SYNC_TABLES` 中会干扰删除同步方案（墓碑表要覆盖所有 SYNC_TABLES）
- 符合"清理遗留问题"的优先级

**风险**：低。如果未来需要恢复，schema 定义在 git 历史中可追溯。

#### 第二步：迁移 BeingProvider 到正确目录

**操作**：
1. 将 `lifeprism/server/providers/being_provider.py` 移动到 `lifeprism/repository/providers/being_provider.py`
2. 更新所有 import 路径：
   - `lifeprism/server/services/being_service.py`
   - 其他引用 `being_provider` 的文件
3. 将原生 SQL INSERT 改为 `_generic_insert`（为后续 hash_id 改造铺路）

**改动示例**（`being_provider.py` 的 `create` 方法）：

```python
# 改前：原生 SQL
with self.db.get_connection() as conn:
    cursor = conn.cursor()
    columns = ", ".join(insert_data.keys())
    placeholders = ", ".join(["?" for _ in insert_data])
    sql = f"INSERT INTO {self.TABLE_NAME} ({columns}) VALUES ({placeholders})"
    cursor.execute(sql, list(insert_data.values()))
    new_id = cursor.lastrowid

# 改后：_generic_insert
new_id = self._generic_insert(insert_data)
```

**理由**：
- `time_paradoxes` 是活跃表，必须支持删除同步
- Provider 目录归属是架构原则，不能例外
- 改用 `_generic_insert` 是后续加 hash_id 的前置条件

**风险**：中。涉及 import 路径变更，需要全量测试 being API。

#### 第三步：统一剩余 4 张表的写入方式

对以下 4 张表，将原生 SQL INSERT 改为 `_generic_insert`：

| 表 | Provider 文件 | 方法 |
|---|---|---|
| `habit_chains` | `lifeprism/repository/providers/habit_chain_providers.py` | `create_chain` |
| `habit_chain_nodes` | `lifeprism/repository/providers/habit_chain_providers.py` | `create_node` |
| `mood_impacts` | `lifeprism/repository/providers/mood_providers.py` | `create_mood_impact` |
| `time_paradoxes` | `lifeprism/repository/providers/being_provider.py`（迁移后） | `create` |

**改动模板**（以 `create_chain` 为例）：

```python
# 改前：原生 SQL
cursor = conn.execute(
    """INSERT INTO habit_chains (name, description, show_in_timeline, created_at, updated_at)
       VALUES (?, ?, ?, ?, ?)""",
    (insert_data["name"], insert_data["description"], insert_data["show_in_timeline"], now_iso, now_iso),
)
chain_id = cursor.lastrowid

# 改后：_generic_insert
insert_data = {
    "name": data["name"],
    "description": data.get("description"),
    "show_in_timeline": data.get("show_in_timeline", 0),
    "created_at": now_iso,
    "updated_at": now_iso,
}
chain_id = self._generic_insert(insert_data)
```

**理由**：
- 统一写入入口，为后续 hash_id 改造铺路
- `_generic_insert` 自动处理时间戳、冲突策略、白名单验证
- 消除同一文件内部的不一致

**风险**：低。`_generic_insert` 内部也是执行 INSERT，行为等价。

### 13.5 合法化后的最终状态

完成三步后，9 张 AUTOINCREMENT 表变为：

| 表 | 状态 | 后续处理 |
|---|---|---|
| `daily_focus` | 从 SYNC_TABLES 移除 | 不参与删除同步 |
| `weekly_focus` | 从 SYNC_TABLES 移除 | 不参与删除同步 |
| `category_map_cache` | 从 SYNC_TABLES 移除 | 不参与删除同步 |
| `time_paradoxes` | Provider 迁移 + 改用 `_generic_insert` | 后续加 hash_id |
| `habit_chains` | 改用 `_generic_insert` | 后续加 hash_id |
| `habit_chain_nodes` | 改用 `_generic_insert` | 后续加 hash_id |
| `mood_impacts` | 改用 `_generic_insert` | 后续加 hash_id |
| `timeline_custom_block` | 已是标准做法 | 后续加 hash_id |
| `user_app_behavior_log` | 已是标准做法 | 后续加 hash_id |

**最终需要加 hash_id 的表从 9 张减少到 6 张**。

### 13.6 更新后的 hash_id 前缀清单

| 表名 | 建议前缀 | 示例 hash_id |
|---|---|---|
| `timeline_custom_block` | `tcb-` | `tcb-a3f8b2c1d4e6` |
| `time_paradoxes` | `tp-` | `tp-...` |
| `mood_impacts` | `mi-` | `mi-...` |
| `habit_chains` | `hc-` | `hc-...` |
| `habit_chain_nodes` | `hcn-` | `hcn-...` |
| `user_app_behavior_log` | `awbl-` | `awbl-...` |

（已移除 `daily_focus`、`weekly_focus`、`category_map_cache` 的前缀）

### 13.7 更新后的实现步骤（含合法化前置任务）

1. **写 ADR 文档**：记录所有决策和方案，放到 `docs/adr/`
2. **【前置】合法化第一步**：清理三张弃用表
3. **【前置】合法化第二步**：迁移 BeingProvider 到 `repository/providers/`
4. **【前置】合法化第三步**：统一 4 张表改用 `_generic_insert`
5. **Schema 变更**：
   - 6 张 AUTOINCREMENT 表加 `hash_id` 字段
   - 新增 `deletion_log` 表
   - 更新 `TABLE_CONFIGS`
6. **数据迁移脚本**：回填 hash_id
7. **同步逻辑修改**：
   - `upsert_rows_with_lww` 去重键改用 hash_id
   - 修复列级 UNIQUE 不识别的 bug（可选）
8. **墓碑机制实现**：
   - 墓碑表 Provider
   - 墓碑写入逻辑（删除拦截）
   - 删除执行逻辑
   - 同步流程集成（Pull/Push/清理）
9. **测试验证**：
   - 合法化后的功能回归测试
   - 单表删除同步测试
   - 多表删除同步测试
   - 边界情况测试（重置同步时间、全量同步等）

### 13.8 TEXT PK 表的标准做法（参考）

三张 TEXT PK 表（todo_list、goal、mood_entries）100% 一致地采用：

- ID 在 **Provider 层**生成（前缀 + uuid[:8] 格式）
- 写入用 `_generic_insert`
- 目录在 `repository/providers/`

**todo_list**（`lifeprism/repository/providers/todo_provider.py`）：
- 模块级函数 `generate_todo_id()` (行 19-21)，返回 `f"t-{uuid.uuid4().hex[:8]}"`
- `create_todo` 方法 (行 195-254) 中：`if "id" not in data: data["id"] = generate_todo_id()`
- 写入：`self._generic_insert(data, on_conflict=self._ON_CONFLICT)`

**goal**（`lifeprism/repository/providers/goal_providers.py`）：
- `create_goal` 方法 (行 167-223) 中：`goal_id = f"goal-{str(uuid.uuid4())[:8]}"`，`data["id"] = goal_id`
- 写入：`self._generic_insert(data)`

**mood_entries**（`lifeprism/repository/providers/mood_providers.py`）：
- `create_mood_entry` 方法 (行 341-376) 中：`new_id = f"mood-{str(uuid.uuid4())[:8]}"`，`insert_data = {"id": new_id}`
- 写入：`self._generic_insert(insert_data)`

AUTOINCREMENT 表加 hash_id 时应遵循相同模式：Provider 层生成 hash_id，写入用 `_generic_insert`。

---

**文档结束（含合法化前置任务）**

新聊天会话请从"13.7 更新后的实现步骤"开始，先写 ADR 文档，然后按合法化三步 → schema 变更 → 墓碑机制的顺序实现。
