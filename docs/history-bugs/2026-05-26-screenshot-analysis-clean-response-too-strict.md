---
version: 1.0
created_at: 2026-05-26
updated_at: 2026-05-26
last_updated: 记录截图分析 LLM 响应清洗策略过严导致有效内容被清空的问题
abstract: 记录 screenshot_analysis.py 中 _clean_llm_response 对 LLM 输出格式要求过严，可能将非严格格式的有效响应清洗为 None，导致截图分析结果丢失。
---

# 截图分析 LLM 响应清洗策略过严

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 Bug 记录 |

## Bug简述

`lifeprism/llm/function/screenshot_analysis.py` 中如果使用 `cleaned_response = _clean_llm_response(response)` 清洗 LLM 响应，清洗策略对输出格式要求过严；当 LLM 没有严格按照预期格式输出时，有效内容可能被清洗为空并最终返回 `"None"`，导致截图分析结果丢失。

## 复用场景

该经验适用于所有将 LLM 自然语言输出写入数据库、摘要、行为分析或结构化后处理的场景。只要上游模型输出可能包含 Markdown、标题、表格、分隔符、短句或非标准列表格式，下游清洗逻辑都需要保留有效信息并提供原文兜底。

## 代码位置

- `lifeprism/llm/function/screenshot_analysis.py:208`：`_clean_llm_response(response)` 定义处。
- `lifeprism/llm/function/screenshot_analysis.py:271-273`：当 `cleaned_lines` 为空时直接返回 `"None"`。
- `lifeprism/llm/function/screenshot_analysis.py:387-388`：当前调用处已注释掉清洗逻辑，直接使用原始 `response`。

## 发生原因

`_clean_llm_response` 以行级过滤为核心，会跳过空行、Markdown 标题、分隔线、表格行、代码块标记以及过短文本。该策略默认 LLM 会输出可被保留规则识别的普通文本或列表项，但实际 LLM 输出存在不稳定性：可能把重点内容放在标题、表格、短句、代码块或其他非预期格式中。

当所有行都被过滤掉时，函数不会回退到原始响应，而是返回 `"None"`。因此问题不在于模型完全没有输出，而是清洗层把不符合格式假设的有效输出误判为无内容。

## 最佳方案

不要把格式清洗设计成硬性丢弃链路。建议采用宽松清洗和原文兜底：

1. 清洗只移除明确的包装噪声，例如代码块围栏和少量 Markdown 标记，不应删除整行有效内容。
2. 如果清洗结果为空但原始 `response.strip()` 非空，应返回原始响应或最小处理后的响应，而不是返回 `"None"`。
3. 判断无内容时仅处理真正的空响应、空白响应或模型明确输出的 `None`。
4. 对截图分析这类容错要求高的链路，优先保存原始 LLM 输出，再在后续展示或检索阶段做轻量规范化。

当前代码中调用处已经改为直接使用原始 `response`，这是避免数据丢失的保守处理。若后续需要恢复清洗，应先为 `_clean_llm_response` 补充覆盖非标准 Markdown、表格、代码块、短句和普通段落的单元测试。
