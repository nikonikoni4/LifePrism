# run_mode 写入 yaml 导致不同入口模式守卫失效

**创建时间**: 2026-07-09
**严重程度**: 中（影响模式守卫行为，但不直接导致崩溃）
**影响范围**: 所有部署模式（full / web_demo / agent_only）

---

## 问题描述

`run_mode` 被定义在 `SettingsManager.DEFAULTS` 字典中，首次启动时写入 `config.yaml`，之后持久化不更新。三个部署入口（`main.py` / `main_web_demo.py` / `main_agent_only.py`）都没有显式设置当前运行模式，完全依赖 yaml 中的值。

结果：yaml 中始终是首次启动时的默认值 `"full"`，即使切换到 `web_demo` 或 `agent_only` 入口，运行时读取到的 `run_mode` 仍然是 `"full"`。

## 影响

以下 4 处模式守卫在切换入口后**全部失效**：

| 位置 | 守卫逻辑 | 失效后果 |
|------|---------|---------|
| `schedule_service.py` | `run_mode != "full"` 跳过定时任务 | `web_demo` 仍注册定时任务（依赖不存在的 Monitor 数据） |
| `sync_service.py`（增量同步） | `run_mode != "full"` 拒绝同步 | `web_demo` 仍允许同步（无意义操作） |
| `sync_service.py`（时间范围同步） | `run_mode != "full"` 拒绝同步 | `web_demo` 仍允许同步 |
| `wechat/channel.py` | `run_mode == "agent_only"` 云端消息路由 | `agent_only` 模式不执行心跳路由判断 |

## 根因

架构问题：`run_mode` 是**运行时配置**（每次启动由入口文件决定），但被放在了**持久化配置** `DEFAULTS` 中。两类配置职责混淆。

## 修复方案

在 `SettingsManager` 中引入 `_runtime_config` 字典，与持久化的 `_config` 分离：

1. 从 `DEFAULTS` 中移除 `run_mode`
2. 新增 `_runtime_config` 字典和 `set_runtime_config()` 方法
3. `run_mode` 属性改为从 `_runtime_config` 读取，默认 `"full"`
4. 三个入口文件在 import 完成后注入对应值：
   - `main.py` → `"full"`
   - `main_web_demo.py` → `"web_demo"`
   - `main_agent_only.py` → `"agent_only"`
5. 删除 `LIFEPRISM_RUN_MODE` 环境变量（部署脚本 + 旧 `run_mode` 属性中的读取逻辑）

## 架构收益

| | `_config`（持久化） | `_runtime_config`（运行时） |
|---|---|---|
| 存储 | yaml 文件 | 仅内存 |
| 生命周期 | 跨重启持久化 | 每次启动重新设置 |
| 内容 | 用户配置（provider、model 等） | 运行模式（run_mode） |

## 相关

- commit: `0084ce1` fix: run_mode 改为运行时配置，避免写入 yaml 配置文件
- `.scratch/linux-deployment-discussion/issues/12-run-mode-sync-guard.md`: 原始 issue 设计文档
