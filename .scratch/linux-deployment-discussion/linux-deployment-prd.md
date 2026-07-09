# PRD: Linux 跨平台部署支持

**创建时间**: 2026-07-08  
**状态**: ready-for-agent  
**优先级**: P1

---

## Problem Statement

LifePrism 当前仅支持 Windows 桌面环境运行，限制了以下使用场景：

1. **Web Demo 演示**：无法在云服务器上部署 Web 版本供外部用户访问和体验
2. **Agent 云端部署**：无法将 AI Agent 部署到服务器，实现 24/7 微信渠道服务（本地关机时无法使用）
3. **跨平台开发**：开发者无法在 Linux/macOS 环境下开发和调试后端服务

核心技术障碍：
- 路径系统依赖 Windows 环境变量（`%LOCALAPPDATA%`）
- Monitor 模块强依赖 Windows API（`pywin32`, `pynput`）
- 依赖管理未区分平台（所有依赖都是必需的）
- 启动流程未隔离可选模块

---

## Solution

实现 LifePrism 的跨平台部署支持，提供三种独立的运行形态：

1. **Windows 桌面完整版**（现有功能保持不变）
   - FastAPI + Electron 前端 + Agent + Monitor
   - 完整的本地数据采集与管理功能

2. **Linux Web Demo**（新增）
   - FastAPI + 静态前端 + Agent（无 Monitor）
   - 通过 Nginx 反向代理对外暴露
   - 用于产品演示和远程访问体验
   - **使用预置的演示数据**，不需要数据同步

3. **Linux Agent Only**（新增）
   - 仅 Agent Loop + WeChat Channel（无 FastAPI，无前端，无 Monitor）
   - 通过微信渠道提供 AI 对话服务
   - 服务器后台运行，本地关机也可用
   - **使用预置的演示数据**，不需要数据同步

**数据同步作为 P2 单独讨论**，本期不实现。

---

## User Stories

### 作为产品负责人
1. 作为产品负责人，我想在云服务器上部署 Web Demo，以便潜在客户可以在线体验 LifePrism 的核心功能，无需下载安装
2. 作为产品负责人，我想展示 LifePrism 的完整界面和数据可视化，以便演示产品价值

### 作为 LifePrism 用户
3. 作为用户，我想将 AI Agent 部署到云服务器，以便出门在外时通过微信对话查询和记录数据，不受本地电脑开关机影响
4. 作为用户，我想通过微信查询今天的电脑使用情况，以便随时了解自己的时间分配
5. 作为用户，我想通过微信记录心情和想法，以便即使不在电脑前也能持续记录
6. 作为用户，我想通过浏览器访问 LifePrism，以便在任何设备上查看我的数据

### 作为开发者
7. 作为开发者，我想在 Linux 开发环境下运行后端服务，以便使用 Linux 服务器进行开发和调试
8. 作为开发者，我想使用统一的依赖管理，以便在不同平台上快速搭建开发环境
9. 作为开发者，我想看到清晰的平台适配文档，以便理解不同运行模式的差异和限制
10. 作为开发者，我想通过简单的命令启动不同模式，以便快速验证功能

### 作为运维人员
11. 作为运维人员，我想通过标准的启动脚本部署服务，以便自动化部署流程
12. 作为运维人员，我想看到清晰的端口和依赖说明，以便配置防火墙和反向代理
13. 作为运维人员，我想使用环境变量配置数据路径，以便灵活管理服务器存储
14. 作为运维人员，我想监控服务的运行状态，以便及时发现和处理问题

---

## Implementation Decisions

### 1. 多入口架构

**决策**：创建三个独立的启动入口文件，而非在单一文件中用 if/else 控制。

**理由**：
- 不同运行形态是**不同的产品形态**，不是同一产品的"模式切换"
- 避免 Python import 机制导致的平台依赖问题（顶部 import 无论如何都会执行）
- 代码更清晰，每个入口文件职责单一
- 依赖按需加载，减少启动时间和内存占用

**文件结构**：
```
lifeprism/server/
├── main.py                  # Windows 桌面完整版（现有文件，需小幅修改）
├── main_web_demo.py         # Linux Web Demo（新增）
└── main_agent_only.py       # Linux Agent Only（新增）
```

**启动命令**：
- Windows 桌面版：`uvicorn lifeprism.server.main:app`
- Linux Web Demo：`uvicorn lifeprism.server.main_web_demo:app --host 0.0.0.0 --port 8101`
- Linux Agent Only：`python -m lifeprism.server.main_agent_only`

### 2. Monitor 模块平台隔离

**决策**：Monitor 模块导入延迟到运行时，并增加平台检查。

**修改点**：
- `main.py` 第 225 行的 monitor 导入移到 if 块内部
- 增加平台检查：`if sys.platform != "win32"` 直接跳过，记录 warning
- 增加 ImportError 捕获：缺少 `pywin32` 等依赖时优雅降级

**预期行为**：
- Windows 上：正常启动 Monitor（如果 `monitor_type == "lifeprism"`）
- Linux 上：即使 `monitor_type == "lifeprism"`，也跳过 Monitor 启动，记录 warning

### 3. 路径系统跨平台适配

**决策**：保持现有路径逻辑不变，所有平台都使用 `config.yaml` 的 `lifeprism_data_path` 配置。

**理由**：
- 逻辑统一，无需针对 Linux 特殊处理
- 部署时通过环境变量 `LIFEPRISM_DATA_PATH` 或配置文件指定数据路径
- Windows 已有的迁移逻辑在 Linux 上也能工作（虽然 Linux 上不需要迁移）

**不修改**：
- `settings_manager.py` 的 `_resolve_config_base_path()` 保持不变
- `_resolve_default_data_path()` 保持不变
- 配置文件读取逻辑保持不变

### 4. 依赖管理

**决策**：保持 `pyproject.toml` 不变，不进行依赖分层。

**理由**：
- Python 依赖安装后不使用不会影响运行（只要代码不导入）
- 真正的隔离在代码层面（通过不同入口和 Monitor 平台检查实现）
- 避免影响 Windows Electron 打包流程
- Linux 上即使安装了 `pywin32`、`pynput`、`mss`，只要不导入就不会有问题

**预期行为**：
- Windows 打包：正常安装所有依赖，Monitor 正常工作
- Linux 部署：安装所有依赖，但不同入口不导入 Monitor 模块

**后备方案**：
如果实际部署时发现 `pywin32` 在 Linux 上无法安装，再考虑使用 `platform_system` 标记：
```toml
dependencies = [
    "pywin32>=306; platform_system=='Windows'",
    "pynput>=1.7.7; platform_system=='Windows'",
    "mss>=9.0.1; platform_system=='Windows'",
]
```

### 6. Web Demo 前端部署

**决策**：前端构建静态文件，通过 Nginx 反向代理统一入口。

**项目需要暴露的信息**（供服务器管理员配置 Nginx）：
- **后端监听端口**：8101（固定）
- **前端静态文件**：`frontend/dist/`（通过 `npm run build` 生成）
- **需要代理的路径**：`/api/*`（包括 SSE 流式接口）
- **SSE 支持**：需要禁用 Nginx 缓冲（`proxy_buffering off`），否则 Chatbot 流式响应会卡顿

**前端构建**：
- `cd frontend && npm run build` 生成 `dist/` 目录
- 部署时将 `dist/` 复制到服务器指定位置

### 5. Agent Only 轻量化

**决策**：Agent Only 模式不启动 FastAPI，仅运行 Agent Loop + Channel。

**不包含的模块**：
- FastAPI 及所有路由
- 定时任务调度器（ScheduleService，因为依赖 Monitor 数据）
- 数据库迁移（首次启动时执行一次即可）
- 资源初始化（简化版，仅初始化必要资源）

**包含的模块**：
- 数据库初始化（`init_database`）
- Agent Loop（`agent_loop.loop()`）
- WeChat Channel（`wechat_channel.start()`）
- 日志系统

**预期资源占用**：
- 内存：< 200MB（vs 完整版 ~500MB）
- 启动时间：< 5 秒（vs 完整版 ~15 秒）

### 7. 启动脚本

**决策**：提供标准化的 bash 启动脚本。

**脚本文件**（`scripts/deployment/`）：
- `start_web_demo.sh`（Linux Web Demo 启动脚本）
- `start_agent_only.sh`（Linux Agent Only 启动脚本）

**环境变量支持**：
- `LIFEPRISM_DATA_PATH`：数据目录路径（现有配置）

---

## Testing Decisions

### 测试原则
- **测试外部行为，不测试实现细节**
- **跨平台测试**：核心功能在 Windows 和 Linux 上都要测试
- **独立性**：每个测试独立运行，不依赖其他测试的状态

### 需要测试的模块

#### 1. 启动入口测试
**测试文件**：`test/integration/test_startup_modes.py`

**测试用例**：
- `test_main_imports_monitor_on_windows`：Windows 上能正常导入 Monitor
- `test_main_web_demo_no_monitor_import`：Web Demo 不导入 Monitor
- `test_main_agent_only_no_fastapi_import`：Agent Only 不导入 FastAPI
- `test_web_demo_startup_completes`：Web Demo 能完整启动
- `test_agent_only_startup_completes`：Agent Only 能完整启动

**参考现有测试**：
- `test/core/integration/` 下的集成测试结构

#### 2. 路径解析测试
**测试文件**：`test/core/unit/config/test_settings_manager_cross_platform.py`

**测试用例**：
- `test_config_base_path_windows`：Windows 上配置路径正确
- `test_config_base_path_linux`：Linux 上配置路径回退到 `localData`
- `test_data_path_from_env_var`：环境变量覆盖默认路径
- `test_data_path_from_config_yaml`：配置文件优先级高于默认

**Mock 策略**：
- Mock `sys.platform` 测试不同平台
- Mock `os.environ` 测试环境变量
- Mock `Path.exists()` 测试配置文件存在性

#### 3. Monitor 降级测试
**测试文件**：`test/core/unit/monitor/test_monitor_platform_check.py`

**测试用例**：
- `test_monitor_import_fails_gracefully_on_linux`：Linux 上 Monitor 导入失败不崩溃
- `test_monitor_type_ignored_on_non_windows`：非 Windows 平台忽略 `monitor_type` 配置
- `test_monitor_startup_warning_logged`：Linux 上尝试启动 Monitor 记录 warning

**参考**：
- `test/core/unit/monitor/` 下现有的 Monitor 测试

#### 4. Agent Only 功能测试
**测试文件**：`test/integration/test_agent_only_mode.py`

**测试用例**：
- `test_agent_loop_starts_without_fastapi`：Agent Loop 能独立启动
- `test_wechat_channel_starts_in_agent_mode`：WeChat Channel 能启动
- `test_agent_tools_work_without_monitor`：Agent 工具在无 Monitor 时正常工作
- `test_database_accessible_in_agent_mode`：数据库读写正常

**Mock 策略**：
- Mock WeChat Channel 的网络请求
- Mock LLM 调用
- 使用临时数据库文件

---

## P2 Implementation: 数据同步方案

> **注意**：以下为 P2 阶段的实现方案，P1 不包含数据同步功能。

### 问题定义

P1 完成后，Windows 本地和 Linux 云端各自独立运行，但用户需要：
1. 在 Windows 本地查看通过微信（Linux Agent）记录的数据
2. 在 Linux 云端使用 Windows 本地采集的 Monitor 数据
3. 两端数据保持一致，支持离线后同步
4. 避免微信消息群发导致的重复回复（本地和云端都收到消息）

### 解决方案

实现 Windows ↔ Linux 双向数据同步（数据库 + 文件），采用主备模式（平时用 Windows，出门时用 Linux Agent）。云端通过心跳机制判断本地是否在线，决定是否处理微信消息。

### P2 User Stories

15. 作为用户，我想在出门前启动 Windows 本地，自动将最新数据同步到云端，以便微信查询时能看到最新的电脑使用数据
16. 作为用户，我想在外通过微信记录心情后，回家打开 Windows 能自动拉取云端的新记录
17. 作为用户，我想在前端设置页面点击"生成云端配置"，自动生成配置文件并提示我复制到云端
18. 作为用户，我想在云端 API Key 过期时，通过 CLI 命令重新加载配置，而不需要重新部署服务
19. 作为用户，我想查看同步状态（上次同步时间、同步记录数），以便确认数据已同步
20. 作为开发者，我想通过云端 CLI 测试 LLM 连接，以便快速验证配置是否正确
21. 作为用户，我想在外通过微信发送消息时，只收到一个回复（本地在线时本地处理，本地离线时云端处理）
22. 作为用户，我想在 Windows 本地关闭时，云端能立即知道并接管微信消息处理
23. 作为用户，我想在 Windows 本地异常崩溃时，云端能在 15 分钟内自动接管微信消息处理
24. 作为用户，我想在外通过微信对话时，云端能使用与本地相同的 session_id，以便对话历史连贯

### P2 Implementation Decisions

#### 1. 同步范围与数据量

**需要同步的表**（30 张静态表 + 动态表）：

**用户输入数据**（15 张）：
- `mood_entries`、`diary`、`todo_list`、`goal`、`goal_journal`、`plan_doc`
- `daily_focus`、`weekly_focus`、`habits`、`habit_challenges`、`habit_checkins`
- `habit_chains`、`habit_chain_nodes`、`timeline_custom_block`、`time_paradoxes`

**元数据**（8 张）：
- `category`、`sub_category`、`mood_types`、`mood_impacts`
- `user_values`、`commitments`、`custom_record_types`、`custom_record_fields`

**Monitor 数据**（3 张）：
- `user_app_behavior_log`、`behavior_analysis`、`raw_behavior_analysis`

**缓存表**（3 张）：
- `multi_purpose_map_cache`、`single_purpose_map_cache`、`category_map_cache`

**统计数据**（1 张）：
- `tokens_usage_log`（云端 token 使用需要统计）

**动态表**（运行时获取）：
- `custom_records_{slug}`（根据 `custom_record_types.slug` 动态同步）

**不同步的表**（16 张）：
- `chat_session`（元数据表，实体在 `session/*.jsonl`）
- `goal_stats`、`daily_report`、`weekly_report`、`monthly_report`（统计缓存，可本地重新生成）
- `schema_version`（迁移版本号，两端独立管理）
- `screen_captures`、`window_events`（Monitor 原始数据，云端用不上）

**数据量估算**（3 个月使用）：
- 总数据量：~16MB（不含 `window_events`）
- 增量同步（10 分钟）：~27KB
- 首次同步：16MB，分批传输（1000 条/批）+ 压缩，约 30-50 秒

**理由**：
- 排除 `window_events` 可减少 10 倍传输量
- 缓存表数据量小（< 1MB），同步比重新计算更高效（避免触发 LLM）
- `tokens_usage_log` 包含云端 token 使用，需要统计
- `raw_behavior_analysis` 数据量小，保持完整性

#### 2. 增量同步机制

**依赖字段**：`updated_at`（需为以下表添加）
- `behavior_analysis`、`category`、`category_map_cache`、`goal`、`mood_entries`
- `sub_category`、`timeline_custom_block`、`todo_list`、`user_app_behavior_log`
- `goal_journal`、`plan_doc`、`daily_focus`、`weekly_focus`、`habit_challenges`
- `habit_checkins`、`habit_chains`、`habit_chain_nodes`、`time_paradoxes`
- `mood_types`、`mood_impacts`、`user_values`、`commitments`
- `custom_record_types`、`custom_record_fields`、`custom_records_{slug}`
- `raw_behavior_analysis`

**查询方式**：
```python
# 利用索引快速查询增量数据
SELECT * FROM {table} WHERE updated_at > ? ORDER BY updated_at ASC
LIMIT ? OFFSET ?  # 分批查询，避免首次同步超时
```

**索引创建**：
```sql
CREATE INDEX IF NOT EXISTS idx_{table}_updated_at ON {table}(updated_at);
```

**性能**：
- 有索引：31 个表 × 5ms = ~155ms
- 无索引：31 个表 × 500ms = ~15 秒

**理由**：
- 不需要扫描全表
- 避免版本号方案的改动成本（30+ 张表改 schema）
- 主备模式下冲突概率极低，无需复杂的 CRDT

**动态表处理**：
```python
def get_all_sync_tables():
    """获取所有需要同步的表（包括动态表）"""
    static_tables = SYNC_TABLES.copy()
    
    # 查询 custom_record_types 获取 slug 列表
    slugs = db.execute("SELECT slug FROM custom_record_types").fetchall()
    
    # 添加动态表
    for (slug,) in slugs:
        static_tables.append(f"custom_records_{slug}")
    
    return static_tables
```

#### 3. 冲突解决策略

**策略**：Last-Write-Wins（最后写入获胜）
- 比较 `updated_at` 时间戳，谁更晚谁保留
- 无需版本号或 `device_id`

**同步原子性**：Best-effort（尽力而为）
- 单条记录失败不阻塞其他记录
- 只有全部成功才更新 `last_sync_time`（避免丢数据）

**冲突判断逻辑**：
```python
if local_row.updated_at <= last_sync_time:
    # 本地未修改 → 直接覆盖
    local_db.replace(remote_row)
elif remote_row.updated_at > local_row.updated_at:
    # 云端更晚 → 覆盖本地
    local_db.replace(remote_row)
else:
    # 本地更晚 → 保留本地（稍后推送）
    pass
```

**理由**：
- NTP 时间同步保证时钟误差 < 1 秒
- 主备模式不会同时修改同一条记录，冲突概率 < 0.1%
- 避免版本号方案的 30+ 张表改动

**明确否决的方案**：
- ❌ 版本号 + `device_id`（改动量太大）
- ❌ cr-sqlite / CRDT（过度设计，适用于多端并发）

#### 4. 通信架构

**方案**：HTTP REST API + 本地主动轮询
- Windows 本地主动发起（避免 NAT 穿透问题）
- Linux 云端被动响应（不需要知道本地 IP）

**同步时机**：
- 启动时立即同步 1 次
- 定时同步（每 10 分钟）

**API 设计**：

**数据库同步 API**：
```
POST /api/sync/pull
  Request: {last_sync_time, tables: [table_name], offset, limit, api_key}
  Response: {changes: {table: [rows]}, sync_time}

POST /api/sync/push
  Request: {changes: {table: [rows]}, api_key}
  Response: {status: 'ok', sync_time}
```

**文件同步 API**：
```
POST /api/sync/pull-files
  Request: {last_sync_time, directories: ['session', 'channel/wechat'], api_key}
  Response: {files: [{path, content_base64_gzip, mtime}], sync_time}

POST /api/sync/push-files
  Request: {files: [{path, content_base64_gzip, mtime}], api_key}
  Response: {status: 'ok', sync_time}
```

**心跳 API**：
```
POST /api/sync/heartbeat
  Request: {event: 'online'|'offline'|'ping', api_key}
  Response: {status: 'ok', server_time}
```

**分批同步机制**：

客户端按表逐个拉取，每表分批 1000 条：

```python
# 客户端 sync_client.py
def pull_from_remote_batched(self, remote_url, api_key, last_sync_time, tables):
    for table_name in tables:
        offset = 0
        batch_size = 1000
        
        while True:
            response = httpx.post(
                url=f"{remote_url}/api/sync/pull",
                json={
                    "last_sync_time": last_sync_time,
                    "tables": [table_name],  # 一次只拉一个表
                    "offset": offset,
                    "limit": batch_size,
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()
            
            rows = data["changes"].get(table_name, [])
            if not rows:
                break
            
            # 应用 Last-Write-Wins 冲突解决
            self._apply_rows(table_name, rows, last_sync_time)
            
            if len(rows) < batch_size:
                break  # 最后一批
            
            offset += batch_size
```

**Repository 支持**：

```python
# sync_repository.py
def query_incremental(self, table_name, last_sync_time, offset=0, limit=None):
    sql = f"SELECT * FROM {table_name} WHERE updated_at > ? ORDER BY updated_at ASC"
    params = [last_sync_time]
    
    if limit is not None:
        sql += f" LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    
    cursor = self.db.execute(sql, params)
    return [dict(row) for row in cursor.fetchall()]
```

**性能估算**：
- 首次同步 16MB（~10,000 条记录）
- 分 10 批，每批 1000 条（~1.6MB）
- 单批耗时 ~3-5 秒（查询 + 网络传输 + 写入）
- 总耗时 ~30-50 秒（可接受）

**理由**：
- 简单可靠，不需要 WebSocket 长连接
- 10 分钟间隔已足够（不需要实时同步）
- 云端无需访问本地（避免家庭网络 NAT 问题）
- 分批避免首次同步超时（httpx timeout=60s）

#### 5. 安全机制

**多层防护**：
1. **API Key 认证**（必须）：32 字节随机字符串
2. **HTTPS 加密传输**（必须）：Let's Encrypt 免费证书
3. **IP 白名单**（可选）：家庭 IP 可能变化
4. **请求签名**（可选）：HMAC-SHA256

**API Key 存储**：
- **本地 Windows**：keyring（Windows 凭据管理器）
- **云端 Linux**：config.yaml（文件权限 600）

**理由**：
- 云端无桌面环境，keyring 不可用
- 同步 API Key 是云端生成的，不是用户敏感信息
- 文件权限 600 + HTTPS 已足够安全

#### 6. 配置管理（Key 统一存储）

**Key 类型**（3 种）：
1. **LLM Provider API Keys**（多个，按 Provider 分组）
   - keyring 命名：`api_key_{provider_name}`
   - 例如：`api_key_anthropic`、`api_key_openai`
2. **微信通道 Token**（1 个）
   - keyring 命名：`wechat_bot_token`
3. **数据同步 API Key**（1 个）
   - keyring 命名：`sync_api_key`

**Key 读取逻辑（统一 fallback 机制）**：

所有 Key 读取时，优先从 keyring 读取（本地场景），fallback 到 config.yaml（云端场景）。

代码修改点（集中在数据返回层，其他代码零感知）：
- `provider_manager.py::get_api_key()` - 增加 config fallback（+10 行）
- `wechat/auth.py::_load_token_from_keyring()` - 增加 config fallback（+8 行）
- `sync/sync_config.py`（新增）- 同步 API Key 读取（+20 行）

**本地配置文件**（不含 Key）：
```yaml
llm:
  provider: anthropic
  model: claude-opus-4
  # API Key 在 keyring: api_key_anthropic
```

**云端配置文件**（包含 Key）：
```yaml
llm:
  provider: anthropic
  model: claude-opus-4

# 云端需要的 Key（从本地 keyring 读取后写入）
wechat_token: "wx_token_..."
sync_api_key: "lifeprism_sync_..."
```

**providers.yaml**（云端）：
```yaml
providers:
  - name: anthropic
    env_key: api_key_anthropic
    api_key: "sk-ant-..."  # 新增字段，仅云端需要
```

**理由**：
- 统一逻辑，所有 Key 都用 keyring（本地）
- 云端无 keyring，fallback 到配置文件
- 代码修改最小，只在读取层截断
- 无耦合，其他代码不需要判断"云端 vs 本地"

#### 7. 配置生成与初始化

**本地生成配置**：

前端设置页面增加"生成云端配置"按钮：
1. 后端从 keyring 读取所有 Key（LLM/微信/同步）
2. 生成完整的 `cloud_init.yaml`（包含所有配置和 Key）
3. 保存到 `{lifeprism_data_path}/cloud_init.yaml`
4. 打开文件夹并选中该文件（Windows: `explorer /select`）
5. 提示用户复制到云端的 `{lifeprism_data_path}/cloud_init.yaml`

**生成的配置文件**（完整，包含 Key）：
```yaml
llm:
  provider: anthropic
  model: claude-opus-4

sync:
  enabled: true
  api_key: "lifeprism_sync_..."

wechat_token: "wx_token_..."
monitor_type: none  # 强制覆盖
```

**云端初始化流程**：

`main_agent_only.py` 启动时：
1. 检测 `{lifeprism_data_path}/cloud_init.yaml` 是否存在
2. 如果存在：
   - 读取配置
   - 写入 `config.yaml` 和 `providers.yaml`
   - 删除 `cloud_init.yaml`（不留痕迹）
3. 继续正常启动

**文件路径约定**：
- 文件名固定：`cloud_init.yaml`
- 本地路径：`{lifeprism_data_path}/cloud_init.yaml`
- 云端路径：`{lifeprism_data_path}/cloud_init.yaml`（临时，写入后删除）

**理由**：
- 用户只需复制一个文件
- 配置包含完整信息（含 Key），云端直接使用
- 临时文件立即删除，不留痕迹
- 不需要加密（SSH 已加密，文件立即删除）

#### 8. 云端 CLI 管理

`main_agent_only.py` 支持命令行参数：

**命令列表**：
```bash
# 正常启动（默认）
python -m lifeprism.server.main_agent_only

# 重新初始化配置（API Key 过期时）
python -m lifeprism.server.main_agent_only reinit-config

# 查看当前配置（脱敏显示）
python -m lifeprism.server.main_agent_only show-config

# 测试 LLM 连接（验证 API Key）
python -m lifeprism.server.main_agent_only test-llm
```

**`reinit-config` 行为**：
- 读取 `cloud_init.yaml`
- 写入 `config.yaml` 和 `providers.yaml`
- 删除 `cloud_init.yaml`
- **不自动重启服务**（用户手动 `systemctl restart`）

**理由**：
- 云端没有前端界面，需要 CLI 管理
- API Key 过期后方便重新配置
- 不自动重启，用户有控制权

#### 9. 云端启动校验

`main_agent_only.py` 启动时强制校验：
```python
if config.get("monitor_type") != "none":
    logger.warning("云端 monitor_type 必须为 none，自动修正")
    settings.set("monitor_type", "none")
```

**理由**：
- 防止配置错误（本地配置复制过来时可能包含 `monitor_type: lifeprism`）
- 云端强制禁用 Monitor

#### 10. 消息路由与本地在线判断

**问题**：微信消息群发到本地和云端，需要避免重复回复。

**解决方案**：云端通过心跳机制判断本地是否在线，在线则跳过处理。

**心跳状态管理（纯内存）**：

```python
# 云端 lifeprism/sync/heartbeat_manager.py（新增）
class HeartbeatManager:
    def __init__(self):
        self._last_heartbeat: datetime | None = None
        self._last_event: str | None = None  # 'online' | 'offline'
        self._lock = Lock()
    
    def update_heartbeat(self):
        """更新心跳时间（每次 sync/pull 时调用）"""
        with self._lock:
            self._last_heartbeat = datetime.now()
    
    def set_event(self, event: str):
        """设置生命周期事件（'online' | 'offline'）"""
        with self._lock:
            self._last_event = event
            self._last_heartbeat = datetime.now()
    
    def is_local_online(self) -> bool:
        """判断本地是否在线"""
        with self._lock:
            if self._last_event == "offline":
                return False  # 显式 offline
            if self._last_heartbeat is None:
                return False  # 从未连接
            elapsed = (datetime.now() - self._last_heartbeat).total_seconds()
            return elapsed < 900  # 15 分钟 = 900 秒
```

**心跳来源**：

1. **复用数据同步**：本地每 10 分钟发起 `POST /api/sync/pull`，云端在处理请求开头调用 `heartbeat_manager.update_heartbeat()`
2. **生命周期事件**：本地 FastAPI 启动/关闭时发送 `POST /api/sync/heartbeat {"event": "online|offline"}`

**状态转换**：
```
初始状态（last_heartbeat=None）
  ↓
本地启动 → POST /api/sync/heartbeat {"event": "online"} 
  → [last_event="online", last_heartbeat=T0]
  ↓
每 10 分钟同步 → POST /api/sync/pull 
  → 云端调用 update_heartbeat() 
  → [last_heartbeat=T1]
  ↓
判断：now() - last_heartbeat < 15min → 在线
  ↓
本地关闭 → POST /api/sync/heartbeat {"event": "offline"}
  → [last_event="offline"]
```

**消息路由逻辑**：

```python
# 云端 WeChat Channel
async def on_message_received(self, message):
    if heartbeat_manager.is_local_online():
        logger.info("本地在线，跳过云端处理")
        return  # 本地会处理
    # 本地离线，云端处理
    await self.agent_loop.process(message)
```

**超时设置**：
- 同步间隔：10 分钟
- 超时判断：15 分钟（10 分钟间隔 + 5 分钟容错）
- 异常退出延迟：最长 15 分钟（可接受）

**场景覆盖**：
- ✅ 本地正常运行：每 10 分钟心跳，云端跳过消息处理
- ✅ 本地正常关闭：发送 offline 事件，云端立即接管
- ✅ 本地异常退出：15 分钟后云端自动接管
- ⚠️ 网络分区：极端情况下可能重复回复（概率 < 1%，可接受）

**理由**：
- 纯内存状态管理，零开销（云端服务长期运行，重启后 15 分钟内自动恢复）
- 不需要数据库表（过度设计）
- 复用同步请求作为心跳，节省网络开销

#### 11. 文件同步

**需要同步的目录/文件**：
```python
SYNC_FILES = [
    "agent/",                         # Agent 配置
    "assets/",                        # 资源文件
    "channel/wechat/account.json",   # ← 必须（微信 session_id）
    "diary/",                         # 日记 MD 文件
    "docs/",                          # 用户文档
    "external_files/",                # 外部文件
    "plan/",                          # 计划文件
    "prompts/",                       # 自定义 prompt
    "session/",                       # chat_history JSONL
    "user/",                          # 用户配置
    "workflow/",                      # 工作流配置
]
```

**不同步的目录/文件**：
```python
EXCLUDE_FROM_SYNC = [
    ".schedule_state.json",           # 定时任务状态
    "config/",                        # 配置文件（手动同步）
    "dataset/",                       # 数据集（不走文件同步）
    "debug_logs/",                    # 调试日志
    "screenshots/",                   # 截图
    "channel/wechat/media/",          # 微信媒体文件
]
```

**增量同步**：

```python
def get_changed_files(directory: Path, last_sync_time: datetime) -> list[dict]:
    """获取自上次同步后变更的文件"""
    changed = []
    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        if mtime > last_sync_time:
            content_bytes = gzip.compress(file_path.read_bytes())
            changed.append({
                "path": str(file_path.relative_to(data_path)),
                "content": base64.b64encode(content_bytes).decode(),
                "mtime": mtime.isoformat()
            })
    return changed
```

**冲突解决**：Last-Write-Wins（比较 `mtime`）

**为什么简单策略足够**：
1. 云端 agent-only **不启动 dreaming**（已确认）
2. 文件修改只来自会话（agent 处理消息）
3. 同一时间只有一端的 agent 在工作（本地在线则云端跳过）
4. **不会同时修改同一个文件**

**性能估算**：
- 单个 session JSONL：~10KB
- 10 分钟增量：1-2 个文件，~20KB
- gzip 压缩率：~70%，传输 ~6KB

**关键文件**：`channel/wechat/account.json` 必须同步，包含微信 session_id，保证云端对话历史连贯。

#### 12. 云端与本地 API 区分

**问题**：当前 `sync_cloud_api.py` 同时被本地和云端注册，职责混乱。

**解决方案**：明确区分云端提供的 API 和本地提供的 API。

**云端 API**（`main_agent_only.py` 提供，端口 8101）：

云端启动轻量 FastAPI 服务，仅同步 API：

```python
# main_agent_only.py
async def _run_agent_and_api():
    # 1. 创建 FastAPI 实例（仅同步 API）
    from fastapi import FastAPI
    from lifeprism.server.api import sync_cloud_router
    
    app = FastAPI(title="LifePrism Agent Only")
    app.include_router(sync_cloud_router)  # 仅云端同步 API
    
    # 2. 启动 FastAPI（后台任务）
    config = uvicorn.Config(app, host="0.0.0.0", port=8101, log_level="info")
    server = uvicorn.Server(config)
    api_task = asyncio.create_task(server.serve())
    
    # 3. 启动 Agent Loop + WeChat Channel
    init_database_full()
    loop_task, wechat_channel = await start_agent_and_channel()
    
    # 4. 等待终止信号
    # ...
```

云端提供的端点：
```
POST /api/sync/pull          # 本地调用：从云端拉取数据
POST /api/sync/push          # 本地调用：推送数据到云端
POST /api/sync/pull-files    # 本地调用：拉取文件
POST /api/sync/push-files    # 本地调用：推送文件
POST /api/sync/heartbeat     # 本地调用：发送心跳/生命周期事件
```

**本地 API**（`main.py` 提供，端口默认）：

本地提供同步状态查询和配置生成：

```python
# main.py
app.include_router(sync_router, prefix="/api/v2")       # ActivityWatch 同步
# app.include_router(sync_cloud_router)  # ← 删除，这是云端提供的
app.include_router(sync_status_router)   # 本地同步状态查询
app.include_router(cloud_config_router)  # 云端配置生成
```

本地提供的端点：
```
GET /api/sync/status                    # 查询同步状态
POST /api/sync/trigger                  # 手动触发同步
POST /api/sync/generate-cloud-config    # 生成云端配置
```

本地调用云端 API：
```python
# SyncClient 通过 httpx 调用云端
httpx.post(f"{remote_url}/api/sync/pull", ...)
httpx.post(f"{remote_url}/api/sync/push", ...)
```

**理由**：
- 云端必须提供 HTTP API（否则本地无法调用 pull/push）
- 本地不应提供云端 API（职责混乱）
- 明确区分：云端提供数据，本地提供状态查询

### P2 Testing Decisions

#### 1. 同步逻辑测试
**测试文件**：`test/integration/test_data_sync.py`

**测试用例**：
- `test_pull_inserts_new_records`：拉取时插入本地不存在的记录
- `test_pull_updates_unmodified_records`：拉取时覆盖本地未修改的记录
- `test_pull_respects_local_changes`：拉取时保留本地更新的记录
- `test_push_sends_local_changes`：推送本地变更到云端
- `test_sync_updates_last_sync_time_only_on_success`：只有全部成功才更新同步时间
- `test_sync_handles_network_failure`：网络失败时的重试逻辑
- `test_pull_batched_large_dataset`：分批拉取大数据集
- `test_dynamic_table_sync`：动态表（custom_records_{slug}）同步

**Mock 策略**：
- Mock HTTP 请求（`httpx.AsyncClient`）
- 使用临时数据库文件
- Mock 时间戳（避免测试依赖实际时间）

#### 2. 配置生成测试
**测试文件**：`test/integration/test_cloud_config_generator.py`

**测试用例**：
- `test_generate_includes_all_keys`：生成的配置包含所有 Key
- `test_generate_reads_from_keyring`：从 keyring 读取 Key
- `test_generate_saves_to_correct_path`：保存到正确路径
- `test_cloud_init_contains_monitor_override`：强制覆盖 `monitor_type: none`

#### 3. 云端初始化测试
**测试文件**：`test/integration/test_cloud_initializer.py`

**测试用例**：
- `test_initializer_detects_cloud_init`：检测 `cloud_init.yaml`
- `test_initializer_writes_config`：写入 `config.yaml`
- `test_initializer_deletes_temp_file`：删除临时文件
- `test_reinit_config_command`：CLI `reinit-config` 命令

#### 4. Key 读取 fallback 测试
**测试文件**：`test/unit/config/test_key_fallback.py`

**测试用例**：
- `test_get_api_key_prefers_keyring`：优先从 keyring 读取
- `test_get_api_key_falls_back_to_config`：keyring 失败时 fallback
- `test_wechat_token_fallback`：微信 Token fallback
- `test_sync_api_key_fallback`：同步 API Key fallback

#### 5. 心跳状态管理测试
**测试文件**：`test/unit/sync/test_heartbeat_manager.py`

**测试用例**：
- `test_is_local_online_initial_state`：初始状态为离线
- `test_is_local_online_after_heartbeat`：心跳后在线
- `test_is_local_online_timeout`：超时后离线
- `test_explicit_offline_event`：显式 offline 事件立即生效
- `test_thread_safety`：多线程安全

#### 6. 文件同步测试
**测试文件**：`test/integration/test_file_sync.py`

**测试用例**：
- `test_pull_files_incremental`：增量拉取文件
- `test_push_files_changed_only`：只推送变更文件
- `test_file_conflict_lww`：文件冲突 Last-Write-Wins
- `test_sync_account_json`：同步 channel/wechat/account.json
- `test_exclude_patterns`：排除指定目录/文件

#### 7. 消息路由测试
**测试文件**：`test/integration/test_message_routing.py`

**测试用例**：
- `test_cloud_skips_when_local_online`：本地在线时云端跳过
- `test_cloud_processes_when_local_offline`：本地离线时云端处理
- `test_cloud_takeover_after_timeout`：超时后云端接管
- `test_explicit_offline_takeover`：显式 offline 后云端接管

#### 8. 云端 API 启动测试
**测试文件**：`test/integration/test_agent_only_api.py`

**测试用例**：
- `test_agent_only_starts_fastapi`：agent-only 启动 FastAPI
- `test_sync_endpoints_available`：同步端点可访问
- `test_heartbeat_endpoint_available`：心跳端点可访问
- `test_agent_loop_starts`：Agent Loop 正常启动

### P2 Out of Scope

以下内容不在 P2 实现范围内：

- 冲突仲裁 UI（记录冲突表，用户手动选择）
- 同步进度条（前端实时显示同步状态）
- 增量同步优化（Delta encoding）
- 数据库静态加密（SQLCipher）
- Web Demo 演示数据生成（AI 生成假数据）
- Docker 容器部署（P3 考虑）
- 文件同步的行级合并（JSONL 文件不做行级 diff）
- 本地在线状态持久化（纯内存管理，服务重启 15 分钟内自动恢复）
- IP 白名单、请求签名（HMAC-SHA256）等高级安全机制（HTTPS + API Key 已足够）

### P2 验收标准

#### 功能验收
- ✅ Windows 启动时自动同步到云端
- ✅ 云端记录的数据能同步回 Windows
- ✅ 前端能生成云端配置文件并打开文件夹
- ✅ 云端 CLI 命令正常工作（`reinit-config`、`show-config`、`test-llm`）
- ✅ API Key 过期后能通过 CLI 重新配置
- ✅ 本地在线时微信消息由本地处理，本地离线时由云端处理
- ✅ 本地正常关闭后云端立即接管微信消息
- ✅ 本地异常退出后云端在 15 分钟内接管微信消息
- ✅ 云端对话使用与本地相同的 session_id（通过同步 channel/wechat/account.json）
- ✅ 动态表（custom_records_{slug}）能正确同步

#### 技术验收
- ✅ 所有 31 张静态表 + 动态表能正确同步
- ✅ 文件同步覆盖所有必需目录（session/、channel/wechat/account.json 等）
- ✅ 增量查询使用索引，耗时 < 200ms（31 个表）
- ✅ 首次同步分批传输，总耗时 < 60 秒
- ✅ Key 读取 fallback 逻辑正常工作
- ✅ 代码修改集中在读取层，无耦合
- ✅ 心跳机制线程安全
- ✅ 云端 agent-only 启动 FastAPI 服务（端口 8101）
- ✅ 本地 main.py 移除 sync_cloud_router 注册
- ✅ 同步测试全部通过

#### 安全验收
- ✅ HTTPS 证书配置正确
- ✅ API Key 认证生效
- ✅ 云端配置文件权限 600

---

## Out of Scope

以下内容**不在 P1/P2 实现范围内**：

### P3 - 未来优化
- Docker 容器部署
- Web Demo 演示数据生成（AI 生成假数据库）
- 同步进度条（前端实时显示）
- 冲突仲裁 UI
- 数据库静态加密（SQLCipher）

### 不考虑
- Linux 上实现 Monitor 模块（明确不做）
- 分布式部署（多实例负载均衡）
- 数据库水平扩展
- 实时同步（10 分钟已足够）

---

## Further Notes

### 风险与缓解

**风险 1**：`pywin32` 可能在 Linux 上无法安装

**缓解**：
- 当前假设 Linux 上能安装 `pywin32`（只是不使用）
- 如果实际部署时发现无法安装，使用 `platform_system` 标记隔离平台依赖
- 不影响 Windows 打包流程

**风险 2**：SSE 流式响应可能因 Nginx 配置不当导致卡顿

**缓解**：
- 文档明确说明需要 `proxy_buffering off`
- 提供测试方法验证 SSE 是否正常工作

### 部署文档要求

需要新增以下文档（`docs/deployment/`）：

1. **Linux 部署指南**（`linux-deployment-guide.md`）
   - 系统要求（Ubuntu 20.04+、Python 3.10+）
   - 依赖安装步骤
   - 三种模式的启动命令
   - 环境变量配置说明
   - 常见问题排查

2. **Nginx 配置说明**（`nginx-setup.md`）
   - 后端端口：8101
   - 需要代理的路径：`/api/*`
   - SSE 支持要求：`proxy_buffering off`
   - 前端静态文件位置


---

## 验收标准

### 功能验收
- ✅ Linux 服务器上能成功启动 Web Demo，浏览器访问正常
- ✅ Linux 服务器上能成功启动 Agent Only，微信对话正常
- ✅ Windows 桌面版功能不受影响，Monitor 正常工作
- ✅ Agent 工具在 Linux 上正常工作（查询、记录）

### 技术验收
- ✅ 所有新增测试通过
- ✅ CI 在 Linux 环境下通过
- ✅ 依赖分层正确，无多余依赖
- ✅ 日志输出正常，无报错或异常 warning

### 文档验收
- ✅ 部署文档完整，按文档能成功部署
- ✅ Nginx 配置示例经过验证
- ✅ 启动脚本能正常运行
- ✅ 环境变量说明清晰

---

**优先级**：P1  
**预计工作量**：3-5 天  
**依赖**：无  
**阻塞**：数据同步功能（P2）
