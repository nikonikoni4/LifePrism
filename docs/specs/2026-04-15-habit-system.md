---
version: 1.1
created_at: 2026-04-15
updated_at: 2026-04-19
last_updated: 新增习惯链条Timeline节点时间计算规则
abstract: 习惯系统规格文档，定义基于习惯堆叠心理学的习惯养成系统，包含锚点机制、等级制挑战系统、打卡与补签、状态流转、链条Timeline时间计算等核心功能的业务规则和技术契约
id: habit-system-v1
title: 习惯系统
status: draft
module: habit
sourc_spec: D:\desktop\软件开发\liferpism多余文档\docs_old\prd\功能需求\习惯系统
related_plan: docs/superpowers/plans/2026-04-19-habit-chain-timeline-trigger-time.md
code_scope:
  - lifeprism/server/api/habit_api.py
  - lifeprism/server/services/habit_service.py
  - lifeprism/server/services/habit_stats_service.py
  - lifeprism/server/services/habit_chain_service.py
  - lifeprism/server/providers/habit_provider.py
  - lifeprism/server/providers/habit_challenge_provider.py
  - lifeprism/server/providers/habit_checkin_provider.py
  - lifeprism/server/providers/habit_chain_provider.py
contract_refs:
  - lifeprism/server/schemas/habit_schemas.py
---

# 习惯系统

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建spec初稿，从旧PRD迁移并核对代码实现 |
| 1.1 | 新增习惯链条Timeline节点时间计算规则 |

## Overview

习惯系统是基于习惯堆叠心理学理论的习惯养成系统，通过已养成的旧习惯（锚点）来触发和养成新习惯。

核心特点：
- 锚点机制：新习惯依附于现实锚点（已有习惯），而非理想状态
- 等级制挑战：采用0-4级渐进式等级系统，而非简单的成功/失败二元判定
- 历史记录：保留完整的习惯养成历史，包括升级、失败等挑战记录
- 心理关怀：没有"失败"，只有"暂时没有实现"；失败后可选择重新开始或暂停

## Scope

### 包含功能

1. 习惯管理：创建、编辑、删除、暂停、恢复习惯
2. 挑战系统：基于等级和频率的动态挑战参数计算，自动升降级
3. 打卡功能：今日打卡、取消打卡、补签（滚动7天窗口）
4. 统计展示：Streak连续天数、今日概览、每周完成率、热力图
5. 习惯链条：展示习惯之间的锚点依赖关系
6. 价值关联：习惯可关联Mind Space中的价值和承诺

### 不包含功能

1. AI分析与智能建议（V2规划）
2. 单个习惯的完成率趋势详情（V2规划）
3. 本周/本月高光提示（V2规划）
4. 地点/状态变化的自动触发（需要额外的传感器支持）

## Core Behavior

### 1. 锚点哲学

新习惯的养成应该以已有习惯为锚点，而非理想状态。

锚点类型：
- 时间锚点：固定时间触发（如7:00起床、12:00午饭）
- 事件锚点：前置事件触发（如吃完早饭后、洗完澡后）
- 场景锚点：地点/状态变化触发（如到公司后、回家后）

注：三种类型是概念上的区分，后端实现不特别区分。

### 2. 习惯分级系统

采用等级制（0-4级）而非简单的成功/失败二元判定。

| 等级 | 名称 | 含义 |
|------|------|------|
| 0 | 萌芽 | 刚开始尝试 |
| 1 | 生根 | 初步建立 |
| 2 | 成长 | 逐渐稳固 |
| 3 | 稳固 | 已成为习惯 |
| 4 | 根深蒂固 | 长期稳定 |

升降级规则：
- 升级：挑战到达endDate且达标时升级（level +1，lv4维持4）
- 失败：挑战未达标时记为failed，等级不变，streakBase归零
- 失败后处理：用户二选一（重新开始当前挑战 / 暂停习惯）

### 3. 挑战参数计算

挑战参数按"等级 × 频率"动态计算。

默认挑战配置（基线为按周配置）：

| 等级变化 | 挑战周数 | daily等价总天数 | daily最低完成天数（85%） |
|----------|----------|------------------|---------------------------|
| 0 → 1 | 2周 | 14天 | 12天 |
| 1 → 2 | 3周 | 21天 | 18天 |
| 2 → 3 | 4周 | 28天 | 24天 |
| 3 → 4 | 8周 | 56天 | 48天 |
| 4维持 | 12周 | 84天 | 72天 |

计算公式：`requiredCompletions = ceil(challengeWeeks × weeklyDays × 0.85)`

其中weeklyDays由频率决定：
- daily: 7天/周
- weekdays: 5天/周
- weekend: 2天/周
- custom: specificDays.length天/周

### 4. 状态流转

习惯只有两种状态：active（活跃中）和paused（暂停中）。

**习惯状态流转**：
- 创建习惯 → active
- active → paused（触发条件：挑战失败后用户选择暂停 / 手动暂停）
- paused → active（触发条件：用户恢复习惯）

**挑战状态流转**（单向，不可逆）：
- in_progress → succeeded（触发条件：endDate到达且completedCount >= requiredCompletions）
- in_progress → failed（触发条件：数学上不可能达标，用户确认失败）
- in_progress → cancelled（触发条件：手动暂停习惯 / 修改等级或频率）

说明：
- succeeded和failed的挑战作为历史记录保留
- cancelled的挑战不作为历史记录
- 挑战状态一旦离开in_progress即终结，后续操作创建新挑战

关键行为：
- 创建习惯：自动创建首个挑战（in_progress）
- 挑战成功：endDate到达且达标，自动创建下一等级挑战，新挑战从当天开始
- 挑战失败：不可能达标时触发，用户选择重新开始或暂停
- 手动暂停：当前挑战标记为cancelled，streakBase归零
- 恢复习惯：创建同等级新挑战，streakBase=0
- 修改等级：取消当前挑战，创建新等级挑战，继承当前Streak为streakBase
- 修改频率：取消当前挑战，按新频率创建挑战，继承当前Streak为streakBase

### 5. 打卡与补签

打卡规则：
- 频率定义"推荐打卡日程"，不是硬约束
- 用户可在频率外的日期打卡，同样计入completedCount
- 同一天只能有一条打卡记录（UNIQUE约束）
- 只能取消当天的打卡

补签规则：
- 时间窗口：滚动7天（today-6 ~ today-1）
- 前提条件：挑战必须为in_progress
- 补签日期必须在挑战周期内（>= startDate）
- 补录会重新计算Streak（可能修复断链）

失败前补签挽救：
- 检测到即将失败时，检查补签能否挽救
- 可补签天数 = 滚动7天窗口内、挑战周期内、尚未打卡的天数
- canSave = requiredCompletions <= completedCount + 可补签天数 + 剩余未来天数

### 6. Streak（连续打卡天数）

Streak采用基数结算制跨挑战周期延续：
- 每个挑战有streakBase字段（挑战开始时继承的Streak基数）
- 当前Streak = streakBase + 本挑战内的连续打卡累计
- 挑战中途若断链，streakBase失效，只看断链后的打卡
- 结算规则：succeeded → 新挑战继承当前Streak为streakBase；failed/cancelled → streakBase=0

Streak判定策略：

**daily频率（逐天判定）**：
- 每次打卡 → Streak +1
- 某天未打卡 → Streak归零（streakBase也失效）
- 今天还未打卡 → 不算断链，从昨天开始计算
- 若连续回溯到挑战startDate未断链 → 加上streakBase

**非daily频率（按天累加 + 周一结算）**：
- 判定单位：周（不是天）
- 实时累加：每次打卡当天Streak +1（不区分是否为specificDays中的日期）
- 当天未打卡：Streak不变（不会按天归零）
- 中断判定时点：仅在周一结算上一自然周（Mon~Sun）
- 中断判定规则：结算时，若上一周打卡次数 < 该周目标，则Streak清零
- 当前周（未闭合）：只做实时累加，不触发失败结算

不完整周处理：
- 有效范围 = [max(周一, startDate), min(周日, today, endDate)]
- 本周目标 = 有效范围内isScheduledDay()为true的天数

### 7. 统计规则

**今日概览**：
- 应打卡数：所有active习惯中，今天为应打卡日的数量
- 已完成数：今天所有active习惯中已有checkin记录的数量
- 计划外打卡不计入分母

**每周完成率**：
- 统计单位：自然周（周一至周日）
- 每个active习惯独立计算该周完成率，然后取算术平均值
- 分母：有效范围内的应打卡天数
- 分子：有效范围内的实际打卡次数（上限为分母）

**热力图**：
- 统计单位：每日
- 当日应完成数：当日所有active习惯中，频率规则匹配的习惯数
- 当日已完成数：当日所有打卡记录数（含计划外打卡）
- 完成率：completedHabits / totalHabits（上限1.0）

### 8. 删除习惯

采用硬删除 + 级联删除：
- 无前置条件：无论active还是paused，均可直接删除
- 级联顺序：habit_checkins → habit_challenges → habits
- 习惯链条处理：将habit_chain_nodes.habit_id置为NULL，节点降级为纯锚点

### 9. 习惯链条 Timeline 节点时间计算

#### 9.1 计算原则

Timeline 节点时间采用**后端计算、前端显示**的分离架构：

- **显式时间**：用户为节点设置的 `trigger_time`，持久化存储
- **计算时间**：后端根据显式时间和计算规则推导的 `calculated_time`，仅作为 API 返回值，不存储

#### 9.2 计算规则

后端根据节点链条中显式设置的 `trigger_time` 计算所有节点的 `calculated_time`：

**规则A（无显式锚点）**：链条中没有任何节点设置显式时间时，所有节点按默认间隔递推计算。

**规则B（有显式锚点）**：
- 第一个锚点之前的节点：从该锚点向前递推
- 相邻锚点之间的节点：在两个锚点之间平均分配时间间隔
- 最后一个锚点之后的节点：从该锚点向后递推

**时间类型区分**：
- 有显式时间的节点：`calculated_time` = `trigger_time`
- 无显式时间的节点：`calculated_time` 根据规则计算得出

#### 9.3 验证规则

前端设置显式时间时，后端需验证时间间隔是否符合最小间距要求。不符合时返回验证错误，阻止保存。

#### 9.4 显示原则

前端 Timeline 组件使用 `calculated_time` 显示节点时间。若节点无 `calculated_time`（兼容旧数据），则 fallback 到 `trigger_time`。

## Technical Contract

### 1. 数据模型

**habits表**：
- id: 习惯ID（格式：habit-xxxxxxxx）
- name: 习惯名称（1-100字符）
- description: 描述（可选，最多500字符）
- frequency_type: 频率类型（daily / weekdays / weekend / custom）
- frequency_config: 频率配置JSON（custom类型时存储specificDays）
- current_level: 当前等级（0-4）
- status: 状态（active / paused）
- value_id: 关联价值ID（可选）
- commitment_id: 关联承诺ID（可选）
- paused_at: 暂停时间（可选）
- created_at: 创建时间
- updated_at: 更新时间

**habit_challenges表**：
- id: 挑战ID（格式：challenge-xxxxxxxx）
- habit_id: 关联习惯ID
- challenge_weeks: 挑战周数
- required_completions: 要求完成次数
- completed_count: 已完成次数
- from_level: 起始等级
- to_level: 目标等级
- start_date: 开始日期（ISO格式）
- end_date: 结束日期（ISO格式）
- streak_base: Streak基数
- status: 状态（in_progress / succeeded / failed / cancelled）
- finished_at: 完成时间（可选）
- created_at: 创建时间
- updated_at: 更新时间

**habit_checkins表**：
- id: 打卡ID（自增）
- habit_id: 关联习惯ID
- challenge_id: 关联挑战ID
- date: 打卡日期（ISO格式）
- completed_at: 打卡时间
- created_at: 创建时间
- UNIQUE约束：(habit_id, date)

**habit_chains表**：
- id: 链条ID（格式：chain-xxxxxxxx）
- name: 链条名称
- description: 描述（可选）
- created_at: 创建时间
- updated_at: 更新时间

**habit_chain_nodes表**：
- id: 节点ID（自增）
- chain_id: 关联链条ID
- habit_id: 关联习惯ID（可为NULL，表示纯锚点）
- node_name: 节点名称
- trigger_time: 触发时间（可选）
- sequence_order: 顺序
- created_at: 创建时间

### 2. API端点

**习惯管理**：
- `POST /habits` - 创建习惯
- `GET /habits` - 获取习惯列表（可选status参数）
- `GET /habits/{habit_id}` - 获取习惯详情
- `PATCH /habits/{habit_id}` - 更新习惯
- `DELETE /habits/{habit_id}` - 删除习惯
- `POST /habits/{habit_id}/pause` - 暂停习惯
- `POST /habits/{habit_id}/resume` - 恢复习惯

**打卡功能**：
- `POST /habits/{habit_id}/checkin` - 今日打卡
- `DELETE /habits/{habit_id}/checkin` - 取消今日打卡
- `POST /habits/{habit_id}/backfill` - 补签
- `POST /habits/backfill-availability` - 查询可补签日期

**结算功能**：
- `GET /habits/check-settlements` - 检查待结算挑战
- `POST /habits/settlement-action` - 执行结算动作（重新开始/暂停）

**统计功能**：
- `GET /habits/stats/today-overview` - 今日概览
- `GET /habits/stats/weekly-completion` - 每周完成率
- `GET /habits/stats/heatmap` - 热力图数据

**习惯链条**：
- `POST /habit-chains` - 创建习惯链条
- `GET /habit-chains` - 获取链条列表
- `GET /habit-chains/{chain_id}` - 获取链条详情
- `PATCH /habit-chains/{chain_id}` - 更新链条
- `DELETE /habit-chains/{chain_id}` - 删除链条

### 3. 核心算法

**挑战参数计算**：
```
challengeWeeks = LEVEL_CHALLENGE_WEEKS[level]  // {0:2, 1:3, 2:4, 3:8, 4:12}
weeklyDays = getWeeklyFrequencyDays(frequency)
totalExpected = challengeWeeks × weeklyDays
requiredCompletions = ceil(totalExpected × 0.85)
```

**挑战结果判定**：
```
remainingCheckinDays = max(0, (endDate - today).days + (今天未打卡 ? 1 : 0))

if (today >= endDate && completedCount >= requiredCompletions):
    → succeeded
else if (requiredCompletions > completedCount + remainingCheckinDays):
    → failed (触发补签挽救检查)
else:
    → in_progress
```

**Streak计算（daily）**：
```
streak = 0
currentDate = today
if (今天已打卡): streak++, currentDate = today - 1

while (currentDate >= challenge.startDate):
    if (有打卡记录): streak++, currentDate--
    else: break

if (currentDate < challenge.startDate && 未断链):
    streak += challenge.streakBase
```

**Streak计算（非daily）**：
```
streak = 0
currentWeekStart = 本周周一

// 当前周（未闭合）：实时累加
for date in [currentWeekStart, today]:
    if (有打卡记录): streak++

// 历史周：逐周回溯
weekStart = currentWeekStart - 7天
while (weekStart >= challenge.startDate):
    weekEnd = weekStart + 6天
    有效范围 = [max(weekStart, challenge.startDate), min(weekEnd, today)]
    本周目标 = 有效范围内应打卡天数
    本周打卡 = 有效范围内实际打卡次数
    
    if (本周打卡 >= 本周目标): 
        streak += 本周打卡
        weekStart -= 7天
    else: 
        break

if (weekStart < challenge.startDate && 未断链):
    streak += challenge.streakBase
```

### 4. Request/Response Schemas

**FrequencyObject**：
```typescript
{
  type: "daily" | "weekdays" | "weekend" | "custom"
  specificDays?: number[]  // 1-7，custom类型时必填
}
```

**ChallengeObject**：
```typescript
{
  id: string
  habitId: string
  fromLevel: number
  toLevel: number
  challengeWeeks: number
  requiredCompletions: number
  completedCount: number
  remainingRestDays: number  // 剩余可休息天数
  startDate: string  // ISO格式
  endDate: string
  streakBase: number
  status: "in_progress" | "succeeded" | "failed" | "cancelled"
  finishedAt?: string
}
```

**HabitListItem**：
```typescript
{
  id: string
  name: string
  description?: string
  frequency: FrequencyObject
  currentLevel: number
  status: "active" | "paused"
  currentChallenge?: ChallengeObject
  valueId?: string
  commitmentId?: string
  createdAt: string
  pausedAt?: string
  streak: number
  anchorInfo?: {
    chainName: string
    nodeName: string
    triggerTime?: string
  }
  todayCompleted: boolean
}
```

**SettlementItem**：
```typescript
{
  challengeId: string
  habitId: string
  habitName: string
  result: "succeeded" | "failed"
  fromLevel: number
  toLevel: number
  completedCount: number
  requiredCompletions: number
  canSaveByBackfill: boolean
}
```

**ChainNodeObject**：
```typescript
{
  id: number
  chainId: number
  sortOrder: number
  name: string
  habitId: string | null
  habitName: string | null
  triggerTime: string | null   // 用户显式设置的触发时间（HH:mm格式）
  calculatedTime: string | null  // 后端计算的时间（HH:mm格式），用于Timeline显示
  createdAt: string
  updatedAt: string
}
```

**TimelineNodeItem**：
```typescript
{
  id: number
  name: string
  habitId: string | null
  habitName: string | null
  triggerTime: string | null   // 用户显式设置的触发时间
  calculatedTime: string | null  // 后端计算的触发时间（用于Timeline显示）
  sortOrder: number
  todayCheckedIn: boolean
}
```

### 5. 业务约束

1. 挑战状态只能从in_progress转换到其他状态，不可逆
2. 同一习惯同一天只能有一条打卡记录
3. 补签窗口限制为滚动7天
4. 等级范围：0-4，lv4之后维持挑战
5. 频率外的日期也可打卡，计入completedCount
6. 挑战成功必须等到endDate到达，失败可提前判定
7. 删除习惯时，链条节点的habit_id置为NULL而非删除节点
8. calculated_time 字段仅作为 API 返回值，不持久化到数据库
9. 链条节点时间验证：相邻节点的显式设置时间必须满足最小间距要求

## Interaction / UX Notes

### 1. 失败处理流程

当检测到挑战即将失败时：
1. 计算补满滚动7天内所有未打卡日能否挽救
2. 能挽救 → 弹窗"是否补录？"
   - 用户补录 → 重算completedCount → 重新执行判定逻辑
   - 用户放弃 → 确认失败
3. 不能挽救 → 确认失败
4. 生成待处理结算条目（不改challenge状态）
5. 弹窗让用户选择：
   - "重新开始"：条件更新challenge为failed，创建同等级新挑战
   - "暂停"：条件更新challenge为failed，习惯状态改为paused
   - "稍后处理"：不改变数据库状态，下次进入页面再次看到待处理结算条目

### 2. 删除确认

删除习惯时前端必须弹窗二次确认："删除后不可恢复，确认删除？"

### 3. 习惯Tips

前端可滚动显示以下习惯养成建议：
- 当你不想做时，执行"最小版本"
- 成为"做那种事的人"
- 用"习惯链条"串联你的早晨或晚间
- 设计你的环境，而非依赖毅力
- 允许暂停，但不要删除
- 给你的习惯一个"为什么"
- 从"小到不可能失败"开始
- 找到你的"锚点"，而不是创造时间

### 4. 结算检查时机

- 用户打卡/取消打卡后立即执行判定逻辑
- 系统定期调用`GET /habits/check-settlements`批量检查所有到期未结算挑战
- 成功的挑战自动落库，失败的挑战仅检测不落库，等待用户确认

## Acceptance Notes

### 1. 核心功能验收

- 创建习惯后自动创建首个挑战，状态为in_progress
- 打卡后completedCount正确增加，Streak正确计算
- 挑战成功后自动升级并创建下一等级挑战，新挑战从当天开始
- 挑战失败后弹窗让用户选择，选择后状态正确变更
- 补签功能只能补录滚动7天内的日期
- 删除习惯后级联删除所有相关记录

### 2. 边界条件验收

- 同一天重复打卡应报错
- 取消非当天的打卡应报错
- 暂停状态的习惯无法打卡
- 补签日期超出7天窗口应报错
- 补签日期早于挑战startDate应报错
- lv4升级后保持lv4，继续维持挑战

### 3. Streak计算验收

- daily频率：某天未打卡应归零
- 非daily频率：周内未打卡不归零，周一结算上一周时才判定
- 补录可能修复断链，Streak应重新计算
- 挑战成功后新挑战继承当前Streak为streakBase
- 挑战失败后新挑战streakBase为0

### 4. 统计数据验收

- 今日概览只统计应打卡的习惯，计划外打卡不计入分母
- 每周完成率按习惯独立计算后取平均，上限100%
- 热力图包含计划外打卡，总览视角不区分计划内外

## Out of Spec

以下内容不在本spec中长期维护：

1. 具体的UI组件树和前端文件结构
2. 数据库迁移脚本和版本管理
3. 具体的实现优先级和阶段拆解
4. 代码级别的实现技巧和库用法
5. 测试用例的详细设计
6. 部署和发布流程
7. 性能优化的具体方案
8. 错误码的详细定义（见error_codes.py）
9. 日志格式和监控指标
10. 前端路由和页面跳转逻辑
