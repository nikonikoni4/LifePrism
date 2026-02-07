# 习惯系统

> 版本: v1.0 | 状态: 设计中 | 更新: 2026-01-31

## 模块定位

价值 → 承诺 → **习惯** → 每日打卡

习惯系统是 Mind Space 中价值与承诺的延伸，帮助用户将抽象的承诺转化为可执行的日常行为。

## 文档索引

| 文档 | 描述 |
|------|------|
| [习惯列表视图](习惯列表视图.md) | 习惯管理 |
| [习惯系统新界面设计](习惯系统新界面设计.md) | 新界面设计 |

---

## 核心理念

### 1. 锚点哲学

新习惯的养成应该以已有习惯为锚点，而非理想状态。

- **现实锚点**：用户当前已稳固的习惯（如吃饭、睡觉）
- **理想锚点**：用户期望达成的习惯状态
- **新习惯依附于现实锚点**：确保可执行性

#### 锚点类型

| 类型 | 示例 | 触发方式 |
|------|------|----------|
| 时间锚点 | 7:00起床、12:00午饭 | 固定时间触发 |
| 事件锚点 | 吃完早饭后、洗完澡后 | 前置事件触发 |
| 场景锚点 | 到公司后、回家后 | 地点/状态变化触发 |

### 2. 习惯分级系统

采用**等级制**而非简单的成功/失败二元判定。

| 等级 | 名称 | 含义 | 颜色 |
|------|------|------|------|
| 0 | 萌芽 | 刚开始尝试 | #E8F5E9 |
| 1 | 生根 | 初步建立 | #A5D6A7 |
| 2 | 成长 | 逐渐稳固 | #66BB6A |
| 3 | 稳固 | 已成为习惯 | #43A047 |
| 4 | 根深蒂固 | 长期稳定 | #2E7D32 |

#### 升降级规则

- **升级**：完成当前等级的挑战目标（如"21天完成18天"）
- **降级**：未完成挑战目标时，退回上一等级，并且将任务状态暂停
- **归零**：降至0级后重新开始

**核心理念：没有"失败"，只有"暂时没有实现"。**

### 3. 历史记录的价值

保留完整的习惯养成历史，包括所有升级、降级记录。

**意义**：
- 习惯养成本就是断断续续的过程
- 看到过往的挣扎和最终成功，能激发自信心
- 帮助用户理解：养成习惯需要时间，不必自我苛责

### 4. 价值与承诺关联

习惯可关联 Mind Space 中的价值和承诺，解释"为什么要养成这个习惯"。

- **价值**：用户是因为什么原因才决定养成这个习惯
- **承诺**：用户是因为哪个承诺才设计这个养成习惯

### 5. 心理健康关怀

- 若检测到用户日常生活缺乏锚点（无规律性行为），系统应温和提示
- 提示内容："日常生活不规律可能影响掌控感，建议先建立一些简单的固定习惯"
- 此功能需结合 AI 分析和 Mind Space 模块（未来实现）

---

## 与 ActivityWatch 集成愿景（V2+）

LifeWatch-AI 的独特优势是拥有用户真实行为数据，未来可实现：

1. **自动发现锚点**：分析用户数据，识别规律性行为（"你每天9:00-9:30通常在看新闻"）
2. **习惯自动验证**：部分习惯（如"每天写代码1小时"）可自动检测完成情况
3. **现实 vs 理想差距可视化**：用真实数据展示习惯执行情况

**V1 暂不实现**，先做独立的手动打卡系统。

---

## 数据模型

### Habit（习惯）

```typescript
interface Habit {
  id: string;
  name: string;
  description?: string;
  frequency: HabitFrequency;

  // 锚点
  anchorType?: 'time' | 'event' | 'scene';
  anchorDescription?: string;
  anchorHabitId?: string;

  // 等级
  currentLevel: number;           // 0-4
  currentChallenge: HabitChallenge;

  // 状态
  status: 'active' | 'paused' | 'archived';

  // 关联
  goalId?: string;
  valueId?: string;
  commitmentId?: string;

  createdAt: string;
  updatedAt: string;
}
```

### HabitFrequency（频率）

```typescript
interface HabitFrequency {
  type: 'daily' | 'weekdays' | 'weekly' | 'custom';
  timesPerWeek?: number;          // weekly 类型
  specificDays?: number[];        // custom 类型 [1,2,3,4,5,6,7]，1=周一
}

// 示例
const dailyFreq: HabitFrequency = { type: 'daily' };
const weekdaysFreq: HabitFrequency = { type: 'weekdays' };
const weeklyFreq: HabitFrequency = { type: 'weekly', timesPerWeek: 3 };
const customFreq: HabitFrequency = { type: 'custom', specificDays: [1, 3, 5] };
```

### HabitChallenge（挑战）

```typescript
interface HabitChallenge {
  id: string;
  habitId: string;
  targetDays: number;             // 目标天数
  requiredCompletions: number;    // 需完成次数
  fromLevel: number;
  toLevel: number;
  startDate: string;
  endDate: string;                // 挑战结束日期（计算得出）
  completedCount: number;
  status: 'in_progress' | 'succeeded' | 'failed';
  finishedAt?: string;
}
```

**重要**：当设置了频率之后需要计算最长完成时间限制，比如每周4次，完成8次，那么最长时间就是14天。

### HabitCheckIn（打卡记录）

```typescript
interface HabitCheckIn {
  id: string;
  habitId: string;
  challengeId: string;
  date: string;                   // YYYY-MM-DD
  completed: boolean;
  note?: string;
  completedAt?: string;
}
```

### HabitHistory（历史记录）

```typescript
interface HabitHistory {
  id: string;
  habitId: string;
  challenge: HabitChallenge;      // 挑战结果快照
  levelChange: 'up' | 'down' | 'reset';
  fromLevel: number;
  toLevel: number;
  actualCompletions: number;      // 实际完成次数
  createdAt: string;
}
```

### Value（价值）- Mind Space

```typescript
interface Value {
  id: string;
  name: string;                   // 如"身心健康"、"持续学习"
  description?: string;
  createdAt: string;
  updatedAt: string;
}
```

### Commitment（承诺）- Mind Space

```typescript
interface Commitment {
  id: string;
  name: string;                   // 如"每天留出时间给自己"
  description?: string;
  valueId?: string;               // 关联的价值ID
  createdAt: string;
  updatedAt: string;
}
```

---

## 数据库表设计

### habits 表

```sql
CREATE TABLE habits (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    frequency_type TEXT NOT NULL,
    frequency_config TEXT,        -- JSON
    anchor_type TEXT,
    anchor_description TEXT,
    anchor_habit_id TEXT,
    current_level INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',
    goal_id TEXT,
    value_id TEXT,
    commitment_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    paused_at TEXT
);
```

### habit_challenges 表

```sql
CREATE TABLE habit_challenges (
    id TEXT PRIMARY KEY,
    habit_id TEXT NOT NULL,
    target_days INTEGER NOT NULL,
    required_completions INTEGER NOT NULL,
    from_level INTEGER NOT NULL,
    to_level INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    completed_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'in_progress',
    finished_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (habit_id) REFERENCES habits(id)
);
```

### habit_checkins 表

```sql
CREATE TABLE habit_checkins (
    id TEXT PRIMARY KEY,
    habit_id TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    date TEXT NOT NULL,
    completed INTEGER NOT NULL,
    note TEXT,
    completed_at TEXT,
    FOREIGN KEY (habit_id) REFERENCES habits(id),
    FOREIGN KEY (challenge_id) REFERENCES habit_challenges(id),
    UNIQUE(habit_id, date)        -- 每个习惯每天只能有一条记录
);
```

### habit_history 表

```sql
CREATE TABLE habit_history (
    id TEXT PRIMARY KEY,
    habit_id TEXT NOT NULL,
    challenge_id TEXT NOT NULL,
    level_change TEXT NOT NULL,   -- 'up' | 'down' | 'reset'
    from_level INTEGER NOT NULL,
    to_level INTEGER NOT NULL,
    actual_completions INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (habit_id) REFERENCES habits(id),
    FOREIGN KEY (challenge_id) REFERENCES habit_challenges(id)
);
```

### values 表（Mind Space）

```sql
CREATE TABLE values (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

### commitments 表（Mind Space）

```sql
CREATE TABLE commitments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    value_id TEXT,                 -- 关联的价值ID（可选）
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (value_id) REFERENCES values(id)
);
```

---

## 统计计算

### 连续天数（Streak）计算

```typescript
function calculateStreak(habitId: string, frequency: HabitFrequency): number {
  // 根据频率类型，从今天往前查找连续完成的记录
  // daily: 每天都要完成
  // weekdays: 工作日要完成
  // weekly: 本周内完成指定次数即可
  // custom: 指定日期要完成
}
```

### 完成率计算

```typescript
function calculateCompletionRate(
  habitId: string,
  startDate: string,
  endDate: string,
  frequency: HabitFrequency
): number {
  // 计算时间范围内应完成次数
  // 计算实际完成次数
  // 返回百分比
}
```

### 热力图数据

```typescript
interface HeatmapData {
  date: string;                  // YYYY-MM-DD
  totalHabits: number;           // 当日应完成习惯数
  completedHabits: number;       // 当日已完成习惯数
  completionRate: number;        // 完成率 0-1
}
```

---

## 默认挑战配置

| 等级变化 | 目标天数 | 需完成天数 | 完成率要求 |
|----------|----------|------------|------------|
| 0 → 1 | 14 | 12 | 85.7% |
| 1 → 2 | 21 | 18 | 85.7% |
| 2 → 3 | 30 | 25 | 83.3% |
| 3 → 4 | 60 | 50 | 83.3% |
| 4 维持 | 90 | 75 | 83.3% |

---

## 版本规划

| 版本 | 功能 | 优先级 |
|------|------|--------|
| V1 | 习惯列表 + 手动打卡 + 等级系统 + 热力图 | 高 |
| V2 | 锚点可视化（时间轴） + 习惯链展示 | 中 |
| V3 | ActivityWatch 数据集成 + 自动打卡 | 中 |
| V4 | AI 分析 + 智能建议 + Mind Space 联动 | 低 |

---

## 相关代码

- 前端: `frontend/page/habits/`（待创建）
- 后端 API: `lifeprism/server/api/habit_api.py`（待创建）
- 后端 Service: `lifeprism/server/services/habit_service.py`（待创建）
