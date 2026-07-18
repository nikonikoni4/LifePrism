# Issue 4: 冲突解决端到端流程（diff3 + LLM 串行 + 重试降级）

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 3-6, 10, 12）

## What to build

实现文件冲突解决的完整端到端流程：diff3 产生冲突标记 → 程序扫描冲突块 → 串行调用 LLM → 解析 JSON 替换指令 → 验证 marker → 执行替换 → 重试与降级。

**冲突标记格式**（来自 grill 讨论决策 3）：

```
<<<<<<< LP-LOCAL-{file_hash_8} #{n}
{ours_content}
=======
{theirs_content}
>>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}
```

- `LP-LOCAL` / `LP-REMOTE`：来源前缀，标记冲突内容来自本地或云端
- `{file_hash_8}`：本地文件 SHA-256 前 8 位，文件级标识
- `{remote_file_hash_8}`：云端文件 SHA-256 前 8 位
- `#{n}`：序号，文件内冲突块唯一标识，程序匹配的真正锚点

**LLM 输出 JSON 格式**（来自 grill 讨论决策 4）：

```json
{
  "conflict_id": 1,
  "start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1",
  "end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1",
  "replacement": "合并后的内容"
}
```

**串行处理流程**（理解 B，来自 grill 讨论决策 5）：

```
1. diff3 产生冲突文件（含 N 个冲突块，每个有唯一标记）
2. 程序扫描所有冲突块，编号 1..N
3. for i in 1..N:
   a. 程序构建 prompt，包含：
      - 唯一核心参数：{conflict_block_with_context}（整块冲突上下文 = 冲突标记前 20~30 行 + 完整冲突块 + 冲突标记后 20~30 行，到文件边界则取消扩展）
      - 可选辅助参数：{conflict_id} / {total_conflicts}（仅提示，不参与校验）
      - 当前方案不传 start_line / end_line（LLM 无文件读取工具，行号无意义）
   b. bus.send(CONFLICT_RESOLVE, 冲突内容) → AgentLoop → LLM（无工具）
   c. LLM 返回 JSON：{conflict_id, start_marker, end_marker, replacement}
   d. 程序验证：
      - JSON 是否可解析（用 json_repair 容错）
      - start_marker + end_marker 是否能在【当前文件】中精确匹配（含模糊匹配兜底）
   e. 验证失败 → 重试（重新 bus.send 同一冲突，最多 3 次）
   f. 3 次都失败 → 默认 keep_ours，记录警告，继续 i+1
   g. 验证成功 → 执行替换 → 文件更新 → 继续 i+1（基于更新后的文件）
4. 所有冲突块处理完，写入最终文件并更新 file_sync_state
```

**重试机制**（来自 grill 讨论决策 6）：

当前方案（无 ReadFileTool）的重试触发条件：
- JSON 解析失败（json_repair 也无法修复）
- start_marker / end_marker 在文件中无法精确匹配（含模糊匹配也失败）

**当前方案不校验行号的理由**：

1. LLM 没有文件读取工具，程序传入的整块上下文是 LLM 唯一信息源
2. LLM 输出的 `start_marker` / `end_marker` 必然来自 prompt 中提供的冲突标记（程序生成），字符串匹配即等价于"位置匹配"
3. 行号对 LLM 是无意义的——LLM 看不到文件全貌，无法验证"第 N 行是冲突标记"
4. 程序的 marker 匹配验证是**字符串精确匹配**，不依赖行号，行号校验是冗余

**未来添加 ReadFileTool 时的重试扩展**：

如果未来切换到添加 ReadFileTool 方案，重试范围需新增：
- 行号校验失败：LLM 输出的 start_line / end_line 与程序计算的行号不一致

**理由**：当 LLM 有 ReadFileTool 时，LLM 会自行读取文件并计算行号，需要校验 LLM 计算的行号与程序计算的行号是否一致，避免行号不一致导致替换错误位置。当前方案中程序直接告知 LLM 上下文（不依赖 LLM 读文件），无此风险。

**重试对象**：
- bus.send 返回结果解析的重试
- 不是工具调用的重试（LLM 无工具）

**重试次数**：3 次

**重试失败处理**：
- 当前冲突块降级为 keep_ours（保留本地版本）
- 记录 WARNING 日志
- 继续处理下一个冲突块（不中断整个文件处理）

**降级策略**（来自决策 10）：

- 单个冲突块失败 → 仅该冲突块降级 keep_ours，其他继续
- 整个文件失败（如 diff3 异常）→ 整个文件回退到 LWW（保留本地 + 备份云端到 sync_conflict/）

**关键设计点**：

- 每个冲突块基于"前一个替换后的文件"重新定位，行号变化不是问题
- 串行执行避免同文件多个替换互相干扰
- marker 匹配优先精确匹配，失败时尝试模糊匹配（正则容忍空格变化），模糊也失败 → 触发重试

## Acceptance criteria

- [ ] 实现冲突标记格式 `<<<<<<< LP-LOCAL-{hash8} #{n}` / `=======` / `>>>>>>> LP-REMOTE-{hash8} #{n}`
- [ ] hash 取文件 SHA-256 前 8 位
- [ ] 序号 #{n} 文件内唯一（多个冲突块序号递增）
- [ ] LLM 输出 JSON 格式：`{conflict_id, start_marker, end_marker, replacement}`
- [ ] 程序按"理解 B"串行处理：一个冲突一次 LLM 调用，处理完一个再处理下一个
- [ ] 每个冲突块基于更新后的文件继续（行号变化不是问题）
- [ ] 程序验证 marker 在当前文件中精确匹配
- [ ] marker 匹配失败时尝试模糊匹配（正则容忍空格变化）
- [ ] 上下文扩展 20~30 行（到文件边界则取消扩展），整块作为一个参数 `{conflict_block_with_context}` 提供
- [ ] **当前方案不传 start_line / end_line**（LLM 无文件读取工具，行号无意义）
- [ ] **当前方案不校验行号**（程序验证基于 marker 字符串精确匹配，行号校验是冗余）
- [ ] 重试机制：最多 3 次，重试范围是 JSON 解析失败或 marker 不匹配（不含行号校验）
- [ ] 3 次重试都失败时降级 keep_ours（保留本地版本）+ 记录 WARNING 日志
- [ ] 单个冲突块失败不中断整个文件处理
- [ ] 整个文件失败时回退到 LWW（保留本地 + 备份云端）
- [ ] 新建 `test/core/unit/sync/test_conflict_marker.py`（标记格式 + 序号唯一性 + 程序匹配）
- [ ] 新建 `test/core/unit/sync/test_conflict_json_parse.py`（JSON 解析、marker 匹配、重试、降级，mock LLM）
- [ ] 扩展 `test/core/integration/sync/test_sync_conflict_resolve.py` 端到端测试
- [ ] 文档中明确说明"未来添加 ReadFileTool 时才需要行号校验"（在重试机制中扩展）
- [ ] behavior.md 冲突场景端到端测试通过
- [ ] 不再出现 LLM 截断数据（冲突场景）
- [ ] 不再出现 WriteFileTool XML 残留（冲突场景）

## Blocked by

- Issue 2: 基于 difflib 自研 diff3 算法正式实现
- Issue 3: CONFLICT_RESOLVE 分支 tools=[] 与 conflict_prompts 模块化

## User stories covered

PRD 用户故事：5, 6, 7, 10, 11, 12, 13, 14, 15, 18, 19, 20, 21, 26, 27, 28, 29, 30, 32（端到端冲突解决流程）

## Related ADRs

- [docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md) - ADR-1 决策 3-6（冲突标记格式、LLM JSON 输出、串行处理、重试降级），本 issue 的核心 ADR。注：ADR-1 的决策编号体系与 PRD 不同，ADR-1 只有 8 项决策，本 issue 实现的 PRD 决策 10（降级策略）和 PRD 决策 12（消息类型）在 ADR-1 中未单独列项，包含在 ADR-1 整体方案中
- [docs/adr/2026-07-17-conflict-failure-policy.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-failure-policy.md) - 冲突失败处理策略（不阻塞 sync_once + 不主动通知用户），PRD 决策 10 降级策略的配套决策
- [docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/) - behavior.md 被破坏事件（本 issue 的触发根因）
