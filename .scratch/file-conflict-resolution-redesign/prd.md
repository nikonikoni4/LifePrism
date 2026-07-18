---
title: File Sync Conflict Resolution Redesign
created_at: 2026-07-17
updated_at: 2026-07-17
status: ready-for-agent
type: feature
---

# File Sync Conflict Resolution Redesign

## Problem Statement

当前文件同步冲突解决机制存在三个严重问题，已在生产环境造成数据破坏：

1. **AI 自主合并导致数据丢失**：2026-07-16 上午 07:45，CONFLICT_RESOLVE 流程在 LLM 合并 `behavior.md` 时，因内容过长导致输出被截断，sync_client 用截断内容覆盖了本地文件，导致用户长期累积的行为记录被永久丢失（详见 `docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md`，严重 P0 bug）

2. **LLM 工具化失控**：`AgentLoop` 的 CONFLICT_RESOLVE 分支给 LLM 注册了 6 个工具（含 `WriteFileTool` / `EditFileTool`），LLM 可绕过 sync_client 直接修改文件，与"LLM 返回合并内容字符串、程序统一写入"的设计假设冲突。这导致 LLM 可能直接覆盖文件，且可能写入 XML 工具调用残留（详见 `docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md`，中等 P2 bug）

3. **缺乏数据备份兜底**：现有备份机制仅触发于事件（数据库迁移、配置迁移、冲突解决前），完全缺失定时全量备份。一旦 AI 合并破坏文件，无任何回滚路径。

用户视角：用户每天通过 Agent 记录行为、日记、心情，这些数据是用户长期累积的核心资产。当同步流程破坏数据时，用户既无法察觉、也无法恢复，对系统的信任度被彻底破坏。

## Solution

重新设计文件同步冲突解决机制，采用三层防线：

1. **第一层（主动防御）**：用 diff3 算法替代 LLM 自主合并。diff3 是确定性算法，输入相同永远输出相同，最差情况是产生 conflict marker，**数据永远在**，不会像 LLM 那样静默截断。

2. **第二层（LLM 辅助合并）**：当 diff3 无法自动合并时，由 Agent 输出"冲突块位置 + 替换文本"的 JSON 指令，程序验证后串行执行替换。Agent 无任何文件工具，不可能直接写文件。

3. **第三层（数据备份兜底）**：实现定时全量备份机制，覆盖文档目录与数据库文件。即使前两层全部失效，也能从备份恢复（详见 ADR `docs/adr/2026-07-17-data-backup-strategy.md` 和 `docs/adr/2026-07-17-backup-sync-decoupled-scope.md`，恢复文档见 `templates/docs/lifewatch/06-数据备份与恢复.md`）。

## User Stories

### diff3 自动合并

1. 作为用户，我希望同步时能自动合并双方对文档的不同区域修改，这样不需要我手动介入
2. 作为用户，当我和云端都修改了同一文档的不同段落时，我希望同步后双方修改都保留
3. 作为用户，当我和云端修改了同一行不同内容时，我希望同步保留冲突标记而非任选一方丢弃
4. 作为系统，当 diff3 算法成功合并文件时，我需要将合并结果写入本地并更新 `file_sync_state`，这样下次同步能正确识别状态
5. 作为系统，当 diff3 算法产生冲突标记时，我需要保留冲突标记并触发 LLM 辅助合并，而不是直接覆盖

### LLM 辅助冲突解决

6. 作为用户，当 diff3 无法自动合并时，我希望 Agent 能介入处理冲突，而不是让我手动处理
7. 作为用户，当冲突发生时，我希望同步立即触发 Agent 处理（实时介入），而不是阻塞等待用户上线
8. 作为系统，CONFLICT_RESOLVE 分支必须给 LLM 注册 `tools = []`，不能赋予任何文件工具，这样 LLM 无法绕过程序直接写文件
9. 作为系统，LLM 必须基于 prompt 中提供的冲突块内容（base/ours/theirs）输出替换指令，不能自行读取文件
10. 作为系统，LLM 必须输出 JSON 格式的替换指令，包含 `conflict_id`、`start_marker`、`end_marker`、`replacement` 字段
11. 作为系统，程序必须按"理解 B"串行处理冲突：一个冲突一次 LLM 调用，处理完一个再处理下一个，基于更新后的文件继续
12. 作为系统，程序必须在执行替换前验证 `start_marker` 和 `end_marker` 能在文件中精确匹配（精确匹配失败时尝试模糊匹配兜底），都失败才触发重试
13. 作为系统，重试机制允许最多 3 次，重试范围是 JSON 解析失败或 marker 不匹配，重试对象是 bus.send 返回结果解析，不是工具调用重试
14. 作为系统，3 次重试都失败时，冲突块降级为 `keep_ours`（保留本地版本），记录警告日志
15. 作为系统，当整个文件的所有冲突块都处理完后，将最终合并结果写入本地并更新 `file_sync_state`
16. 作为 AI 助手，在处理冲突时，我需要看到每个冲突块的完整上下文（base/ours/theirs 内容 + 冲突标记外扩展 20~30 行上下文，整块作为一个参数提供），这样我能做出合理决策。当前方案不需要告知 LLM 冲突标记行号（LLM 无文件读取工具，行号无意义）；未来如添加 ReadFileTool 才需要行号作为校验依据。
17. 作为 AI 助手，我的输出必须是严格的 JSON 格式，不能输出自然语言解释，这样程序能可靠解析

### 冲突标记格式

18. 作为系统，diff3 生成的冲突标记必须包含"序号 + hash + 来源前缀"，这样同一文件多个冲突块能唯一区分
19. 作为系统，冲突标记格式必须为 `<<<<<<< LP-LOCAL-{file_hash_8} #{n}` / `=======` / `>>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}`，序号保证文件内唯一
20. 作为系统，hash 取文件 SHA-256 前 8 位，当前阶段作为唯一标识装饰，未来可扩展为版本快照关联
21. 作为系统，`LP-LOCAL` / `LP-REMOTE` 前缀标记冲突内容来源（本地/云端），便于 LLM 理解上下文

### 空文件与 template 文件过滤

22. 作为系统，空文件（内容 `strip()` 后为空）不应写入 `file_sync_state`，从根本解决空文档覆盖问题
23. 作为系统，启动时必须计算 `templates/` 目录下所有文件的 hash，写入 `template_hashes` 集合
24. 作为系统，写入 `file_sync_state` 前必须检查文件 hash 是否在 `template_hashes` 集合中，是则跳过
25. 作为用户，我不希望 template 初始化文档触发同步冲突，因为这些是系统默认文档，不携带用户数据

### 第三类文件处理

26. 作为系统，非空、非 template 的"第三类文件"（如 user.md、behavior.md）必须走 diff3 + LLM 辅助合并流程
27. 作为用户，对于 diary/agent/user 目录下的第三类文件，我希望默认采用 diff3 合并，因为这比 LLM 自主合并更可靠
28. 作为系统，JSONL 文件维持现状 LWW（append-only 或 row-level LWW），不走 diff3
29. 作为系统，JSON 文件维持现状 LWW，不走 diff3

### 降级与备份

30. 作为系统，当冲突处理失败（3 次重试都失败）时，必须保留本地版本，并将云端版本备份到 `sync_conflict/{timestamp}/`
31. 作为用户，我希望 sync_conflict/ 目录有清理机制（30 天保留），不会无限增长占满磁盘
32. 作为系统，当整个文件冲突处理流程异常时，整个文件回退到 LWW（保留本地 + 备份云端），避免数据破坏
33. 作为用户，我希望有定时全量备份作为最后兜底，即使冲突处理破坏了文件也能恢复（详见独立 spec）

### Prompt 模块化

34. 作为系统，冲突解决的 prompt 必须走 `PromptLoader` 模块，不能硬编码
35. 作为系统，新建 `conflict_prompts.md` 模块文件，复用现有 prompt 管理机制（版本管理、参数注入）
36. 作为系统，prompt 必须告知 LLM 明确的冲突位置（含 start_marker / end_marker）和冲突内容，让 LLM 基于提供的内容输出替换指令
37. 作为系统，prompt 必须包含输出格式约束（严格 JSON、字段说明、示例），降低 LLM 输出格式错误的概率
38. 作为系统，prompt 必须经过测试（参考 `test/llm_prompt_test/` 模块的测试模式）

## Implementation Decisions

### 1. diff3 算法实现（已决策：选项 C 自研）

**决策**：采用 **选项 C**——基于 Python 标准库 `difflib` 自研 3-way merge。

**决策日期**：2026-07-17

**实现基础**：已有探索性测试目录 `test/explore/diff3_self_difflib/`（包含原型实现和完整测试套件），作为正式实现的起点：
- `difflib_merge.py`：原型实现（176 行），需迁移到 `lifeprism/sync/diff3.py` 并整理为正式模块
- `test_scenarios.py`：7 经典 3-way merge 场景测试
- `test_edge_cases.py`：17 边界场景测试（中英文、emoji、Markdown、CRLF、无尾换行等）
- `test_git_oracle.py`：67 个 oracle 用例，对比 git merge 输出
- `REPORT.md`：稳定性测试报告，记录测试结果

**决策依据**（基于稳定性测试报告 `test/explore/diff3_self_difflib/REPORT.md`）：

1. **满足 PRD 核心需求**：
   - 7 个经典场景 **8/8 通过**（含多冲突序号唯一性测试）
   - 边界场景 **17/17 通过**（中英文、emoji、Markdown、CRLF、无尾换行等）
   - **数据永不丢失**——所有冲突场景 ours/theirs 内容均完整保留（在合并结果或冲突块中），满足 PRD 第一层防线"数据永远在"的核心安全属性
   - 性能富余：1500 行 76-92 ms，LifeWatch 文档场景完全够用

2. **与 git merge 一致性达标**：
   - 67 个 oracle 用例，**状态判定 100% 一致**（67/67 正确判定"能否自动合并"）
   - 文本一致率 89.6%，分歧均无数据丢失
   - 冲突切分粒度更细（重复行区段切成更多小冲突块），对 PRD 第二层 LLM 串行合并**反而更友好**

3. **零外部依赖**：纯标准库 `difflib`，无供应链风险、无版本兼容问题、无许可证约束（对比选项 E 的 GPL-2.0-or-later 限制）

4. **自研代码量小（176 行）**：易审阅、易维护、易测试

**可靠性保证方案**：
- 单元测试覆盖 7 个经典 3-way merge 场景（双方改不同区域、双方改同一行、一方删除一方修改等）
- 用 `git merge` 作为 oracle 对比测试（生成随机文本变更，对比自研与 git 输出）
- 失败模式可控：最差情况产生 conflict marker 或降级 keep_ours，不会静默截断数据

**已知限制及缓解**：

| # | 限制 | 实际影响 | 缓解 |
|---|---|---|---|
| ~~空 base 子集冲突块偏大~~ | **生产不触发** | PRD 决策 7 过滤空文件，无 `parent_hash` 即不进入 diff3 |
| diff 对齐算法差异（difflib Ratcliff-Obershelp vs git Myers） | 文本非字节级一致（89.6%），无数据丢失 | 可接受，状态判定 100% 一致 |
| 冲突切分粒度更细 | 与 git 冲突块数不同 | **正向影响**，对 LLM 串行合并更友好 |
| 超长文件 O(n²) | `behavior.md` 等长期累积文件可能超长 | **当前可接受**：后续将 `behavior.md` 按月分片（如 `behavior-2026-07.md`），从根本上规避超长文件场景；也可加大小阈值降级 LWW |
| 行级合并语义 | 对 JSON 等结构化文件可能破坏结构 | PRD 已明确 JSON/JSONL 走 LWW，不走 diff3 |

**后续延伸工作（不在本 PRD 范围）**：
- `behavior.md` 按月分片机制（独立 spec 处理）
- 超长文件阈值降级 LWW（实测触发后再决策）

**diff3 输入**：
- `base`：`parent_hash` 对应的文件内容（common ancestor，已存在）
- `ours`：本地当前文件内容
- `theirs`：云端当前文件内容

**diff3 输出**：
- 自动合并成功 → 合并后的文件内容
- 自动合并失败 → 含 conflict marker 的文件内容（标记格式见决策 3）

### 2. CONFLICT_RESOLVE 分支工具注册改造

**修改 `lifeprism/llm/agent/loop.py`**：

- 当前：注册 6 个工具（ReadFileTool / WriteFileTool / EditFileTool / FileTreeTool / SearchFileTool / SearchStringTool）
- 改造后：`tools = []`（与 CLASSIFY 分支一致）
- 理由：CONFLICT_RESOLVE 是纯文本合并任务，输入已在 InboundMessage.content 中提供，无需任何工具

### 3. 冲突标记格式

**格式**（来自 grill 讨论决策）：

```
<<<<<<< LP-LOCAL-{file_hash_8} #{n}
{ours_content}
=======
{theirs_content}
>>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}
```

**字段说明**：
- `LP-LOCAL` / `LP-REMOTE`：来源前缀，标记冲突内容来自本地或云端
- `{file_hash_8}`：本地文件 SHA-256 前 8 位，文件级标识，未来可扩展为版本快照关联
- `{remote_file_hash_8}`：云端文件 SHA-256 前 8 位
- `#{n}`：序号，文件内冲突块唯一标识，程序匹配的真正锚点

**示例**：
```
<<<<<<< LP-LOCAL-a3f8b2c1 #1
本周心情总结
=======
云端补全的心情总结
>>>>>>> LP-REMOTE-7e9d4f2b #1
```

### 4. LLM 输出 JSON 格式

**格式**（来自 grill 讨论决策）：

```json
{
  "conflict_id": 1,
  "start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1",
  "end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1",
  "replacement": "合并后的内容"
}
```

**程序匹配逻辑**：
- 按 `start_marker` + `end_marker` 完整字符串精确匹配
- 优先精确匹配，失败时尝试模糊匹配（正则容忍空格变化）
- 模糊匹配也失败 → 触发重试

### 5. 串行处理流程（理解 B）

**流程**（来自 grill 讨论决策）：

```
1. diff3 产生冲突文件（含 N 个冲突块，每个有唯一标记）
2. 程序扫描所有冲突块，编号 1..N
3. for i in 1..N:
   a. 程序构建 prompt，包含：
      - 当前是第 i 个冲突（共 N 个）
      - 当前冲突块的 base/ours/theirs 内容
      - 当前冲突块的 start_marker / end_marker
      - 前后 20~30 行上下文（扩展范围，到文件边界则取消扩展）
   b. bus.send(CONFLICT_RESOLVE, 冲突内容) → AgentLoop → LLM（无工具）
   c. LLM 返回 JSON：{conflict_id, start_marker, end_marker, replacement}
   d. 程序验证：
      - JSON 是否可解析（用 json_repair 容错）
      - start_marker + end_marker 是否能在【当前文件】中精确匹配
   e. 验证失败 → 重试（重新 bus.send 同一冲突，最多 3 次）
   f. 3 次都失败 → 默认 keep_ours，记录警告，继续 i+1
   g. 验证成功 → 执行替换 → 文件更新 → 继续 i+1（基于更新后的文件）
4. 所有冲突块处理完，写入最终文件并更新 file_sync_state
```

**关键设计点**：
- 每个冲突块基于"前一个替换后的文件"重新定位，行号变化不是问题
- 串行执行避免同文件多个替换互相干扰

### 6. 重试机制

**重试范围**（来自 grill 讨论决策）：

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

### 7. 空文件过滤

**实现位置**：`_sync_files_full_flow` 扫描阶段

**逻辑**：
- 扫描本地文件时，跳过 `content.strip() == ""` 的文件
- 这些文件不写入 `file_sync_state`
- 从根本解决空文档覆盖问题（2026-07-14 bug 根因）

### 8. Template 文件 hash 过滤

**实现**：
- 启动时计算 `templates/` 目录下所有文件的 hash，写入 `template_hashes` 集合（内存）
- 写入 `file_sync_state` 前检查文件 hash 是否在 `template_hashes` 集合中
- 是则跳过（不入 file_sync_state）
- 数据源单一：从 `templates/` 目录派生，不硬编码

### 9. sync_conflict/ 清理机制

**当前**：冲突解决前备份到 `sync_conflict/{timestamp}/`，无清理，永久保留

**改造**：
- 沿用数据备份 spec 的清理策略
- 30 天保留期，超期自动删除子目录
- 备份时同时备份本地和云端两个版本（当前仅备份本地）

### 10. 降级策略

**触发条件**：
- 整个文件冲突处理流程异常（如 diff3 失败、所有冲突块都重试失败）
- 整个文件回退到 LWW（保留本地 + 备份云端到 sync_conflict/）

**降级粒度**：
- 单个冲突块失败 → 仅该冲突块降级 keep_ours，其他继续
- 整个文件失败 → 整个文件降级 LWW

### 11. Prompt 模块化

**新建 prompt 模块**：
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
- 程序重试机制新增"行号校验"项（详见决策 6 重试机制）

**Prompt 内容要点**：
- 角色：你是文件冲突解决助手
- 任务：基于提供的冲突块上下文内容，输出合并后的替换文本
- 输出格式约束：严格 JSON，字段说明，示例
- 上下文：整块冲突上下文（含 base/ours/theirs + 扩展 20~30 行）
- 禁止：不能输出自然语言解释，不能输出 markdown code fence

### 12. CONFLICT_RESOLVE 消息类型

**保留现有 `MessageType.CONFLICT_RESOLVE`**：
- 当前：承载整个文件的合并任务
- 改造后：承载单个冲突块的合并任务（串行处理，每个冲突块一次 bus.send）
- InboundMessage.content 结构变化：从"完整文件内容"改为"单个冲突块内容 + 标记 + 上下文"

## Testing Decisions

### 测试接缝（Seams）

**优先复用现有接缝**：

1. **Seam 1：diff3 算法层**（新增单元测试）
   - 位置：`test/core/unit/sync/test_diff3_merge.py`
   - 测试内容：7 个经典 3-way merge 场景
   - 优先 art：参考 `test/core/unit/sync/test_compute_file_hash.py`（同模块单元测试模式）

2. **Seam 2：冲突标记生成与解析**（新增单元测试）
   - 位置：`test/core/unit/sync/test_conflict_marker.py`
   - 测试内容：标记格式正确性、序号唯一性、程序精确匹配
   - 优先 art：参考 `test/core/unit/sync/test_compute_file_hash.py`

3. **Seam 3：CONFLICT_RESOLVE Loop 工具注册**（扩展现有测试）
   - 位置：`test/core/integration/llm/agent/test_conflict_resolve_loop.py`（已存在）
   - 测试内容：验证 `tools = []`，验证 LLM 无文件工具
   - 优先 art：已存在的测试文件

4. **Seam 4：LLM 输出 JSON 解析与验证**（新增单元测试）
   - 位置：`test/core/unit/sync/test_conflict_json_parse.py`
   - 测试内容：JSON 解析、marker 匹配、重试逻辑、降级 keep_ours
   - 使用 mock LLM 返回（不调用真实 LLM）

5. **Seam 5：SyncClient 集成**（扩展现有测试）
   - 位置：`test/core/integration/sync/test_sync_conflict_resolve.py`（已存在）
   - 测试内容：端到端冲突解决流程、串行处理、降级、备份
   - 优先 art：已存在的测试文件

6. **Seam 6：空文件与 template 过滤**（新增单元测试）
   - 位置：`test/core/unit/sync/test_file_filter.py`
   - 测试内容：空文件跳过、template hash 过滤

7. **Seam 7：Prompt 模块**（新增 prompt 测试）
   - 位置：`test/llm_prompt_test/test_conflict_resolve.py`
   - 测试内容：prompt 格式、参数注入、输出约束
   - 优先 art：参考 `test/llm_prompt_test/test_activity_summary.py`

### 测试原则

- **只测试外部行为，不测试实现细节**
- **单元测试优先**：diff3 算法、标记解析、JSON 解析用单元测试
- **集成测试覆盖端到端**：从 diff3 输入到文件写入完整流程
- **mock LLM**：测试 LLM 输出解析逻辑时不调用真实 LLM，用 mock 返回预设 JSON
- **git merge 作为 oracle**：diff3 算法测试用 git merge 输出作为对照

### diff3 算法测试场景

1. 双方改不同区域 → 自动合并成功
2. 双方改同一行不同内容 → 产生冲突
3. 一方删除一方修改 → 产生冲突
4. 一方空文件一方有内容 → 产生冲突
5. 双方都新增内容（不同位置）→ 自动合并成功
6. 双方都新增内容（同一位置）→ 产生冲突
7. 一方整段移动 → 自动合并成功

## Out of Scope

### 不在本 PRD 范围

1. **数据库同步冲突解决**：数据库仍走 row-level LWW，不在本次改造范围
2. **WriteFileTool XML 残留 bug 修复**：详见 `docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md`（WriteFileTool 写入前校验、CustomProvider XML 解析补全）
3. **前端冲突处理 UI**：不做前端冲突处理界面，通过 Agent 对话通道通知用户
4. **长文档分流策略**：不做"按文档大小分流"的中期方案，先验证 diff3 + LLM 辅助合并的可靠性
5. **完整 git-like snapshot tree**：不引入 dejavu 式的完整 CAS + chunk 去重，主备模式下 per-file hash + diff3 足够
6. **云端 Agent 主动写 user/ 下文件的边界场景**：当前认为罕见，待实测频率后再决策
7. **CONFLICT_RESOLVE 消息类型废弃**：保留现有消息类型，仅改变 InboundMessage.content 结构
8. **LLM 是否应该有 read 工具**：本次决策为不给写入工具（WriteFileTool/EditFileTool 已确定禁止），但 ReadFileTool 是否给予 LLM 是**未决问题**，需要后续依据实际情况决定（LLM 在没有外部可获取 context 的情况下是否能正常合并）。
   - **当前方案**：不给 ReadFileTool，prompt 中提供整块冲突上下文（冲突标记前 20~30 行 + 完整冲突块 + 冲突标记后 20~30 行，整块作为一个参数）。**不传 start_line / end_line 行号**——LLM 无文件读取工具，行号对 LLM 无意义；程序验证基于 marker 字符串精确匹配，不依赖行号
   - **备选触发条件**：如果实际测试发现 20~30 行扩展上下文不足以让 LLM 做出合理合并决策，则切换到添加 ReadFileTool 方案
   - **备选方案**：给 LLM ReadFileTool，prompt 改为只告知冲突位置行号（start_line / end_line），LLM 自行读取完整文件上下文，输出格式不变（仍是 JSON 替换指令）。**此时才需要 LLM 输出行号作为校验依据**——因为行号是 LLM 自己计算的，需要校验与程序计算的行号是否一致，避免替换错误位置
   - **关键区别**：ReadFileTool 是只读工具，不会造成数据破坏（与 WriteFileTool 风险等级不同），可后续按需添加
9. **数据备份恢复 API / 前端 UI**：恢复场景频率极低（年频），仅做备份，不做恢复 API/UI。恢复通过手工操作 + 文档指导（详见 `templates/docs/lifewatch/06-数据备份与恢复.md`）。未来如频率提升，可基于此文档扩展为 API + Agent 通道
10. **plan 目录同步**：plan 加入备份范围但不加入同步范围（同步改造是独立决策，不在本 PRD 范围）

## Further Notes

### 关联文档

- **严重 bug 历史**：`docs/history-bugs/2026-07-16-conflict-resolve-llm-destroys-behavior-md.md`（behavior.md 被破坏根因）
- **XML 残留 bug**：`docs/history-bugs/2026-07-17-write-file-xml-tag-residue-in-doc.md`（WriteFileTool XML 标签残留）
- **空文档覆盖 bug**：`docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md`（LWW 空文档覆盖根因）
- **数据备份 ADR**：`docs/adr/2026-07-17-data-backup-strategy.md`（第三层防线 - 备份策略）
- **备份同步范围解耦 ADR**：`docs/adr/2026-07-17-backup-sync-decoupled-scope.md`（第三层防线 - 范围解耦）
- **冲突失败处理 ADR**：`docs/adr/2026-07-17-conflict-failure-policy.md`（失败处理策略）
- **文件同步 spec**：`docs/specs/2026-07-16-data-sync-files-spec.md`（现有同步机制）
- **冲突解决 ADR**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md`（11 态矩阵设计）

### 思源笔记参考

- 思源笔记的同步冲突处理由独立 Go 库 `dejavu` 实现，基于 git-like snapshot tree + 3-way merge
- dejavu 是自研的 3-way merge，不依赖现成 diff3 库
- 思源不使用行级 conflict marker（.sy 是 JSON，行级标记会破坏结构）
- 思源采用文件级冲突副本 + history 索引（FTS 可搜索）
- LifeWatch-AI 借鉴其"无行级 marker、文件级备份"思路，但因 .md 文件支持行级 marker，采用行级 marker + 程序替换方案

### 已知风险

1. **diff3 算法实现风险**：自研可能有边界 bug，需充分测试 + git merge 对比验证
2. **LLM 输出格式不稳定风险**：LLM 可能不严格遵守 JSON 格式，需 json_repair 容错 + 3 次重试 + 降级 keep_ours
3. **prompt 硬编码技术债**：当前部分 prompt 走硬编码，需迁移到 PromptLoader 模块
4. **prompt 未测试技术债**：当前 prompt 未经过 `test/llm_prompt_test/` 模块测试
5. **sync_conflict/ 无限增长风险**：当前无清理机制，需纳入 30 天保留策略
6. **WriteFileTool XML 残留风险**：本 PRD 通过 CONFLICT_RESOLVE 不给工具消除冲突场景风险，但其他场景（CHAT 分支）仍有风险，需独立修复

### 未决问题（需后续 grill 讨论或实现时决策）

1. ~~**diff3 算法选型**：选项 C（difflib 自研）vs 选项 E（merge3 包 + 包装），取决于可靠性验证结果~~ **已决策（2026-07-17）：采用选项 C 自研，详见 Implementation Decisions §1**
2. ~~**文本备份与恢复流程**：数据备份 spec 已定义机制，但文本备份的具体实现细节（如备份频率、恢复粒度）需进一步讨论~~ **已决策（2026-07-17）：详见 Implementation Decisions §13-18**
3. ~~**云端 Agent 主动写 user/ 文件的边界场景**：当前认为罕见，待实测频率后决策是否需要额外防护~~ **已决策（2026-07-17）：保持现状，走 diff3 + LLM 辅助合并（理解 B 串行处理）流程，与本地修改同等对待**
4. ~~**冲突处理失败时的同步阻塞行为**：整个文件失败时是否阻塞整个 sync_once，还是仅跳过该文件继续其他~~ **已决策（2026-07-17）：不阻塞 sync_once，仅跳过冲突文件，其他继续；冲突文件降级 keep_ours（保留本地版本），云端版本备份到 sync_conflict/（修复点：当前仅备份本地版本，需同时备份云端版本）**
5. ~~**Agent 通知用户的触发时机**：冲突发生时是否立即通知，还是等用户下次对话时主动告知~~ **已决策（2026-07-17）：仅日志记录 + sync_conflict/ 备份，不主动通知用户（与"不做 Agent 恢复通道"整体决策一致）。用户通过查看 sync_conflict/ 目录被动发现**

### 实施顺序建议

1. **第一阶段（消除根因）**：
   - CONFLICT_RESOLVE 分支改为 `tools = []`
   - 新建 `conflict_prompts.md` 模块
   - 实现空文件 + template 过滤

2. **第二阶段（diff3 替代 LLM 自主合并）**：
   - 选型并实现 diff3 算法
   - 实现冲突标记格式
   - 实现 LLM 辅助合并串行流程
   - 实现重试与降级

3. **第三阶段（数据备份兜底）**：
   - 新建 `BackupService` + `lifeprism/backup/constants.py`
   - 集成到 `ScheduleService`（cron 调度）
   - 实现完整性校验
   - sync_conflict/ 清理机制

4. **第四阶段（恢复文档）**：
   - 创建 `templates/docs/lifewatch/06-数据备份与恢复.md`
   - 指导用户手工恢复操作

5. **第五阶段（测试覆盖）**：
   - diff3 算法单元测试（7 场景 + git merge 对比）
   - 冲突标记解析测试
   - LLM 输出 JSON 解析测试
   - 端到端集成测试
   - prompt 测试
   - 备份完整性校验测试

### 验收标准

**冲突解决部分**：
- [ ] CONFLICT_RESOLVE 分支 `tools = []`
- [ ] 新建 `conflict_prompts.md` 模块，走 PromptLoader
- [ ] 空文件不入 `file_sync_state`
- [ ] template 文件 hash 过滤生效
- [ ] diff3 算法通过 7 场景单元测试
- [ ] diff3 算法通过 git merge 对比测试
- [ ] 冲突标记格式正确（序号 + hash + 前缀）
- [ ] LLM 输出 JSON 可靠解析（含 json_repair 容错）
- [ ] 串行处理流程正确（基于更新后文件继续）
- [ ] 重试机制生效（3 次重试 + 降级 keep_ours）
- [ ] sync_conflict/ 同时备份本地和云端版本（**修复当前 bug：[sync_client.py:1610-1614](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1610-L1614) 仅备份本地版本**）
- [ ] sync_conflict/ 备份结构清晰（如 `sync_conflict/{ts}/{path}.local.md` + `{path}.remote.md`）
- [ ] sync_conflict/ 30 天清理机制生效
- [ ] 冲突失败时不阻塞 sync_once，仅跳过冲突文件
- [ ] 单个冲突块重试 3 次失败时降级 keep_ours（保留本地版本）+ 记录 WARNING 日志
- [ ] 整个文件冲突处理异常时回退 LWW + 记录 ERROR 日志（不主动通知用户）
- [ ] behavior.md 冲突场景端到端测试通过
- [ ] 不再出现 WriteFileTool XML 残留（冲突场景）
- [ ] 不再出现 LLM 截断数据（冲突场景）

**数据备份部分**：
- [ ] 新建 `BackupService` 单例（`lifeprism/server/services/backup_service.py`）
- [ ] 新建 `lifeprism/backup/constants.py`（BACKUP_DIRS、BACKUP_EXCLUDED_FILENAMES、BACKUP_DB_FILES）
- [ ] 文档备份：每天 03:00 自动触发，覆盖 session/diary/agent/user/plan
- [ ] 数据库备份：每 8 小时（00/08/16 点）自动触发，全量备份 lifewatch_ai.db
- [ ] 备份位置：`{lifeprism_data_path}/backups/{docs,db}/{timestamp}/`
- [ ] 平铺存储（非 zip），支持文件管理器直接查看
- [ ] 文档与数据库各自保留最新 3 份
- [ ] 备份完整性校验：文件数量 + hash 比对 + `PRAGMA integrity_check`
- [ ] 校验失败自动删除损坏备份并记录 ERROR 日志
- [ ] 云端 agent_only 模式不执行备份（复用 `run_mode != "full"` 守卫）
- [ ] 创建 `templates/docs/lifewatch/06-数据备份与恢复.md` 恢复指导文档

**Sync 专用日志部分**：
- [ ] 新增 `setup_sync_logging(log_dir)` 函数（`lifeprism/utils/logger.py`）
- [ ] `settings_manager._setup_logging` 调用 `setup_sync_logging`
- [ ] sync.log 文件路径为 `{lifeprism_data_path}/debug_logs/sync.log`
- [ ] maxBytes=500KB，backupCount=0（覆盖式滚动）
- [ ] 启动时不清空 sync.log（追加写入）
- [ ] sync_client.py 同步日志同时写入 sync.log + lifeprism.log + 控制台（验证 propagate）
- [ ] 冲突处理日志（超时/失败/成功/降级 keep_ours）出现在 sync.log 中
- [ ] sync.log 超过 500KB 时被清空重写（覆盖式）
- [ ] sync_client.py / loop.py 代码无改动

---

## 数据备份实施决策（2026-07-17 grill 讨论）

### 13. 备份范围与格式

**文档备份目录**（独立定义，不依赖 `SYNC_DIRECTORIES`）：

```python
# lifeprism/backup/constants.py（新建）

BACKUP_DIRS = [
    "session/",   # 聊天会话 JSONL
    "diary/",     # 日记 MD
    "agent/",     # Agent 身份/记忆/配置
    "user/",      # 用户级数据
    "plan/",      # 计划文档（仅备份，不加入同步范围）
]

BACKUP_EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}
```

**数据库备份清单**：

```python
BACKUP_DB_FILES = [
    "dataset/lifewatch_ai.db",   # 主数据库（全量备份，含所有表）
]
```

**注意**：
- `chat_history.db` 已弃用，不在备份范围
- 数据库是**全量备份**（不同于同步的 `SYNC_TABLES` 31 张表子集），包含本地产能表、配置表、file_sync_state 等所有表
- plan 加入备份但不加入同步（同步改造是独立决策）

**备份格式**：平铺 + 文件夹时间戳，不打包 zip

```
{lifeprism_data_path}/backups/
├── docs/
│   ├── 2026-07-17T03-00-00/         ← 每日文档快照
│   │   ├── session/
│   │   ├── diary/
│   │   ├── agent/
│   │   ├── user/
│   │   └── plan/
│   ├── 2026-07-16T03-00-00/
│   └── 2026-07-15T03-00-00/
└── db/
    ├── lifewatch_ai-2026-07-17T08-00-00.db    ← SQLite Online Backup 产物
    ├── lifewatch_ai-2026-07-17T16-00-00.db
    └── lifewatch_ai-2026-07-18T00-00-00.db
```

**选择平铺而非 zip 的理由**：
1. 用户可直接用文件管理器查看备份内容（关键需求）
2. 单文件恢复只需复制，无需解压
3. 数据库 .db 文件可用 DB Browser 直接打开
4. LifePrism 数据量小（文档几 MB、数据库几 MB），3 份总和不超 50MB，无压缩需求
5. 现代备份工具（restic、borg）均采用平铺 + 去重，zip 适合归档不适合备份

### 14. 备份频率

| 备份对象 | 频率 | 触发时间 | 保留份数 |
|---------|------|---------|---------|
| 文档 | 每天 1 次 | 本地 03:00 | 3 份 |
| 数据库 | 每 8 小时 1 次 | 本地 00:00 / 08:00 / 16:00 | 3 份 |

**数据库频率高于文档的理由**：数据库写入频率更高（Monitor 每 30 秒~5 分钟写入一次 user_app_behavior_log），需更短丢失窗口。

**丢失窗口分析**：
- 文档：最差情况丢失 24 小时（可接受，文档是 Agent 低频写入）
- 数据库：最差情况丢失 8 小时（含聊天记录、心情、日记、习惯打卡等核心数据）

### 15. 调度机制

**复用现有 `ScheduleService`**（`lifeprism/server/services/schedule_service.py`）：

```python
# schedule_service.py 修改

from lifeprism.server.services.backup_service import backup_service

class ScheduleService:
    def __init__(self) -> None:
        # ... 现有代码 ...

        # 注册备份任务
        self._system_jobs.extend([
            {
                "func": backup_service.backup_documents,
                "trigger": "cron",
                "kwargs": {"cron_expr": "0 3 * * *"},  # 每天本地 03:00
                "job_id": "backup_documents",
            },
            {
                "func": backup_service.backup_database,
                "trigger": "cron",
                "kwargs": {"cron_expr": "0 0,8,16 * * *"},  # 每天本地 00/08/16 点
                "job_id": "backup_database",
            },
        ])
```

**复用现有特性**：
- 本地时区处理：`pytz.timezone(get_user_timezone())`
- 状态持久化：`_save_cron_state` 机制（避免重启后重复执行）
- 启动补偿：错过 03:00 时启动后异步执行一次
- run_mode 守卫：`run_mode != "full"` 时跳过备份（云端 agent_only 不备份）

**职责分离**：
- `ScheduleService`：何时执行（cron、状态持久化、启动补偿）
- `BackupService`：如何执行（文件复制、SQLite Backup API、保留策略、完整性校验）

### 16. BackupService 设计

```python
# lifeprism/server/services/backup_service.py（新建）

class BackupService:
    """备份服务（单例）
    
    职责：执行备份逻辑（不负责调度，调度由 ScheduleService 负责）
    """

    async def backup_documents(self) -> None:
        """文档全量备份（保留 3 份）
        
        流程：
        1. 创建 backups/docs/{timestamp}/ 目录
        2. 复制 BACKUP_DIRS 下的文件（排除 BACKUP_EXCLUDED_FILENAMES）
        3. 完整性校验：文件数量比对 + 每个文件 hash 比对
        4. 校验失败 → 删除损坏备份 → 记录 ERROR 日志
        5. 清理超过 3 份的旧备份（按时间戳排序，保留最新 3 份）
        """

    async def backup_database(self) -> None:
        """数据库全量备份（保留 3 份，使用 SQLite Online Backup API）
        
        流程：
        1. SQLite Online Backup: 
           source = sqlite3.connect(lifewatch_ai.db)
           target = sqlite3.connect(backups/db/lifewatch_ai-{timestamp}.db)
           source.backup(target)
        2. 完整性校验：PRAGMA integrity_check
        3. 校验失败 → 删除损坏备份 → 记录 ERROR 日志
        4. 清理超过 3 份的旧备份（按时间戳排序，保留最新 3 份）
        """

backup_service = BackupService()
```

**关键设计点**：
1. SQLite Online Backup API：`sqlite3.Connection.backup(target)`，路径完全自定义，不阻塞业务读写
2. 完整性校验：见决策 17
3. 保留策略：按时间戳排序，保留最新 3 份，旧的删除
4. 原子性：文档备份用 tempfile + os.rename 保证原子性；数据库备份 SQLite API 本身原子

### 17. 备份完整性校验（方案 A 完整校验）

**文档备份校验**：
```python
async def _verify_docs_backup(self, source_root, backup_root) -> bool:
    """校验文档备份完整性
    
    Returns:
        True 表示校验通过，False 表示校验失败
    """
    # 1. 比对文件数量
    source_files = list(source_root.rglob("*"))
    backup_files = list(backup_root.rglob("*"))
    if len(source_files) != len(backup_files):
        return False
    
    # 2. 比对每个文件的 hash
    for src_file, bak_file in zip(source_files, backup_files):
        if compute_file_hash(src_file) != compute_file_hash(bak_file):
            return False
    
    return True
```

**数据库备份校验**：
```python
async def _verify_db_backup(self, backup_path) -> bool:
    """校验数据库备份完整性
    
    Returns:
        True 表示校验通过，False 表示校验失败
    """
    import sqlite3
    conn = sqlite3.connect(backup_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    conn.close()
    return result == "ok"
```

**校验失败处理**：
- 删除损坏的备份目录/文件
- 记录 ERROR 日志（含失败原因）
- 不影响其他任务（调度器独立）

### 18. 恢复策略（仅文档指导，不做 API）

**决策**：
- ❌ 不做恢复 API
- ❌ 不做前端恢复 UI
- ❌ 不做 Agent 恢复通道
- ✅ 仅做备份，恢复通过手工操作
- ✅ 写恢复说明文档：`templates/docs/lifewatch/06-数据备份与恢复.md`

**决策前提**：
1. 恢复场景频率极低（年频）
2. 为低频场景做 API/UI 投入产出比低
3. 本地测试时用户可立即手工恢复（用户是开发者，熟悉文件操作）
4. 未来如有需要，可基于此文档扩展为 API + Agent 通道

**文档内容要点**：
- 备份位置说明（`{lifeprism_data_path}/backups/`）
- 文档恢复操作步骤（复制单个文件或整个时间戳目录）
- 数据库恢复操作步骤（关闭服务 → 替换 .db 文件 → 重启服务）
- 恢复前强烈建议手动备份当前数据
- 恢复后对 file_sync_state 的影响（下次同步会触发 CONFLICT，预期行为）
- 文档面向 Agent 可读，未来 Agent 可通过 ReadFileTool 读取以指导用户

**关键设计点**：
- 不需要 pre_restore 快照机制：用户手工恢复时自行决定是否先备份当前状态
- 文档应强烈建议恢复前手动备份当前数据（复制到 `backups/pre_restore-{ts}/`）
- 数据库恢复必须停服（SQLite 文件被覆盖时不能有连接）
- 文档恢复不停服，但需暂停 sync_client（避免恢复过程中同步覆盖）

### 19. 冲突失败处理与通知策略（2026-07-17 grill 讨论）

**问题 2 决策：冲突失败时的同步阻塞行为**

- **采用方案 B**：仅跳过冲突文件，其他继续
- 冲突文件降级为 `keep_ours`（保留本地版本）
- **不阻塞 sync_once**，符合"主备模式不需要实时性"原则
- 冲突文件状态保持为 CONFLICT，下次 sync_once 会重新尝试 diff3 + LLM 辅助合并

**问题 3 决策：用户通知时机**

- **采用方案 C**：仅日志记录 + sync_conflict/ 备份，不主动通知用户
- 与"不做 Agent 恢复通道"整体决策一致
- 用户通过查看 sync_conflict/ 目录被动发现
- 未来如需主动通知，可扩展为 Agent 启动时检查日志

**关键修复点：sync_conflict/ 必须同时备份本地和云端版本**

当前 [sync_client.py:1610-1614](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1610-L1614) 只备份本地版本：

```python
# 当前（有 bug）：
backup_path = (data_path / "sync_conflict" / timestamp_str / file_path).resolve()
backup_path.parent.mkdir(parents=True, exist_ok=True)
backup_path.write_text(local_content, encoding="utf-8")  # 只备份本地
```

**改造后**：

```python
# 改造后（同时备份本地和云端）：
conflict_dir = (data_path / "sync_conflict" / timestamp_str / file_path).resolve()
conflict_dir.parent.mkdir(parents=True, exist_ok=True)

# 备份本地版本
(conflict_dir.parent / f"{file_path.name}.local.md").write_text(local_content, encoding="utf-8")

# 备份云端版本
(conflict_dir.parent / f"{file_path.name}.remote.md").write_text(remote_content, encoding="utf-8")
```

**备份目录结构**：

```
sync_conflict/
└── 20260717_154500/
    └── agent/behavior.md/        ← 文件路径作为目录名
        ├── behavior.md.local.md   ← 本地版本
        └── behavior.md.remote.md  ← 云端版本
```

或更简单的扁平化结构：

```
sync_conflict/
└── 20260717_154500/
    ├── agent__behavior.md.local.md    ← 本地版本（路径用 __ 分隔）
    └── agent__behavior.md.remote.md   ← 云端版本
```

**修复理由**：
1. 当前只备份本地版本，云端版本在降级 keep_ours 后永久丢失
2. 用户无法对比本地与云端差异，无法判断 keep_ours 是否正确
3. 如果用户发现 keep_ours 选错了，没有云端版本可恢复
4. 同时备份两份让用户有完整的对比和恢复能力

**保留策略**：
- sync_conflict/ 保留 30 天（与决策 9 一致）
- 超过 30 天的冲突备份自动清理
- 每个冲突时间戳目录包含本地和云端两份备份

### 20. Sync 专用日志（sync.log）

**决策**：新增 sync 专用日志文件，独立记录同步过程和冲突处理过程，同时保留在全局 `lifeprism.log` 中。

**目标**：
- 独立查看同步过程，无需从混合日志中筛选
- 控制磁盘占用（上限 500KB，覆盖式滚动）
- 不影响现有日志架构，零侵入 sync_client.py / loop.py

**实现机制**（利用 Python logging 层级传播）：

- `sync_client.py` 的 `__name__` 为 `lifeprism.sync.sync_client`，是 `lifeprism.sync` 的子 logger
- 给 `lifeprism.sync` logger 附加专用 `RotatingFileHandler`
- 通过 `propagate=True`（默认）实现：日志同时写入 sync.log + lifeprism.log + 控制台
- **sync_client.py / loop.py 都不需要改动**

**配置参数**：

| 参数 | 值 | 说明 |
|------|-----|------|
| 文件路径 | `{lifeprism_data_path}/debug_logs/sync.log` | 与 `lifeprism.log` 同目录 |
| maxBytes | 500 * 1024（500KB） | 满足"只写入最大 500k"需求 |
| backupCount | 0 | 覆盖式：超过 500KB 时清空重新写，不保留备份文件 |
| encoding | utf-8 | 与现有 FileHandler 一致 |
| formatter | `TruncatingFormatter(_LOG_FORMAT)` | 复用现有 formatter，截断保护 2000 字符 |
| 启动行为 | 不清空，追加写入 | 保留上次启动后的同步日志，由 500KB 滚动自然淘汰 |

**改动点**：

1. **`lifeprism/utils/logger.py`** 新增 `setup_sync_logging(log_dir: Path)` 函数（约 15 行）：
   ```python
   def setup_sync_logging(log_dir: Path) -> None:
       """配置 sync 专用日志（RotatingFileHandler，覆盖式 500KB）"""
       from logging.handlers import RotatingFileHandler
       log_dir.mkdir(parents=True, exist_ok=True)
       sync_log = log_dir / "sync.log"
       handler = RotatingFileHandler(
           sync_log,
           maxBytes=500 * 1024,
           backupCount=0,
           encoding="utf-8",
       )
       handler.setFormatter(TruncatingFormatter(_LOG_FORMAT))
       # 给 lifeprism.sync logger 附加专用 handler
       sync_logger = logging.getLogger("lifeprism.sync")
       sync_logger.addHandler(handler)
       # propagate=True（默认），日志自动传播到 root logger
       # → 同时写入 sync.log + lifeprism.log + 控制台
   ```

2. **`lifeprism/config/settings_manager.py`** `_setup_logging` 末尾追加一行：
   ```python
   def _setup_logging(self) -> None:
       from lifeprism.utils.logger import setup_file_logging, setup_sync_logging
       setup_file_logging(self._lifeprism_data_path / "debug_logs")
       setup_sync_logging(self._lifeprism_data_path / "debug_logs")  # 新增
   ```

3. **sync_client.py / loop.py**：**无需改动**

**覆盖范围**：

- ✅ sync_client.py 全部日志（同步流程 + 冲突处理流程 + 错误重试）
- ✅ sync/ 目录下所有子模块（constants.py、hash_utils.py、heartbeat_manager.py、sync_config.py）
- ❌ loop.py 中 LLM 调用的通用日志（不区分消息类型，不在 sync.log 中）
  - 冲突处理 LLM 调用的**返回值**会通过 sync_client.py 的 `bus.send` 返回结果记录在 sync.log 中（如 "AI 合并超时"、"AI 返回空内容"、"AI 合并完成"）
  - LLM 调用过程中的工具调用细节日志（如 "工具调用：..."）不写入 sync.log

**验证方式**：

- 触发一次同步 → 检查 `sync.log` 是否包含 sync_client.py 的同步日志
- 同时检查 `lifeprism.log` 是否也有相同日志（验证 propagate）
- 模拟日志超 500KB → 检查 sync.log 是否被清空重写（覆盖式）
- 模拟冲突处理 → 检查 sync.log 是否包含 "冲突解决完成"、"AI 合并超时" 等关键日志

**决策原因**：

1. **零侵入业务代码**：利用 Python logging 层级传播，不需要在 sync_client.py 中切换 logger
2. **磁盘占用可控**：500KB 覆盖式滚动，总占用始终 ≤ 500KB，不会无限增长
3. **与全局日志并存**：sync.log 是 lifeprism.log 的子集，不是替代关系。用户既可单独查看 sync.log 快速定位同步问题，也可在 lifeprism.log 中看到全局上下文
4. **实现简单**：约 15 行新增代码 + 1 行调用，无外部依赖，复用现有 `TruncatingFormatter`
5. **冲突处理日志聚焦**：sync_client.py 中的冲突处理日志（超时/失败/成功/降级 keep_ours）是 sync.log 的核心内容，便于回溯冲突处理历史
