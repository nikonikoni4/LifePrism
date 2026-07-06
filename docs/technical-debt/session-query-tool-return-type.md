---
title: Session Query 工具返回类型不符合 PRD
created: 2026-07-06
severity: medium
component: lifeprism/llm/agent/tools/session_query.py
---

# Session Query 工具返回类型不符合 PRD

## 问题描述

`session_query.py` 中的两个工具当前返回 `str`（JSON 字符串），但 PRD 设计要求返回结构化数据：
- `QuerySessionListTool` 应返回 `dict[str, dict[str, str]]`
- `QuerySessionHistoryTool` 应返回 `list[dict[str, str]]`

## 问题根因

在实现过程中发现工具返回 `dict` 会导致 `tool` 角色消息的 `content` 是 dict 类型，而 LLM 提供商要求必须是字符串，因此临时修改为返回 JSON 字符串。

## 当前状态

- ✅ 功能正常工作（返回 JSON 字符串可以被 LLM 解析）
- ❌ 与 PRD 设计不一致
- ❌ 方法签名使用 `Any` 返回类型（违反类型注解规范）
- ✅ `loop.py` 中已有兜底逻辑将 dict/list 转为 JSON 字符串

## 影响

- **功能影响**：无，当前实现可以正常工作
- **代码质量**：类型注解不明确，调用方需要自行解析 JSON 字符串
- **一致性**：与 PRD 设计不一致

## 修复方案

### 方案 A：回退到 PRD 设计（推荐）

1. 修改 `execute()` 返回类型：
   - `QuerySessionListTool.execute()` → `dict[str, dict[str, str]] | str`
   - `QuerySessionHistoryTool.execute()` → `list[dict[str, str]] | str`

2. 修改返回语句：
   - 成功时返回 dict/list（不调用 `json.dumps()`）
   - 失败时返回 `ERROR` 前缀的字符串

3. 依赖 `loop.py` 第 155-162 行的兜底逻辑将 dict/list 转为 JSON 字符串

**优点**：
- 符合 PRD 设计
- 类型注解明确
- 调用方可以直接使用结构化数据（如果需要）

**缺点**：
- 需要回退代码

### 方案 B：修改 PRD，统一返回字符串

1. 更新 PRD 的返回类型说明
2. 修改 `execute()` 返回类型为 `str`
3. 保持当前实现不变

**优点**：
- 无需修改代码
- 统一工具接口（所有工具返回字符串）

**缺点**：
- 与原始 PRD 设计不一致
- 调用方需要自行解析 JSON

## 清理计划

1. 决定采用方案 A 或方案 B
2. 如果采用方案 A：
   - 回退 `session_query.py` 第 79、192、303 行的 `json.dumps()` 调用
   - 修改方法签名返回类型
   - 测试确认 `loop.py` 兜底逻辑正常工作
3. 如果采用方案 B：
   - 更新 PRD 文档
   - 修改方法签名返回类型为 `str`

## 相关文件

- `lifeprism/llm/agent/tools/session_query.py`
- `lifeprism/llm/agent/loop.py` (第 155-162 行：兜底逻辑)
- `.scratch/wechat-session-enhancement/prd.md` (第 66-90 行：工具返回类型定义)
- `lifeprism/CLAUDE.md` (类型注解规范)
