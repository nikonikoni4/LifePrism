---
version: 2.4
created_at: 2026-04-10
updated_at: 2026-08-18
last_updated: 新增 startup-optimization-phased-strategy ADR（启动慢优化分阶段执行策略：1+3 先做、2 暂不修改只记录）
abstract: 架构决策目录索引，用于导航 ADR 文档并说明长期设计取舍。
---

## startup-optimization-phased-strategy
- updated_at: 2026-08-19
- path: `docs/adr/2026-08-19-startup-optimization-phased-strategy.md`
- 触发规则：当需要理解为什么启动慢优化只执行方案 1（删除微信 token 测试）和方案 3（send_heartbeat 改 fire-and-forget）而暂不执行方案 2（启动同步改 fire-and-forget）、或后续启动同步异步化时读取（含锁内移、shutdown 处理、task 引用持有等 6 条必须满足的约束）
- 内容摘要：LifePrism 启动慢优化采用分阶段策略。方案 1+3 风险极低先执行，方案 2 涉及锁释放时机变更、违反 ADR 2026-07-25-global-task-state 决策 4 契约、shutdown 冲突、task GC 等多重风险暂不修改只记录。3 个决策前提：1+3 可能已足够、方案 2 风险暂时不可接受、分阶段可降低决策风险。备选触发：1+3 修复后启动仍慢则启动方案 2，按 6 条约束执行（锁内移、task 引用持有、shutdown 处理未完成任务、SSH 隧道保持 await、task 内部异常处理、ADR 2026-07-25 同步更新）

## custom-prompt-user-role-injection
- updated_at: 2026-08-18
- path: `docs/adr/2026-08-18-custom-prompt-user-role-injection.md`
- 触发规则：当需要理解 chat agent 自定义规则（custom_prompt.md）为什么以 user role 而非 system 注入、注入位置为何在组装期前缀区而非会话历史、`<system-reminder>` 包裹与说明文本的设计依据、或修改 Context.build_prefix_messages / 注入格式时读取
- 内容摘要：用户自定义规则采用 user role 前缀区动态注入（方案 B），否决 system prompt 追加（方案 A，备选）与首轮持久化（方案 C，compact 会压缩丢失）。4 个决策前提：Claude Code 实证以 user role 注入 CLAUDE.md（已验证）、用户规则不应凌驾于系统规则（角色层级即注入缓解）、tools->system->messages 稳定前缀缓存共识、provider 接受连续 user 消息（假设，待实测）。备选触发：规则完全无法遵守时切回方案 A。同步零改动（agent/ 白名单 + 空文件过滤天然覆盖）。

## ssh-tunnel-encryption
- updated_at: 2026-07-27
- path: `docs/adr/2026-07-27-ssh-tunnel-encryption.md`
- 触发规则：当需要理解为什么新增 SSH 隧道模式、HTTP/HTTPS/SSH 三种模式并存的选型依据、外部环境约束（家庭 IP 变动、ICP 备案复杂）如何驱动技术选型、或修改 sync.connection_mode 配置时读取
- 内容摘要：在家庭网络 IP 变动 + 国内服务器 ICP 备案复杂的场景下，新增 SSH 隧道作为云端同步的加密通道，与已有 HTTP/HTTPS 模式并存。9 个决策前提（IP 变动、防火墙限制、HTTP 明文风险、HTTPS 需证书、证书需域名、域名需备案、流程复杂不可接受、三种模式并存、用户熟悉 SSH）。4 个可选方案：A（HTTPS+域名+备案，备选）、B（HTTP+API Key，内网测试用）、C（SSH 隧道，当前选择）、D（VPN/内网穿透，用户不熟悉否决）。备选触发：备案完成→A，内网测试→B，熟悉 VPN→D。

## global-task-state
- updated_at: 2026-07-25
- path: `docs/adr/2026-07-25-global-task-state.md`
- 触发规则：当需要理解本地任务（10点序列 + 4h 任务）与云端 sync_once 的互斥机制、跨线程通信方案选型（threading.Condition）、backup_documents 为何并入 10点任务、4h 任务为何纳入 LOCAL_TASK 互斥、或修改 GlobalTaskState 单例时读取
- 内容摘要：引入 GlobalTaskState 单例（IDLE/LOCAL_TASK/CLOUD_SYNC 三态），用 threading.Condition 跨线程协调本地定时任务与云端 sync_once 互斥。8 个决策——（决策 1）三态枚举 + threading.Condition + LazySingleton；（决策 2）backup_documents 从独立 03:00 cron 移除并入 10点任务子步骤（解决凌晨3点未开机不补备份问题），执行序列 incremental_sync → dreaming → backup_documents；（决策 3）4h process_session_message 纳入 LOCAL_TASK 互斥（写 behavior.md 与 sync 冲突）；（决策 4）云端 sync 遇 LOCAL_TASK 放弃本次 + 调 ping 端点（不等待，10分钟周期容忍）；（决策 5）10点任务遇 CLOUD_SYNC 用有限等待 + 超时降级（5分钟，dreaming/backup 仍执行）；（决策 6）数据库备份不参与互斥（SQLite Online Backup 不阻塞读写）；（决策 7）跨线程通信用 threading.Condition 而非 asyncio.Lock/线程 Lock（需 wait/notify 能力）；（决策 8）与现有 SyncClient._is_syncing 共存不整合（拆分关注点）。supersede `2026-07-17-data-backup-strategy.md` 中"文档每天 03:00 备份一次"决策。

## deletion-sync-tombstone
- updated_at: 2026-07-23
- path: `docs/adr/2026-07-22-deletion-sync-tombstone.md`
- 触发规则：当需要理解墓碑同步流程架构（专用端点 vs SYNC_TABLES、事务边界设计、LWW 简化策略、Aggregator 实例化方式、sync_once 顺序）、或修改墓碑同步相关代码时读取
- 内容摘要：墓碑同步流程的 5 个关键决策——（决策 1）从 `SYNC_TABLES` 移除 `deletion_log`，新增 3 个专用端点（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`），避免双重同步和 LWW 语义不匹配；（决策 2）HTTP 在事务外，DELETE + 墓碑写入在事务内（cursor 变体方法），保证原子性且 HTTP 超时不锁库；（决策 3）本地已有墓碑则 `INSERT OR IGNORE` 跳过（不比较 `updated_at`），墓碑不更新使 LWW 比较无意义；（决策 4）`CustomRecordRepository.__init__` 实例化 `DeletionLogProvider`（符合 Repository 规则，不导入全局单例）；（决策 5）`sync_once` 流程为 墓碑 Pull → 数据 Pull → 墓碑 Push → 数据 Push → 文件 → 清理 → 更新 `last_sync_time`。supersede `2026-07-22-deletion-log-table.md` 中"deletion_log 加入 SYNC_TABLES"决策。

## deletion-log-table
- updated_at: 2026-07-23
- path: `docs/adr/2026-07-22-deletion-log-table.md`
- 触发规则：当需要理解 deletion_log 墓碑表 schema 决策、字段命名 target_table 而非 table_name 的理由、update_at=True 配置语义、LWW 比较字段选择、或修改 DELETION_LOG_CONFIG 时读取
- 内容摘要：新增 deletion_log 墓碑表的 schema 决策（字段命名、时间戳配置、LWW 比较字段）。三个关键决策——（决策 1）字段名用 `target_table` 而非 `table_name`，避免与 schema 配置 dict 的 `table_name` 元字段混淆；（决策 2）配置 `update_at: True`，让墓碑表参与 LWW 比较路径；（决策 3）LWW 比较用 `updated_at` 而非 `created_at`，墓碑不更新使 `updated_at == created_at`，比较结果等价。**部分被 supersede**：原决策中"deletion_log 加入 SYNC_TABLES"已被 [2026-07-22-deletion-sync-tombstone.md](./2026-07-22-deletion-sync-tombstone.md) 取代（改用专用端点）；schema 决策仍然有效。

## add-hash-id-to-autoincrement-tables
- updated_at: 2026-07-23
- path: `docs/adr/2026-07-22-add-hash-id-to-autoincrement-tables.md`
- 触发规则：当需要理解为什么为 6 张 AUTOINCREMENT 表新增 hash_id 字段、迁移方法选型（ALTER + 回填 + CREATE UNIQUE INDEX vs 删表重建）、或修改迁移脚本时读取
- 内容摘要：为实现删除同步功能，为 6 张 AUTOINCREMENT 表新增 `hash_id TEXT NOT NULL UNIQUE` 字段作为跨端稳定标识。用户初始倾向删表重建（因简单且不了解 SQLite ALTER TABLE 限制），经评估后采用 ALTER TABLE ADD COLUMN + 回填 + CREATE UNIQUE INDEX 方式（不丢数据且与 m012 一致）。决策前提：删除同步需要墓碑表模式、墓碑需要跨端稳定标识、自增 id 两端不同、项目已采用 LWW 策略、SQLite ALTER TABLE 限制。未来多客户端并发场景下 LWW + 墓碑不足时考虑 CRDT。文档影响已修正：同步表数量从 31 张变 29 张（见 [2026-07-22-deletion-sync-tombstone.md](./2026-07-22-deletion-sync-tombstone.md)）。

## add-hash-id-to-remaining-autoincrement-tables
- updated_at: 2026-07-24
- path: `docs/adr/2026-07-24-add-hash-id-to-remaining-autoincrement-tables.md`
- 触发规则：当需要理解为什么 daily_focus/weekly_focus/category_map_cache 在 m016 中补充 hash_id、或修改这 3 张表的 hash_id 相关配置时读取
- 内容摘要：m015 审计遗漏了 3 张 AUTOINCREMENT 同步表（daily_focus/weekly_focus/category_map_cache），导致墓碑跨端删除命中错误记录。采用与 m015 相同方法（ALTER + CREATE UNIQUE INDEX + 回填）补充 hash_id。category_map_cache 有确认的删除路径，不能作为已知限制接受。

## hash-id-sync-only-identifier
- updated_at: 2026-07-22
- path: `docs/adr/2026-07-22-hash-id-sync-only-identifier.md`
- 触发规则：当需要理解为什么 hash_id 不作为主键、_PRIMARY_KEY 保持自增 id、_generic_insert 兜底生成逻辑、或修改 Provider 主键相关代码时读取
- 内容摘要：hash_id 定位为同步专用标识（非主键），`_PRIMARY_KEY` 保持自增 id 不变，调用方无感知。用户初始想用 hash_id 作主键，但发现本地 CRUD（update/delete/get_by_id）全部使用自增 id，改 _PRIMARY_KEY 会导致 WHERE 条件失效、调用方全部需要改造，改动面远超 PRD 1 范围。决策前提：6 张表自增 id 两端不同、5 张表有 Provider 用自增 id、所有调用方传 int id、用户判断改动面太广。未来本地 CRUD 也需要用 hash_id 时切换到方案 B（改 _PRIMARY_KEY）。

## habit-chain-tables-not-synced
- updated_at: 2026-07-22
- path: `docs/adr/2026-07-22-habit-chain-tables-not-synced.md`
- 触发规则：当需要理解为什么 habit_chains 和 habit_chain_nodes 不参与同步、chain_id 外键断裂问题、或修改 SYNC_TABLES 时读取
- 内容摘要：habit_chains 和 habit_chain_nodes 因 `chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致导致外键断裂。从 SYNC_TABLES 临时移除（仍加 hash_id 字段为未来恢复做准备）。决策前提：chain_id 引用自增 id 导致外键断裂、当前云端 agent 无 habit 链条数据需求、chain_id 改引用 hash_id 属于 PRD 2 范围。备选触发：云端 agent 需要 habit 链条数据 + 服务器网页浏览时恢复同步（恢复前必须先解决 chain_id 外键问题）。

## backup-sync-decoupled-scope
- updated_at: 2026-07-17
- path: `docs/adr/2026-07-17-backup-sync-decoupled-scope.md`
- 触发规则：当需要理解为什么备份范围与同步范围独立定义、为什么 plan 加入备份但不加入同步、或修改 BACKUP_DIRS / SYNC_DIRECTORIES 时读取
- 内容摘要：备份范围与同步范围解耦，独立定义 `BACKUP_DIRS = [session/, diary/, agent/, user/, plan/]`（含 plan），不依赖 `SYNC_DIRECTORIES`。决策前提：同步和备份职责不同（同步是功能性，备份是数据安全性）、plan 无同步必要（Agent 无法读取 plan 文件夹）、plan 与数据库高度绑定、sync_client 不稳定不引入新变量。未来 plan 需要多端访问时可在 SYNC_DIRECTORIES 中加入（独立决策）。

## conflict-failure-policy
- updated_at: 2026-07-17
- path: `docs/adr/2026-07-17-conflict-failure-policy.md`
- 触发规则：当需要理解冲突失败后 sync_once 的行为、为什么不主动通知用户、sync_conflict/ 为什么需要同时备份本地和云端、或修改冲突失败处理逻辑时读取
- 内容摘要：冲突失败时不阻塞 sync_once（仅跳过冲突文件，其他继续），冲突文件降级 keep_ours（保留本地版本），不主动通知用户（仅日志 + sync_conflict/ 备份），与"不做 Agent 恢复通道"整体决策一致。关键修复：sync_conflict/ 必须同时备份本地和云端版本（当前 bug：[sync_client.py:1610-1614](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1610-L1614) 仅备份本地）。未来面向终端用户或冲突频率显著提升时切换到 Agent 通知方案。

## data-backup-strategy
- updated_at: 2026-07-17
- path: `docs/adr/2026-07-17-data-backup-strategy.md`
- 触发规则：当需要理解数据备份格式、备份频率、调度器选择、为什么不做恢复 API、或修改 BackupService 设计时读取
- 内容摘要：数据备份采用平铺存储（非 zip）+ 复用现有 ScheduleService（APScheduler 已是项目依赖）+ 不做恢复 API（仅文档指导手工恢复）。文档每天 03:00 备份一次，数据库每 8 小时（00/08/16 点）备份一次，各自保留 3 份。数据库使用 SQLite Online Backup API 全量备份。新建 BackupService 单例（职责：执行备份逻辑，不负责调度）。完整性校验：文件数量 + hash 比对 + PRAGMA integrity_check。决策前提：恢复场景频率极低（年频）、查看便利性是硬需求、用户是开发者可手工恢复。未来频率提升时基于恢复文档扩展为 API + Agent 通道。

## conflict-resolution-diff3-replaces-llm
- updated_at: 2026-07-17
- path: `docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md`
- 触发规则：当需要理解为什么 CONFLICT_RESOLVE 分支改为 tools=[]、diff3 算法选型、冲突标记格式（LP-LOCAL-{hash8} #{n}）、LLM 输出 JSON 替换指令、串行处理流程、3 次重试降级、或修改文件冲突解决机制时读取
- 内容摘要：文件冲突解决从 LLM 自主合并改为 diff3 算法 + LLM 辅助合并（无工具），消除 AI 截断数据风险。修订原 ADR `2026-07-14-file-sync-conflict-resolution.md` 决策 3（原决策为 AI 驱动合并 + LLM 有文件工具）。触发原因：2026-07-16 behavior.md 被破坏事件证明 LLM 自主合并不安全。具体决策：基于 difflib 自研 diff3（约 150 行代码，无外部依赖，避免 merge3 包 GPL 协议纠纷）、CONFLICT_RESOLVE `tools = []`、冲突标记 `<<<<<<< LP-LOCAL-{hash8} #{n}`、LLM 输出 JSON 替换指令、串行处理（理解 B，一个冲突一次 LLM 调用）、3 次重试降级 keep_ours。未来需要多端同步时切换到完整 git-like 方案。

## sync-system-timeline
- updated_at: 2026-07-27
- path: `docs/adr/2026-07-27-sync-system-timeline.md`
- 触发规则：需要理解数据同步系统的完整决策历程、各 ADR 之间的因果关系、哪些是主动设计哪些是 Bug 驱动修正、或做同步模块整体复盘时读取
- 内容摘要：数据同步系统的完整决策时间线，串联原始方案讨论（7/8）→ 核心架构决策（7/9）→ 文件同步重构（7/14，Bug 驱动）→ 动态表同步重构（7/16，Bug 驱动）→ 冲突与备份策略（7/17）→ 删除同步与数据库重构（7/22-7/24，Bug 驱动）→ 全局任务状态互斥（7/25）→ SSH 隧道加密通道（7/27）八个阶段。标注 4 种触发类型：主动设计（8 个）、Bug 驱动（10 个）、事故驱动（2 个）、外部环境约束（1 个）。包含决策依赖图、主动设计 vs Bug 驱动分类、前提→风险文档索引。

## dynamic-tables-sync-definition-comparison
- updated_at: 2026-07-16
- path: `docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md`
- 触发规则：当需要理解动态表同步的触发机制、为什么新增端点拉取云端定义、为什么删除 get_all_sync_tables、或修改动态表建表流程时读取
- 内容摘要：采用"拉取云端定义 → 本地 slug 对比 → 双向建表"方案，替代原 pull 前后快照对比。新增 `GET /api/sync/dynamic-tables-definitions` 端点查询云端 types + fields 两张 meta 表，本地用 slug 集合对比触发双向建表（本地建表只执行 DDL 不写 meta，让 pull 统一同步数据）。删除 `get_all_sync_tables`，动态表列表由建表步骤产出。决策前提：动态表字段不会被修改（前提 1）、主备模式（前提 2）、sync_once 期间无并发修改（前提 3，假设，需独立决策并发锁）。

## file-sync-conflict-resolution
- updated_at: 2026-07-16
- path: `docs/adr/2026-07-14-file-sync-conflict-resolution.md`
- 触发规则：当需要理解文件同步的冲突处理方案、为什么白名单只包含 session/diary/agent/user、account.json 为什么改数据库存储、或修改文件同步的增量识别和冲突判定逻辑时读取
- 内容摘要：五个关联决策——（决策 1）采用 per-file version tracking（parent_hash + current_hash + 11 状态决策矩阵）替代纯 LWW mtime 比较；（决策 2）同步白名单对齐 Agent 工具白名单（ALLOWED_DIRS + session），chat_history.json 明确排除（云端无 dreaming task 不会变更）；（决策 3）MD 冲突由 AI 驱动解决（新增 CONFLICT_RESOLVE 消息类型），AI 直接拿到两份文档内联内容，可用 read_file 读相关上下文做智能合并，替代用户手动处理。冲突备份路径为 sync_conflict/{timestamp}/，不在 SYNC_DIRECTORIES 和 ALLOWED_DIRS 中，AI 无法直接读取，仅做安全兜底；（决策 4）account.json 改为数据库存储（wechat_account_state 表），从文件白名单移除；（决策 5）API 协议采用三阶段设计（check → fetch/push → verify），mtime 第一重过滤 + hash 精确判断 + verify 一致性校验。v2.3 补充：决策 5 原遗漏"文件存在性判断"讨论，导致回归 bug（云端重装后本地未改文件被错误 SKIP），修复方案为 check 端点新增返回 `all_paths`（完整路径清单）。决策基于主备模式前提（同一时间只有一端 Agent 工作），备选触发覆盖 6 种前提失效场景。

## sync-full-sync-strategy
- updated_at: 2026-07-14
- path: `docs/adr/2026-07-14-sync-full-sync-strategy.md`
- 触发规则：当需要理解同步系统全量同步触发机制、为什么不做云端维护同步时间、或修改 LWW 冲突解决中"时间相等"处理逻辑时读取
- 内容摘要：两个关联决策——（决策 1）全量同步采用"重置同步进度按钮"方案（清空本地 last_sync_time 触发全量同步），否决"云端维护 sync_state 表"方案。核心原因：方案二是务实的最小可行方案，方案一引入云端状态管理复杂度且在多客户端轮流同步场景下存在静默数据丢失风险。（决策 2）LWW 中 updated_at 相等时跳过而非覆盖，Push 端 `>` 改为 `>=`，Pull 端新增相等跳过分支。决策前提：当前单客户端使用模式，方案二能完全覆盖换服务器/云端 DB 重置/本地 DB 重置场景。备选触发：多客户端场景出现时重新评估方案一。

## custom-records-time-string-not-convert
- updated_at: 2026-07-13
- path: `docs/adr/2026-07-13-custom-records-time-string-not-convert.md`
- 触发规则：当需要理解自定义记录模块中自定义字段的时间处理策略、为什么自定义字段时间不做 UTC 转换、或计划新增系统级 datetime 字段时读取
- 内容摘要：两个关联决策——（决策 A）自定义字段中的时间视为普通字符串，原样存储原样显示，不做时区转换；核心原因是自定义字段是"用户数据"而非"系统时间"。（决策 B，未来方向）为动态表新增必填系统级 datetime 字段替代 created_at 做日期筛选，Agent 输入本地 YYYY-MM-DD HH:MM:SS 经格式校验后转 UTC ISO 存储。决策 A 的前提：自定义字段不用于查询/筛选、field_type 不引入 date/datetime 类型、YYYY-MM-DD HH:MM:SS 格式天然字典序=时间序。

## date-to-utc-conversion-boundary
- updated_at: 2026-07-13
- path: `docs/adr/2026-07-13-date-to-utc-conversion-boundary.md`
- 触发规则：当需要理解前端日期查询的转换位置、单表/聚合查询的参数传递策略、或新增日期查询 API 时读取
- 内容摘要：确立日期到 UTC 时间范围的转换边界为"组件内转换"（组件 onChange 回调），系统内部保持 UTC ISO 8601 纯净格式。单表查询：有 date 字段传 date，只有 datetime 传 start_time/end_time（UTC）。聚合查询（混合表）传 date + start_time/end_time，后端根据表结构选择使用哪个参数。决策基于：工程复用性不存在（只有 2 处转换）、架构清晰性优先、前端日期来源可靠（input[type="date"] 保证格式）。决策前提：转换需求量 <= 5 个 API、无统一 DatePicker 组件、14 行代码重复可接受。

## time-conversion-layering
- updated_at: 2026-07-12
- path: `docs/adr/2026-07-12-time-conversion-layering.md`
- 触发规则：当需要理解时间转换在哪个层级进行、为什么不用装饰器自动转换、或新增 LLM 工具时参考转换模式时读取
- 内容摘要：确立时间转换的层级边界——前端负责双向转换（就近转换原则），后端工具函数输入输出保持 UTC ISO 8601。转换发生在 execute 方法层（工具调用入口），而非工具函数内部或 Repository 层。决策基于：代码可读性与显式性 > 自动化、后端工具函数可被非 LLM 调用（需保持 UTC 纯净）。

## cloud-init-first-sync-full-clear
- updated_at: 2026-07-17
- path: `docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md`
- 触发规则：当需要理解云端种子数据初始化策略、首次同步流程（全清覆盖）、为什么否决数据库同步黑名单、或修改 sync_once 首次同步分支时读取
- 内容摘要：否决"黑名单双向过滤"方案，采用"首次同步云端全清 + 本地全量覆盖"方案。首次同步分支：检测未初始化 → full-clear（清空 SYNC_TABLES + 同步文件）→ 全量推送数据库 → 全量推送文件 → mark-initialized。动态表首次只覆盖定义表（custom_record_types/fields），实际数据表在后续增量同步处理。mood_impacts 自增键经验证不影响同步，不改造。决策前提：云端 agent_only 无网页端（前提 3，失效则整体策略需重评估）、动态表入口只有定义表（前提 5，孤儿表不影响功能）。

## key-fallback-strategy
- updated_at: 2026-07-14
- path: `docs/adr/2026-07-09-key-fallback-strategy.md`
- 触发规则：当需要理解密钥存储策略、Key 为什么从 config.yaml 迁移到 storage.yaml、storage.yaml 的命名原因、run_mode 隔离逻辑、或修改云端/本地的 Key 读取写入路径时读取
- 内容摘要：v1.0 决策 keyring + config.yaml fallback，否决 .env 环境变量方案。v1.1 将 Key 从 config.yaml 分离到 storage.yaml（权限 600），