# write_file 工具 XML 标签残留到文档正文

## 元信息

- **发现时间**: 2026-07-17
- **修复状态**: ❌ 待修复（中等优先级，已知存在但默认"工具是好的"）
- **影响范围**: 所有通过 Agent 调用 `WriteFileTool` / `EditFileTool` 写入的文档
- **bug 类型**: Provider 解析失败 + 数据污染
- **严重程度**: 中等（P2）
  - **数据污染**：LLM 工具调用的 XML 标签被原样写入文档正文，破坏文档结构
  - **不易察觉**：文档从第 4 行才开始真正内容，前 3 行是 XML 残留，用户/Agent 可能不立即发现
  - **与已知 bug 关联**：是 [2026-06-30-custom-provider-missing-xml-tool-call-parsing.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md) 的不同表现

## 触发规则

在以下场景时阅读此文档：
- 排查"文档开头出现 `<tool_call><function=write_file>` 等 XML 标签"
- 修改 `WriteFileTool` / `EditFileTool` 的调用或解析逻辑
- 修改 `CustomProvider._parse()` 或 `LiteLLMProvider._parse_response()` 的 XML 工具调用解析
- 排查 Agent 写入的文档内容包含 XML 工具调用残留
- 设计"LLM 是否应该有写入工具"或"工具调用输出格式"
- 评估"程序替换 vs LLM 直接写入"的方案选择

## 问题描述

**现象**：Agent 通过 `WriteFileTool` 写入文档时，LLM 的工具调用 XML 标签被原样写入文档正文，而非被解析为工具调用执行。

**实际样本（behavior.md 开头）**：

```
1: <function=write_file>
2: <parameter=file_path>user/daily_data/behavior_merged.md</parameter>
3: <parameter=content># 行为总结与日记记录
4: 
5: ## 2026-07-14
6: ### 聊天记录总结
...（正文从第 4 行才开始）
```

**问题**：
- 第 1-3 行是 LLM 工具调用的 XML 标签，被当作文档正文写入
- 文档真正内容从第 4 行才开始（`# 行为总结与日记记录`）
- 文档结构被破坏，但不易察觉（Markdown 渲染器可能忽略未知标签）

## 根因分析

### 关联已有 bug

[2026-06-30-custom-provider-missing-xml-tool-call-parsing.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md) 已记录：
- `CustomProvider._parse()` 缺少 XML 工具调用解析
- 模型（如 mimo-v2.5）在多轮工具调用时，第二次响应将工具调用以 XML 格式写入 `content` 字段，而非原生 `msg.tool_calls`
- `CustomProvider` 解析失败 → `tool_calls=[]` → XML 文本被当作 `content` 返回

**本 bug 是同一根因的不同表现**：
- 已有 bug：XML 文本进入 `content` → 被记录到 `llm_call_logger` 日志
- 本 bug：XML 文本进入 `content` → 被当作"LLM 最终回复" → 被 `WriteFileTool` 写入文档

### 为什么会写入文档

1. LLM 生成工具调用 XML（`<function=write_file>...`）
2. Provider 解析失败 → `tool_calls=[]`，XML 文本保留在 `content`
3. Agent Loop 收到 `content`（含 XML 文本）→ 当作 LLM 的"最终回复"
4. 如果上下文是"写入文件"，`content` 被直接写入目标文件
5. 文档正文出现 XML 标签残留

## 代码位置

### 1. CustomProvider 解析（根因）

**位置**：[lifeprism/llm/providers/custom_provider.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/providers/custom_provider.py)（`_parse` 方法）

**问题**：缺少 `_parse_xml_tool_calls` 回退逻辑（已在 2026-06-30 bug 中记录）

### 2. WriteFileTool 写入路径

**位置**：[lifeprism/llm/agent/tools/filesystem.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/filesystem.py)（`WriteFileTool.execute`）

**问题**：写入前不校验 `content` 是否包含 XML 工具调用标签，直接写入

### 3. Agent Loop 处理

**位置**：[lifeprism/llm/agent/loop.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/loop.py)

**问题**：当 `tool_calls=[]` 且 `content` 非空时，直接当作最终回复处理，不检测 content 是否是 XML 工具调用残留

## 修复方案

### 方案 A（推荐）：CONFLICT_RESOLVE 不给写入工具

**当前正在讨论的冲突解决改造**已决定：CONFLICT_RESOLVE 分支不给 Agent `WriteFileTool` / `EditFileTool`，Agent 只输出"冲突块位置 + 替换文本"，由程序执行替换。

**收益**：从根本上消除冲突解决场景下的 XML 残留风险。

**局限**：不解决其他场景（CHAT 分支的 DREAM_TASK 等）的 XML 残留问题。

### 方案 B（兜底）：WriteFileTool 写入前校验

在 `WriteFileTool.execute` 写入前检测 `content` 是否以 `<function=` 开头或包含 `<parameter=`：

```python
def execute(self, file_path: str, content: str) -> dict:
    # 校验是否是 XML 工具调用残留
    if content.strip().startswith("<function=") or "<parameter=" in content[:200]:
        return {
            "success": False,
            "error": "content 疑似 XML 工具调用残留，拒绝写入。请检查 Provider 解析逻辑。"
        }
    # 正常写入...
```

**收益**：兜底所有场景，无论哪个分支调用 WriteFileTool 都能拦截。

**局限**：误报风险（用户文档中合法包含 `<parameter=` 的场景，极罕见）。

### 方案 C（根因修复）：CustomProvider 补全 XML 解析

已在 [2026-06-30 bug](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md) 中记录，从 `LiteLLMProvider` 搬来 `_parse_xml_tool_calls`。

**收益**：从源头解决 XML 工具调用解析问题。

### 推荐实施顺序

1. **方案 A**（冲突解决改造时一起做）：消除冲突场景风险
2. **方案 B**（独立做）：兜底所有场景
3. **方案 C**（已在 2026-06-30 bug 中记录）：根因修复

## 验证方法

1. 构造一个 LLM 倾向于输出 XML 工具调用的场景（如使用 mimo-v2.5 多轮工具调用）
2. 触发 Agent 写入文件
3. 检查文件开头是否包含 `<function=` 或 `<parameter=` 标签
4. 应用方案 B 后，验证写入被拒绝并返回错误

## 预防措施

1. **WriteFileTool 写入前校验**（方案 B）：作为兜底机制
2. **Agent 工具白名单原则**：默认 `tools = []`，按需添加，避免不必要的写入工具
3. **Provider 解析完整性测试**：对所有 Provider（CustomProvider / LiteLLMProvider）做 XML 工具调用解析测试
4. **文档写入后校验**：写入后读取首行，检测是否包含 XML 标签

## 关联文档

- **关联 bug**：[2026-06-30-custom-provider-missing-xml-tool-call-parsing.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md)（同一根因的日志表现）
- **关联 bug**：[2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)（CONFLICT_RESOLVE 给 LLM 写入工具的根因）
- **正在讨论的方案**：冲突解决改造中"Agent 输出替换文本 + 程序替换"的设计，从根本上避免此 bug 在冲突场景复发
