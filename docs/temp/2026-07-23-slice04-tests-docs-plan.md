# PRD 3 Slice 04 剩余实现方案 v2（端到端测试 + 文档）

> 依据：`docs/temp/2026-07-23-prd3-tombstone-impl-plan-v2.md` Slice 04 的 4.2 + 4.3
> 日期：2026-07-23
> 前置状态：Slice 01-03 代码 + Slice 04 的 4.1（custom_record_aggregator 改造）已完成
> 修订：v2 — 修复审查报告 C1-C8 + M1-M7 + m1-m8

## 一、范围界定

### 已完成（不重复）
- 所有代码层实现（deletion_log_provider cursor 方法、sync_repository cursor 方法、3 个 API 端点、sync_client 3 个方法 + sync_once 集成、custom_record_aggregator.delete_entry 改造）
- 单元测试（test_deletion_log_provider.py 8 个 seam、test_deletion_log_sync_membership.py 2 个 seam）

### 待实现
1. 端到端集成测试 `test/core/integration/sync/test_sync_deletion.py`（覆盖 PRD S2 全部 10 个测试接缝）
2. ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`
3. 既有 ADR `docs/adr/2026-07-22-deletion-log-table.md` 标记 superseded 部分
4. spec 更新 `docs/specs/2026-07-16-data-sync-core-spec.md`（含 Functional Checklist + key_function）
5. PRD 更新 `.scratch/deletion-sync-03-tombstone/prd.md`
6. known-limitations 新增（2 个独立文件）
7. history-bugs 标记已修复 + 索引更新
8. 各 index.md 同步更新

## 二、端到端集成测试方案

### 测试文件
`test/core/integration/sync/test_sync_deletion.py`，使用 `pytestmark = pytest.mark.core` 模块级标记（与 test_sync_conflict_resolve.py 一致）

### 测试模式
参考 `test/core/integration/sync/test_sync_conflict_resolve.py`：
- 模块级 `initialized_db` fixture（初始化所有表）
- `sync_repository` + `sync_client` fixture（含 `mock_event_loop` fixture）
- mock httpx 响应（模块级 `_make_mock_response` helper 函数，非 fixture）
- 每个测试前后清理 `deletion_log` 表 + 相关业务表

### 测试场景（对齐 PRD S2 + 端到端验收标准，共 14 个场景）

#### 第一组：基本删除传播（PRD US21 / 端到端验收 1-2）

**场景 1：TEXT 主键表删除 → Push 同步传播**
- 插入 mood_entries 记录（TEXT PK 表）
- 通过 mood_provider.delete() 删除（_generic_delete 写墓碑，record_id = TEXT id）
- 调用 `_push_deletion_log` → mock httpx 捕获请求
- 断言：httpx 被调用，payload 含 1 条墓碑，target_table=mood_entries，source=local，record_id=TEXT id

**场景 2：AUTOINCREMENT 表删除 → Push 同步传播（C1 修复）**
- 插入 timeline_custom_block 记录（AUTOINCREMENT 表，有 hash_id）
- 通过 provider.delete() 删除（_generic_delete 写墓碑，record_id = hash_id）
- 调用 `_push_deletion_log` → mock httpx 捕获请求
- 断言：墓碑 record_id = hash_id（非自增 id），target_table=timeline_custom_block

**场景 3：Pull 墓碑 → 本地执行 DELETE + 写副本**
- 本地插入 1 条 mood_entries 记录
- mock httpx 返回 1 条云端墓碑（target_table=mood_entries, record_id=本地记录 id）
- 调用 `_pull_deletion_log`
- 断言：记录被删除，deletion_log 新增 1 条 source=cloud 副本

**场景 4：Pull 墓碑 → AUTOINCREMENT 表按 hash_id 删除（C1 修复）**
- 本地插入 1 条 timeline_custom_block 记录
- mock httpx 返回 1 条云端墓碑（target_table=timeline_custom_block, record_id=该记录 hash_id）
- 调用 `_pull_deletion_log`
- 断言：`execute_tombstone_delete_with_cursor` 用 `WHERE hash_id = ?` 删除（非 `WHERE id = ?`），记录被删除

#### 第二组：墓碑顺序与不被回写（PRD US22 / 端到端验收 2）

**场景 5：墓碑 Pull 在数据 Pull 之前 + 不被数据 Pull 写回（C3 修复 / US22）**
- 本地插入 1 条 mood_entries 记录
- mock httpx：
  - `/pull-deletion-log` 返回 1 条墓碑（target_table=mood_entries, record_id=该记录 id）
  - `/pull`（数据 Pull）返回该记录的 upsert 数据（模拟云端仍有该记录）
- 调用 `sync_once`（mock 掉文件同步 + 动态表对比）
- 断言：最终本地无该记录（墓碑 Pull 的 DELETE 覆盖了数据 Pull 的 upsert）
- 断言：调用顺序为 `_pull_deletion_log` → `pull_from_remote`（可通过 mock 调用顺序断言）

#### 第三组：LWW 与失败处理（PRD US16-18 / 端到端验收 8）

**场景 6：LWW 跳过（本地已有墓碑）**
- 本地预先写入墓碑（source=local）
- mock httpx 返回同 (target_table, record_id) 的云端墓碑
- 调用 `_pull_deletion_log`
- 断言：不执行 DELETE，不覆盖本地墓碑（INSERT OR IGNORE 保留旧墓碑）

**场景 7：Pull 失败事务回滚**
- 本地插入 2 条记录
- mock httpx 返回 2 条墓碑
- mock `execute_tombstone_delete_with_cursor` 在第 2 条抛异常
- 调用 `_pull_deletion_log`
- 断言：第 1 条 DELETE 也被回滚（事务未 commit），deletion_log 无 cloud 副本

**场景 8：sync_once 失败时 last_sync_time 未更新（C7 修复 / US18）**
- 预设 `sync.last_sync_time` = 某固定值
- mock httpx 在 `/pull-deletion-log` 抛 httpx.HTTPStatusError
- 调用 `sync_once`（预期抛异常）
- 断言：`sync.last_sync_time` 仍为预设值（未更新）

#### 第四组：墓碑清理（PRD US14-15 / 端到端验收 7）

**场景 9：墓碑清理在同步成功后执行**
- 插入 2 条墓碑：1 条 created_at 远早于 last_sync_time，1 条 created_at 晚于
- 调用 `_cleanup_deletion_log(remote_url, api_key, last_sync_time)`，mock httpx cleanup 端点返回成功
- 断言：本地仅 created_at <= last_sync_time 的墓碑被清理，新墓碑保留

#### 第五组：动态表与级联删除（PRD / 端到端验收 5-6）

**场景 10：动态表删除写墓碑（custom_record_aggregator）**
- 创建自定义记录类型 + 录入 entry
- 调用 `CustomRecordRepository.delete_entry` 删除
- 断言：deletion_log 新增 1 条，target_table=custom_<slug>，record_id=entry_id，source=local
- 断言：记录已物理删除

**场景 11：delete_entry 不存在记录不产生孤儿墓碑**
- 调用 `delete_entry` 传入不存在的 entry_id
- 断言：抛 EntityNotFoundError，deletion_log 无新增

**场景 12：级联删除同步传播所有级联表（C2 修复）**
- 插入 habit + habit_challenges + habit_checkins 各 1 条（三表都在 SYNC_TABLES，habit_chains/habit_chain_nodes 已移除不在范围）
- 通过 habit_provider.delete() 删除 habit（_generic_delete 写 habit 墓碑）
- 说明：当前 _generic_delete 只为被删表本身写墓碑，级联删除需调用方逐表删除
- 调用方（如 habit_service）逐表 delete habit_challenges + habit_checkins（各写墓碑）
- 调用 `_push_deletion_log` → mock httpx 捕获请求
- 断言：payload 含 3 条墓碑（target_table 分别为 habits / habit_challenges / habit_checkins）

#### 第六组：边界场景（PRD US19-20 / 端到端验收 3-4）

**场景 13：重置 last_sync_time 后墓碑仍工作（C4 修复 / US19 / G7）**
- 插入若干墓碑（source=local 和 source=cloud 各几条）
- 设置 `sync.last_sync_time = ""`（模拟重置）
- 调用 `_push_deletion_log(remote_url, api_key, "")` 
- 断言：`get_tombstones_since("")` 返回所有未清理墓碑，httpx 被调用

**场景 14：全量首同步不传播墓碑（C5 修复 / US20）**
- mock `_check_cloud_initialized` 返回 False（触发首同步路径）
- mock httpx 所有端点
- 调用 `sync_once`
- 断言：`_pull_deletion_log` / `_push_deletion_log` / `_cleanup_deletion_log` 均未被调用（可通过 mock 断言 call_count == 0）

#### 第七组：多表批量删除（PRD S2）

**场景 15：多表批量删除同步（C6 修复）**
- 一次 sync_once 中删除 mood_entries + timeline_custom_block + diary 各 1 条
- 调用 `_push_deletion_log`
- 断言：payload 含 3 条墓碑，target_table 分别为 3 张表

#### 第八组：空场景（边界保护）

**场景 16：空墓碑 Pull/Push 不报错**
- Pull：mock httpx 返回空 tombstones 列表 → 调用 `_pull_deletion_log` → 断言：httpx 被调用但返回空，事务不执行 DELETE
- Push：本地无 source=local 墓碑 → 调用 `_push_deletion_log` → 断言：httpx 不被调用（本地查询为空时提前返回）

### 不覆盖的场景（说明理由）
- **API 端点 HTTP 层测试**：push/pull/cleanup-deletion-log 端点的 HTTP 请求/响应/认证属于 core/api 范围，不在本集成测试覆盖。3 个端点的业务逻辑（LWW + DELETE + 写副本）通过 mock httpx + 真实 SyncRepository 间接验证。
- **双数据库端到端**：mock httpx 已覆盖 SyncClient 行为（LWW、事务、顺序），双数据库增加复杂度但无额外覆盖价值。
- **删除-更新冲突反向测试**：PRD US23 明确列为"已知限制接受——不自动处理"。此场景的预期行为在 known-limitations 文档中记录，无需测试锁定（因为"不处理"意味着行为不确定，测试无法断言确定结果）。

## 三、文档方案

### 3.1 ADR `docs/adr/2026-07-22-deletion-sync-tombstone.md`
遵循 ADR 格式（参考 `2026-07-22-deletion-log-table.md`），包含完整章节：

- frontmatter: version 1.0, status: decided
- **问题界定**：删除操作无法跨端同步的传播机制设计
- **现状**：引用既有 ADR `2026-07-22-deletion-log-table.md`，说明其"deletion_log 加入 SYNC_TABLES"的决策已在本 ADR 中被 supersede
- **决策前提**：两节点假设、墓碑不可变、LWW 机制
- **可选方案**（M6 修复，至少为关键决策列方案 A/B + 优势/劣势）：
  - 决策 1：专用端点 vs 复用数据同步端点
  - 决策 2：deletion_log 从 SYNC_TABLES 移除 vs 保留
  - 决策 3：cursor 事务边界 vs 独立连接
  - 决策 4：LWW 跳过简化 vs 完整 updated_at 比较
  - 决策 5：清理非原子 vs 分布式事务
- **决策逻辑**：前提 → 方案映射表
- **最终决策**：
  1. 墓碑同步机制（deletion_log 表记录删除意图，Pull/Push/Cleanup 三阶段）
  2. 专用端点（3 个端点独立于数据同步通道）
  3. `deletion_log` 从 `SYNC_TABLES` 移除（supersede 既有 ADR）
  4. 事务边界 cursor 版本（DELETE + 副本写入同事务，_with_cursor 变体保证原子性）
  5. INSERT OR IGNORE 语义（重复写入保留旧墓碑）
  6. LWW 跳过简化（适用前提 + 边缘场景说明）
  7. 清理非原子（依赖幂等重试）
  8. Pull/Push 顺序（墓碑 Pull 在数据 Pull 前，墓碑 Push 在数据 Push 前）
- **决策原因**：每条决策的理由
- **后续影响**：链接到 spec 更新、known-limitations

### 3.2 既有 ADR supersede 处理（M1 修复）
修改 `docs/adr/2026-07-22-deletion-log-table.md`：
- frontmatter 新增 `superseded_by: 2026-07-22-deletion-sync-tombstone.md`，status 改为 `superseded`
- 顶部添加说明："本 ADR 中关于 deletion_log 加入 SYNC_TABLES 的决策已被 `2026-07-22-deletion-sync-tombstone.md` supersede（墓碑走专用通道）。其余 schema 决策（字段命名、update_at 配置、LWW 比较字段）仍然有效。"

修改 `docs/adr/index.md`：
- 更新 `2026-07-22-deletion-log-table.md` 的描述，注明 supersede 关系
- 新增 `2026-07-22-deletion-sync-tombstone.md` 索引项

### 3.3 spec 更新 `docs/specs/2026-07-16-data-sync-core-spec.md`（M3/M4/m5 修复）
- 新增"墓碑同步流程"章节（描述 Pull/Push/Cleanup 三阶段流程 + 专用端点 + cursor 事务边界）
- 新增 `<key_function>` 标签标注对外接口：
  - `sync_client._pull_deletion_log` / `_push_deletion_log` / `_cleanup_deletion_log`
  - 3 个 API 端点处理函数
  - `DeletionLogProvider.create_tombstone` / `get_tombstones_since` / `cleanup_before` / `write_tombstone_with_cursor` / `get_tombstone_with_cursor` / `create_tombstone_with_cursor`
  - `SyncRepository.execute_tombstone_delete` / `execute_tombstone_delete_with_cursor`
- 更新 Functional Checklist 新增"墓碑同步"功能分组（含可逐项打勾的功能点）：
  - [ ] 墓碑 Pull 在数据 Pull 之前执行
  - [ ] 墓碑 Push 在数据 Push 之前执行
  - [ ] 墓碑清理在同步成功后执行
  - [ ] 墓碑同步失败时 last_sync_time 不更新
  - [ ] deletion_log 不在 SYNC_TABLES 中
  - [ ] TEXT 主键表删除可传播
  - [ ] AUTOINCREMENT 表删除按 hash_id 传播
  - [ ] 动态表删除可传播
  - [ ] 全量首同步不传播墓碑
- 更新表数描述：abstract 改为"29 张静态表 + 1 张墓碑表（专用通道）+ 动态 custom 表"，同步更新正文相关表述

### 3.4 PRD 更新 `.scratch/deletion-sync-03-tombstone/prd.md`（M2 修复）
按 v2 4.3 要求更新：
- US16：改为"墓碑比较使用 `updated_at` 字段作 LWW——墓碑不修改，插入时 `created_at == updated_at`，行为等价"
- "墓碑 LWW 比较"章节：同步更新描述
- "决策汇总"表"冲突策略"行：更新为"墓碑 `updated_at` 作 LWW（等价于 `created_at`，因墓碑不修改）"
- "模块改造清单"：更新 `sync_cloud_api.py` 改造内容为"新增 3 个专用端点"
- "Implementation Decisions"中 `deletion_log` 从 `SYNC_TABLES` 移除的说明

### 3.5 known-limitations 新增（M5 修复，拆分为 2 个独立文件）

**文件 1**：`docs/known-limitations/delete-update-conflict-not-resolved.md`
按 known-limitations-and-debt-rules.md 6.1 节必备字段：
- 问题描述：A 删除记录后 B 更新同记录，同步后两端数据不一致
- 影响范围 + 严重程度：低（两节点场景罕见）
- 当前假设：两节点不会同时对同一条记录做删除+更新
- 触发条件：A 删除 + B 更新同记录，在同步窗口内
- 临时方案/计划改进：不处理，接受为已知限制
- 相关文档：引用 PRD US23 + ADR

**文件 2**：`docs/known-limitations/delete-recreate-conflict-tombstone-skip.md`
按同模板：
- 问题描述：删除后重新创建同 id 记录，旧墓碑 LWW 跳过简化逻辑不会再次触发删除
- 影响范围 + 严重程度：低
- 当前假设：删除-重建是罕见操作
- 触发条件：删除记录后又用相同 id 重新创建
- 临时方案/计划改进：预期行为，新记录通过数据 sync 的 upsert 存活
- 相关文档：引用 ADR LWW 跳过简化章节

更新 `docs/known-limitations/index.md`：新增 2 个索引项

### 3.6 history-bugs 标记已修复
修改 `docs/history-bugs/2026-07-16-database-delete-not-synced.md`：
- 修复状态改为 ✅ 已修复
- 补充修复方案说明（Tombstone 墓碑机制 + PRD 1/2/3）
- 补充修复时间

更新 `docs/history-bugs/index.md`：更新该条目的内容摘要（从"P1，待修复"改为"已修复"）

## 四、文件变更清单

### 新建
1. `test/core/integration/sync/test_sync_deletion.py` — 端到端集成测试（16 个场景）
2. `docs/adr/2026-07-22-deletion-sync-tombstone.md` — 墓碑同步 ADR
3. `docs/known-limitations/delete-update-conflict-not-resolved.md` — 已知限制 1
4. `docs/known-limitations/delete-recreate-conflict-tombstone-skip.md` — 已知限制 2

### 修改
1. `docs/adr/2026-07-22-deletion-log-table.md` — 标记 superseded 部分
2. `docs/adr/index.md` — 新增 ADR 索引项 + 更新既有项描述
3. `docs/specs/2026-07-16-data-sync-core-spec.md` — 新增墓碑同步章节 + Functional Checklist + key_function + 表数更新
4. `.scratch/deletion-sync-03-tombstone/prd.md` — 更新 US16 / 决策汇总 / 模块改造清单
5. `docs/known-limitations/index.md` — 新增 2 个索引项
6. `docs/history-bugs/2026-07-16-database-delete-not-synced.md` — 标记已修复
7. `docs/history-bugs/index.md` — 更新条目摘要

## 五、风险与对策

### 风险 1：mock httpx 无法覆盖云端处理逻辑
**对策**：集成测试聚焦 SyncClient 行为（LWW、事务、顺序），云端端点逻辑由 DeletionLogProvider 单元测试覆盖。

### 风险 2：测试隔离（deletion_log 残留）
**对策**：每个测试前后清理 deletion_log 表 + 相关业务表（参考 test_deletion_log_provider.py 的 cleanup fixture）。

### 风险 3：ADR 与既有 ADR 冲突（M1 修复）
**问题**：`2026-07-22-deletion-log-table.md` 声称 deletion_log 加入 SYNC_TABLES，但实际已移除。
**对策**：既有 ADR 标记 superseded_by + status=superseded，顶部添加说明。新 ADR 明确 supersede 关系。index.md 同步更新。

### 风险 4：mock 粒度过粗导致测试脆弱
**对策**：mock httpx 在 `httpx.post` 层级，验证请求 URL + payload；不 mock SyncRepository 内部方法（保持真实数据库操作）。

### 风险 5：级联删除场景依赖调用方逐表删除
**问题**：`_generic_delete` 只为被删表本身写墓碑，级联删除需调用方（如 habit_service）逐表删除。
**对策**：测试场景 12 直接调用 provider.delete() 逐表删除，验证每张表都写墓碑。不依赖 habit_service 的级联逻辑。

### 风险 6：场景 5（顺序验证）mock 复杂度高
**问题**：需同时 mock pull-deletion-log 和 pull（数据）两个端点，且验证调用顺序。
**对策**：使用 `mock.call_order` 或 `MagicMock.mock_calls` 断言调用顺序。

### 风险 7：spec 表数描述不一致（M4 修复）
**对策**：明确更新后的表述为"29 张静态表 + 1 张墓碑表（专用通道）+ 动态 custom 表"。

### 风险 8：PRD 更新可能影响 issue 文件
**对策**：PRD 更新仅修改描述性内容（US16、决策汇总等），不改变验收标准。

## 六、执行顺序

1. 写端到端测试 `test_sync_deletion.py`（16 个场景，为既有代码补充回归测试）
2. 运行测试确认全绿
3. 写 ADR `2026-07-22-deletion-sync-tombstone.md`
4. 修改既有 ADR `2026-07-22-deletion-log-table.md` 标记 superseded
5. 更新 spec（墓碑同步章节 + Functional Checklist + key_function + 表数）
6. 更新 PRD（US16 + 决策汇总 + 模块改造清单）
7. 新建 2 个 known-limitations 文件 + 更新索引
8. 标记 history-bugs 已修复 + 更新索引
9. 更新 ADR index.md
10. 运行全量测试确认无回归
