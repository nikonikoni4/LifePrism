---
version: 1.0
created_at: 2026-04-24
updated_at: 2026-04-24
last_updated: 创建 usage_service 切换到 tokens_usage_store 的实施计划
abstract: 将 usage_service 的 token 统计来源从 server_lw_data_provider 迁移到 lifeprism.storage.tokens_usage_store，优先使用 query_tokens_usage 通用方法并在 service 层完成聚合。
title: usage_service 切换到 tokens_usage_store 实施计划
status: active
related_spec:
---

# Usage Service Tokens Store Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `usage_service.py` 的统计数据来源替换为 `lifeprism.storage.tokens_usage_store`，不修改 `tokens_usage_store` 既有方法语义。  
**Architecture:** 在 `usage_service` 内通过 `tokens_usage_store.query_tokens_usage()` 拉取明细数据，并以私有聚合函数复刻旧接口输出结构（按日、按 mode、全量汇总），保持返回 schema 与价格计算逻辑不变。  
**Tech Stack:** Python, Storage Provider (`QueryOptions` + `TokensUsageProvider`), Pydantic schema

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 plan 初稿 |

### Task 1: 替换数据源依赖并搭建查询适配

**Files:**
- Modify: `lifeprism/server/services/usage_service.py`

**Step 1: 写一个最小回归测试（或已有测试定位）**
- 目标：覆盖 `get_usage_stats(date)` 的返回结构字段存在性和类型。

**Step 2: 运行测试确认基线**
- Run: `pytest -k usage -q`
- Expected: 通过或定位当前相关测试集。

**Step 3: 修改 import 和查询入口**
- 将 `server_lw_data_provider` 替换为 `from lifeprism.storage import tokens_usage_store`
- 引入 `QueryOptions`，新增私有查询函数，支持：
  - `date` 当日范围查询
  - `start_time/end_time` 范围查询
  - 可选 `mode` 过滤

**Step 4: 运行静态检查与基础测试**
- Run: `pytest -k usage -q`
- Expected: 相关测试通过。

### Task 2: 在 service 层实现聚合适配（优先复用通用方法）

**Files:**
- Modify: `lifeprism/server/services/usage_service.py`

**Step 1: 实现聚合私有函数**
- `_aggregate_by_date(records) -> dict[str, dict]`
- `_aggregate_by_mode(records) -> dict[str, dict]`
- `_aggregate_total(records) -> dict`

**Step 2: 替换 4 类旧查询用途**
- 今日按日数据（overview）
- 今日按 mode 数据（processing + other）
- 全量总计
- 全量按 mode

**Step 3: 保持业务计算不变**
- 不改变：
  - `total_price` / `avg_cost` 计算方式
  - round 精度
  - `MODE_CLASSIFICATION` 排除逻辑

**Step 4: 运行测试**
- Run: `pytest -k usage -q`
- Expected: 通过。

### Task 3: 校验与收尾

**Files:**
- Modify: `lifeprism/server/services/usage_service.py`（如需修复）

**Step 1: 诊断检查**
- 使用 IDE 诊断检查编辑文件报错。

**Step 2: 执行最小端到端验证**
- 调用 `get_usage_stats(YYYY-MM-DD)`（测试或脚本）
- 验证返回 `UsageStatsResponse` 结构完整。

**Step 3: 清理与提交建议**
- 清理临时脚本（若有）
- 建议提交信息：`refactor: migrate usage stats source to tokens_usage_store`
