---
version: 1.0
created_at: 2026-07-12
updated_at: 2026-07-12
last_updated: 2026-07-12
abstract: 确立时间转换职责的分层架构——数据层只返回 UTC ISO，LLM 工具 execute 层负责输入转换，工具函数内部显式转换输出。否决装饰器自动转换方案。
status: decided
---

# 时间转换职责分层架构

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

UTC 时区迁移（见 [2026-07-12-migrate-to-utc-timezone](.\2026-07-12-migrate-to-utc-timezone.md)）完成后，数据库统一存储 UTC ISO 8601。但"在哪里做 UTC ↔ 本地时间转换"成为了一个需要明确决策的架构问题。

这个问题在讨论中暴露了三个具体痛点：

1. **dreaming() 复用 LLM 工具的混淆**：`dreaming()` 定时任务为了代码复用，调用了为 AI 设计的 LLM 工具（如 `query_user_activity_summary`）。但 LLM 工具内部有本地↔UTC 转换逻辑，dreaming 不是 AI 调用，却要遵守 AI 的接口契约，职责不清。
2. **"一层层过滤"的担忧**：LLM 工具输入时转 UTC 查库，输出时又转本地给 AI，AI 再输入本地时间，工具又转 UTC 查库。这种来回转换让用户质疑是否应该直接给 AI UTC 时间。
3. **Repository 返回格式决策的动摇**：用户一度想让 Repository 层根据调用方返回不同格式（增加 `return_local_time` 参数），因为"修改点较多且容易出错"。

### 讨论范围

- 时间转换在哪个层级进行：数据层、工具函数层、execute 方法层
- LLM 工具的输入输出时间格式
- 定时任务（dreaming）调用 LLM 工具时的转换职责
- 是否采用装饰器自动转换

### 非讨论范围

- 数据库存储格式（已在 [2026-07-12-migrate-to-utc-timezone](.\2026-07-12-migrate-to-utc-timezone.md) 决定为 UTC ISO）
- 前端时间处理（前端就地转换，见 Issue #21-#26）
- 具体的代码实现细节（见 Issue #27-#31）

### 模糊信息的明确定义

- **对外时间**：面向用户和面向 AI 的时间，格式为本地 `YYYY-MM-DD HH:MM:SS`（无时区标识）
- **内部时间**：数据库存储、模块间传输的时间，格式为 UTC ISO 8601（带时区标识）
- **就地转换**：转换发生在消费点（组件/工具内部），不在中间模块做转换
- **execute 层**：指 LLM 工具的 `execute` 方法，是 AI 调用工具的入口

### 问题深度

这是涉及**架构原则和长期维护**的深层决策：
- 影响 LLM 工具的接口契约（难以回退）
- 影响所有时间相关工具的代码结构
- 影响未来新增工具的开发模式

## 现状

### 当前实现

**LLM 工具（`lifeprismsystem.py`）**：
- `_parse_local_time()`：在工具函数内部将 AI 输入的本地时间转 UTC
- `_utc_to_local()`：在工具函数内部将查询结果的 UTC 转本地给 AI
- 工具函数既做转换又做查询，职责混合

**dreaming() 定时任务**：
- 硬编码本地时间 `f"{date} {DAILY_START_HOUR}"`（如 `2026-07-12 04:00:00`）
- 调用 `query_user_activity_summary`（LLM 工具），工具内部转 UTC 查库
- 复用了为 AI 设计的工具，但 dreaming 不是 AI 调用

**Repository 层**：
- 直接返回 UTC ISO 数据，不做转换
- 但有 5 处遗留 bug（用本地时间字符串查 UTC 时间戳字段，见 Issue #30）

### 现有问题

1. **职责不清**：LLM 工具既做转换又做查询，dreaming 复用时混淆
2. **转换分散**：`_utc_to_local` 在 `lifeprismsystem.py` 被调用 10+ 次，分散在各处
3. **格式不一致**：`custom_records_tool.py` 和 `session_query.py` 未做输出转换，AI 看到的是 UTC 时间
4. **静默错误风险**：如果上游转换有 bug，Repository 层不报错，查询结果静默错误

### 不能忽略的约束

1. **AI 输入格式不可控**：AI 可能输出各种格式（本地 `YYYY-MM-DD HH:MM:SS`、带偏移 ISO、`Z` 后缀等），转换函数需要兼容
2. **时间字段用途多样**：同一字段可能用于显示（需转本地）或计算（需保持 UTC），只有工具函数知道字段用途
3. **返回类型多样**：Repository 返回 `list[dict]`、`tuple(list[dict], int)`、`dict` 等，难以统一处理

## 可选方案

### 方案 A：LLM 工具内部显式转换（推荐）

工具函数只接收 UTC ISO，execute 方法负责输入转换（本地→UTC），工具函数内部在格式化输出时显式调用 `utc_to_local_display` 转换显示用字段。

**优势**

- 转换逻辑在显式调用处，可调试性好
- 工具函数知道字段用途（显示 vs 计算），能精确控制哪些字段转
- 字段改名时会 `KeyError` 立即暴露问题
- 改动集中在一个文件（`lifeprismsystem.py`），符合"拆分大任务"原则
- 与已有 ADR 决策一致

**劣势**

- 每个工具都要手动写转换代码，有 10+ 处重复
- 新增工具时可能遗漏转换

### 方案 B：装饰器 + 中间层包装

新建 `repository_wrappers.py`，为每个 LLM 工具调用的 Repository 查询创建包装函数，用装饰器自动转换返回数据中的时间字段。

**优势**

- 转换逻辑集中，减少重复代码
- LLM 工具代码更简洁

**劣势**

- 时间字段有显示和计算两种用途，装饰器无法区分，会误转计算用字段
- 字段改名时装饰器静默跳过，不报错
- 返回类型多样（list、tuple、JSONL 文件等），装饰器难以统一覆盖
- 日期字段（`YYYY-MM-DD`）可能被误转时区
- 转换逻辑隐藏在装饰器中，调试困难
- 引入冗余中间层，只做透传 + 转换

### 方案 C：Repository 层增加 `return_local_time` 参数

Repository query 方法增加参数，调用方选择返回本地还是 UTC。

**优势**

- LLM 工具不需要自己转输出

**劣势**

- Repository 职责变重，违反"数据层只返回 UTC"原则
- 返回类型不确定（有时 UTC 有时本地），破坏类型一致性
- 需要透传参数到所有查询函数，修改量大
- 非数据层职责扩散

## 演进历史

本次决策经历了多次动摇和调整：

| 版本 | 方案 | 解决的问题 | 引入的新问题 |
| ---- | ---- | ---------- | ------------ |
| v1 | LLM 工具内部转换（`_parse_local_time` + `_utc_to_local`） | 初步解决 AI 输入输出时区问题 | 职责混合，dreaming 复用混淆 |
| v2 | 考虑 Repository 层增加 `return_local_time` 参数 | 减少工具层转换代码 | 违反数据层职责单一，修改量大，用户动摇 |
| v3 | 考虑装饰器 + 中间层包装 | 集中转换逻辑，减少重复 | 静默失败、字段用途差异、返回类型多样，审查后否决 |
| v4 | LLM 工具内部显式转换（方案 A，最终） | 回到 v1 思路，但职责更清晰：execute 层负责输入转换，工具函数负责输出转换 | 有少量重复代码，但可接受 |

用户在 v2 和 v3 阶段都有明显动摇：
- v2 阶段：用户说"我有点动摇了，因为当前大模型的工具调用改动较多且容易出错"
- v3 阶段：用户主动提出装饰器方案，要求"派出一个 agent 审查是否合理"
- v4 阶段：审查报告指出装饰器风险后，用户确认回到方案 A

## 最终决策

选择**方案 A：LLM 工具内部显式转换**。

具体分层职责：
- **数据层（Repository）**：只返回 UTC ISO，不转换
- **execute 方法层**：负责输入转换（本地 `YYYY-MM-DD HH:MM:SS` → UTC ISO）
- **工具函数层**：接收 UTC ISO 查库，内部在格式化输出时显式调用 `utc_to_local_display` 转换显示用字段
- **dreaming**：硬编码本地时间后马上就地转 UTC ISO（用 `local_to_utc_iso(build_local_datetime(...))`），然后调用工具函数

## 决策原因

### 1. 字段用途差异是核心约束

时间字段不仅用于显示，还用于计算。例如 `_category_stats` 函数用 `start_time`/`end_time` 做时间区间截断（[lifeprismsystem.py:221-238](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/lifeprismsystem.py#L221-L238)）。如果装饰器提前转成本地 `YYYY-MM-DD HH:MM:SS`，计算时还要重新解析，徒增复杂度和出错点。

只有工具函数知道字段用途，所以转换必须在工具函数内部显式进行。

### 2. 静默失败比显式报错更危险

字段改名时：
- 装饰器方案：`time_fields=["start_time"]` 中的字段在新数据中不存在，装饰器静默跳过，AI 收到 UTC ISO 格式，格式不一致但无报错
- 显式调用方案：工具函数中 `log["start_time"]` 会直接 `KeyError`，立即暴露问题

### 3. 返回类型多样难以统一覆盖

Repository 返回 `list[dict]`、`tuple(list[dict], int)`、`dict` 等，`session_query.py` 还直接读 JSONL 文件返回自定义结构。装饰器无法统一覆盖这些异构数据源。

### 4. 与已有决策一致

已有 ADR（[2026-07-12-migrate-to-utc-timezone](.\2026-07-12-migrate-to-utc-timezone.md)）和 `time-handling-rules.md` 确立了"内外分离"原则：组件/模块内部使用本地时区时，在传出去的那一刻就地转为 UTC ISO 8601。方案 A 与此一致。

### 5. 改动范围可控

方案 A 的改动集中在 `lifeprismsystem.py`、`custom_records_tool.py`、`session_query.py` 三个文件，符合"拆分大任务"原则。不需要新建中间层，不需要改 Repository 层。

## 后续影响

### 代码层面

- **新增 LLM 工具时**：需要在 execute 方法开头调用 `local_to_utc_iso` 转换输入，在格式化输出时调用 `utc_to_local_display` 转换显示字段
- **新增 Repository 查询时**：不需要做任何时间转换，只返回 UTC ISO
- **Issue #27-#31** 的实施基于此决策

### 开发规范

- `docs/coding-rules/time-handling-rules.md` 已有"内外分离"原则，本决策是其具体应用
- 新增工具开发时，参考 `lifeprismsystem.py` 的 execute 层转换模式

### 风险和缓解

**主要风险**：
1. **遗漏转换**：新增工具时可能忘记在 execute 层或输出格式化时做转换
   - 缓解：代码审查 checklist 中增加"时间字段是否转换"检查项
2. **AI 输入格式不可控**：AI 可能输出非标准格式
   - 缓解：`local_to_utc_iso` 函数兼容多种格式（`YYYY-MM-DD HH:MM:SS`、带偏移 ISO、`Z` 后缀）

### 复盘事项

- Issue #28 实施后，验证转换是否正确覆盖所有已注册工具
- 后续如果新增非 LLM 调用路径（如 API 层直接调 Repository），确认是否需要类似的转换策略
