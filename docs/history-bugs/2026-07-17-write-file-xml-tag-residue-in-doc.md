# write_file 工具 XML 标签残留到文档正文

## 元信息

- **发现时间**: 2026-07-17（初次记录），2026-07-18（补充根因）
- **修复状态**: ❌ 待修复（P1，已查明真实根因为 max_tokens 截断）
- **影响范围**: CONFLICT_RESOLVE 场景下大文件冲突合并
- **bug 类型**: max_tokens 截断 + Provider 解析失败 + 数据污染
- **严重程度**: 较严重（P1）
  - **数据污染**：LLM 工具调用的 XML 标签被原样写入文档正文，破坏文档结构
  - **不易察觉**：文档从第 4 行才开始真正内容，前 3 行是 XML 残留，用户/Agent 可能不立即发现
  - **与已知 bug 关联**：是 [2026-06-30-custom-provider-missing-xml-tool-call-parsing.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md) 的不同表现，但真实根因不同

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

**实际样本（user.md 开头）**：

```
1: <tool_call>
2: <function=edit_file>
3: <parameter=file_path>D:\desktop\软件开发\LifeWatch-AI\localData\user\user.md</parameter>
4: <parameter=old_content># USER.md
5: 
6: ## 基本信息
...
67: ...（全部旧内容，约 67 行）
68: <parameter=new_content># USER.md
...（全部新内容，约 67 行）
...
```

**问题**：
- 第 1-3 行是 LLM 工具调用的 XML 标签，被当作文档正文写入
- 缺少 `</tool_call>` 闭合标签（因 max_tokens=4096 截断）
- 文档结构被破坏，但不易察觉（Markdown 渲染器可能忽略未知标签）

## 根因分析

2026-07-18 排查发现：此前认为"Provider 缺少 XML 解析"是根因，但这是误导。真实根因如下。

### 根因 1（真实根因）：max_tokens=4096 截断导致 XML 不完整

**本质**：LLM 输出被 `max_tokens=4096` 硬截断，生成的 XML 工具调用缺少 `</tool_call>` 闭合标签，导致 `finish_reason` 为 `"stop"` 非 `"tool_calls"`，XML 解析分支被跳过。

**完整调用链**：

```
1. sync_client._resolve_conflicts() 检测到 user.md 冲突
   ↓
2. 构建 CONFLICT_RESOLVE 消息，包含本地和云端完整内容（约 67 行 × 2）
   ↓
3. AgentLoop._process_msg() → _run_agent_loop() → llm.chat(tools=tools)
   ↓
4. llm.chat() 未传入 max_tokens → 使用默认值 4096（base.py:75）
   ↓
5. AI 尝试输出 edit_file 的 XML 调用
   ├─ XML 标签开销 + old_content（67行）+ new_content（67行）≈ 远超 4096 tokens
   ├─ 输出在第 ~4096 token 处被截断
   └─ 缺少 </tool_call> 闭合标签
   ↓
6. finish_reason = "stop"（非 "tool_calls"）
   ↓
7. _parse_response() 第 421-431 行条件检查：
   ├─ finish_reason == "tool_calls"？ → ❌ 否（实际是 "stop"）
   └─ XML 解析分支跳过 ← 关键！
   ↓
8. 不完整的 XML 文本作为 LLMResponse.content 返回
   ↓
9. sync_client._resolve_conflicts() 第 1599 行：
   merged_content = result.response.content（拿到原始 XML 文本）
   ↓
10. 第 1617 行：_safe_write_file(local_file, merged_content)
    → XML 工具调用标签被直接写入文件
```

**代码位置**：

| 步骤 | 位置 | 问题 |
|------|------|------|
| 4 | [base.py:75](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/base.py#L75) | `max_tokens: int = 4096` 默认值过低 |
| 3 | [loop.py:112](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/agent/loop.py#L112) | `_run_agent_loop` 未为 CONFLICT_RESOLVE 传参 `max_tokens` |
| 7 | [litellm_provider.py:421-431](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/litellm_provider.py#L421-L431) | XML 解析条件要求 `finish_reason == "tool_calls"`，截断后为 `"stop"` |
| 9-10 | [sync_client.py:1599-1617](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/../../../sync/sync_client.py) | 直接将 `response.content`（含 XML）写入文件 |

**关键验证（测试结果）**：

| 测试场景 | 参数含 `<` | 缺少 `</tool_call>` | 解析结果 |
|----------|-----------|-------------------|----------|----------|
| Test 1: 简单内容 | ❌ | ❌ | ✅ 正确解析 |
| Test 2: 内容包含 `<` | ✅ | ❌ | ❌ 参数丢失 |
| Test 3: 内容包含 `>` | ❌ | ❌ | ✅ 正确解析（`>` 不影响） |
| Test 4: 内容同时包含 `<` 和 `>` | ✅ | ❌ | ❌ 只提取到 file_path |
| Test 5: 缺少 `</tool_call>` | ❌ | ✅ | ❌ 无法找到 tool_call 块 |
| Test 6: 真实场景（含 Markdown 链接） | ✅ | ✅ | ❌ 双重失败，解析为空 |

### finish_reason="length" 截断检测验证（2026-07-18）

2026-07-18 使用 `LiteLLMProvider`（dashscope/qwen-turbo）进行了截断检测测试：

| max_tokens | finish_reason | completion_tokens | 匹配？ |
|-----------|---------------|------------------|--------|
| 30 | `"length"` ✅ | 30 | ✅ 完美匹配 |
| 50 | `"length"` ✅ | 50 | ✅ 完美匹配 |
| 4096 | `"length"` ✅ | 4096 | ✅ 完美匹配 |

**结论**：`LiteLLMProvider.chat()` 正确传递了 `finish_reason="length"`，可以在 `_resolve_conflicts` 中通过 `response.finish_reason == "length"` 可靠检测输出截断。

### 根因 2（潜在原因）：XML 参数正则的 `<` 漏洞

即使 max_tokens 足够、XML 完整闭合，当前的正则表达式 `([^<]*)` 在参数值包含 `<` 字符时（如 Markdown 链接 `[AI](https://example.com)`、代码块等）也会解析失败。

**代码位置**：

- [custom_provider.py:96](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/custom_provider.py#L96)
- [litellm_provider.py:343](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/litellm_provider.py#L343)

`param_pattern = r"<parameter=([^>]+)>([^<]*)</parameter>"`

`([^<]*)` 在遇到 `<` 时提前终止，提取的参数不完整。

### 根因 3（设计缺陷）：CONFLICT_RESOLVE 不应注册写入工具

程序（`_resolve_conflicts`）本身已负责将 `response.content` 写入文件（第 1617 行 `_safe_write_file`），但仍给 LLM 注册了 `WriteFileTool`/`EditFileTool`（[loop.py:493-495](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/agent/loop.py#L493-L495)）。这导致：
1. AI 被误导去使用工具而非直接输出文本
2. 工具调用 XML 格式的输出体积远大于纯文本，更容易触发 max_tokens 截断

**总结**：
- **真实根因**（本次 user.md 事故）：max_tokens=4096 截断 → XML 不完整 → 解析跳过 → 全文写入
- **潜在根因**：正则 `<` 漏洞（即使无截断也会失败）
- **设计根因**：CONFLICT_RESOLVE 不应给写入工具（多余的诱惑）

## 代码位置

### 1. max_tokens 默认值过低（真实根因）

**位置**：[base.py:75](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/base.py#L75)

```python
max_tokens: int = 4096  # ← 默认值仅 ~3000 中文字符，大文件合并远远不够
```

### 2. _run_agent_loop 未按场景传入 max_tokens

**位置**：[loop.py:112](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/agent/loop.py#L112)

```python
response: LLMResponse = await llm.chat(messages=messages, tools=tools)
# 未传入 max_tokens → 使用默认值 4096
```

CONFLICT_RESOLVE 场景需要更大的 max_tokens（如 8192 或 16384），但未做区分。

### 3. XML 解析条件依赖 finish_reason

**位置**：[litellm_provider.py:421-431](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/litellm_provider.py#L421-L431)

```python
if (
    finish_reason == "tool_calls"  # ← 截断后为 "stop"，条件不成立
    and not tool_calls
    and content
    and "<tool_call>" in content
):
```

### 4. sync_client 直接将 response.content 写入文件

**位置**：[sync_client.py:1599-1617](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/sync/sync_client.py#L1599-L1617)

```python
merged_content = result.response.content if result.response else ""
# ... 没有校验 merged_content 是否是 XML 标签
_safe_write_file(local_file, merged_content.encode("utf-8"))
```

### 5. XML 参数正则漏洞（潜在原因）

**位置**：[custom_provider.py:96](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/custom_provider.py#L96) / [litellm_provider.py:343](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/litellm_provider.py#L343)

```python
param_pattern = r"<parameter=([^>]+)>([^<]*)</parameter>"
#                                    ^^^^^^ ← 不能包含 < ，参数值含 URL 就失败
```

## 修复方案

### 方案 A（推荐，场景化 max_tokens）：_run_agent_loop 按消息类型传入合理 max_tokens

**根因**：`_run_agent_loop`（[loop.py:112](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/agent/loop.py#L112)）调用 `llm.chat()` 不传 `max_tokens`，CONFLICT_RESOLVE 场景使用默认值 4096 严重不足。

**修复**：在 `_process_msg` 中根据 `msg.type` 传入合适的 `max_tokens`：

```python
# CONFLICT_RESOLVE 场景需要更大的输出窗口
if msg.type == MessageType.CONFLICT_RESOLVE:
    result, tool_call_chain = await self._run_agent_loop(
        session, system_prompt, tools, tool_registry, max_tokens=8192
    )
else:
    result, tool_call_chain = await self._run_agent_loop(
        session, system_prompt, tools, tool_registry
    )
```

`_run_agent_loop` 透传 `max_tokens` 到 `llm.chat(messages=messages, tools=tools, max_tokens=max_tokens)`。

**收益**：从根本上解决大文件冲突合并时输出被截断的问题。

**局限**：需要评估 8192 是否足够（取决于具体文件大小和模型 token 计费）。

### 方案 B（兜底）：_resolve_conflicts 写入前校验 XML 残留

在 [sync_client.py:1599](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/sync/sync_client.py#L1599) 写入前增加校验：

```python
merged_content = result.response.content if result.response else ""
# 校验是否包含 XML 工具调用残留（截断或不完整）
if merged_content.strip().startswith("<tool_call>") or "<function=" in merged_content[:500]:
    logger.error("_resolve_conflicts: AI 返回内容包含 XML 工具调用残留，保留本地版本")
    continue
```

**收益**：兜底避免 XML 标签污染文件。

### 方案 C（短期）：CONFLICT_RESOLVE 不给写入工具

**位置**：[loop.py:492-499](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/agent/loop.py#L492-L499)

程序（`_resolve_conflicts`）自己负责写入，不需要 AI 通过工具写文件。去掉 `WriteFileTool`/`EditFileTool` 后：
- AI 只能输出纯文本合并结果
- 输出体积减少一半（无需 XML 标签开销）
- 从根本上消除此场景的 XML 残留风险

```python
elif msg.type == MessageType.CONFLICT_RESOLVE:
    # CONFLICT_RESOLVE 不给写入工具，程序自己负责写入
    tools = []  # 或只保留 ReadFileTool 用于辅助读取上下文
```

**收益**：消除冲突场景的 XML 残留风险，减少 token 消耗。

### 方案 D（根因修复）：修复 XML 参数正则

将 `([^<]*)` 替换为可正确处理 `<` 字符的模式，如非贪婪匹配 `(.*?)`：

```python
param_pattern = r"<parameter=([^>]+)>(.*?)</parameter>"  # 非贪婪匹配
```

**收益**：从源头解决 XML 参数值包含 `<` 时的解析失败问题。

**风险**：`(.*?)` 的 `re.DOTALL` 跨行模式已在 `tool_call_pattern` 启用，`re.findall` 后续的 `param_pattern` 没有 `re.DOTALL`，需要验证跨行场景。

### 推荐实施顺序

1. **方案 C**（即时，冲突改造时一起做）：CONFLICT_RESOLVE 不给写入工具，消除诱惑
2. **方案 B**（兜底）：写入前校验 XML 残留，防止任何路径的数据污染
3. **方案 A**（场景化 max_tokens）：大文件冲突合并场景调高 max_tokens
4. **方案 D**（根因修复）：修复 XML 参数正则 `<` 漏洞

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

- **关联 bug**：[2026-06-30-custom-provider-missing-xml-tool-call-parsing.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-custom-provider-missing-xml-tool-call-parsing.md)（同一 XML 残留现象的日志表现，但当时未查明 max_tokens 截断根因）
- **关联 bug**：[2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)（CONFLICT_RESOLVE 给 LLM 写入工具 + 大文件截断，与当前 bug 根因相同）
- **关联 bug**：[2026-06-30-read-file-max-chars-causes-excessive-tool-calls.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-06-30-read-file-max-chars-causes-excessive-tool-calls.md)（同样是"硬编码默认限制导致输出不完整"的模式）
- **ADR**：[2026-07-17-conflict-resolution-diff3-replaces-llm.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md)（冲突解决改造方案，从根本上避免此 bug）
