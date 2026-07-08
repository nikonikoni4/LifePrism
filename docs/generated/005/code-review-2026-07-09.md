# Code Review Report

**审查范围**: P2 数据同步方案 Issue #01~#10（`.scratch/linux-deployment-discussion/issues-p2/`）
**审查时间**: 2026-07-09
**变更文件**: 10 个 Issue 文档 + 1 个 PRD 文档

## 架构上下文

### 相关 ADR
- `docs/adr/2026-04-24-store-interface-encapsulation.md` (stable) — Repository 层强封装 + 受控透传
- `docs/adr/2026-07-08-linux-deployment-multiple-entrypoints.md` (decided) — 多入口架构
- `docs/adr/2026-07-06-custom-records-storage.md` (decided) — 自定义记录存储

### 相关 Spec
- `docs/specs/2026-07-06-repository-core-spec.md` — Repository 数据访问层核心规格
- `docs/specs/2026-04-20-config-spec.md` — 配置管理模块规格（API Key 存储优先级）
- `docs/specs/2026-07-06-config-settings-spec.md` — SettingsManager / ProviderManager 规格

### 相关编码规则
- `docs/coding-rules/backend-core-rules.md` — Repository 层分层、SQL 隔离原则
- `docs/coding-rules/backend-api-rules.md` — API 层路由规范（目录为 `server/api/` 非 `routes/`）
- `docs/coding-rules/backend-error-handling.md` — 异常分层捕获、except Exception 限制

### 决策覆盖
- 10/10 Issue 有 PRD 关联
- 同步方案尚未提升为正式 ADR/Spec，全部位于 `.scratch/` 临时讨论区
- Issue 描述的代码已全部实现，本次审查聚焦 Issue 文档与实际代码/PRD 之间的一致性偏差

## 审查结果

Found 19 issues（置信度 >= 80）:

---

### Issue 1: API 契约不一致 — api_key 传递方式导致认证永远失败
- **类型**: Architecture
- **置信度**: 95
- **位置**: Issue #03/#04（服务端）vs Issue #05（客户端）
- **详情**: Issue #03/#04 设计服务端从请求体 JSON 读取 `api_key` 字段进行认证。但 Issue #05 中 SyncClient 未规定如何传递 api_key，实际客户端代码通过 `Authorization: Bearer` HTTP Header 发送。服务端只读请求体、客户端只发 Header，两端认证永远无法通过。
- **依据**: `sync_cloud_api.py` 从 `request.json()` 读取 `api_key`；`sync_client.py` 使用 `headers={"Authorization": f"Bearer {api_key}"}`。Issue 文档未在 #05 中强制对齐传递方式。

---

### Issue 2: API 契约不一致 — 请求/响应字段名不匹配导致数据丢失
- **类型**: Architecture
- **置信度**: 95
- **位置**: Issue #03/#04（服务端）vs Issue #05（客户端）
- **详情**: 服务端 Pull 响应返回 `{"changes": {...}, "sync_time": "..."}`，客户端读 `response["tables"]`；服务端 Push 期望请求体 `{"changes": {...}, "api_key": "..."}`，客户端发送 `{"tables": {...}}` 且无 `api_key` 字段。字段名完全不匹配，Pull 拿不到数据，Push 请求被 Pydantic 校验拒绝。
- **依据**: Issue #03 响应格式定义 `changes` 字段；Issue #05 SyncClient 代码使用 `tables` 字段。两端未统一字段命名。

---

### Issue 3: 时间戳比较格式不统一 + LWW 冲突策略在 Push 端未实现
- **类型**: Architecture / Best Practices
- **置信度**: 85
- **位置**: Issue #05
- **详情**: 
  1. **时间戳格式不统一**：LWW 冲突解决通过字符串比较 `updated_at`，但 `last_sync_time` 写入使用 `%Y-%m-%d %H:%M:%S`（空格分隔），服务端 `sync_time` 使用 `isoformat()`（T 分隔）。空格（ASCII 32）< T（ASCII 84），导致字典序比较结果错误，可能用旧数据覆盖新数据。Issue 未规定统一时间格式。
  2. **Push 端 LWW 未实现**：服务端 Push 接口使用 `INSERT OR REPLACE` 无条件覆盖，不比较 `updated_at` 时间戳。实际行为是"最后推送的赢"而非"最后写入的赢"，旧数据可以覆盖新数据。
- **依据**: Issue #05 描述 LWW 逻辑仅存在于 Pull 端（客户端比较 local.updated_at vs remote.updated_at），Push 端（Issue #04）无任何时间戳比较逻辑。PRD 第 3 节明确要求 Last-Write-Wins 策略。

---

### Issue 4: 阻塞事件循环 — 同步 HTTP 调用在 async 上下文中
- **类型**: Architecture / Performance
- **置信度**: 85
- **位置**: Issue #05/#06
- **详情**: `SyncClient.sync_once()` 在 asyncio 事件循环中运行，但使用阻塞式 `httpx.post()`（同步 HTTP 客户端）进行网络请求。这会阻塞整个事件循环，导致 Agent Loop 和微信消息处理被卡住。Issue #06 的 `_is_syncing` 标志只是掩盖了并发问题，真正的阻塞问题未被识别。
- **依据**: Issue #06 使用 `asyncio.create_task()` 创建后台任务，但 Issue #05 的 SyncClient 使用同步 `httpx.post`。应使用 `httpx.AsyncClient` 或 `asyncio.to_thread()` 包装同步调用。`lifeprism/CLAUDE.md` 要求异步上下文中不阻塞事件循环。

---

### Issue 5: 动态 SQL 构建存在 SQL 注入风险
- **类型**: Security
- **置信度**: 85
- **位置**: Issue #03/#04/#05
- **详情**: `SyncRepository.query_incremental()` 执行 `SELECT * FROM {table} WHERE updated_at > ?`，`upsert_rows()` 执行 `INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})`。表名 `{table}` 和列名 `{columns}` 直接字符串拼接，且服务端接收的 `tables` 参数来自请求体（用户可控）。Issue 全文未提及白名单校验。API Key 一旦泄露，攻击者可注入恶意表名读取任意表数据。
- **依据**: `sync_repository.py` 中 `query_incremental` 和 `upsert_rows` 使用 f-string 拼接表名。Issue #03 第 46 行 `SELECT * FROM {table} WHERE updated_at > ?` 无白名单校验。`docs/coding-rules/create-table-rules.md` 要求使用 `_TABLE_NAME`/`_PRIMARY_KEY` 白名单防注入。

---

### Issue 6: PRD 要求分批同步 + gzip 压缩但 Issue 完全未体现
- **类型**: Documentation / Performance
- **置信度**: 90
- **位置**: Issue #03/#04/#05
- **详情**: PRD 第 4 节明确要求"分批同步（1000 条/批）"和"压缩传输（gzip，压缩率 60-70%）"，但 Issue #03（Pull）、#04（Push）、#05（SyncClient）三个核心 Issue 均未体现分批和压缩。首次同步 16MB 数据一次性传输，可能导致 HTTP 超时、内存溢出、失败后全量重传。
- **依据**: PRD 第 394-396 行明确要求分批和 gzip；Issue #03/#04 的请求/响应格式无分页参数（`limit`/`cursor`/`offset`）；Issue #05 的 SyncClient 无分批循环逻辑。PRD 技术验收标准要求"增量查询使用索引，耗时 < 100ms"，但首次全量同步无性能保障。

---

### Issue 7: Issue #03/#04 未提及 HTTPS 强制要求
- **类型**: Security
- **置信度**: 85
- **位置**: Issue #03/#04
- **详情**: PRD 第 5 节明确要求 HTTPS 加密传输，但 Issue #03/#04 完全未提及 HTTPS，且未声明对 Issue #11（HTTPS/API Key Auth）的 `Blocked by` 依赖。若 #03/#04 先于 #11 实现部署，API Key 会在 HTTP 下明文传输。
- **依据**: PRD 第 405-408 行要求 HTTPS（Let's Encrypt）；PRD 安全验收标准要求"HTTPS 证书配置正确"。Issue #03/#04 的验收标准无 HTTPS 相关检查项。

---

### Issue 8: Issue #01 文档过时 — 描述的变更已完成
- **类型**: Documentation
- **置信度**: 95
- **位置**: Issue #01
- **详情**: Issue #01 声称 9 个表需要添加 `update_at: True`，且 `behavior_analysis` 和 `mood_entries` 当前为 `"update_at": False`。但实际 `database.py` 中这 9 个表已全部配置为 `"update_at": True`。Issue 还声称 `timeline_custom_block` 需要添加 `UNIQUE(start_time)` 约束，但该约束已存在于 `table_constraints` 中。文档未同步实际代码状态。
- **依据**: `lifeprism/config/database.py` 中 `behavior_analysis` 配置为 `"update_at": True`（第 1561 行附近）；`timeline_custom_block` 的 `table_constraints` 已包含 `"UNIQUE(start_time)"`。Issue #01 第 20-28 行的描述与实际不符。

---

### Issue 9: API 路径与项目实际架构不一致
- **类型**: Architecture / Documentation
- **置信度**: 95
- **位置**: Issue #03/#04
- **详情**: Issue #03/#04 指定新增 `lifeprism/server/routes/sync_api.py`，但项目中 `lifeprism/server/routes/` 目录不存在。根据 `docs/coding-rules/backend-api-rules.md` 和实际代码，API 路由层位于 `lifeprism/server/api/`，实际同步路由文件为 `lifeprism/server/api/sync_cloud_api.py`。
- **依据**: `lifeprism/server/api/__init__.py` 汇聚所有 router；`docs/coding-rules/backend-api-rules.md` 规定路由文件位于 `server/api/`。Issue #03 第 49 行和 Issue #04 第 48 行均使用错误路径 `routes/sync_api.py`。

---

### Issue 10: Issue #02 中 provider_manager 路径错误
- **类型**: Documentation
- **置信度**: 90
- **位置**: Issue #02
- **详情**: Issue #02 第 21 行描述 `provider_manager.py::get_api_key()`，上下文隐含该文件位于 `lifeprism/llm/` 目录。实际文件位于 `lifeprism/config/provider_manager.py`。`main_agent_only.py` 和 `config/__init__.py` 均从 `lifeprism.config.provider_manager` 导入。
- **依据**: 实际路径 `lifeprism/config/provider_manager.py`（第 620-638 行 `get_api_key()` 方法）；项目中不存在 `lifeprism/llm/provider_manager.py`。

---

### Issue 11: 认证逻辑在 Issue #03/#04 中重复描述
- **类型**: Code Quality
- **置信度**: 90
- **位置**: Issue #03/#04
- **详情**: Issue #03 和 #04 对 API Key 认证逻辑逐字重复了 5 行描述（读取 api_key → 比较 → 抛出 ValidationError → 不使用 try/except）。应在 #03 定义一次、#04 引用，或提取为独立的认证依赖。
- **依据**: Issue #03 第 50-54 行与 Issue #04 第 49-53 行内容完全相同。

---

### Issue 12: 服务端认证读取方式偏离 Issue #02 的统一入口设计
- **类型**: Architecture
- **置信度**: 85
- **位置**: Issue #03/#04 vs Issue #02
- **详情**: Issue #02 设计了 `sync_config.get_sync_api_key()` 作为同步 API Key 的统一读取入口（keyring 优先 + config fallback）。但 Issue #03/#04 的认证逻辑未明确要求使用此函数，实际服务端代码使用 `settings_manager.get_setting("sync_api_key")` 直接读取配置，绕过了 keyring fallback 机制，偏离了"Key 读取统一入口"的设计意图。
- **依据**: Issue #02 第 29-32 行明确要求通过 `sync/sync_config.py` 的 `get_sync_api_key()` 读取；实际 `sync_cloud_api.py` 使用 `settings_manager.get_setting` 绕过 fallback。PRD 第 6 节要求"代码修改点集中在数据返回层"。

---

### Issue 13: API Key 比较未要求常量时间比较（时序攻击风险）
- **类型**: Security
- **置信度**: 80
- **位置**: Issue #03/#04
- **详情**: Issue #03/#04 描述 API Key 认证为"与配置中的 `sync_api_key` 比较"，未要求使用 `secrets.compare_digest()` 进行常量时间比较。普通字符串比较（`==`）在字符不匹配时会提前返回，攻击者可通过测量响应时间逐字符猜测 API Key。
- **依据**: Issue #03 第 52 行"与配置中的 `sync_api_key` 比较"未指定比较方法。Python `secrets.compare_digest()` 是防时序攻击的标准做法。

---

### Issue 14: 云端 config.yaml 文件权限 600 未在 Issue 中要求
- **类型**: Security
- **置信度**: 80
- **位置**: Issue #09
- **详情**: PRD 第 5 节明确要求"云端 Linux：config.yaml（文件权限 600）"，PRD 安全验收标准要求"云端配置文件权限 600"。但 Issue #09（云端配置初始化）的验收标准中无文件权限设置要求，CloudInitializer 写入 config.yaml 和 providers.yaml 后未设置文件权限。
- **依据**: PRD 第 414 行"文件权限 600"；PRD 安全验收标准第 636 行"云端配置文件权限 600"。Issue #09 验收标准（第 49-75 行）无权限设置检查项。

---

### Issue 15: INSERT OR REPLACE 对 AUTOINCREMENT 表的 id 污染
- **类型**: Architecture
- **置信度**: 80
- **位置**: Issue #05
- **详情**: Issue #05 的 Category B 策略对 AUTOINCREMENT + UNIQUE 约束的表（`user_app_behavior_log`、`category_map_cache`）传入完整行数据（含远程 id）执行 `INSERT OR REPLACE`。这会污染 `sqlite_sequence`、造成 id 空洞、破坏未来外键引用、丧失幂等性。更稳健的方案是不传 id（写 NULL），让本地自增，仅靠 UNIQUE 约束判重。
- **依据**: Issue #05 第 50-51 行"传入完整行数据（含远程 id）"。Issue 声称"经验证无外键引用这两张表的 id"，但如果未来新增外键引用，此方案会成为隐患。

---

### Issue 16: 认证逻辑应提取为 FastAPI Depends
- **类型**: Code Quality / Best Practices
- **置信度**: 80
- **位置**: Issue #03/#04
- **详情**: API Key 认证逻辑在 Pull 和 Push 两个端点中重复描述。FastAPI 惯例是使用 `Depends()` 或 `APIKeyHeader` 提取为可复用的认证依赖，自动复用且能在 OpenAPI 文档中生成认证标注。Issue 应在设计阶段就明确使用 Depends 模式。
- **依据**: `docs/coding-rules/backend-api-rules.md` 规定使用 APIRouter；FastAPI 官方文档推荐 `Depends()` 用于认证依赖。Issue #03/#04 手动在每个路由中调用认证函数。

---

### Issue 17: 魔法数字散落在多个 Issue 中
- **类型**: Code Quality
- **置信度**: 80
- **位置**: Issue #06/#07/#10 等
- **详情**: 多个硬编码数值散落在 Issue 描述中：10 分钟同步间隔（#06）、32 字节 API Key 长度（#07）、API Key 脱敏后 8 位（#10）、1000 条/批（PRD 提到但 #05 未实现）。这些数值应定义为命名常量或配置项，而非硬编码。
- **依据**: Issue #06 第 22 行"每 10 分钟"；Issue #07 第 26 行 `secrets.token_urlsafe(32)`；Issue #10 第 30 行"只显示后 8 位"。`lifeprism/CLAUDE.md` 要求避免魔法数字。

---

### Issue 18: 原子性保证与 PRD Best-effort 策略矛盾
- **类型**: Architecture
- **置信度**: 80
- **位置**: Issue #05 vs PRD
- **详情**: Issue #05 要求"只有全部成功才更新 `last_sync_time`"（表级原子性），但 PRD 第 3 节要求"单条记录失败不阻塞其他记录"（行级容错）。两者矛盾：Issue #05 的原子性意味着任何一张表失败都不更新 `last_sync_time`，而 PRD 的 Best-effort 要求部分失败时仍继续同步其他表。实际实现中 `executemany` 单条失败会回滚整批，两者都未真正实现。
- **依据**: Issue #05 第 68 行"只有全部成功才更新 `last_sync_time`"；PRD 第 348 行"单条记录失败不阻塞其他记录"。

---

### Issue 19: 首次全量同步无特殊处理
- **类型**: Performance
- **置信度**: 80
- **位置**: Issue #03/#05
- **详情**: 首次同步时 `last_sync_time` 为空，会拉取全部 13 张表约 16MB 数据。Issue #03 的 Pull 接口无分页、无超时配置、无断点续传。HTTP 默认 30 秒超时会导致首次同步失败。Issue #05 也未对首次同步做特殊处理（如分批拉取、超时延长）。
- **依据**: PRD 第 301 行"第一次同步：16MB，分批传输 + 压缩，约 1-2 分钟"；Issue #03 无 `limit`/`cursor` 分页参数；Issue #05 的 `sync_once()` 无首次同步判断逻辑。

---

## 变更摘要

本次审查对象为 P2 数据同步方案的 10 个 Issue 文档（Issue #01~#10），涵盖数据库 Schema 变更、Key 读取 Fallback、同步 API（Pull/Push）、本地同步客户端、定时同步、配置生成器（前后端）、云端初始化、云端 CLI 管理等模块。

**关键发现**：Issue 描述的代码已全部实现，但 Issue 文档与实际代码、PRD 之间存在显著一致性偏差：

1. **阻断性问题（4 个）**：API 契约不一致（认证失败 + 字段名不匹配）、时间戳格式不统一导致数据覆盖、阻塞事件循环
2. **安全/架构隐患（4 个）**：SQL 注入风险、HTTPS 未要求、分批+gzip 缺失、AUTOINCREMENT id 污染
3. **文档/质量问题（11 个）**：Issue #01 过时、路径错误、重复描述、魔法数字等

**最核心的问题**是 Issue #03/#04（服务端）与 Issue #05（客户端）之间的 API 契约完全不一致，导致同步功能在当前状态下无法正常工作。建议优先修复 P0 阻断性问题，然后处理 P1 安全/架构隐患。
