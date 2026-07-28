---
version: 1.1
created_at: 2026-07-16
updated_at: 2026-07-26
last_updated: v1.1 加入 SSH 隧道子模块（无域名场景安全传输），与 core / files 并列为第三个子 spec
abstract: 数据同步模块总览，定义模块整体职责、子模块分层架构、依赖规则和子 spec 索引。原 spec 因内容超过 500 行拆分为 data-sync-core-spec 和 data-sync-files-spec；2026-07-26 新增 data-sync-ssh-tunnel-spec 覆盖 SSH 隧道连接方式。
---

# 数据同步模块总览

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 从 `2026-07-11-data-sync-spec.md` 拆分，创建总览索引 |
| 1.1 | 加入 SSH 隧道子模块（data-sync-ssh-tunnel-spec），覆盖无域名场景下的安全传输通道 |

## Overview

**业务问题**：Windows 本地和 Linux 云端各自独立运行。用户需要通过微信（Linux Agent）记录数据后能在本地查看，也需要云端 Agent 能访问本地采集的 Monitor 数据。两端数据需要保持一致，且避免微信消息被双端重复回复。

**核心职责**：
- **数据库双向同步**：30 张静态表 + 动态 custom 表，基于 `updated_at` 字段的增量同步，含动态表定义对比与双向建表
- **文件双向同步**：per-file version tracking（parent_hash + current_hash）替代纯 LWW mtime，三阶段 API 协议（check → fetch/push → verify/commit）
- **SSH 隧道（可选）**：无域名场景下的安全传输通道，通过 SSH 加密的本地端口转发替代 HTTPS
- **心跳与消息路由**：纯内存心跳状态管理，本地离线时云端接管微信消息处理
- **云端配置初始化**：本地生成 cloud_init.yaml → 云端消费写入 config.yaml + providers.yaml
- **认证安全**：API Key 认证 + HTTPS / SSH 加密传输

## 子模块架构

```
数据同步模块
├─ 数据库同步 (data-sync-core-spec)
│   ├─ 30 张静态表增量 Pull/Push
│   ├─ 动态表定义对比（slug 集合差集 → 双向建表）
│   └─ LWW 冲突解决（三类表分类写入）
├─ 文件同步 (data-sync-files-spec)
│   ├─ per-file version tracking（parent_hash + current_hash）
│   ├─ 三阶段 API 协议（check / fetch / push / verify / commit）
│   ├─ 冲突分流（MD → AI 合并，JSONL → LWW）
│   └─ 同步白名单（对齐 Agent 工具白名单）
├─ SSH 隧道 (data-sync-ssh-tunnel-spec) [可选]
│   ├─ SSH 加密的本地端口转发（asyncssh）
│   ├─ 密钥自动生成与 keyring 存储
│   ├─ 状态机管理 + 心跳保活 + 指数退避重连
│   └─ remote_url 拦截（_read_remote_url 统一入口）
├─ 心跳管理
│   └─ 纯内存状态（15 分钟超时，offline 立即生效）
├─ 消息路由
│   └─ 本地在线 → 云端跳过；本地离线 → 云端接管
└─ 配置桥接
    ├─ 本地 CloudConfigGenerator（生成 cloud_init.yaml）
    └─ 云端 CloudInitializer（消费 → config.yaml + providers.yaml）
```

## 依赖规则

- **数据库同步** 不依赖文件同步（可以独立工作）
- **文件同步** 在数据库同步之后执行（`sync_once` 顺序）
- **SSH 隧道** 是可选的传输层加密方案，不依赖数据库同步或文件同步，但 SSH 模式下两者都通过隧道传输
- **心跳** 通过数据库 Pull 请求隐式更新（`/api/sync/pull` 开头调用 `update_heartbeat()`）
- **消息路由** 独立于同步周期（WeChat Channel 收到消息时即时判断）
- **配置桥接** 是同步的前置条件（云端必须先完成配置初始化）

## 子 Spec 索引

| Spec | 职责 | 文档 |
|------|------|------|
| 数据库同步 + 动态表 + 心跳路由 | 静态表增量同步、动态表定义对比与建表、LWW 冲突解决、心跳状态管理、消息路由、云端配置初始化 | [data-sync-core-spec](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-core-spec.md) |
| 文件同步 | per-file version tracking、三阶段 API 协议、冲突分流（AI 合并 / LWW）、同步白名单 | [data-sync-files-spec](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-files-spec.md) |
| SSH 隧道 | 无域名场景下的安全传输通道、SSH 密钥管理、隧道状态机与重连、remote_url 拦截、SyncClient SSH 集成 | [data-sync-ssh-tunnel-spec](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-26-data-sync-ssh-tunnel-spec.md) |

## 跨层交互典型场景

1. **首次云端部署**：本地生成 cloud_init.yaml → 云端 CloudInitializer 消费 → 全量同步（清空 last_sync_time → pull 全部数据 + 同步文件 + 动态表重建）
2. **日常使用**：启动时 sync_once（数据库 Pull/Push → 文件同步）→ 定时 10 分钟循环
3. **动态表差异**：本地拉取云端定义 → slug 对比 → 本地建表 + 云端重建 → pull/push 数据
4. **文件冲突**：本地 push → 云端 check（hash 检测到冲突）→ 本地 fetch → AI 合并（MD）或 LWW（JSONL）→ push 回云端
5. **SSH 隧道模式**：切换到 SSH 模式 → 自动生成密钥 → 部署公钥到云端 → SyncClient 启动隧道 → 所有同步流量走 localhost → 隧道断开自动重连

## Out of Scope

本模块不覆盖以下内容，请参考相应文档：

- **Config 模块配置管理**：[`docs/specs/2026-07-06-config-settings-spec.md`](./2026-07-06-config-settings-spec.md) — SettingsManager、ProviderManager、双层命名体系
- **Agent 执行引擎**：[`docs/specs/2026-07-06-llm-agent-spec.md`](./2026-07-06-llm-agent-spec.md) — AgentLoop、Tool 注册
- **ActivityWatch 数据同步**：[`docs/specs/2026-04-16-classify-spec.md`](./2026-04-16-classify-spec.md) — SyncService 分类管线

## 相关文档

- **ADR 时间线**：[`docs/adr/2026-07-27-sync-system-timeline.md`](../adr/2026-07-27-sync-system-timeline.md)
- **数据流 - 核心同步**：[`docs/flows/2026-07-11-data-sync-flow.md`](../flows/2026-07-11-data-sync-flow.md)
- **数据流 - SSH 隧道生命周期**：[`docs/flows/2026-07-26-ssh-tunnel-flow.md`](../flows/2026-07-26-ssh-tunnel-flow.md)
- **SSH 隧道已知限制**：[`docs/known-limitations/ssh-tunnel-limitations.md`](../known-limitations/ssh-tunnel-limitations.md)
- **remote_url 访问规则**：[`docs/coding-rules/sync-remote-url-access-rules.md`](../coding-rules/sync-remote-url-access-rules.md)
- **已知限制**：[`docs/known-limitations/index.md`](../known-limitations/index.md)
- **技术债**：[`docs/technical-debt/index.md`](../technical-debt/index.md)
- **历史 Bug**：[`docs/history-bugs/index.md`](../history-bugs/index.md)
