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

### 数据同步（Data Sync）— P2 计划

**使用模式**：主备模式（平时用 Windows 桌面版，出门时用 Linux Agent Only）

**同步单位**：记录级别（Row-level），尽力而为（Best-effort）
- 单条记录失败不阻塞其他记录
- 只有全部成功才更新 `last_sync_time`（避免丢数据）

**hash_id（同步标识）**：
- **定位**：同步专用标识，不是主键；它是给 AUTOINCREMENT 表补充的跨端定位字段，本地 CRUD 仍使用自增 `id`
- **背景**：6 张 AUTOINCREMENT 表（`timeline_custom_block`、`time_paradoxes`、`mood_impacts`、`habit_chains`、`habit_chain_nodes`、`user_app_behavior_log`）的自增 ID 在两端不同，不能作为跨端稳定标识
- **格式**：`{prefix}{uuid.hex[:12]}`，例如 `mi-a1b2c3d4e5f6`；前缀由 `lifeprism/sync/constants.py` 的 `HASH_ID_PREFIXES` 定义
- **用途**：同步 pull/push 时定位同一条逻辑记录；墓碑表 `deletion_log.record_id` 对 AUTOINCREMENT 表存 `hash_id`，对 TEXT PRIMARY KEY 表存主键
- **不用途**：本地 `get_by_id`、update、delete 不使用 `hash_id`；存在业务 UNIQUE 时，LWW 冲突判定不使用 `hash_id` 作为业务唯一键，而使用 `table_constraints` 中声明的业务 UNIQUE
- **参考**：`docs/adr/2026-07-22-hash-id-sync-only-identifier.md`

**通信方式**：HTTP REST API + 本地主动轮询
- Windows 本地主动发起（避免 NAT 问题）
- 云端被动响应（不需要知道本地 IP）
- 同步时机：启动时立即同步 + 定时同步（每 10 分钟）

**同步范围**：

**数据库同步**（31 张静态表 + 动态表）：
- **用户输入数据**（15 张）：`mood_entries`、`diary`、`todo_list`、`goal`、`goal_journal`、`plan_doc`、`daily_focus`、`weekly_focus`、`habits`、`habit_challenges`、`habit_checkins`、`habit_chains`、`habit_chain_nodes`、`timeline_custom_block`、`time_paradoxes`
- **元数据**（8 张）：`category`、`sub_category`、`mood_types`、`mood_impacts`、`user_values`、`commitments`、`custom_record_types`、`custom_record_fields`
- **Monitor 数据**（3 张）：`user_app_behavior_log`、`behavior_analysis`、`raw_behavior_analysis`
- **缓存表**（3 张）：`multi_purpose_map_cache`、`single_purpose_map_cache`、`category_map_cache`
- **统计数据**（1 张）：`tokens_usage_log`（云端 token 使用需要统计）
- **动态表**：`custom_records_{slug}`（根据 `custom_record_types.slug` 运行时获取）

**不同步的表**（16 张）：
- `chat_session`（元数据表，实体在 `session/*.jsonl`）
- `goal_stats`、`daily_report`、`weekly_report`、`monthly_report`（统计缓存，可本地重新生成）
- `schema_version`（迁移版本号，两端独立管理）
- `screen_captures`、`window_events`（Monitor 原始数据，云端用不上）

**文件同步**（11 个目录/文件）：
- 需要同步：`agent/`、`assets/`、`channel/wechat/account.json`、`diary/`、`docs/`、`external_files/`、`plan/`、`prompts/`、`session/`、`user/`、`workflow/`
- 不同步：`.schedule_state.json`、`config/`、`dataset/`、`debug_logs/`、`screenshots/`、`channel/wechat/media/`
- **关键文件**：`channel/wechat/account.json` 必须同步（包含微信 session_id，保证对话历史连贯）

**增量同步机制**：
- 依赖 `updated_at` 字段（需为 31 张表添加此字段）
- 查询：`WHERE updated_at > last_sync_time ORDER BY updated_at ASC LIMIT ? OFFSET ?`（分批查询）
- 使用索引：`CREATE INDEX idx_{table}_updated_at ON {table}(updated_at)`
- 查询耗时：~155ms（31 个表 × 5ms）

**分批同步机制**：
- 客户端按表逐个拉取，每表分批 1000 条
- 避免首次同步超时（httpx timeout=60s）
- 首次同步 16MB（~10,000 条）：分 10 批，总耗时 ~30-50 秒

**冲突解决**：Last-Write-Wins（最后写入获胜）
- 比较 `updated_at` 时间戳，谁更晚谁保留
- 无需版本号或 device_id（主备模式冲突概率 < 0.1%）
- NTP 时间同步保证时钟误差 < 1 秒

**消息路由与心跳机制**：
- **问题**：微信消息群发到本地和云端，需要避免重复回复
- **解决方案**：云端通过心跳机制判断本地是否在线
- **心跳来源**：
  1. 复用数据同步：本地每 10 分钟发起 `POST /api/sync/pull`，云端调用 `heartbeat_manager.update_heartbeat()`
  2. 生命周期事件：本地 FastAPI 启动/关闭时发送 `POST /api/sync/heartbeat {"event": "online|offline"}`
- **判断逻辑**：`now() - last_heartbeat < 15min` → 在线
- **消息路由**：本地在线时云端跳过处理，本地离线时云端处理
- **状态管理**：纯内存（`HeartbeatManager`），不使用数据库

**API 区分**：
- **云端 API**（`main_agent_only.py` 提供，端口 8101）：
  - `POST /api/sync/pull`、`POST /api/sync/push`（数据库同步）
  - `POST /api/sync/pull-files`、`POST /api/sync/push-files`（文件同步）
  - `POST /api/sync/heartbeat`（心跳/生命周期事件）
- **本地 API**（`main.py` 提供）：
  - `GET /api/sync/status`（查询同步状态）
  - `POST /api/sync/trigger`（手动触发同步）
  - `POST /api/sync/generate-cloud-config`（生成云端配置）

**数据量估算**：
- 总数据量（3 个月）：~16MB（不含 window_events）
- 增量同步（10 分钟）：~27KB
- 首次同步：16MB，分批传输（1000 条/批）+ 压缩（gzip），约 30-50 秒

**安全机制**：
- API Key 认证（32 字节随机字符串，`secrets.compare_digest` 防时序攻击）
- HTTPS 加密传输（Let's Encrypt 免费证书）

**配置管理**：
- **Key 存储**：本地用 keyring（Windows 凭据管理器），云端用 config.yaml
- **配置生成**：本地生成 `cloud_init.yaml`（包含完整配置和所有 Key）
- **配置初始化**：云端启动时读取 `cloud_init.yaml` → 写入 `config.yaml` → 删除临时文件
- **配置文件路径**：
  - 本地：`{lifeprism_data_path}/cloud_init.yaml`
  - 云端：`{lifeprism_data_path}/cloud_init.yaml`（临时），写入后删除
- **前端交互**：点击生成 → 保存到本地 → 打开文件夹并选中 → 提示用户复制到云端

**云端 CLI 管理**（`main_agent_only.py` 命令行）：
- `reinit-config`：重新初始化配置（从 `cloud_init.yaml` 读取并覆盖 `config.yaml`）
- `show-config`：查看当前配置（脱敏显示）
- `test-llm`：测试 LLM 连接

**Key 读取逻辑**（统一的 fallback 机制）：
- LLM API Key：`provider_manager.get_api_key()` → keyring 优先 → fallback 到 `providers.yaml::api_key`
- 微信 Token：`WechatAuth._load_token_from_keyring()` → keyring 优先 → fallback 到 `config.yaml::wechat_token`
- 同步 API Key：`sync_config.get_sync_api_key()` → keyring 优先 → fallback 到 `config.yaml::sync_api_key`
- 代码修改点集中在数据返回层，其他代码零感知云端/本地差异

**不存在的概念**：
- 实时同步（10 分钟已足够）
- 版本号冲突检测（主备模式不需要）
- cr-sqlite / CRDT（过度设计）
- 配置文件加密（SSH 已加密 + 文件立即删除）
- secrets.yaml（统一用 config.yaml）
- 本地在线状态持久化（纯内存管理，服务重启 15 分钟内自动恢复）
- IP 白名单、请求签名（HTTPS + API Key 已足够）

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
