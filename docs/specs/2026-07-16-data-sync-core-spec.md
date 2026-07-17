---
version: 2.0
created_at: 2026-07-16
updated_at: 2026-07-16
last_updated: 从 v1.0（2026-07-11-data-sync-spec.md）拆分重构；新增动态表定义对比与双向建表子节；更新 API 端点表（6→10）；新增 wechat_account_state 同步；更新 key_function
abstract: Windows 本地 ↔ Linux 云端数据同步模块核心规格（数据库同步 + 动态表同步 + 心跳路由 + 云端配置初始化），定义 30 张静态表增量同步、动态表 slug 集合对比双向建表、LWW 冲突解决和认证安全的技术契约
status: draft
module: sync
---

# 数据同步模块规格 — 核心（数据库同步 + 动态表 + 心跳路由 + 配置初始化）

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 2.0 | 从原 `2026-07-11-data-sync-spec.md` 拆分，拆分文件同步到独立 spec |
| 1.0 | 创建 spec 初稿 |

## Overview

**业务问题**：P1 完成后，Windows 本地和 Linux 云端各自独立运行。用户需要通过微信（Linux Agent）记录数据后能在本地查看，也需要云端 Agent 能访问本地采集的 Monitor 数据。两端数据需要保持一致，且避免微信消息被双端重复回复。

**核心职责**：
- **数据库双向同步**：30 张静态表 + 动态 custom 表，基于 `updated_at` 字段的增量同步
- **动态表同步**：拉取云端定义 → slug 集合对比 → 双向建表（本地 DDL only，云端全量替换）
- **心跳与消息路由**：纯内存心跳状态管理，本地离线时云端接管微信消息处理
- **云端配置初始化**：本地生成 cloud_init.yaml → 云端消费写入 config.yaml + providers.yaml
- **认证安全**：API Key 认证 + HTTPS 加密传输

## Scope

### 范围内

- 增量同步机制（`updated_at` 字段 + 分批拉取，每批 1000 条）
- LWW（Last-Write-Wins）冲突解决策略
- 动态表定义对比（slug 集合差集 → 双向建表）
- 心跳状态管理（纯内存，15 分钟超时）
- 消息路由（本地在线时云端跳过消息处理）
- API 端点：pull / push / heartbeat / dynamic-tables-definitions / rebuild-dynamic-tables
- 云端配置生成与初始化（CloudConfigGenerator → CloudInitializer）
- API Key 认证
- 前端同步状态查询

### 范围外

- 文件同步（per-file version tracking、三阶段协议、AI 合并）→ [`data-sync-files-spec`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-files-spec.md)
- 冲突仲裁 UI（用户手动选择）
- 同步进度条
- cr-sqlite / CRDT 多端并发方案
- 数据库静态加密（SQLCipher）
- Docker 容器部署
- ActivityWatch 数据同步（属于 SyncService，与云端同步无关）

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 云端配置生成

- [ ] 前端点击"生成云端配置"后，`{lifeprism_data_path}/cloud_init.yaml` 被创建
- [ ] cloud_init.yaml 包含 llm.provider（display_name）、llm.model、wechat_token、sync.api_key、monitor_type: none
- [ ] providers 列表包含所有有 env_key 且有 api_key 的 provider
- [ ] 同步 API Key 首次生成时使用 `secrets.token_urlsafe(32)`，key_is_new=true
- [ ] 同步 API Key 已存在时（keyring 中），key_is_new=false

### 云端配置初始化

- [ ] `cloud_init.yaml` 存在时，`CloudInitializer.initialize()` 验证配置完整性
- [ ] 验证失败时抛出 ConfigError，**不删除** cloud_init.yaml
- [ ] 验证通过后写入 config.yaml（含 provider、model、wechat_token、sync_api_key、monitor_type: none）
- [ ] 验证通过后写入 providers.yaml（注入对应 provider 的 api_key 字段）
- [ ] 全部成功后删除 cloud_init.yaml
- [ ] monitor_type 强制覆盖为 "none"
- [ ] llm.provider 为 display_name（如 "Xiaomi MIMO"）时，验证能正确匹配 providers[].name（如 "xiaomi_mimo"）

### 数据库同步

- [ ] 本地启动后自动执行一次完整同步（定义对比 → pull → push）
- [ ] 定时同步每 10 分钟执行一次
- [ ] 并发控制：同步中的新请求被跳过，不重复执行
- [ ] Pull：按表分批拉取（每批 1000 条），应用 LWW 冲突解决
- [ ] Push：增量查询 `updated_at > last_sync_time` 的记录推送到云端
- [ ] 无 updated_at 列的表（mood_types 等）直接全量覆盖
- [ ] LWW 中 `updated_at` 相等时跳过而非覆盖
- [ ] 所有步骤成功后更新 `last_sync_time`（整体原子性）

### 动态表同步

- [ ] 在 pull 之前拉取云端动态表定义（`GET /api/sync/dynamic-tables-definitions`）
- [ ] 云端有但本地无的 slug → 本地建表（只执行 DDL，不写 meta）
- [ ] 本地有但云端无的 slug → 发送重建请求到云端
- [ ] 两端 slug 一致 → 不触发任何操作
- [ ] 不再每次同步都出现"重建动态表: skipped"日志
- [ ] 动态表列表（custom_{slug}）加入 `SYNC_TABLES`，参与数据 pull/push

### 心跳与消息路由

- [ ] 每次 sync/pull 请求同时更新心跳时间戳
- [ ] 本地启动时发送 online 事件，关闭时发送 offline 事件
- [ ] 显式 offline 事件立即生效，is_local_online() 返回 False
- [ ] 心跳超时（15 分钟）后，is_local_online() 返回 False
- [ ] 本地在线时，云端 WeChat Channel 跳过消息处理
- [ ] 本地离线时，云端接管消息处理

### 认证安全

- [ ] 所有同步 API 需要 `Authorization: Bearer {api_key}` 认证
- [ ] 使用 `secrets.compare_digest()` 防时序攻击
- [ ] 本地 API Key 存储在 keyring 中
- [ ] 云端 API Key 存储在 config.yaml 中（fallback 路径）

## Technical Contract

### SyncRepository — 同步数据仓库

<key_function>
- lifeprism/repository/sync_repository.py
  - sync_repository.SyncRepository.query_incremental:223
  - sync_repository.SyncRepository.upsert_rows:351
  - sync_repository.SyncRepository.upsert_rows_with_lww:567
  - sync_repository.SyncRepository.batch_get_existing_updated_at:429
  - sync_repository.SyncRepository.get_custom_record_slugs:788
  - sync_repository.SyncRepository.get_primary_key_field:718
  - sync_repository.SyncRepository.get_unique_fields:745
  - sync_repository.SyncRepository.has_updated_at:771
  - sync_repository.SyncRepository.count_rows:145
  - sync_repository.SyncRepository.count_rows_batch:182
  - sync_repository.SyncRepository.create_local_data_tables:908
  - sync_repository.SyncRepository.rebuild_dynamic_tables:964
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `query_incremental(table_name, last_sync_time, offset, limit)` | 增量查询 updated_at > last_sync_time 的记录 | 支持 offset/limit 分页；表名通过 TABLE_CONFIGS 白名单校验 |
| `upsert_rows(table_name, rows)` | 批量 INSERT OR REPLACE 写入 | AUTOINCREMENT 表自动剥离 id；列名白名单校验 |
| `upsert_rows_with_lww(table_name, rows)` | 带 LWW 冲突解决的批量写入 | 按主键或 UNIQUE 约束批量查询后内存比较 |
| `batch_get_existing_updated_at(table_name, pk_field, pk_values)` | 批量查询已存在记录的 updated_at | 单连接 IN 查询，避免 N+1 |
| `get_custom_record_slugs()` | 查询所有自定义记录类型的 slug | 用于动态发现 custom_{slug} 表 |
| `get_primary_key_field(table_name)` | 解析主键字段名 | 动态表（custom_{slug}）返回 "id" |
| `get_unique_fields(table_name)` | 解析 UNIQUE 约束字段列表 | 无 UNIQUE 约束时返回 None |
| `has_updated_at(table_name)` | 检查表是否有 updated_at 列 | 通过 TABLE_CONFIGS 的 update_at 标志判断 |
| `create_local_data_tables(slug_to_fields)` | 本地建表（只执行 DDL） | 表已存在时跳过；不写 meta 数据 |
| `rebuild_dynamic_tables(types)` | 云端全量重建动态表 | 按 slug 逐个 CREATE/SKIP；孤儿表**不删除**（需 tombstone 机制） |

**安全约束**：
- 所有表名通过 TABLE_CONFIGS 白名单或动态表前缀（`custom_`）校验
- 所有列名通过 TABLE_CONFIGS 的 columns 白名单校验
- AUTOINCREMENT 表的 id 字段写入时被剥离，防止污染 sqlite_sequence

### SyncClient — 本地同步客户端

<key_function>
- lifeprism/sync/sync_client.py
  - sync_client.SyncClient.sync_once
  - sync_client.SyncClient.pull_from_remote
  - sync_client.SyncClient.push_to_remote
  - sync_client.SyncClient._sync_dynamic_tables_definitions:295
  - sync_client.SyncClient._create_local_dynamic_tables:375
  - sync_client.SyncClient._rebuild_remote_dynamic_tables:406
  - sync_client.SyncClient.start_scheduled_sync
  - sync_client.SyncClient.try_start_sync
  - sync_client.SyncClient.finish_sync
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `sync_once(tables, directories)` | 执行一次完整同步 | 定义对比 → Pull → Push（数据库+文件），全部成功才更新 last_sync_time |
| `_sync_dynamic_tables_definitions(remote_url, api_key)` | 拉取云端定义 → slug 对比 → 双向建表 | 返回更新后的动态表 slug 列表 |
| `_create_local_dynamic_tables(slug_to_fields)` | 本地建动态数据表 | 委托给 SyncRepository.create_local_data_tables() |
| `_rebuild_remote_dynamic_tables(remote_url, api_key)` | 发送本地定义给云端重建 | POST /api/sync/rebuild-dynamic-tables |
| `start_scheduled_sync(interval_seconds=600)` | 启动后台定时同步 | 默认 10 分钟间隔；并发锁保护 |
| `try_start_sync()` | 原子获取同步锁 | threading.Lock 保护；已在使用中返回 False |
| `finish_sync()` | 释放同步锁 | try...finally 确保释放 |

**同步流程顺序**（sync_once）：
```
1. _sync_dynamic_tables_definitions  → 拉取云端定义、slug 对比、双向建表
2. pull_from_remote                   → 分批拉取数据库变更
3. push_to_remote                     → 推送本地数据库变更
4. _sync_files_full_flow              → 文件三阶段同步
5. 更新 last_sync_time                → 全部成功后才更新
```

### Sync Cloud API — 云端同步端点

<key_function>
- lifeprism/server/api/sync_cloud_api.py
  - sync_cloud_api.sync_pull:129
  - sync_cloud_api.sync_push:189
  - sync_cloud_api.sync_heartbeat:224
  - sync_cloud_api.sync_dynamic_tables_definitions
  - sync_cloud_api.sync_rebuild_dynamic_tables:313
  - sync_cloud_api.verify_sync_api_key:93
</key_function>

**API 端点**：

| 端点 | 方法 | Request Body | Response |
|------|------|-------------|----------|
| `/api/sync/pull` | POST | `{last_sync_time, tables, offset, limit}` | `{changes: {table: [rows]}, sync_time}` |
| `/api/sync/push` | POST | `{changes: {table: [rows]}}` | `{status: "ok", sync_time}` |
| `/api/sync/heartbeat` | POST | `{event: "online"\|"offline"\|"ping"}` | `{status: "ok", server_time}` |
| `/api/sync/dynamic-tables-definitions` | GET | (none) | `{types: [{slug, fields}]}` |
| `/api/sync/rebuild-dynamic-tables` | POST | `{types: [{slug, fields}]}` | `{rebuilt: [{slug, action}], sync_time}` |
| `/api/sync/pull-files/check` | POST | → 见 [data-sync-files-spec](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-files-spec.md) | |
| `/api/sync/pull-files/fetch` | POST | → 见 files-spec | |
| `/api/sync/push-files` | POST | → 见 files-spec | |
| `/api/sync/pull-files/verify` | POST | → 见 files-spec | |
| `/api/sync/pull-files/commit` | POST | → 见 files-spec | |

**认证**：所有端点需要 `Authorization: Bearer {api_key}` HTTP Header，使用 `secrets.compare_digest()` 常量时间比较。

**心跳设计**：`/api/sync/pull` 在请求开头隐式更新心跳，`/api/sync/heartbeat` 显式处理生命周期事件（online/offline/ping）。

### HeartbeatManager — 心跳状态管理器

<key_function>
- lifeprism/sync/heartbeat_manager.py
  - heartbeat_manager.HeartbeatManager.update_heartbeat:42
  - heartbeat_manager.HeartbeatManager.set_event:52
  - heartbeat_manager.HeartbeatManager.is_local_online:67
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `update_heartbeat()` | 仅更新时间戳，不改变 _last_event | 由 sync/pull 请求触发 |
| `set_event("online"\|"offline")` | 设置生命周期事件 | offline 立即生效，is_local_online() 返回 False |
| `is_local_online()` | 判断本地是否在线 | 优先级：offline > 从未连接 > 超时（15 分钟） |

### CloudConfigGenerator — 云端配置生成器

<key_function>
- lifeprism/config/cloud_config_generator.py
  - cloud_config_generator.CloudConfigGenerator.generate_cloud_config:38
  - cloud_config_generator.CloudConfigGenerator._build_config:129
  - cloud_config_generator.CloudConfigGenerator._collect_provider_keys:89
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `generate_cloud_config()` | 生成 cloud_init.yaml | 返回 `(path: str, key_is_new: bool)`；从 keyring 读取所有 Key |

**生成内容**：
```yaml
llm:
  provider: "Xiaomi MIMO"     # display_name，来自 settings.get("provider")
  model: "mimo-v2.5"           # 来自 settings.get("model")
sync:
  enabled: true
  api_key: "lifeprism_sync_..."  # 同步认证 Key
wechat_token: "wx_token_..."     # 微信 Token
monitor_type: none               # 强制为 none
providers:                       # 有 env_key 且有 api_key 的 provider
  - name: xiaomi_mimo            # 内部 name（用于匹配 providers.yaml）
    env_key: api_key_xiaomi_mimo # keyring username
    api_key: "sk-c25f..."        # 明文 API Key
```

### CloudInitializer — 云端配置初始化器

<key_function>
- lifeprism/config/cloud_initializer.py
  - cloud_initializer.CloudInitializer.initialize:81
  - cloud_initializer.CloudInitializer.should_initialize:52
  - cloud_initializer.CloudInitializer._validate:148
  - cloud_initializer.CloudInitializer._write_config_yaml:204
  - cloud_initializer.CloudInitializer._write_providers_yaml:255
  - cloud_initializer.CloudInitializer.validate_monitor_type:313
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `should_initialize()` | 检测 cloud_init.yaml 是否存在 | 返回 bool |
| `initialize()` | 执行云端配置初始化 | 验证 → 写入 config.yaml → 写入 providers.yaml → 删除 cloud_init |
| `validate_monitor_type()` | 运行时校验 monitor_type 必须为 none | 非 none 时自动修正为 "none" |

**验证规则**：
- 必需字段：wechat_token、sync.api_key、llm.provider、llm.model
- providers 列表不能为空
- llm.provider 可以是 display_name，通过 `provider_manager.get_provider_id()` 转为内部 name 后匹配 providers[].name
- 对应 provider 必须有 api_key

### 同步范围

#### 同步的表（30 张静态表 + 动态表）

| 类别 | 表名 |
|------|------|
| 用户输入数据（15张） | mood_entries, diary, todo_list, goal, goal_journal, plan_doc, daily_focus, weekly_focus, habits, habit_challenges, habit_checkins, habit_chains, habit_chain_nodes, timeline_custom_block, time_paradoxes |
| 元数据（9张） | category, sub_category, mood_types, mood_impacts, user_values, commitments, custom_record_types, custom_record_fields, wechat_account_state |
| Monitor 数据（3张） | user_app_behavior_log, behavior_analysis, raw_behavior_analysis |
| 缓存表（3张） | multi_purpose_map_cache, single_purpose_map_cache, category_map_cache |
| 统计数据（1张） | tokens_usage_log |
| 动态表 | custom_{slug}（运行时从 dynamic-tables-definitions 端点发现） |

#### 不同步的表

- chat_session（实体在 session/*.jsonl）
- goal_stats、daily_report、weekly_report、monthly_report（统计缓存，可本地重新生成）
- schema_version（迁移版本号，两端独立管理）
- screen_captures、window_events（Monitor 原始数据，数据量大且云端用不上）

### 动态表同步机制

**设计决策**: 见 ADR [dynamic-tables-sync-definition-comparison](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-16-dynamic-tables-sync-definition-comparison.md)

**流程**：
1. 在 pull 之前调用 `GET /api/sync/dynamic-tables-definitions` 获取云端定义 `{types: [{slug, fields}]}`
2. 取本地 slugs（从 `custom_record_types` 表查询）与云端 slugs 做差集比较
3. 云端有但本地无 → `create_local_data_tables()` 本地建表（只执行 DDL，不写 meta；表已存在则跳过）
4. 本地有但云端无 → `POST /api/sync/rebuild-dynamic-tables` 发送本地定义给云端
5. 两端一致 → 无操作
6. 动态表 slug 列表加入 SYNC_TABLES，后续 pull/push 正常同步数据

**建表策略**：
- 本地建表：只执行 `CREATE TABLE IF NOT EXISTS`（DDL），不写 `custom_record_types` 和 `custom_record_fields` meta 数据。让 pull 阶段统一拉取两端的 meta 数据。
- 远端重建：按 slug 逐个 CREATE（表不存在时）/ SKIP（表已存在时）。`rebuild_dynamic_tables` **不执行 DROP**，孤儿表清理需要独立的 tombstone 机制。

### 冲突解决策略

**LWW（Last-Write-Wins）**：
- 数据库：比较 `updated_at` 时间戳，更晚的保留；相等时跳过
- 无物理 updated_at 列的表（mood_types 等）不参与增量比较，直接覆盖

**设计理由**：
- NTP 时间同步保证时钟误差 < 1 秒
- 主备模式下，同一时间只有一端的 Agent 在工作（本地在线时云端跳过消息处理），冲突概率 < 0.1%
- 无需复杂的版本号或 CRDT 方案

### 消息路由规则

```
云端 WeChat Channel 收到消息
    │
    ├─ heartbeat_manager.is_local_online() == True
    │   → 本地在线，跳过云端处理（本地会处理）
    │
    └─ heartbeat_manager.is_local_online() == False
        → 本地离线，云端 Agent Loop 处理
```

| 场景 | 行为 | 接管延迟 |
|------|------|----------|
| 本地正常运行 | 每 10 分钟心跳，云端跳过消息 | — |
| 本地正常关闭 | 发送 offline 事件，云端立即接管 | < 1 秒 |
| 本地异常退出 | 15 分钟超时后云端自动接管 | ≤ 15 分钟 |
| 网络分区 | 极端情况可能重复回复 | 概率 < 1% |

## Design Rationale

**为什么用 LWW 而非 CRDT？**
- 主备模式下冲突概率极低，LWW 已足够
- 30+ 张表改 schema 为 CRDT 成本过高
- LWW 不需要额外的版本号字段或 device_id

**为什么心跳状态用纯内存而非数据库？**
- 云端服务长期运行，重启后 15 分钟内可通过首次 sync 自动恢复
- 数据库持久化是过度设计，增加维护成本
- 纯内存零开销，线程安全通过 threading.Lock 保证

**为什么动态表用 slug 集合对比而非快照？**
- 快照对比只能检测"云端→本地"方向，检测不到"本地主动新增动态表"
- slug 对比直接比较两端定义，方向正确，能同时覆盖双向变更
- 对比逻辑简单（集合差集），易维护

**为什么 cloud_init.yaml 的 llm.provider 存 display_name？**
- 与本地 config.yaml 语义一致（provider 字段始终是 display_name）
- 云端写入 config.yaml 后保持与本地相同的格式
- 验证时通过 `provider_manager.get_provider_id()` 转为内部 name 匹配 providers 列表

**为什么 provider 有两层命名（display_name ↔ name）？**
- `name`（内部标识符）：全小写+下划线，用于 keyring/env_key 查找、ProviderSpec 匹配、providers.yaml 索引
- `display_name`（用户可见名）：含大小写空格，用于前端下拉框、config.yaml.provider 字段
- 设计原则：用户可见层用 display_name，系统内部层用 name，转换入口统一为 `get_provider_id()`

**有哪些约束？**
- 同步依赖于 NTP 时间同步，时钟偏差 > 1 秒可能影响 LWW 准确性
- **时区一致性要求**：本地和云端必须使用相同时区生成 `updated_at`，否则 LWW 比较会失效
- 消息路由在网络分区场景下可能产生重复回复（概率 < 1%）
- 云端 agent-only 不启动 dreaming，文件修改只来自会话处理

**有哪些已知限制？**
- 首次同步 16MB 数据需要 30-50 秒（分 10 批，每批 ~5 秒）
- 15 分钟超时意味着异常退出后最长 15 分钟才能云端接管
- 无实时同步能力，依赖 10 分钟定时轮询

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **文件同步**：[`docs/specs/2026-07-16-data-sync-files-spec.md`](./2026-07-16-data-sync-files-spec.md) — per-file version tracking、三阶段协议、AI 合并
- **Config 模块配置管理**：[`docs/specs/2026-07-06-config-settings-spec.md`](./2026-07-06-config-settings-spec.md) — SettingsManager、ProviderManager、双层命名体系
- **Agent 执行引擎**：[`docs/specs/2026-07-06-llm-agent-spec.md`](./2026-07-06-llm-agent-spec.md) — AgentLoop、Tool 注册
- **ActivityWatch 数据同步**：[`docs/specs/2026-04-16-classify-spec.md`](./2026-04-16-classify-spec.md) — SyncService 分类管线
