---
version: 1.0
created_at: 2026-10-08
updated_at: 2026-10-08
last_updated: 创建文档，登记 ToolUseGuard 在 lifeprism 与 myagent 两份实现并存的漂移风险
abstract: 路径护栏 ToolUseGuard 从 myagent 复制进 lifeprism 后两份实现并存，逻辑改动不会自动同步；记录生效方、漂移后果与收敛方向。
---

# ToolUseGuard 在 lifeprism 与 myagent 两份并存

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档，登记复制来源、漂移风险与收敛方向 |

## 问题描述

### 两份实现的位置

| 归属 | 路径 | 状态 |
| ---- | ---- | ---- |
| myagent | `agent/src/myagent/agent/guard/tool_use_guard.py` | 原始实现，仍保留 |
| lifeprism | `lifeprism/llm/guard/tool_use_guard.py` | 2026-10-08 复制而来，**实际生效的一份** |

### 注册点

`lifeprism/llm/runtime/service.py:312-314` 注册的是 lifeprism 那份：

```python
tool_guard = ToolUseGuard({"allow_path": guard_paths})
context.register_policy(
    AgentPolicySpec(TOOL_CALL, [tool_guard.file_sys_path_guard], tool_guard)
)
```

导入来自 `lifeprism.llm.guard`（`service.py:15`）。

### 为什么会有两份

需求是把护栏实现收归 lifeprism。myagent 侧那份不能删——它是独立仓库，可能仍有其他消费方。
复制是最小改动，代价是两份实现此后各自演化。

## 当前影响

- **逻辑漂移**：改 myagent 那份，lifeprism 行为不变；改 lifeprism 那份，myagent 行为不变。护栏是安全判据，漂移的后果是"以为护住了，其实没有"。
- **当前暴露面积小**：lifeprism 内只有 `service.py` 一处注册。风险随 myagent 消费方增加而上升。
- **payload 类型不在漂移范围内**：两份都从 `myagent.infra.events.payload` 导入 `ToolCallInfo` / `ToolCallPayload`。这条依赖是有意保留的——事件广播的就是那两个类的实例，类型必须同源。
- **副本已产生格式差异**：lifeprism 侧的 pre-commit 要求 `ruff format` 通过，副本的两处函数签名已重排（原文是 `tool_user_config : dict` 这类带空格写法）。因此逐行 diff 时除文档字符串外还会看到签名行。这是格式差异，不是逻辑差异。

## 优化方案

按推荐顺序：

1. **给 myagent 那份加迁移标注**（成本最低）
   在 `myagent/agent/guard/tool_use_guard.py` 顶部加 `deprecated` 说明，指向 lifeprism 版，声明 lifeprism 为唯一维护点。作用是挡住"改错文件"。
2. **删除 myagent 那份**（需先确认无消费方）
   确认 myagent 内无引用后删除，漂移问题从根上消失。
3. **抽公共包**（成本最高）
   把护栏提到两边都依赖的第三方包。仅当出现第三个消费方时再评估。

## 相关代码文件

| 文件 | 作用 |
| ---- | ---- |
| `lifeprism/llm/guard/tool_use_guard.py` | 生效实现 |
| `lifeprism/llm/guard/__init__.py` | 包导出 |
| `lifeprism/llm/runtime/service.py` | 注册点（15、312-314） |
| `agent/src/myagent/agent/guard/tool_use_guard.py` | 原始实现 |
| `test/core/integration/test_myagent_runtime.py` | 断言护栏注册与白名单行为（514、518） |

## 相关文档

- waterfall 订阅契约：`docs/coding-rules/2026-09-18-waterfall订阅契约.md`（该文档在 myagent 仓库）
