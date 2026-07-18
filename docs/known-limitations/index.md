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
