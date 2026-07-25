# PRD 3 墓碑同步流程 - 收尾方案（测试修复 + 文档）

> 日期：2026-07-23
> 依据：
> - `.scratch/deletion-sync-03-tombstone/prd.md`（PRD 3）
> - `docs/temp/2026-07-23-prd3-tombstone-impl-plan-v2.md`（实现方案 v2，已通过审查）
> - `docs/temp/2026-07-23-slice04-tests-docs-plan.md`（Slice 04 计划 v2）
> - 已完成的代码实现（Slice 01-03 + Slice 04 的 4.1）
> 前置状态：代码层全部实现完成，端到端测试文件已存在但存在 schema 缺陷

## 一、当前状态盘点

### 已完成代码
- ✅ `lifeprism/sync/constants.py`：`SYNC_TABLES` 已移除 `deletion_log`（line 62-65 注释说明）
- ✅ `lifeprism/repository/providers/deletion_log_provider.py`：完整 Provider（含 `write_tombstone_with_cursor` / `get_tombstone_with_cursor` / `create_tombstone_with_cursor` cursor 变体）
- ✅ `lifeprism/repository/sync_repository.py`：`execute_tombstone_delete` + `execute_tombstone_delete_with_cursor`
- ✅ `lifeprism/server/api/sync_cloud_api.py`：3 个端点（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`）+ Pydantic 模型 + 认证
- ✅ `lifeprism/sync/sync_client.py`：`_pull_deletion_log` / `_push_deletion_log` / `_cleanup_deletion_log` + `sync_once` 集成（line 264/270/278）
- ✅ `lifeprism/repository/aggregators/custom_record_aggregator.py`：`delete_entry` 写墓碑 + 实例化 `DeletionLogProvider`（line 87-89, 710）
- ✅ `test/core/unit/storage/test_deletion_log_provider.py`：8 个 seam 单元测试
- ✅ `test/core/unit/sync/test_deletion_log_sync_membership.py`：2 个 seam 成员测试（已翻转断言）

### 待修复
1. ❌ `test/core/integration/sync/test_sync_deletion.py` 存在 schema 缺陷：
   - 场景 2/4/15 通过 `custom_block_repository.create_custom_block()` 创建记录，缺少 `color` 字段（NOT NULL）
   - 错误：`sqlite3.IntegrityError: NOT NULL constraint failed: timeline_custom_block.color`

### 待实现（文档）
1. ❌ ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`（新建）
2. ❌ 既有 ADR `docs/adr/2026-07-22-deletion-log-table.md` supersede 处理
3. ❌ ADR `docs/adr/index.md` 新增条目 + 更新既有条目描述
4. ❌ spec `docs/specs/2026-07-16-data-sync-core-spec.md` 更新（墓碑同步章节 + Functional Checklist + key_function + 表数）
5. ❌ PRD `.scratch/deletion-sync-03-tombstone/prd.md` 更新（US16 + 决策汇总 + 模块改造清单）
6. ❌ 3 个 known-limitations 文件 + `docs/known-limitations/index.md` 更新
7. ❌ history-bugs `docs/history-bugs/2026-07-16-database-delete-not-synced.md` 标记已修复 + `docs/history-bugs/index.md` 更新

## 二、方案

### 2.1 修复测试 schema 缺陷

`timeline_custom_block.color` 在 `database.py:707` 是 NOT NULL，测试场景 2/4/15 的 `create_custom_block` 调用缺少该字段。

**修复方式**：在 3 处 `create_custom_block` 调用补充 `"color": "#ff0000"` 字段（参考既有测试 `test/core/unit/storage/test_l1_remaining_delete_tombstone.py:238` 的用法）。

涉及行：
- `test_sync_deletion.py:252-261`（场景 2）
- `test_sync_deletion.py:340-349`（场景 4）
- `test_sync_deletion.py:813-822`（场景 15）

修复后再次运行 `python -m pytest test/core/integration/sync/test_sync_deletion.py -v`，确认 16 个场景全绿。

### 2.2 运行全量测试确认无回归

```bash
python -m pytest test/ -q --tb=short
```

**预期**：除已知的 m009 pre-existing 失败（22 项，与 PRD 3 无关）外，其他测试全绿。

### 2.3 文档方案

#### 2.3.1 ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`（新建）

遵循 `docs/docs-rules/docs-write-rules.md` 的正文文档规则 + 既有 ADR 格式（参考 `2026-07-22-deletion-log-table.md`）：

**frontmatter**：
```yaml
version: 1.0
created_at: 2026-07-22
updated_at: 2026-07-23
last_updated: 创建墓碑同步机制 ADR，supersede 既有 deletion-log-table ADR 中"deletion_log 加入 SYNC_TABLES"决策
abstract: 删除同步墓碑机制决策，含专用端点（3 个）+ cursor 事务边界 + LWW 跳过简化 + Pull/Push 顺序 + 清理非原子 + deletion_log 从 SYNC_TABLES 移除
status: decided
```

**正文章节**（按 ADR 标准格式）：
1. **版本**（1.0 创建初稿）
2. **问题界定**：
   - 问题简述：删除操作跨端传播机制设计
   - 讨论范围：Pull/Push/Cleanup 三阶段流程、专用端点、事务边界、LWW、清理策略
   - 非讨论范围：schema 字段命名（见既有 ADR）、`_generic_delete` 写墓碑逻辑（PRD 2）
   - 模糊信息定义：cursor 变体、LWW 跳过简化、墓碑不可变
3. **现状**：引用既有 `2026-07-22-deletion-log-table.md`，说明其中"加入 SYNC_TABLES"的决策被本 ADR supersede
4. **决策前提**：
   - 前提 1：严格两节点（本地↔云端）
   - 前提 2：墓碑不可变（插入后不 UPDATE）
   - 前提 3：项目已采用 LWW 机制
   - 前提 4：HTTP 操作不能在事务内
   - 前提 5：删除-更新冲突作为已知限制接受
5. **可选方案**（5 个关键决策，每个含方案 A/B + 优势/劣势）：
   - 决策 1：专用端点 vs 复用数据同步端点
   - 决策 2：`deletion_log` 从 `SYNC_TABLES` 移除 vs 保留
   - 决策 3：cursor 事务边界 vs 独立连接
   - 决策 4：LWW 跳过简化 vs 完整 updated_at 比较
   - 决策 5：清理非原子（幂等重试）vs 分布式事务
6. **决策逻辑**：前提 → 方案映射表
7. **演进历史**：v1 表格
8. **最终决策**（8 条）：
   - 墓碑同步机制（deletion_log 表记录删除意图，Pull/Push/Cleanup 三阶段）
   - 专用端点（3 个端点独立于数据同步通道）
   - `deletion_log` 从 `SYNC_TABLES` 移除（supersede 既有 ADR）
   - 事务边界 cursor 版本（DELETE + 副本写入同事务）
   - INSERT OR IGNORE 语义（重复写入保留旧墓碑）
   - LWW 跳过简化（适用前提 + 边缘场景说明）
   - 清理非原子（依赖幂等重试）
   - Pull/Push 顺序（墓碑 Pull 在数据 Pull 前，墓碑 Push 在数据 Push 前）
9. **决策原因**：每条决策的理由
10. **后续影响**：
    - 链接到 spec 更新
    - 链接到 known-limitations
    - supersede 关系：`2026-07-22-deletion-log-table.md` 中"加入 SYNC_TABLES"决策被本 ADR supersede

#### 2.3.2 既有 ADR supersede 处理（含两个 ADR）

**ADR 1**：`docs/adr/2026-07-22-deletion-log-table.md`
- frontmatter 新增 `superseded_by: 2026-07-22-deletion-sync-tombstone.md`，`status` 改为 `superseded`
- 顶部 `## 版本` 章节后添加说明段：
  ```
  > **Supersede 说明**：本 ADR 中关于 `deletion_log` 加入 `SYNC_TABLES` 的决策（见"决策前提"前提 1、"后续影响"段落）已被 [2026-07-22-deletion-sync-tombstone.md](./2026-07-22-deletion-sync-tombstone.md) supersede（墓碑走专用通道，不走 SYNC_TABLES）。
  > 其余 schema 决策（字段命名 `target_table`、`update_at: True` 配置、LWW 比较字段 `updated_at`）仍然有效。
  ```
- 在"后续影响"段中标注"（已 supersede，见新 ADR）"

**ADR 2**：`docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md`
- 该 ADR 第 147 行"文档影响"段写有 `data-sync-core-spec.md` 同步表数量从 31 张变 30 张（移除 2 张 habit 表 + 新增 1 张 `deletion_log` 墓碑表：31 - 2 + 1 = 30）。此表述基于"deletion_log 加入 SYNC_TABLES"前提，前提已被新 ADR supersede
- 修改第 147 行，将"31 - 2 + 1 = 30"修正为"31 - 2 = 29 张静态表 + 1 张墓碑表（专用通道，不参与 SYNC_TABLES 数据同步，详见 `2026-07-22-deletion-sync-tombstone.md`）"
- 在该行末尾追加注释"（注：`deletion_log` 加入 SYNC_TABLES 决策已被 `2026-07-22-deletion-sync-tombstone.md` supersede）"

#### 2.3.3 ADR index.md 更新

修改 `docs/adr/index.md`：
- 在 `## deletion-log-table` 条目中：
  - 描述末尾追加"（注：'加入 SYNC_TABLES' 决策已被 `2026-07-22-deletion-sync-tombstone.md` supersede）"
  - `last_updated` 更新为 `2026-07-23`
- 在 `## add-hash-id-to-autoincrement-tables` 条目中：
  - 描述末尾追加"（注：第 147 行'31 - 2 + 1 = 30'表述基于 deletion_log 加入 SYNC_TABLES 前提，已 supersede，正确表述为'29 张静态表 + 1 张墓碑表专用通道'）"
  - `last_updated` 更新为 `2026-07-23`
- 新增 `## deletion-sync-tombstone` 条目
- **排序规则**：同日期 ADR 按"supersede 关系"排序——新 ADR（`deletion-sync-tombstone`）排在被 supersede 的 ADR（`deletion-log-table`、`add-hash-id-to-autoincrement-tables`）之前，让读者先看到最新决策

#### 2.3.4 spec 更新 `docs/specs/2026-07-16-data-sync-core-spec.md`

按 spec-write-rules.md 要求（需读取该规则确认结构）。更新内容：
- abstract：表数从"30 张"改为"29 张静态表 + 1 张墓碑表（专用通道）+ 动态 custom 表"
- 正文中相关表数描述同步更新
- **修正"同步的表"表格归类**（line 296-307）：
  - line 296 标题"同步的表（30 张静态表 + 动态表）"改为"同步的表（29 张静态表 + 动态表）"
  - line 306 删除"墓碑表（1张）"行（deletion_log 不再属于 SYNC_TABLES）
  - 在新章节"墓碑同步流程"中以独立段落说明"deletion_log 走专用通道（Pull/Push/Cleanup 三端点），不参与 SYNC_TABLES 数据同步"
- 新增"墓碑同步流程"章节（位置：在现有"30 张静态表增量同步"章节之后）：
  - 描述 Pull/Push/Cleanup 三阶段流程
  - 专用端点 + cursor 事务边界
  - Pull/Push 顺序（墓碑 Pull 在数据 Pull 前）
  - 失败处理（整个 sync_once 失败，不更新 last_sync_time）
- 新增 `<key_function>` 标签标注：
  - `sync_client._pull_deletion_log` / `_push_deletion_log` / `_cleanup_deletion_log`
  - 3 个 API 端点处理函数
  - `DeletionLogProvider` 6 个对外方法
  - `SyncRepository.execute_tombstone_delete` / `execute_tombstone_delete_with_cursor`
- Functional Checklist 新增"墓碑同步"功能分组，明确 9 项：
  1. 墓碑 Pull 在数据 Pull 之前执行
  2. 墓碑 Push 在数据 Push 之前执行
  3. 墓碑清理在同步成功后执行
  4. A 删除 → B 同步后记录消失
  5. 墓碑阻止已删记录被回写（US22）
  6. 重置 last_sync_time 后墓碑仍工作（US19）
  7. 全量首同步不传播墓碑（US20）
  8. 级联删除同步传播所有级联表
  9. sync_once 失败时不更新 last_sync_time（US18）

#### 2.3.5 PRD 更新 `.scratch/deletion-sync-03-tombstone/prd.md`

按方案 v2 4.3 节要求：
- US16 改为："墓碑比较使用 `updated_at` 字段作 LWW——墓碑不修改，插入时 `created_at == updated_at`，行为等价"（当前 PRD line 106 已是该表述，需确认无变化）
- "墓碑 LWW 比较"章节（line 71-73）确认描述一致
- "决策汇总"表"冲突策略"行（line 197）确认描述一致
- "模块改造清单"表（line 123-135）已包含全部模块，确认 `sync_cloud_api.py` 改造内容为"新增 3 个专用端点"
- "Implementation Decisions"中"未决问题"段落（line 275-279）已说明 `deletion_log` 从 `SYNC_TABLES` 移除的决策

**实际工作**：通读 PRD 全文，确认描述与最终实现一致；如有偏差，按"最小修改"原则更新描述性内容（不改验收标准）。

#### 2.3.6 known-limitations 新增 3 个文件 + 更新 index

按 `docs/docs-rules/known-limitations-and-debt-rules.md` 6.1 节模板（必备字段：问题描述、影响范围 + 严重程度、当前假设、触发条件、临时方案或计划改进、相关文档）。

**文件 1**：`docs/known-limitations/delete-update-conflict-not-resolved.md`
- 问题描述：A 删除记录后 B 更新同记录，同步后两端数据不一致（删除 vs 更新冲突）
- 影响范围：所有 SYNC_TABLES 表的删除操作
- 严重程度：低（两节点场景罕见）
- 当前假设：两节点不会同时对同一条记录做删除+更新
- 触发条件：A 删除 + B 更新同记录，在同步窗口内
- 临时方案/计划改进：不处理，接受为已知限制（PRD US23 明确）
- 相关文档：PRD US23 + ADR `2026-07-22-deletion-sync-tombstone.md`

**文件 2**：`docs/known-limitations/delete-recreate-conflict-tombstone-skip.md`
- 问题描述：删除后重新创建同 id 记录，旧墓碑 LWW 跳过简化逻辑不会再次触发删除
- 影响范围：所有 SYNC_TABLES 表
- 严重程度：低
- 当前假设：删除-重建是罕见操作
- 触发条件：删除记录后又用相同 id 重新创建
- 临时方案/计划改进：预期行为，新记录通过数据 sync 的 upsert 存活
- 相关文档：ADR LWW 跳过简化章节

**文件 3**：`docs/known-limitations/file-deletion-not-synced.md`
- 问题描述：文件系统删除操作不走 LifePrism 同步管控，不传播到对端
- 影响范围：所有 SYNC_DIRECTORIES（session/diary/agent/user）下的文件
- 严重程度：低（文件删除不传播是设计选择，文件冲突解决通过版本 hash 处理修改冲突，与删除传播是独立机制）
- 当前假设：用户不会在两端同时删除同一文件并期望传播
- 触发条件：A 删除文件 X，B 端 X 永久保留
- 临时方案/计划改进：不处理，记为已知限制
- 相关文档：ADR `2026-07-14-file-sync-conflict-resolution.md` + `2026-07-22-deletion-sync-tombstone.md`

**更新 `docs/known-limitations/index.md`**：
- 在"## 索引"章节末尾追加 3 个新条目，按既有格式（`### N. 标题` + 描述段）
- **修正"## 文档格式"章节**（line 95-102）：当前只列了 4 字段（问题描述、影响范围、相关文档、注意事项），与 `known-limitations-and-debt-rules.md` 6.1 节要求的 6 字段不一致。补充"当前假设"、"触发条件"、"临时方案或计划改进"3 个字段，对齐规则文档

#### 2.3.7 history-bugs 标记已修复 + 更新 index

修改 `docs/history-bugs/2026-07-16-database-delete-not-synced.md`：
- 元信息：`- **修复状态**: ⏳ 待修复` 改为 `- **修复状态**: ✅ 已修复（2026-07-23）`
- 在"## 候选修复方案"表后新增"## 修复实施"章节：
  - 实施时间：2026-07-23
  - 采用方案：Tombstone 表（方案 B）
  - 实施范围：PRD 1（Schema 变更）+ PRD 2（代码适配）+ PRD 3（墓碑同步流程）三个阶段
  - commit hash：通过 `git log --oneline -- lifeprism/config/database.py`（PRD 1）/ `lifeprism/repository/base_providers/lw_base_data_provider.py`（PRD 2）/ `lifeprism/sync/sync_client.py`（PRD 3）查询各阶段对应 commit hash
  - 关键文件：deletion_log_provider.py / sync_client.py / sync_cloud_api.py / sync_repository.py / custom_record_aggregator.py
  - 验收：16 个端到端测试场景全绿，无回归
  - 引用 ADR：`docs/adr/2026-07-22-deletion-sync-tombstone.md`

**更新 `docs/history-bugs/index.md`**：找到 `## 2026-07-16-database-delete-not-synced` 条目（line 36-41），将内容摘要中"P1，待修复"改为"P1，已修复 2026-07-23"，补充"采用 Tombstone 表方案（deletion_log 墓碑表 + 专用端点 Pull/Push/Cleanup 三阶段同步 + cursor 事务边界）"。

### 2.4 执行顺序

1. **修复测试 schema 缺陷**（2.1）→ 运行 `test_sync_deletion.py` 确认全绿
2. **运行全量测试**（2.2）→ 确认无回归
3. **写 ADR** `2026-07-22-deletion-sync-tombstone.md`（2.3.1）
4. **修改既有 ADR** `2026-07-22-deletion-log-table.md` 标记 superseded（2.3.2）
5. **更新 ADR index.md**（2.3.3）
6. **更新 spec** `2026-07-16-data-sync-core-spec.md`（2.3.4）
7. **更新 PRD** `.scratch/deletion-sync-03-tombstone/prd.md`（2.3.5）
8. **新建 3 个 known-limitations 文件**（2.3.6）
9. **更新 known-limitations/index.md**（2.3.6）
10. **标记 history-bugs 已修复**（2.3.7）
11. **更新 history-bugs/index.md**（2.3.7）
12. **最终验证**：再次运行测试确认全绿

## 三、文件变更清单

### 修改（2 个测试 + 10 个文档）
1. `test/core/integration/sync/test_sync_deletion.py` — 3 处补充 `color` 字段
2. `docs/adr/2026-07-22-deletion-sync-tombstone.md` — 新建
3. `docs/adr/2026-07-22-deletion-log-table.md` — 标记 superseded
4. `docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md` — 修正第 147 行表数表述 + supersede 标注
5. `docs/adr/index.md` — 新增条目 + 更新 2 个既有条目描述
6. `docs/specs/2026-07-16-data-sync-core-spec.md` — 修正表格归类 + 新增章节 + Functional Checklist 9 项 + key_function
7. `.scratch/deletion-sync-03-tombstone/prd.md` — 描述性更新
8. `docs/known-limitations/delete-update-conflict-not-resolved.md` — 新建
9. `docs/known-limitations/delete-recreate-conflict-tombstone-skip.md` — 新建
10. `docs/known-limitations/file-deletion-not-synced.md` — 新建
11. `docs/known-limitations/index.md` — 追加 3 个条目 + 修正"文档格式"章节
12. `docs/history-bugs/2026-07-16-database-delete-not-synced.md` — 标记已修复 + 新增"修复实施"章节
13. `docs/history-bugs/index.md` — 更新条目摘要

## 四、风险与对策

### 风险 1：测试 schema 修复后仍有其他失败
**对策**：用 `-x` 标志逐个修复，每修一个跑一次。若发现 mock 粒度问题（如 sync_once 需要更多 mock），按方案 v2 风险 5 对策处理。

### 风险 2：ADR 与既有 ADR 描述冲突
**对策**：既有 ADR 只标记 superseded 部分（"加入 SYNC_TABLES"决策），schema 决策（字段命名、update_at、LWW 字段）保持有效。新 ADR 明确 supersede 范围。

### 风险 3：spec 表数描述遗漏
**对策**：通读 spec 全文，搜索所有"30 张"出现位置逐一更新为"29 张静态表 + 1 张墓碑表（专用通道）"。

### 风险 4：PRD 描述更新影响 issue 文件
**对策**：PRD 更新仅修改描述性内容，不改变验收标准。issue 文件已执行完成，不回溯修改。

### 风险 5：known-limitations 文件重叠
**对策**：3 个文件主题明确不重叠——删除-更新冲突（操作类型冲突）、删除-重建冲突（同 id 复用）、文件删除不同步（文件系统非数据库）。

### 风险 6：history-bugs 修复方案描述不准确
**对策**：引用实际 commit hash（待定）+ ADR 链接，让读者可追溯。

## 五、不做什么

1. 不修改代码层实现（已完成且通过单元测试）
2. 不修改 PRD 验收标准（仅描述性更新）
3. 不修改既有 issue 文件（已执行完成）
4. 不创建额外的 progress / technical-debt 文档（无对应场景）
5. 不修改 ARCHITECTURE.md（无架构变更，仅同步流程细化）
