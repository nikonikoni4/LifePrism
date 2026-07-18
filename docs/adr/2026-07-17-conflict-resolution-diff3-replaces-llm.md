---
version: 1.0
created_at: 2026-07-17
updated_at: 2026-07-17
last_updated: 2026-07-17
abstract: 文件冲突解决从 LLM 自主合并改为 diff3 算法 + LLM 辅助合并（无工具），消除 AI 截断数据的风险
status: decided
---

# 文件冲突解决改用 diff3 + LLM 辅助合并

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

2026-07-16 上午 07:45，CONFLICT_RESOLVE 流程在 LLM 合并 `behavior.md` 时，因内容过长导致输出被截断，sync_client 用截断内容覆盖了本地文件，导致用户长期累积的行为记录被永久丢失（详见 `docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md`，P0 严重生产 bug）。

根因是 [loop.py:492-499](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/loop.py#L492-L499) 中 CONFLICT_RESOLVE 分支给 LLM 注册了 6 个工具（含 `WriteFileTool` / `EditFileTool`），LLM 可绕过 sync_client 直接修改文件。

必须重新决策文件冲突解决机制，消除 AI 截断数据的根本风险。

### 讨论范围

- 文件同步冲突解决机制（仅 `.md` 文件）
- CONFLICT_RESOLVE 消息类型的工具注册和 LLM 调用方式
- 冲突标记格式和程序替换流程
- LLM 输出格式和重试降级策略

### 非讨论范围

- 数据库同步冲突（仍走 row-level LWW）
- JSONL / JSON 文件冲突（仍走 LWW）
- 数据备份机制（见 ADR `2026-07-17-data-backup-strategy.md`）
- 冲突失败后的通知策略（见 ADR `2026-07-17-conflict-failure-policy.md`）

### 问题深度

涉及架构原则——AI 与程序的职责边界划分。原决策让 LLM 作为"文件操作员"（持有写入工具），新决策让 LLM 降级为"内容建议者"、程序升级为"决策执行者"。

## 现状

**原决策**（[2026-07-14-file-sync-conflict-resolution.md](./2026-07-14-file-sync-conflict-resolution.md) 决策 3）：

> MD 冲突由 AI 驱动解决（新增 CONFLICT_RESOLVE 消息类型），AI 直接拿到两份文档内联内容，可用 read_file 读相关上下文做智能合并。

**实际实现的问题**：

1. CONFLICT_RESOLVE 给 LLM 注册了 6 个工具（含 WriteFileTool / EditFileTool），LLM 可直接覆盖文件
2. LLM 输出整文档内容，长文档会被截断（context 限制）
3. 失败模式是"静默截断"——数据被破坏后用户无法察觉
4. LLM 可能写入 XML 工具调用残留（详见 `docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md`）

**已存在的 git-like 基础**：

`file_sync_state` 表已存储 `parent_hash`（common ancestor）+ `current_hash`（ours），云端有 `current_hash`（theirs）。3-way merge 的输入齐全。

## 决策前提

- 前提 1（事实）：2026-07-16 behavior.md 被破坏事件证明"LLM 自主合并 + 文件工具"模式存在静默截断风险
- 前提 2（事实）：项目已有 `parent_hash` 字段，3-way merge 的 common ancestor 已就绪
- 前提 3（事实）：CONFLICT_RESOLVE 是纯文本合并任务，LLM 无需读取文件外部上下文（输入已在 InboundMessage.content 中提供）
- 前提 4（用户偏好）：用户偏好无外部依赖（merge3 包是 GPL 协议，可能存在开源协议纠纷；difflib 是 Python 标准库）
- 前提 5（用户判断）：自研 difflib 实现够用，不需要引入外部库
- 前提 6（事实）：`sync_conflict/` 已有冲突前备份机制（本地版本），冲突文件内容可恢复

## 可选方案

### 方案 A：继续 LLM 自主合并（保持现状）

LLM 持有 WriteFileTool / EditFileTool，直接写入合并结果。

**优势**

- 现有实现，无需改造
- LLM 有文件工具可读上下文做更智能的合并

**劣势**

- 静默截断风险无法消除（behavior.md 事件根因）
- LLM 可能写入 XML 工具调用残留
- 长文档超出 context 限制时输出被截断

### 方案 B：diff3 替代 LLM 自主合并

用 diff3 算法做自动合并（基于 parent_hash 作为 common ancestor），失败的冲突块由 LLM 输出 JSON 替换指令，程序串行执行替换。

**优势**

- diff3 是确定性算法，最差情况是产生 conflict marker，数据永远在
- LLM 无文件工具，不可能直接覆盖文件
- LLM 只输出冲突块替换指令（不是整文档），不会因长文档截断
- 失败模式可控（降级 keep_ours，不会静默丢失数据）

**劣势**

- 需要自研 diff3 算法（约 150 行代码 + 测试）
- LLM 输出 JSON 可能不严格遵守格式（需 json_repair 容错 + 重试机制）
- 串行处理多次 LLM 调用，比单次调用慢

### 方案 C：完整 git-like（pygit2 / dulwich）

引入完整 git-like snapshot tree + chunk 去重（参考思源 dejavu）。

**优势**

- 成熟的合并算法
- 支持完整版本回滚

**劣势**

- 大规模重构
- 引入外部依赖（pygit2 / dulwich）
- 对主备模式过度设计
- 数据库同步仍是 LWW，文件层面引入 git 不能解决整体问题

## 决策逻辑

| 前提条件 | 对应方案 | 备注 |
|----------|----------|------|
| behavior.md 事件证明 LLM 自主合并不安全 + parent_hash 已存在 + 主备模式不需要完整 git | 方案 B（diff3 + LLM 辅助） | 当前选择 |
| 未来需要多端同步或对象存储中心 | 方案 C（完整 git-like） | 备选触发条件 |
| LLM 上下文窗口足够大 + LLM 输出可控性显著提升 | 方案 A（继续 LLM 自主合并） | 不推荐，与现状相同风险 |

## 最终决策

当前成立的前提：
- 前提 1（behavior.md 事件证明现状不安全）
- 前提 2（parent_hash 已存在）
- 前提 3（LLM 无需文件工具即可决策）
- 前提 4（用户偏好无外部依赖）
- 前提 5（自研够用）

因此选择 **方案 B（diff3 + LLM 辅助合并）**，具体包括：

1. **diff3 算法自研**：基于 Python 标准库 `difflib` 实现 3-way merge，约 150 行代码
2. **CONFLICT_RESOLVE 分支 `tools = []`**：LLM 无任何文件工具，与 CLASSIFY 分支一致
3. **冲突标记格式**：`<<<<<<< LP-LOCAL-{file_hash_8} #{n}` / `=======` / `>>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}`（序号 + hash + 来源前缀），hash 取文件 SHA-256 前 8 位，`{file_hash_8}` 为本地文件 hash，`{remote_file_hash_8}` 为云端文件 hash
4. **LLM 输出 JSON**：`{conflict_id, start_marker, end_marker, replacement}`
5. **串行处理（理解 B）**：一个冲突一次 LLM 调用，处理完一个再处理下一个，基于更新后的文件继续
6. **3 次重试 + 降级 keep_ours**：JSON 解析失败或 marker 不匹配时重试，3 次都失败保留本地版本
7. **LLM 上下文扩展**：prompt 中只传**一个核心参数**——整块冲突上下文（冲突标记前 20~30 行 + 完整冲突块 + 冲突标记后 20~30 行，到文件边界则取消扩展）。**当前方案不传 `start_line` / `end_line` 行号**——LLM 无文件读取工具，行号对 LLM 无意义；程序验证基于 `start_marker` / `end_marker` 字符串精确匹配，不依赖行号
8. **ReadFileTool 未决**：本次决策仅确定不给写入工具（WriteFileTool/EditFileTool 禁止），ReadFileTool 是否给予 LLM 是未决问题。当前方案为不给 ReadFileTool，依赖 prompt 中整块冲突上下文（一个参数）。如果实际测试发现扩展上下文不足以让 LLM 做出合理合并决策，则切换到添加 ReadFileTool 方案（只读工具，风险等级与 WriteFileTool 不同）。**未来添加 ReadFileTool 时**：prompt 改为只告知冲突位置行号，LLM 自行读取完整文件上下文；此时才需要 LLM 输出行号作为校验依据（因为行号是 LLM 自己计算的，需要校验与程序计算的行号是否一致），重试机制新增"行号校验"项

前提失效时的切换路径：
- 若未来需要多端同步或对象存储中心 → 切换到方案 C（完整 git-like）
- 若自研 diff3 算法在实际使用中发现可靠性问题 → 重新评估方案 A 或 C
- 若实际测试发现 20~30 行扩展上下文不足以让 LLM 做出合理合并决策 → 切换到添加 ReadFileTool 方案（只读工具，prompt 改为只告知冲突位置行号，输出格式不变，重试机制新增行号校验）

## 决策原因

- 原因 1：behavior.md 事件证明 LLM 自主合并不安全，必须改变现状
- 原因 2：diff3 是确定性算法，失败模式是 conflict marker（数据永远在），不会静默丢失
- 原因 3：LLM 降级为"内容建议者"消除了 WriteFileTool XML 残留和截断风险
- 原因 4：parent_hash 已存在，自研成本约 150 行代码，无外部依赖（用户偏好）
- 原因 5：主备模式下 per-file hash + diff3 足够，不需要完整 git-like snapshot tree

## 后续影响

**代码结构**：
- 新建 `lifeprism/sync/diff3.py`（diff3 算法）
- 修改 `lifeprism/llm/agent/loop.py`（CONFLICT_RESOLVE `tools = []`）
- 修改 `lifeprism/sync/sync_client.py`（串行处理 + JSON 解析 + 重试降级）
- 新建 `templates/prompts/conflict_prompts.md`（prompt 模块化）

**测试**：
- diff3 算法单元测试（7 场景 + git merge 对比）
- 冲突标记解析测试
- LLM 输出 JSON 解析测试（mock LLM）
- 端到端集成测试

**关联文档**：
- `docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md`（触发本次决策的 bug）
- `docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md`（XML 残留 bug，本次决策消除冲突场景风险）
- `.scratch/file-conflict-resolution-redesign/prd.md`（完整 PRD）
- `docs/adr/2026-07-14-file-sync-conflict-resolution.md`（原决策，本次决策修订决策 3）
