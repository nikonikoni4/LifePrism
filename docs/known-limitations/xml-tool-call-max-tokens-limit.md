# XML 工具调用在 max_tokens 不足时的限制

## 元信息

- **状态**: `acknowledged`（已确认，当前阶段不处理）
- **严重程度**: 中
- **影响范围**: 所有通过 XML 格式进行工具调用的场景（CONFLICT_RESOLVE、DREAM_TASK 等）

## 问题描述

当 LLM 需要输出 XML 格式的工具调用（如 `<tool_call><function=write_file>...`），但输出内容超过 `max_tokens` 限制时，XML 会被截断为不完整片段，导致：

1. **`finish_reason` 变为 `"length"`**：而非 `"tool_calls"`，XML 解析分支默认跳过
2. **XML 不完整**：缺少 `</tool_call>` 闭合标签，正则解析失败
3. **内容回退**：截断的 XML 文本被当作普通 content 返回，可能被写入目标文件

## 当前处理

2026-07-18 已修复的两层防护：

1. **主动检测**：`_resolve_conflicts` 中检测 `response.finish_reason == "length"`，跳过写入并记录 error 级别日志
2. **XML 解析增强**：`_parse_xml_tool_calls` 新增不完整 XML 的 fallback 匹配（`r"<tool_call>(.*)"`），能正确处理缺少 `</tool_call>` 的截断 XML

## 当前限制

- `max_tokens` 默认值已从 4096 翻倍到 8192（[base.py:75](file:///d:/desktop/软件开发/LifeWatch-AI/explore/LifePrism/lifeprism/llm/providers/llm_providers/base.py#L75)）
- 但极大型文档的冲突合并仍可能超出 8192，需进一步场景化调参
- 未来冲突解决改造为 diff3 算法后可彻底消除此限制（LLM 只做小范围合并）

## 触发条件

- LLM 工具调用输出（XML 格式）超过当前 `max_tokens` 配置值
- 高发场景：CONFLICT_RESOLVE 处理大文件（如 `user.md`、`behavior.md`）

## 临时方案

- 调高 `max_tokens`（修改 `GenerationSettings.max_tokens`）
- 在 `_process_msg` 中按 `msg.type` 传入不同的 `max_tokens`（CONFLICT_RESOLVE 场景用更大值）
- 冲突解决改造方案（diff3 替代纯 LLM 合并）可从根本上消除

## 相关文档

- **Bug**: [2026-07-17-write-file-xml-tag-residue-in-doc.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md)
- **ADR**: [2026-07-17-conflict-resolution-diff3-replaces-llm.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md)
- **Bug**: [2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md)
