---
version: 1.0
created_at: 2026-07-13
updated_at: 2026-07-13
last_updated: 2026-07-13
abstract: 确定前端日期到 UTC 时间范围的转换边界位置，以及单表、聚合查询的参数传递方式。核心决策：组件内转换，聚合查询传 date + UTC 范围。
status: decided
---

# 前端日期到 UTC 时间范围的转换边界与查询参数传递策略

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

系统中存在多个 API 需要按日期查询数据，但数据库表结构不统一：
- 部分表有独立 `date` 字段（如 `todo_list`、`diary`）
- 部分表只有 `start_time/end_time` datetime 字段（如 `user_app_behavior_log`、`timeline_custom_block`）

现有问题：
1. 前端日期（`YYYY-MM-DD`）与 UTC datetime 字段的转换位置不明确（组件内 vs API 层）
2. 查询只有 datetime 字段的表时，转换逻辑分散在多个 API 文件中
3. 聚合查询同时涉及有 date 字段和只有 datetime 字段的表，参数传递策略未定义

触发决策的直接原因：
- Timeline Custom Block API 修复时发现"日期查询 datetime 字段表"导致查询失败
- Timeline Stats API 返回空数据，根因是字符串拼接时间而非正确的 UTC 转换
- 需要系统性解决此类问题，而非单点修复

### 讨论范围

本次决策覆盖：
1. **转换边界位置**：前端日期 → UTC 时间范围的转换应在哪一层进行
2. **查询场景分类**：单表（有 date）、单表（只有 datetime）、聚合（混合表）的参数传递策略
3. **混合查询处理**：聚合 API 同时查询有 date 和只有 datetime 的表时，如何传参

本次决策需要回答的关键问题：
- Q1：转换位置是组件内还是 API 层？
- Q2：单表查询只有 datetime 字段时，前端传什么参数？
- Q3：聚合查询混合表时，前端传什么参数？
- Q4：后端如何从 UTC 时间范围反向解析本地日期？

### 非讨论范围

- 数据库表结构重构（如为 `user_app_behavior_log` 添加 `date` 字段）
- 时区配置机制（已由 `user_timezone` 配置完成）
- 后端 `build_utc_time_range()` 函数的实现细节

### 模糊信息的明确定义

- **"就近转换"**：在本文中指"前端负责日期 → UTC 转换，后端不处理时区"，而非"在最接近数据源的地方转换"
- **"组件内转换"**：指在日期选择器的 `onChange` 回调中转换，而非在通用 DatePicker 组件内部转换
- **"聚合查询"**：指单个 API 同时查询多个不同结构的表（有 date + 只有 datetime）
- **"单表查询"**：指单个 API 只查询一个表，或查询多个结构相同的表（都只有 datetime）

### 问题深度

这是一个架构原则决策，涉及：
- 系统分层职责（前端组件 vs API 层 vs 后端）
- 数据格式纯净性（系统内部是否允许本地时间格式渗透）
- 长期维护成本（代码重复 vs 统一封装）

不只是单个 API 的修复，而是确定一套通用规则。

## 现状

### 当前实现状态

| API | 表结构 | 前端参数 | 转换位置 | 状态 |
|-----|--------|---------|---------|------|
| Todo API | 有 `date` 字段 | `date=YYYY-MM-DD` | 无需转换 | ✅ 正常 |
| Diary API | 有 `date` 字段 | `date=YYYY-MM-DD` | 无需转换 | ✅ 正常 |
| Custom Block API | 只有 datetime | `start_time/end_time`（UTC） | API 层转换 | ✅ 已修复 |
| Category Update Logs API | 只有 datetime | `start_time/end_time`（UTC） | API 层转换 | ✅ 已修复 |
| Timeline Stats API | 只有 datetime | `date=YYYY-MM-DD` | 后端字符串拼接 | ❌ 查询失败 |
| Timeline Overview API | 只有 datetime | `date=YYYY-MM-DD` | 后端字符串拼接 | ❌ 查询失败 |
| Report API（日/周/月报） | 混合表 | `date=YYYY-MM-DD` | 后端 `build_utc_time_range()` | ✅ 正常 |

### 已知事实

1. **前端日期来源固定**：
   - 只能来自浏览器 `input[type="date"]` 或前/后一天按钮
   - 格式由 `formatDateToYYYYMMDD()` 强制保证为 `YYYY-MM-DD`
   - 不存在手动输入或外部传入错误时间戳的风险

2. **转换代码重复度低**：
   - 当前只有 2 个 API 需要日期 → UTC 转换（Custom Block、Category Logs）
   - 转换代码共 14 行，分散在 2 个 API 文件中
   - 不存在"一个 DatePicker 组件被大量复用"的场景

3. **UTC 时间可反向解析为本地日期**：
   - ISO 8601 格式自带时区信息：`"2026-07-12T22:00:00.000Z"`
   - 后端可通过 `datetime.fromisoformat().astimezone(user_tz).date()` 解析
   - 解析结果准确（测试用例：`"2026-07-12T22:00:00Z"` → 本地 `2026-07-13`）

### 约束与风险

1. **工程复用性不存在**：
   - 没有统一的 DatePicker 组件封装
   - 日期查询分散在不同页面，无高频复用场景
   - "组件层封装转换逻辑"无法降低代码重复

2. **Timeline Stats 不是聚合查询**：
   - 只查询 `user_app_behavior_log` 单表
   - 虽然调用路径涉及多个模块（builder/service），但数据源单一
   - 应归类为"单表 datetime 查询"

3. **聚合查询存在冲突**：
   - 如果组件只输出 `{ start_time, end_time }`，则无法传 `date` 给聚合 API
   - 如果组件只输出 `date`，则单表 datetime 查询需要在 API 层转换（违反"组件内转换"原则）

## 可选方案

### 决策点 1：转换位置

#### 方案 A：API 层转换

```typescript
// 组件：输出本地日期
<DatePicker onChange={(date) => setSelectedDate(date)} />

// API 层：转换为 UTC 范围
async getStats(date: string) {
  const start = toISOStringUTC(new Date(`${date}T00:00:00`));
  const end = toISOStringUTC(new Date(`${date}T23:59:59.999`));
  return fetch(`...?start_time=${start}&end_time=${end}`);
}
```

**优势**
- 组件通用，可同时用于"有 date 字段"和"只有 datetime"的场景
- 实施成本低（Custom Block 已采用此方案）
- 覆盖所有场景（不依赖组件是否存在）

**劣势**
- 转换逻辑分散在多个 API 文件（当前 2 处，共 14 行）
- 本地时间格式（`YYYY-MM-DD`）渗透到系统内部（API 层及以下）
- 违反"系统内部保持纯净"原则

#### 方案 B：组件内转换

```typescript
// 组件：转换后输出 UTC 范围
<DatePicker 
  onChange={(date) => {
    const start = toISOStringUTC(new Date(`${date}T00:00:00`));
    const end = toISOStringUTC(new Date(`${date}T23:59:59.999`));
    setTimeRange({ start_time: start, end_time: end });
  }}
/>

// API 层：直接使用
async getStats(start_time: string, end_time: string) {
  return fetch(`...?start_time=${start_time}&end_time=${end_time}`);
}
```

**优势**
- 系统内部只有 UTC ISO 8601 格式（API 层及以下保持纯净）
- 转换逻辑集中在组件 `onChange` 回调（虽然无法消除重复）
- 明确的转换边界：组件输出的数据即为系统内部格式

**劣势**
- 组件失去通用性（无法同时用于"有 date 字段"的场景）
- 对聚合查询支持不足（需要同时输出 date + UTC 范围）
- 当前实施成本高（Custom Block 已采用 API 层转换，需要重构）

### 决策点 2：单表查询参数

#### 场景 2.1：单表 - 有 date 字段（无争议）

**方案**：前端传 `date=YYYY-MM-DD`，后端 `WHERE date = ?`

无需转换，所有方案一致。

#### 场景 2.2：单表 - 只有 datetime 字段

**方案 A**：前端传 `start_time/end_time`（UTC ISO）

与决策点 1 的"组件内转换"对应。

**方案 B**：前端传 `date`，后端调用 `build_utc_time_range()` 转换

与决策点 1 的"API 层转换"对应，但进一步延后到后端。

### 决策点 3：聚合查询参数（混合表）

#### 方案 A：传 date，后端分别处理

```typescript
// 前端：保持简单
onChange={(date) => setSelectedDate(date)}

// 后端：根据表结构选择
def get_report(date: str):
    todos = todo_repo.get_by_date(date)  # 有 date 字段
    start_time, end_time = build_utc_time_range(date)
    behaviors = behavior_repo.get_by_time_range(start_time, end_time)
```

**优势**
- 前端简单，无需知道后端表结构
- 后端灵活，可根据每个表选择合适的查询方式

**劣势**
- 后端需要调用 `build_utc_time_range()` 转换
- 违反"就近转换"原则（前端知道时区，应该前端转）

#### 方案 B：传 date + UTC 范围

```typescript
// 前端：同时输出两种格式
onChange={(date) => {
  const start_time = toISOStringUTC(...);
  const end_time = toISOStringUTC(...);
  setQueryParams({ date, start_time, end_time });
}}

// 后端：分别使用
def get_report(date: str, start_time: str, end_time: str):
    todos = todo_repo.get_by_date(date)
    behaviors = behavior_repo.get_by_time_range(start_time, end_time)
```

**优势**
- 符合"就近转换"原则（前端负责时区转换）
- 后端逻辑简单，直接使用参数

**劣势**
- 参数冗余（date 和 UTC 范围包含相同信息）
- 前端需要知道后端是聚合查询

#### 方案 C：完全使用 date（重构表结构）

为所有表添加 `date` 字段，统一用 `WHERE date = ?` 查询。

**优势**
- 查询简单高效，可建立日期索引

**劣势**
- 需要数据库迁移，成本高
- 维护两份时间数据（date + datetime）
- 本次不考虑此方案

## 最终决策

### 决策 1：转换位置 - 组件内转换

选择 **方案 B：组件内转换**。

### 决策 2：单表查询参数

| 表结构 | 前端输出 | API 参数 |
|--------|---------|---------|
| 有 date 字段 | `date` | `date` |
| 只有 datetime | `start_time/end_time` | `start_time/end_time` |

### 决策 3：聚合查询参数 - 传 date + UTC 范围

选择 **方案 B：传 date + UTC 范围**。

## 决策原因

### 决策 1：为什么选择组件内转换

**核心原因**：系统内部应保持纯净，不让用户视角的数据（本地日期）渗透进来。

**判断逻辑**：
1. **工程复用性评估**：
   - 前提：如果存在大量日期查询需要转换，且 DatePicker 组件被高频复用，则 API 层转换可减少代码重复
   - 实际调查结果：只有 2 个 API 需要转换，无统一 DatePicker 组件
   - 结论：工程复用性不存在，API 层转换的"便利性"理由不成立

2. **架构清晰性**：
   - 组件边界 = 转换边界：用户交互层输出本地日期，组件 `onChange` 回调转换为 UTC，系统内部全程 UTC
   - API 层及以下不需要知道"本地日期"概念
   - 清晰的职责分离

3. **可预测性**：
   - API 函数签名明确：`getStats(start_time: string, end_time: string)`，而非 `getStats(date: string)`
   - 调用方一眼看出参数是 UTC 时间范围，而非需要转换的本地日期

**依据信息**：
- Subagent 调查报告：只有 2 个 API 需要转换，14 行代码重复
- 用户明确表达："不能让本地时间干扰内部系统，让内部系统保持纯净是我想要达到的目的"
- 前端代码确认：日期来源固定，格式由浏览器保证，无错误输入风险

**决策前提**（如果前提不成立，需重新决策）：
- 前提 1：日期查询转换的需求量不大（<= 5 个 API）
- 前提 2：不存在统一的 DatePicker 组件被大量复用
- 前提 3：架构优先级高于代码重复（14 行重复可接受）

**如果前提失效的重新决策条件**：
- 如果未来需要转换的 API 超过 10 个，且转换逻辑完全一致 → 考虑封装 `dateToUTCRange()` 工具函数
- 如果创建了统一的 DatePicker 组件并被广泛复用 → 考虑在组件内部封装转换（而非 `onChange` 回调）
- 如果系统演进为"前端只负责展示，时区完全由后端处理" → 考虑 API 层或后端转换

### 决策 2：为什么单表 datetime 查询传 UTC 范围

**原因**：与决策 1 一致，组件内转换后，API 参数自然为 UTC 时间范围。

**语义清晰性**：`start_time/end_time` 参数名明确表示这是时间范围，而非日期。

### 决策 3：为什么聚合查询传 date + UTC 范围

**核心原因**：平衡"就近转换"原则和后端灵活性。

**判断逻辑**：
1. **后端能否从 UTC 时间范围反向解析本地日期？**
   - 前提：ISO 8601 格式自带时区信息
   - 验证：`datetime.fromisoformat("2026-07-12T22:00:00Z").astimezone(user_tz).date()` → `2026-07-13`（正确）
   - 结论：技术上可行

2. **是否只传 UTC 范围（方案 D，未列入可选方案）？**
   - 如果只传 `start_time/end_time`，后端需要解析时区转换为本地日期
   - 解析依赖 `user_timezone` 配置，增加复杂度
   - 不如直接传 `date`，让后端根据表结构选择使用哪个参数

3. **是否只传 date（方案 A）？**
   - 如果只传 `date`，后端需要调用 `build_utc_time_range()` 转换
   - 违反"就近转换"原则（前端知道时区，却让后端转换）
   - 但前端无需知道后端是否是聚合查询，接口更简单

4. **最终选择传 date + UTC 范围（方案 B）**：
   - 前端：符合"就近转换"，一次转换提供两种格式
   - 后端：灵活选择，有 date 字段的表用 `date`，只有 datetime 的表用 `start_time/end_time`
   - 代价：参数冗余（date 和 UTC 范围包含相同信息）

**依据信息**：
- 用户判断："如果是 +8 时区，2026-07-13 → 2026-07-12T22:00:00，这个能否从 start_time 中解析正确的日期呢？"
- 技术验证：Python `datetime` 库支持时区解析，结果正确
- 工程考虑：参数冗余可接受，换取后端逻辑清晰

**决策前提**（如果前提不成立，需重新决策）：
- 前提 1：前端日期来源可靠（浏览器 `input[type="date"]` 保证格式）
- 前提 2：用户不会手动构造错误的 UTC 时间范围
- 前提 3：参数冗余不会导致前后端数据不一致（date 和 UTC 范围必须对应同一天）

**如果前提失效的重新决策条件**：
- 如果发现"date 和 UTC 范围不一致"的 bug（如前端传错参数） → 改为只传 UTC 范围，后端统一解析
- 如果参数冗余导致接口复杂度显著增加 → 改为只传 date（方案 A），后端负责转换
- 如果前端存在"非日期选择器"的输入方式（如直接传时间戳） → 重新评估"过度考虑"的判断

**当前判断"过度考虑"的依据**：
- Subagent 确认：日期只能来自 `input[type="date"]` 或前/后一天按钮
- 格式化函数 `formatDateToYYYYMMDD()` 强制标准化输出
- 错误风险极低（页面崩溃 > 传递错误参数）

## 后续影响

### 代码结构影响

1. **需要修改的文件**：
   - Timeline Stats API：`timeline/api.ts`（前端）+ `timeline_api.py`（后端 API）+ `timeline_service.py`（Service）+ `timeline_builder.py`（Builder）
   - Timeline Overview API：同上
   - 其他可能受影响的 API（待排查）

2. **修改模式**：
   - 前端：在 API 调用前转换 `date → { start_time, end_time }`
   - 后端 API 层：参数从 `date: str` 改为 `start_time: str, end_time: str`
   - 后端 Service/Builder：删除字符串拼接逻辑（`f"{date} 00:00:00"`），直接使用 UTC 参数

3. **聚合查询修改**（如 Report API）：
   - 前端：传 `{ date, start_time, end_time }`
   - 后端：有 date 字段的表用 `date`，只有 datetime 的表用 `start_time/end_time`

### 测试影响

1. **单元测试**：
   - 需要更新测试用例，改为传 UTC 时间范围
   - 验证跨时区边界的查询（本地日期边界 ≠ UTC 边界）

2. **集成测试**：
   - 验证 Timeline Stats/Overview 返回正确数据
   - 验证聚合查询同时使用 date 和 UTC 范围

### 文档影响

1. **更新已有文档**：
   - `docs/coding-rules/time-handling-rules.md`：明确"组件内转换"规则
   - `docs/history-bugs/2026-07-13-timeline-custom-block-date-query-datetime-field.md`：标注"已采用组件内转换"

2. **新增文档**：
   - 本决策文档（ADR）
   - 前端 API 层转换示例（代码注释或 README）

### 长期维护影响

1. **新增 API 时的规范**：
   - 查询有 date 字段的表：前端传 `date`
   - 查询只有 datetime 的表：前端在组件 `onChange` 中转换，传 `start_time/end_time`
   - 聚合查询（混合表）：前端传 `date + start_time/end_time`

2. **代码审查检查点**：
   - 禁止在 API 层或后端用 `f"{date} 00:00:00"` 拼接时间字符串
   - 禁止在后端调用 `build_utc_time_range()`（聚合查询除外）
   - 前端日期选择器的 `onChange` 必须包含时区转换逻辑

3. **潜在重构方向**：
   - 如果转换逻辑重复超过 5 处，封装 `dateToUTCRange()` 工具函数
   - 如果创建统一 DatePicker 组件，在组件内封装转换
   - 如果表结构统一为都有 `date` 字段，简化为只传 `date`

### 需要后续验证的事项

1. **Timeline Stats 修复后性能验证**：
   - 查询结果是否完整（不再返回空数据）
   - 查询速度是否可接受（datetime 字段无索引）

2. **聚合查询参数冗余的实际影响**：
   - 是否存在 `date` 和 `start_time/end_time` 不一致的 bug
   - 参数传递是否增加了接口复杂度

3. **组件内转换的代码重复度**：
   - 如果重复逻辑超过 10 处，是否需要重新评估封装策略

4. **前端日期来源假设的持续验证**：
   - 是否始终只能来自日期选择器
   - 是否出现"手动构造时间戳"的新需求
