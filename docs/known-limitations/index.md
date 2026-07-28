# Known Limitations（已知限制）

本目录记录系统当前已知的限制、约束和未解决的问题。

## 索引


### 1. Mood Entries 和 Custom Records 日期查询问题

- **文件**: `mood-and-custom-records-date-query-issues.md`
- **状态**: `acknowledged`（已确认但尚未修复）
- **严重程度**: 中
- **影响范围**: Mood Entries API、Custom Records API
- **问题描述**: 表中缺少独立 `date` 字段，只有 `created_at/updated_at` datetime 字段，导致按日期查询需要后端时区转换，无法建立日期索引，查询效率低
- **触发条件**: 数据量超过 10 万条或查询响应时间超过 1 秒时需重构
- **临时方案**: 当前使用 `build_utc_time_range()` 转换，功能正确但效率低

### 2. 数据库同步时间依赖与主备时钟偏差

- **文件**: `sync-time-dependency-and-clock-skew.md`
- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 低
- **影响范围**: 数据库同步（30 张静态表 + 动态自定义记录表 + 文件同步）
- **问题描述**: 同步完全依赖客户端 `last_sync_time` 判断增量范围，主备切换场景下若云端时钟慢于本机时钟，极端情况下可能丢失云端新写入的数据。已确认所有时间均使用 UTC ISO 8601，当前不是 bug
- **触发条件**: 主备切换 + 云端时钟比本机慢 + 偏差窗口内恰好有数据写入（NTP 正常时偏差 < 1 秒，风险极低）
- **根本前提**: 本机使用时云端不产生数据（Agent 不处理消息）。若前提改变（多客户端等），同步需重做

### 3. 前端时间显示与后端时区配置解耦

- **文件**: `frontend-timezone-display-decoupled-from-config.md`
- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 低
- **影响范围**: 前端所有时间显示组件
- **问题描述**: 前端时间显示走浏览器本地时区（`new Date` 自动跟随系统），不读取后端 `settings.timezone` 配置；后端 AI 工具按配置时区显示。二者各自动态获取，非硬编码，但当浏览器时区与配置时区不一致时会出现显示差异
- **触发条件**: 浏览器/系统时区与 `settings.timezone` 配置不一致（如跨时区出差未同步修改系统时区）
- **临时方案**: 保持现状，依赖"用户所在地 = 系统时区 = 配置时区"的使用前提

### 4. 云端部署安全限制

- **文件**: `cloud-security-limitations.md`
- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 高
- **影响范围**: 云端部署全链路（密钥存储、传输、生成）
- **问题描述**: (1) wxid 明文存储，攻击者可伪装 AI 机器人；(2) API Key 明文存储，攻击者可滥用 LLM 服务；(3) 同步 API Key 无法重新生成（config.yaml fallback 污染）；(4) 同步数据传输未启用 HTTPS，Bearer Token 明文传输
- **替代方案**: 限制 4 已增加 SSH 隧道备注——SSH 隧道模式可作为 HTTPS 的替代方案，无需域名和证书（详见条目 12）
- **计划改进**: frontend 增加 Key 更换确认键、Key 统一到 storage.yaml + run_mode 隔离读写、Let's Encrypt TLS + Nginx 反向代理

### 5. keyring 包在 Linux headless 环境可能不可用

- **文件**: `cloud-security-limitations.md`（限制 5）
- **状态**: `discussing`（方案待讨论）
- **严重程度**: 中
- **影响范围**: 所有 Key 读取链路（sync_config、wechat/auth、provider_manager、settings_manager）
- **问题描述**: keyring 是顶层 import，Linux headless 环境可能缺少 D-Bus/gnome-keyring 等系统组件导致 import 失败。所有模块的 lazy fallback 逻辑只在运行时生效，import 阶段无法保护
- **计划改进**: 三个候选方案待讨论——(A) keyring import 懒加载 (B) 本地也放弃 keyring 统一 storage.yaml (C) keyring 配置为 Windows-only 可选依赖

### 6. behavior.md 持续增长与同步影响

- **文件**: `behavior-md-growth-and-sync-impact.md`
- **状态**: `acknowledged`（已确认，当前阶段不处理）
- **严重程度**: 低（当前）→ 中（未来文件增长到 1MB+ 时）
- **影响范围**: 文件同步（传输大小 + AI 冲突合并 token 消耗）
- **问题描述**: behavior.md 由 dreaming task 追加式写入，持续增长。当前约 300KB 可接受，但增长到 1MB+ 后 AI 冲突合并可能超出 token 限制
- **触发条件**: behavior.md 超过 1MB 或 AI 冲突合并因 token 限制失败
- **计划改进**: 按月拆分 behavior.md（当前月活跃写入 + 历史归档不再修改），需修改 dreaming task 写入逻辑

### 7. XML 工具调用在 max_tokens 不足时的限制

- **文件**: `xml-tool-call-max-tokens-limit.md`
- **状态**: `acknowledged`（已确认，当前不进一步处理）
- **严重程度**: 中
- **影响范围**: 所有 XML 格式工具调用场景（CONFLICT_RESOLVE 高发）
- **问题描述**: LLM 输出超过 max_tokens 时 XML 被截断（缺少 `</tool_call>`），解析失败。当前已修复：finish_reason="length" 主动检测 + XML 解析 fallback。默认 max_tokens 已从 4096 翻倍到 8192
- **触发条件**: 大文件冲突合并（如 user.md、behavior.md）
- **计划改进**: 冲突解决改 diff3 算法后可彻底消除

### 8. habit 链条表不参与同步

- **文件**: `habit-chain-tables-not-synced.md`
- **状态**: `acknowledged`（已确认，待 PRD 2 恢复）
- **严重程度**: 低（当前云端 agent 无 habit 链条数据需求）
- **影响范围**: `habit_chains` 和 `habit_chain_nodes` 两张表不参与数据库同步
- **问题描述**: `habit_chain_nodes.chain_id` 引用 `habit_chains.id`（自增 id），同步后两端 id 不一致导致外键断裂。临时从 `SYNC_TABLES` 移除，`HASH_ID_PREFIXES` 仍保留（hash_id 字段照加）
- **触发条件**: 云端 agent 需要 habit 链条数据 + 服务器网页浏览时恢复同步，恢复前必须先解决 `chain_id` 外键问题（改引用 `hash_id`，属于 PRD 2 代码适配范围）
- **临时方案**: 两张表从 `SYNC_TABLES` 移除并标注 `# TODO PRD 2`，详见 ADR `docs/adr/2026-07-22-habit-chain-tables-not-synced.md`

### 9. 删除-更新冲突不解决

- **文件**: `delete-update-conflict-not-resolved.md`
- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 低（主备模式下冲突概率 < 0.1%）
- **影响范围**: 所有同步表的删除-更新并发场景
- **问题描述**: A 端删除记录后写墓碑，B 端若同时更新该记录（upsert 写回），B 端的更新会覆盖 A 端的删除意图，导致记录"复活"或更新丢失。墓碑同步不比较 `updated_at`，无法检测对端是否有更新版本
- **触发条件**: 出现真实的删除-更新冲突导致用户可见的数据丢失，或项目从主备模式转向多客户端并发模式
- **临时方案**: 依赖每日全量备份恢复，或用户手工重新创建记录

### 10. 删除-重建冲突时墓碑跳过新记录

- **文件**: `delete-recreate-conflict-tombstone-skip.md`
- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 中（出现概率中等，但发生时数据丢失严重）
- **影响范围**: 所有同步表的"删除-重建"冲突场景
- **问题描述**: A 端删除记录 R 后写墓碑，B 端在收到墓碑前重建同 ID 的新记录 R'，A 端墓碑 Pull 到 B 端后会因 `UNIQUE` 约束 `INSERT OR IGNORE` 跳过，导致 R' 在 A 端被错误删除而墓碑副本未写入
- **触发条件**: 出现真实的删除-重建冲突导致用户可见的数据丢失，或业务流程中有"删除-重建"的高频操作
- **临时方案**: 依赖每日全量备份恢复，或建议用户重建时使用新 ID 避免与已删记录冲突

### 11. 文件删除不走墓碑同步

- **文件**: `file-deletion-not-synced.md`
- **状态**: `acknowledged`（已确认，按当前使用场景不修复）
- **严重程度**: 低（文件删除场景少，且 `file_sync_state` 的 LWW 通常能正确处理）
- **影响范围**: `SYNC_DIRECTORIES` 白名单目录中的文件删除
- **问题描述**: 墓碑同步机制（`/pull-deletion-log`、`/push-deletion-log`、`/cleanup-deletion-log`）只覆盖数据库记录的删除传播，不覆盖文件删除。文件删除依赖 `file_sync_state` 表的 LWW 机制，可能出现"幽灵文件"（已删文件被对端拉回）
- **触发条件**: 出现真实的"幽灵文件"问题，或文件删除-修改并发频率显著提升
- **临时方案**: 依赖每日全量备份恢复，或用户手动删除"幽灵文件"

### 12. SSH 隧道已知限制（8 项）

- **文件**: `ssh-tunnel-limitations.md`
- **状态**: `acknowledged`（已确认，当前 PRD 范围下有意接受的设计选择）
- **严重程度**: 低~中（不影响核心功能可用性，仅是运维体验和密钥管理限制；其中限制 8 为安全性限制，严重程度中）
- **影响范围**: 模式 C（SSH 隧道）连接模式
- **问题描述**: SSH 隧道方案当前 PRD 范围下的 8 项设计限制：(1) 本地需保持 LifePrism 进程（隧道随进程关闭）；(2) 依赖云端 SSH 服务可用；(3) 私钥丢失无法恢复（需重新生成密钥对）；(4) 不支持私钥导入（仅前端生成）；(5) 密钥保留不覆盖（多端切换可能公钥不一致）；(6) 无私钥轮换 UI（无"重新生成密钥对"按钮）；(7) 隧道状态非实时显示（需手动"测试连接"验证）；(8) SSH 主机密钥验证未启用（known_hosts=None，存在 MITM 风险）
- **触发条件**: 使用 SSH 隧道模式（部署文档模式 C）
- **临时方案**: 各项限制均有对应的临时排查/恢复步骤，详见 `ssh-tunnel-limitations.md` 各限制的"临时方案或计划改进"章节
- **相关文档**: 部署文档 `docs/deployment/cloud-https-setup.md` 模式 C、PRD `.scratch/ssh-tunnel-integration/prd.md` Out of Scope、代码实现 `lifeprism/sync/ssh_tunnel.py:172`

### 13. 云端 API 端口默认绑定 127.0.0.1（无法公网 http 直连）

- **文件**: `cloud-api-default-bind-localhost.md`
- **状态**: `acknowledged`（已确认，当前 PRD 范围下有意接受的设计选择）
- **严重程度**: 低（设计选择，非缺陷；SSH 隧道模式下功能不受影响）
- **影响范围**: 云端 agent-only 模式下所有尝试通过公网 http 直接访问 8102 端口的场景
- **问题描述**: `lifeprism/server/main_agent_only.py:136` 默认返回 `127.0.0.1`，导致云端 8102 端口仅本机可访问，公网无法通过 `http://<云端IP>:8102` 直接访问同步 API。这是 SSH 隧道方案的服务端基础设计（关闭公网暴露以保障安全），但 Nginx 反代、调试或未走 SSH 隧道的直连场景需通过环境变量 `LIFEPRISM_API_HOST=0.0.0.0` 覆盖才能访问
- **触发条件**: 用户尝试通过公网 IP 直接 http 访问 8102、部署 Nginx 反代时未设置 `LIFEPRISM_API_HOST`、调试场景下从外部网络 curl 云端 8102 端口
- **临时方案**: 启动 agent-only 前设置 `export LIFEPRISM_API_HOST=0.0.0.0`
- **相关文档**: 代码实现 `lifeprism/server/main_agent_only.py:136`、SSH 隧道方案 Issue `.scratch/ssh-tunnel-integration/issues/01-8102-bind-localhost.md`、SSH 隧道已知限制 `ssh-tunnel-limitations.md`

> 时区和时间格式不一致问题已于 2026-07-12 通过 UTC 时区迁移解决，相关规范见 `docs/coding-rules/time-handling-rules.md`，决策见 `docs/adr/2026-07-12-migrate-to-utc-timezone.md`。

## 说明

已知限制文档用于：
1. **透明记录**：明确系统当前的技术债和设计约束
2. **风险管理**：帮助开发者了解潜在风险，避免引入新问题
3. **修复规划**：为未来的改进提供清晰的问题清单

## 文档格式

每个限制文档应包含：
- **问题描述**：清晰说明限制是什么
- **影响范围**：哪些功能受影响，严重程度如何
- **当前假设**：系统依赖的脆弱前提
- **相关文档**：指向调查报告、ADR 等
- **注意事项**：开发时需要注意的事项

## 状态说明

- `acknowledged`：已确认但尚未修复
- `mitigating`：正在实施缓解措施
- `planned`：已纳入修复计划
- `resolved`：已解决（归档到 history）
