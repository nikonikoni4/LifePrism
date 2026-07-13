---
version: 1.0
created_at: 2026-07-13
updated_at: 2026-07-13
last_updated: 2026-07-13
abstract: 确定自定义记录数据表中自定义字段时间不进行时区转换，视为普通字符串原样存储和显示。同时确立未来方向：为动态表新增必填系统级 datetime 字段替代 created_at 用于日期筛选。
status: decided
---

# 自定义记录：自定义字段时间不转换 + 未来新增系统级 datetime 字段

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

在 UTC 时区迁移（m008/m009）的背景下，自定义记录模块存在两个关联问题：

1. **决策 A：自定义字段中的时间值是否需要做 UTC 转换？**

   自定义记录的数据表（`custom_<slug>`）中，自定义字段（`field_N`）可能包含 Agent 写入的时间字符串（如 `YYYY-MM-DD HH:MM:SS`）。这些字段是否需要像 `created_at` 一样做时区转换？

2. **决策 B（未来方向）：当前通过 `created_at` 做日期筛选是否合适？**

   当前 `query_entries` 使用 `created_at` 做 `WHERE created_at >= ? AND created_at <= ?` 的日期范围筛选。但 `created_at` 是记录创建时间，而非事件发生时间——用户创建的记录可能是过去某个时间的事件（如"上周三跑步 30 分钟"）。

   触发决策的直接原因：m009 迁移已发现遗漏了动态表 `custom_<slug>` 的 `created_at`/`updated_at` 迁移（记录在 [mood-and-custom-records-date-query-issues.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/known-limitations/mood-and-custom-records-date-query-issues.md)），在讨论修复方案时引出"为什么要用 created_at 做日期筛选"的深层问题。

### 讨论范围

本次决策覆盖：
1. 自定义字段中时间的处理策略（不转换 vs 识别并转换）
2. 当前 `created_at` 筛选的适用性和局限
3. 未来新增系统级 datetime 字段的方向（不做具体实现设计）

### 非讨论范围

- m010 迁移脚本的具体实现
- 新增 datetime 字段的详细 schema 设计
- `field_type` 枚举扩展的具体方案

### 模糊信息的明确定义

- **"自定义字段"**：指 `custom_record_fields` 定义的动态字段，运行时存储在 `custom_<slug>` 表以 `field_N` 命名的列中
- **"系统级字段"**：指 `id`、`created_at`、`updated_at` 及未来可能新增的 `event_time` 等由系统管理、非用户定义的字段
- **"不转换"**：指原样存储、原样显示，不做 `datetime(col, '-8 hours')` 等时区偏移

### 问题深度

决策 A 是架构原则决策，涉及：
- 系统字段（`created_at`）和用户数据字段（`field_N`）的职责边界
- 对"什么算时间数据"的定义

决策 B 是未来方向确定，为后续 m010 迁移和实施提供依据。

## 现状

### 决策 A 的相关事实

1. **自定义字段类型当前只有 `text`**：
   - Schema 定义 `field_type: str = Field(default="text")`
   - DDL 始终使用 `TEXT` 列类型
   - Spec 和 ADR 均确认 P1 仅 `text`
   - 未来计划扩展 `int` 和 `float`，均与时间无关

2. **自定义字段仅用于显示，不用于查询/筛选**：
   - 查询 API 只用 `created_at` 做时间筛选（[custom_record_aggregator.py:L413-L474](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/repository/aggregators/custom_record_aggregator.py#L413-L474)）
   - `WHERE created_at >= ? AND created_at <= ?` + `ORDER BY created_at DESC`
   - 自定义字段内容不做查询条件，不做排序键

3. **Agent 写入的日期格式天然支持排序**：
   - Agent 写入自定义字段的格式为 `YYYY-MM-DD HH:MM:SS`（本地时间显示格式）
   - 此格式字符串的字典序 = 时间序，排序列时结果正确
   - 无需额外转换即可支持排序

4. **识别并转换自定义字段中的时间存在风险**：
   - 无法可靠判断哪个 `field_N` 包含时间（字段名和 `field_type` 都不提供此信息）
   - 可能误转换非时间文本
   - 可能遗漏含时间的文本字段

5. **数据路径简单**：
   - 后端 DB → 前端展示（中间无需时间计算）
   - 不做聚合统计、不做时区比较、不做时间范围查询

### 决策 B 的相关事实

1. **当前日期筛选依赖 `created_at`**：
   - REST API 接收 `start_date`/`end_date`（`YYYY-MM-DD`），转 UTC 范围后查 `WHERE created_at >= ? AND created_at <= ?`
   - Agent Tool 同理，date_range 最终走同一查询方法

2. **`created_at` 语义不匹配事件时间**：
   - `created_at` = 记录被写入系统的时间
   - 用户想查询的是事件发生时间（如"1 月 3 号的运动记录"）
   - 两者可能不同（今天记录昨天的运动）

3. **系统级时间处理已标准化**：
   - `created_at`/`updated_at` 统一使用 UTC ISO 8601（`get_utc_now_iso()`）
   - 展示层通过 `utc_to_local_display()` 转为本地 `YYYY-MM-DD HH:MM:SS`
   - 转换基础设施（`build_utc_time_range`）已就绪

### 约束与风险

1. **m009 遗漏的影响**：动态表 `custom_<slug>` 的 `created_at` 尚未迁移，新旧数据混合时区不一致
2. **决策 B 需要在 m010 迁移之前确定**：如果新增 datetime 字段，m010 应一并处理动态表迁移 + 新增字段

## 可选方案

### 决策点 A：自定义字段中的时间如何处理

#### 方案 A：识别并转换为 UTC

根据 `custom_record_fields.field_type` 判断，对 `date`/`datetime` 类型字段做 UTC 转换。

**优势**
- 与系统时间处理策略一致
- 跨时区场景下时间语义正确

**劣势**
- 当前无 `date`/`datetime` 类型，需要新增类型支持
- 无法可靠识别 `text` 类型中包含的时间值
- 转换错误风险（误转换、漏转换）
- 增加系统复杂度，收益不明确

#### 方案 B：原样存储，不转换（选中）

将自定义字段视为用户输入的原始数据，不做任何时区转换。

**优势**
- 实现简单，无需新增逻辑
- 无识别错误风险
- 与当前数据路径一致（只显示不查询）
- `YYYY-MM-DD HH:MM:SS` 格式天然支持字典序排序

**劣势**
- 跨时区场景下，用户看到的时间可能与 UTC 时区预期不一致
- 未来如果需要按自定义字段时间做筛选，需要进行转换

### 决策点 B：是否继续使用 `created_at` 做日期筛选

#### 方案 A：继续用 `created_at`（当前状态）

**优势**
- 无需改动

**劣势**
- 语义错误（创建时间 ≠ 事件时间）
- 用户无法查询过去发生的事件（如果记录是后来创建的）

#### 方案 B：新增系统级 datetime 字段替代 `created_at`（选中）

在动态表 `custom_<slug>` 上新增必填的 datetime 字段：
- Agent 输入本地 `YYYY-MM-DD HH:MM:SS` → 格式校验 → 转 UTC ISO → 存储
- 查询时用此字段替代 `created_at` 做日期筛选
- 如果没有可写的时间，提示 Agent 输入当前时间

**优势**
- 语义正确（记录的是事件发生时间）
- 查询结果准确
- 与系统 UTC 策略一致

**劣势**
- 需要新增迁移
- 需要修改插入逻辑和查询逻辑
- Agent 需要额外提供时间信息

## 最终决策

### 决策 A：自定义字段时间不转换

选择 **方案 B：原样存储、不转换**。

自定义字段值是用户的原始输入数据，视为普通字符串处理。`created_at`/`updated_at` 等系统级字段保持 UTC 转换。

### 决策 B：未来新增系统级 datetime 字段

选择 **方案 B：新增必填系统级 datetime 字段**。

在动态表上新增 datetime 字段，替代 `created_at` 作为日期筛选的依据。

**字段设计要点**：
- 字段为必填
- Agent 输入格式为本地 `YYYY-MM-DD HH:MM:SS`
- 后端做格式校验（正则）
- 无可用时间时，提示 Agent 输入当前时间
- 存储时转换为 UTC ISO 8601（与 `created_at` 一致）
- 查询时用此字段做 `WHERE event_time >= ? AND event_time <= ?`

## 决策原因

### 决策 A：为什么自定义字段不转换

**核心原因**：自定义字段是"用户数据"，不是"系统时间"。

**判断逻辑**：

1. **职责分离**：
   ```
   created_at / updated_at  →  系统时间，需要 UTC 统一、需要查询、需要排序
   自定义字段 (field_N)     →  用户数据，只做展示，不需要查询、不需要转换
   ```
   `created_at` 转 UTC 有意义——它是系统基础设施。自定义字段的时间是"用户填的内容"，和用户写的一段文字里的"下午3点"没有本质区别——你不会去转换"下午3点"的时区。

2. **数据路径不经过时间逻辑**：
   - 前提：自定义字段时间不用于查询、筛选（由 `created_at` 或未来的 event_time 负责）
   - 前提：数据路径是后端 DB → 前端展示，中间不需要时间计算
   - 逻辑：前提成立 → 时间是普通字符串 → 无需时区转换

3. **Agent 写入的格式天然可用**：
   - `YYYY-MM-DD HH:MM:SS` 字符串的字典序 = 时间序
   - 如果未来需要排序，无需额外转换
   - 这是 ISO 格式的自然福利，而非刻意的时间处理

4. **转换的风险大于收益**：
   - 识别困难（`field_type` 只有 `text`）
   - 误转换风险
   - 未来扩展 `int`/`float` 也不涉及时间

**决策前提**（如果前提不成立，需重新决策）：
- 前提 1：自定义字段时间不用于系统级查询、筛选、聚合
- 前提 2：`field_type` 不引入 `date`/`datetime` 类型
- 前提 3：排序由 `YYYY-MM-DD HH:MM:SS` 格式的字典序保证（前提成立）
- 前提 4：不存在"跨时区用户查看自定义字段时间需要转换"的需求

**如果前提失效的重新决策条件**：
- 如果未来需要对自定义字段时间做查询 → 需要引入 `field_type=datetime` 并确定转换策略
- 如果 `field_type` 引入 `date`/`datetime` → 重新评估是否需要转换（取决于查询需求）
- 如果跨时区用户抱怨自定义字段时间显示不一致 → 考虑前端添加时区标注而非转换存储值

### 决策 B：为什么新增加 datetime 字段替代 `created_at`

**核心原因**：`created_at` 是"记录创建时间"，不是"事件发生时间"，语义不匹配。

**判断逻辑**：

1. **语义正确性**：
   - 当前：`created_at` = "用户什么时候创建了这条记录" → 用这个做"事件发生在哪天"的筛选是错的
   - 正确：event_time = "这个事件发生在什么时间" → 这是查询应该依据的字段

2. **必填的合理性**：
   - Agent 总能提供一个时间——最差就是当前时间
   - "没有可写的时间"不是跳过填写的理由，而是提示 Agent 用当前时间
   - 必填 + 格式校验保证了数据完整性

3. **数据流设计**：
   ```
   Agent 输入: "2026-07-13 14:30:00"  (本地 YYYY-MM-DD HH:MM:SS)
        ↓  后端格式校验（正则）
        ↓  转换为 UTC ISO 8601
   存储: "2026-07-13T06:30:00.000000+00:00"
        ↓  查询: WHERE event_time >= ? AND event_time <= ?
        ↓  展示: utc_to_local_display() → "2026-07-13 14:30:00"
   ```
   与 `created_at` 的处理流程完全一致。

**决策前提**：
- 前提 1：Agent 能够可靠地提供事件时间
- 前提 2：`YYYY-MM-DD HH:MM:SS` 格式校验足够防止错误输入
- 前提 3：m009 遗漏的 `created_at` 迁移在 m010 中一并处理

**如果前提失效的重新决策条件**：
- 如果 Agent 频繁提供错误时间 → 需要增强提示词或添加"从对话上下文推断时间"的逻辑
- 如果自定义记录的使用模式变为"很少需要时间筛选" → 字段可改为可选

## 后续影响

### 代码结构影响

1. **决策 A 无需代码修改**：自定义字段时间本来就是字符串处理，确认此策略即可

2. **决策 B 需要实施（后续 PR）**：
   - 动态表 DDL：新增 `event_time TEXT NOT NULL` 列
   - 插入逻辑：Agent Tool 接收本地 `YYYY-MM-DD HH:MM:SS`，格式校验 + 转 UTC
   - 查询逻辑：`WHERE event_time >= ? AND event_time <= ?` 替代 `created_at`
   - 迁移脚本 (m010)：新增字段 + 迁移动态表的 `created_at`/`updated_at`
   - Agent Tool 描述更新：提示 Agent 提供事件时间

### 测试影响

1. **格式校验测试**：`YYYY-MM-DD HH:MM:SS` 正确/错误格式
2. **跨时区边界测试**：本地日期边界 ≠ UTC 边界时的查询正确性
3. **必填约束测试**：Agent 不提供时间时的行为

### 文档影响

1. **更新已有文档**：
   - `docs/coding-rules/time-handling-rules.md`：明确"自定义字段不转换"的例外规则
   - `docs/known-limitations/mood-and-custom-records-date-query-issues.md`：补充决策变更

2. **关联历史 bug**：
   - `docs/history-bugs/2026-07-13-timeline-custom-block-date-query-datetime-field.md`：Custom Block 的 bug 修复思路与本次决策一致——系统字段做转换，用户字段不转换

### 长期维护影响

1. **新增自定义字段类型时的规则**：
   - `text`/`int`/`float` → 不做时间转换
   - 只有系统级字段（`created_at`/`updated_at`/`event_time`）才做 UTC 转换
   - 清晰的边界：系统字段 ≠ 用户字段

2. **代码审查检查点**：
   - 禁止对自定义字段执行 `datetime(col, '-8 hours')` 等转换
   - 新增系统级时间字段时，必须确认转换策略
