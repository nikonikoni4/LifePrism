# Issue 3: CONFLICT_RESOLVE 分支 tools=[] 与 conflict_prompts 模块化

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 2 和 11）

## What to build

消除 behavior.md 被破坏事件的根本风险——将 CONFLICT_RESOLVE 分支从"LLM 持有文件工具"改为"LLM 无任何工具"，并将 prompt 从硬编码迁移到 PromptLoader 模块。

**改造 1：CONFLICT_RESOLVE 工具注册**

修改 `lifeprism/llm/agent/loop.py`（当前 [loop.py:492-499](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/loop.py#L492-L499) 注册了 6 个工具含 WriteFileTool/EditFileTool）：

- 当前：注册 6 个工具（ReadFileTool / WriteFileTool / EditFileTool / FileTreeTool / SearchFileTool / SearchStringTool）
- 改造后：`tools = []`（与 CLASSIFY 分支一致）
- 理由：CONFLICT_RESOLVE 是纯文本合并任务，输入已在 InboundMessage.content 中提供，无需任何工具

**改造 2：Prompt 模块化**

新建 prompt 模块：

- 模块名：`conflict`
- 文件：`templates/prompts/conflict_prompts.md`
- prompt 名：`resolve_conflict`
- 复用 `PromptLoader.load_prompt(PromptRef("conflict", "resolve_conflict"))` 加载

**参数注入策略**（当前方案：无 ReadFileTool）：

当前 prompt 只需要**一个核心参数**——整块冲突上下文：

```python
# 唯一核心参数
{conflict_block_with_context}
```

- 内容定义：从冲突标记起始位置向前扩展 20~30 行 + 完整冲突块（含 base/ours/theirs 内容和冲突标记）+ 冲突标记结束位置向后扩展 20~30 行
- 边界处理：到文件边界则取消该侧扩展
- 直接作为 msg 消息发送给 LLM，LLM 基于这段内容输出替换指令

**可选辅助参数**：
- `{conflict_id}` / `{total_conflicts}`：告知 LLM 当前是第几个冲突（共 N 个），帮助 LLM 理解上下文范围（仅用于提示，不参与程序校验）

**当前方案不传 start_line / end_line 的理由**：

1. LLM 没有文件读取工具，无法自行读取文件，行号对 LLM 无意义
2. 程序的 marker 匹配验证基于 `start_marker` / `end_marker` 字符串精确匹配，不依赖行号
3. 整块上下文已包含足够信息让 LLM 做决策，行号是冗余信息

**未来添加 ReadFileTool 时的参数扩展**：

如果未来发现 20~30 行扩展上下文不足以让 LLM 做出合理合并决策，切换到添加 ReadFileTool 方案时：
- 新增参数：`{start_line}` / `{end_line}`（冲突标记的行号）
- 此时 LLM 会自行读取文件上下文，但行号是 agent 自己计算的，需要 LLM 输出时包含行号作为**校验依据**，避免行号不一致
- 程序重试机制新增"行号校验"项（详见 Issue 4 重试机制）

**Prompt 内容要点**：
- 角色：你是文件冲突解决助手
- 任务：基于提供的冲突块上下文内容，输出合并后的替换文本
- 输出格式约束：严格 JSON，字段说明，示例（具体 JSON 格式在 Issue 4 中定义）
- 上下文：整块冲突上下文（含 base/ours/theirs + 扩展 20~30 行）
- 禁止：不能输出自然语言解释，不能输出 markdown code fence

**关键约束**：
- 不包含 LLM 调用流程和串行处理（在 Issue 4 中实现）
- 不包含 JSON 输出格式定义（在 Issue 4 中定义）
- 本 issue 只负责"工具清空 + prompt 模块化"两个改造点

## Acceptance criteria

- [ ] `lifeprism/llm/agent/loop.py` CONFLICT_RESOLVE 分支改造为 `tools = []`
- [ ] 验证 LLM 在 CONFLICT_RESOLVE 分支无任何文件工具
- [ ] 扩展 `test/core/integration/llm/agent/test_conflict_resolve_loop.py` 验证 `tools = []`
- [ ] 新建 `templates/prompts/conflict_prompts.md` 模块文件
- [ ] prompt 只需 1 个核心参数：`{conflict_block_with_context}`（整块冲突上下文 = 冲突标记前 20~30 行 + 完整冲突块 + 冲突标记后 20~30 行）
- [ ] 可选辅助参数：`{conflict_id}` / `{total_conflicts}`（仅用于提示，不参与程序校验）
- [ ] **不传** `start_line` / `end_line` 参数（当前方案无 ReadFileTool，行号对 LLM 无意义）
- [ ] prompt 走 `PromptLoader.load_prompt(PromptRef("conflict", "resolve_conflict"))` 加载
- [ ] prompt 内容包含：角色、任务、输出格式约束、上下文说明、禁止事项
- [ ] prompt 文档明确说明"未来添加 ReadFileTool 时才需要 start_line / end_line 参数"
- [ ] 新建 `test/llm_prompt_test/test_conflict_resolve.py`（参考 `test/llm_prompt_test/test_activity_summary.py` 模式）
- [ ] prompt 测试通过（格式、参数注入、输出约束）

## Blocked by

None - can start immediately

## User stories covered

PRD 用户故事：8, 9, 16, 17, 34, 35, 36, 37, 38（CONFLICT_RESOLVE tools=[] + Prompt 模块化）

## Related ADRs

- [docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md) - ADR-1 决策 2（CONFLICT_RESOLVE tools=[]）+ ADR-1 决策 7（LLM 上下文扩展：一个核心参数 conflict_block_with_context）+ ADR-1 决策 8（ReadFileTool 未决问题），本 issue 的核心 ADR。注：ADR-1 决策编号与 PRD 不同，ADR-1 决策 7 对应 PRD 决策 11 的"参数注入策略"
- [docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/) - behavior.md 被破坏事件（本 issue 工具清空的触发原因）
- [docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/) - WriteFileTool XML 残留 bug（本 issue 通过 tools=[] 消除冲突场景风险）
