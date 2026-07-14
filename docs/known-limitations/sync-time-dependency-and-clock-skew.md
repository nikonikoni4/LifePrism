---
version: 1.0
created_at: 2026-07-14
updated_at: 2026-07-14
last_updated: 创建文档初稿
abstract: 数据库同步完全依赖客户端 last_sync_time 判断增量范围，主备模式下存在时钟偏差导致数据丢失的极端风险。记录当前主备使用前提、时间统一性确认、时钟偏差风险评估。
---

# 同步时间依赖与主备时钟偏差限制

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题描述

### 同步机制概述

当前数据库同步采用**客户端驱动、完全依赖 `last_sync_time`** 的增量同步策略：

1. **Pull（远程拉取）**：客户端将本地的 `last_sync_time` 通过 POST body 发送给云端，云端执行 `SELECT * FROM {table} WHERE updated_at > ?`（`?` = 客户端的 `last_sync_time`），返回增量变更记录
2. **Push（本地推送）**：客户端使用本地的 `last_sync_time` 执行 `query_incremental()`（即 `WHERE updated_at > last_sync_time`），将本地变更推送到云端
3. **LWW 冲突解决**：Pull 时在内存中比较远程和本地的 `updated_at` 字符串（均为 UTC ISO 8601），谁更晚谁保留；`updated_at` 相等时跳过

**关键特征**：
- 云端**无状态**：不存储任何同步状态（无 `sync_state` 表），`last_sync_time` 仅存储在客户端 `config.yaml` 中
- Pull 和 Push 都使用**同一个客户端本地** `last_sync_time`
- 时间比较基于**字符串比较**（UTC ISO 8601 格式天然支持字典序 = 时间序）

代码路径：
- `lifeprism/sync/sync_client.py` — `sync_once()` (L199-232), `pull_from_remote()` (L234-356), `push_to_remote()` (L358-407)
- `lifeprism/repository/sync_repository.py` — `query_incremental()` (L223-292)
- `lifeprism/server/api/sync_cloud_api.py` — `sync_pull()` (L147-204), `sync_push()` (L207-239)

### 时间统一性确认

**所有时间均使用 UTC ISO 8601 格式，已确认无需修改：**

| 组件 | 时间生成/解析 | 格式 |
|------|-------------|------|
| `last_sync_time` 生成 | `datetime.now(timezone.utc).isoformat()` | `2026-07-14T10:30:00.123456+00:00` |
| 数据库 `updated_at` | `datetime('now')` (SQLite) 或 `datetime.now(timezone.utc).isoformat()` | 同上 |
| 客户端 `fromisoformat` 解析 | Python 3.11+ 原生支持 UTC 后缀，返回 aware datetime | — |
| 服务端 `parse_iso_to_aware` | 对 naive 字符串补充 `tzinfo=UTC`（不转换时间值） | — |
| 增量查询 `WHERE updated_at > ?` | 字符串比较，双方均为 UTC ISO 8601 | 字典序 = 时间序 ✅ |
| LWW `updated_at` 比较 | `str(remote_updated_at) > str(local_updated_at)` | 字符串比较 |

**结论**：当前时间处理是正确的，不存在本地时间混入的问题。

## 影响范围

- **严重程度**：低（极端情况下才触发）
- **影响范围**：数据库同步（30 张静态表 + 动态自定义记录表）+ 文件同步
- **触发条件**：主备切换场景下，本机与云端时钟偏差超过数据写入间隔

## 根本前提：主备使用模式

当前同步机制建立在以下**根本前提**之上：

> **本机在使用时，云端不能使用。** 云端通过心跳检测（`heartbeat_manager`）判断本机是否在线，当检测到本机连接时，云端 Agent 不会处理微信消息。由于云端所有数据处理都经过 Agent，因此按设计，本机存在时云端理论上不会产生新数据。

**如果这个前提改变（如引入手机端等多客户端场景），数据同步机制需要重做。** 详见 `docs/adr/2026-07-14-sync-full-sync-strategy.md` 中关于方案一"多客户端静默数据丢失"的分析。

## 时钟偏差风险

### 风险场景

由于 Pull 和 Push 都使用**客户端本地** `last_sync_time`，在以下极端场景下可能出现数据丢失：

1. 本机最后一次同步，`last_sync_time` 更新为 `12:00 UTC`（本机时钟）
2. 本机关闭，云端接管
3. 云端时钟比本机慢 1 小时（显示 `11:00 UTC`）
4. 云端在 `11:30 UTC`（云端时钟）创建了一条新记录，`updated_at` = `11:30 UTC`
5. 本机重新上线，Pull 请求发送 `last_sync_time = 12:00 UTC`
6. 云端执行 `WHERE updated_at > '12:00 UTC'` → **不返回 `11:30 UTC` 的记录**
7. **该记录永久丢失**（不会被同步到本机）

### 为什么实际风险低

1. **NTP 时间同步**：现代操作系统默认启用 NTP，云端服务器和本机通常与同一 NTP 池同步，偏差通常在**毫秒到秒级**
2. **主备切换有时间窗口**：本机关闭 → 云端检测到离线（心跳超时）→ 云端 Agent 接管，这个过程本身有几秒到几分钟的延迟，远大于 NTP 偏差
3. **时钟偏差方向性**：即使有偏差，只有当云端时钟**慢于**本机时钟时才会丢失数据（云端记录的时间 < 本机 `last_sync_time`）。如果云端时钟**快于**本机，数据仍能被正确拉取
4. **实际偏差量级**：正常运行的服务器和 PC，NTP 同步下的时钟偏差通常在 **±1 秒以内**，极限情况（NTP 故障、虚拟机暂停恢复）可能达到数分钟，但几乎不可能达到 1 小时

### 量化分析

| 时钟偏差 | 丢失风险 | 实际可能性 |
|---------|---------|-----------|
| < 1 秒 | 几乎为零 | NTP 正常工作的默认状态 |
| 1–30 秒 | 极低（需在偏差窗口内恰好有数据写入） | NTP 临时故障 |
| 1–5 分钟 | 低 | NTP 长时间故障、虚拟机暂停恢复 |
| > 1 小时 | 中等 | 手动修改系统时间、严重 NTP 配置错误 |

**实际结论**：在 NTP 正常工作的前提下，本机与云端数据库时间不会差太多，差几秒到几分钟都是可接受的，不会造成实际的数据丢失问题。

## 相关文档

- `docs/adr/2026-07-14-sync-full-sync-strategy.md` — 全量同步策略决策（方案 B：重置同步进度按钮），包含 LWW 相等跳过决策
- `docs/coding-rules/time-handling-rules.md` 第 6 节 — 数据同步时间规则
- `docs/adr/2026-07-12-migrate-to-utc-timezone.md` — UTC 时区迁移决策
- `.scratch/linux-deployment-discussion/issues-p2/05-sync-client-basic.md` — 同步客户端设计参考

## 注意事项

1. **不要引入本地时间**：所有同步相关时间（`last_sync_time`、`updated_at`）必须保持 UTC ISO 8601，禁止使用 `datetime.now()` 无时区参数
2. **前提变更需重做同步**：如果引入多客户端（手机端等）或改变主备使用模式，当前同步机制需要重新设计（引入 `client_id`、云端状态表等）
3. **重置同步进度是兜底方案**：如果怀疑有时钟偏差导致的数据不一致，可通过"重置同步进度"按钮触发全量同步来修复（`POST /api/sync/reset-sync-progress`）
4. **`updated_at` 字符串比较依赖格式一致性**：LWW 使用字符串比较，依赖 UTC ISO 8601 格式的字典序等于时间序。如果未来改变时间格式，LWW 逻辑必须同步修改
