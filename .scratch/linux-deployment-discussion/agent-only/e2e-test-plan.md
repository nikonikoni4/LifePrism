# Agent-Only 数据同步端到端测试方案

**创建时间**: 2026-07-09
**状态**: 已完成
**测试类型**: 端到端 (E2E) 本地模拟测试
**测试结果**: **42/42 全部通过**

---

## 1. 测试架构

### 1.1 角色分配

| 角色 | 代码路径 | 运行模式 | 数据目录 | 端口 |
|------|---------|---------|---------|------|
| **本地 (Local)** | `d:\desktop\软件开发\LifeWatch-AI` | SyncClient (主仓库) | `localData/dataset/lifewatch_ai.db` | N/A (客户端) |
| **云端 (Cloud)** | `d:\desktop\软件开发\LifeWatch-AI\explore\LifePrism` | `test_sync_server.py` (轻量 FastAPI) | `explore\LifePrism\localData\dataset\lifewatch_ai.db` | **8102** |

### 1.2 网络拓扑

```
本地 SyncClient (httpx)
    ↓ POST /api/sync/pull
    ↓ POST /api/sync/push
    ↓ POST /api/sync/pull-files
    ↓ POST /api/sync/push-files
    ↓ POST /api/sync/heartbeat
云端 FastAPI (uvicorn, port=8102)
    → SyncRepository (SQLite)
    → HeartbeatManager (内存)
```

### 1.3 API Key

- **同步 API Key**: `test_heartbeat_key_abc123xyz` (已在 cloud_init.yaml 和本地 config.yaml 中配置)
- **认证方式**: `Authorization: Bearer {api_key}` Header

---

## 2. 环境准备

### 2.1 云端端口修改

修改 `explore\LifePrism\lifeprism\server\main_agent_only.py`:
- `port=8101` -> `port=8102` (2 处: uvicorn.Config 和日志输出)

### 2.2 云端测试服务器

由于 agent-only 模式启动 Agent Loop 需要完整的 LLM 依赖链，测试中使用 `test_sync_server.py` 作为云端服务：
- 使用 `importlib` 直接加载 `sync_cloud_api` 模块，绕过 `__init__.py` 的重导入链
- 包含完整的 CloudInitializer + 数据库初始化 + FastAPI 同步 API
- 不启动 Agent Loop 和 WeChat Channel，确保同步 API 稳定运行
- 在 CloudInitializer 完成后调用 `settings.reload()` 重新加载配置

### 2.3 云端 cloud_init.yaml 初始化

- 用户已将 `cloud_init.yaml` 放置在 `explore\LifePrism\localData\cloud_init.yaml`
- 修复: `llm.provider` 从显示名称 `Xiaomi MIMO` 改为 provider ID `xiaomi_mimo_token_plan`（与 providers 列表中的 name 匹配）
- 云端首次启动时，`CloudInitializer` 读取并写入 `config.yaml` 和 `providers.yaml`，然后删除 `cloud_init.yaml`

### 2.4 本地配置

在本地 `config.yaml` 中添加同步配置:
```yaml
sync_api_key: test_heartbeat_key_abc123xyz
sync.remote_url: http://localhost:8102
sync.last_sync_time: ''
```

---

## 3. 测试用例与结果

### TC-01: 云端服务启动 (7/7 PASS)

**步骤**:
1. 修改云端端口为 8102
2. 启动 `test_sync_server.py`
3. 等待启动完成

**验证结果**:
- [x] cloud_init.yaml 已被删除
- [x] config.yaml 存在
- [x] config.yaml 包含 sync_api_key
- [x] config.yaml monitor_type 为 none
- [x] config.yaml 包含 wechat_token
- [x] providers.yaml 包含 xiaomi_mimo_token_plan 的 api_key
- [x] FastAPI 8102 端口可访问

### TC-02: API Key 认证 (5/5 PASS)

**验证结果**:
- [x] 无 Authorization Header -> 422 INVALID_SYNC_API_KEY
- [x] 错误 API Key -> 422 INVALID_SYNC_API_KEY
- [x] 正确 API Key -> 200
- [x] 响应包含 changes 字段
- [x] 响应包含 sync_time 字段

### TC-03: 心跳机制 (5/5 PASS)

**验证结果**:
- [x] heartbeat online -> 200, server_time 返回
- [x] online 响应包含 server_time
- [x] heartbeat ping -> 200
- [x] heartbeat offline -> 200
- [x] 无效事件 -> 422

### TC-04: 数据库 Pull 同步 (5/5 PASS)

**验证结果**:
- [x] Pull 后本地出现云端记录 (mood_entries)
- [x] mood_type_id 正确
- [x] score 正确
- [x] content 正确
- [x] 多表批量拉取: category 同步成功

### TC-05: 数据库 Push 同步 (4/4 PASS)

**验证结果**:
- [x] Push 后云端出现本地记录 (mood_entries)
- [x] mood_type_id 正确
- [x] score 正确
- [x] content 正确

### TC-06: 整体同步 sync_once (4/4 PASS)

**验证结果**:
- [x] sync_once 执行成功
- [x] last_sync_time 已更新 (2026-07-09T07:41:57.919554+00:00)
- [x] sync_once: 云端记录同步到本地
- [x] sync_once: 本地记录同步到云端

### TC-07: 文件同步 (4/4 PASS)

**验证结果**:
- [x] Push: 云端出现本地文件 (session/ 目录)
- [x] Push: 文件内容一致
- [x] Pull: 本地出现云端文件
- [x] Pull: 文件内容一致

### TC-08: LWW 冲突解决 (2/2 PASS)

**验证结果**:
- [x] LWW (本地未修改): 云端覆盖本地 (last_sync_time="" 时本地视为未修改)
- [x] LWW (本地已修改且更新): 保留本地数据 (本地 updated_at > 云端 updated_at)

### TC-09: 原子性保证 (4/4 PASS)

**验证结果**:
- [x] 同步失败正确抛异常 (ConnectError)
- [x] 失败后 last_sync_time 未更新
- [x] sync_once 错误 URL 正确抛异常
- [x] sync_once 失败后 last_sync_time 未更新

### TC-10: 并发安全 (2/2 PASS)

**验证结果**:
- [x] 同步中时 try_start_sync() 返回 False
- [x] 空闲时 try_start_sync() 返回 True

---

## 4. 测试总结

### 4.1 总体结果

| 测试阶段 | 测试用例 | 通过数 | 状态 |
|---------|---------|-------|------|
| 环境验证 | TC-01 | 7/7 | PASS |
| 连通性 | TC-02 + TC-03 | 10/10 | PASS |
| 数据库同步 | TC-04 + TC-05 + TC-06 | 13/13 | PASS |
| 文件同步 | TC-07 | 4/4 | PASS |
| LWW 冲突 | TC-08 | 2/2 | PASS |
| 原子性 | TC-09 | 4/4 | PASS |
| 并发安全 | TC-10 | 2/2 | PASS |
| **总计** | **10 个用例** | **42/42** | **全部通过** |

### 4.2 发现的问题与修复

1. **cloud_init.yaml provider 名称不匹配**: `llm.provider` 使用显示名称 `Xiaomi MIMO`，但 providers 列表中 name 是 provider ID。修复: 改为 `xiaomi_mimo_token_plan`
2. **settings 单例未重新加载**: `CloudInitializer` 写入 config.yaml 后，`settings` 单例仍持有旧配置。修复: 在 `CloudInitializer.initialize()` 后调用 `settings.reload()`
3. **API 模块导入链过重**: `lifeprism.server.api.__init__.py` 导入所有路由，触发大量 LLM 依赖。修复: 使用 `importlib` 直接加载 `sync_cloud_api` 模块

### 4.3 测试覆盖的功能

- cloud_init.yaml 原子初始化 (消费 -> 写入 -> 删除)
- API Key 认证 (无/错误/正确)
- 心跳机制 (online/ping/offline/无效事件)
- 数据库 Pull 同步 (单表 + 多表批量)
- 数据库 Push 同步 (增量推送)
- 整体 sync_once (数据库 + 文件 + last_sync_time 更新)
- 文件同步 (推送 + 拉取 + 内容一致性)
- LWW 冲突解决 (本地未修改 -> 覆盖, 本地已修改 -> 保留)
- 原子性保证 (失败时 last_sync_time 不更新)
- 并发安全 (try_start_sync 锁机制)

---

## 5. 测试脚本

测试脚本位于临时工作目录:
- `test_connectivity.py` - 连通性测试 (TC-01, TC-02, TC-03)
- `test_db_sync.py` - 数据库同步测试 (TC-04, TC-05, TC-06)
- `test_advanced.py` - 高级测试 (TC-07, TC-08, TC-09, TC-10)

云端测试服务器:
- `explore\LifePrism\test_sync_server.py` - 轻量 FastAPI 同步服务
