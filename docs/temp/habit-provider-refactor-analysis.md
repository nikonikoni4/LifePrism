# Habit Provider 重构分析

## 表结构分析

### 1. habits 表
- **表名**: `habits`
- **主键**: `id` (TEXT)
- **日期字段**: 无
- **时间字段**: 无
- **时间戳**: `created_at`, `updated_at`
- **字段列表**:
  - `id`: TEXT PRIMARY KEY - 习惯唯一标识
  - `name`: TEXT NOT NULL - 习惯名称
  - `description`: TEXT - 习惯描述
  - `frequency_type`: TEXT NOT NULL - 频率类型 ('daily'|'weekly')
  - `frequency_config`: TEXT - JSON 存储额外频率配置
  - `current_level`: INTEGER DEFAULT 0 - 当前等级 0-4
  - `status`: TEXT DEFAULT 'active' - 'active'|'paused'
  - `value_id`: TEXT - 关联价值ID（可空）
  - `commitment_id`: TEXT - 关联承诺ID（可空）
  - `paused_at`: TEXT - 暂停时间（可空）
  - `created_at`: TEXT - 创建时间
  - `updated_at`: TEXT - 更新时间

### 2. habit_challenges 表
- **表名**: `habit_challenges`
- **主键**: `id` (TEXT)
- **日期字段**: `start_date`, `end_date` (用于日期范围查询)
- **时间字段**: 无
- **时间戳**: `created_at`, `updated_at`
- **外键**: `habit_id` REFERENCES habits(id)
- **字段列表**:
  - `id`: TEXT PRIMARY KEY - 挑战唯一标识
  - `habit_id`: TEXT NOT NULL - 所属习惯ID
  - `challenge_weeks`: INTEGER NOT NULL - 挑战周数
  - `required_completions`: INTEGER NOT NULL - 最低完成次数
  - `from_level`: INTEGER NOT NULL - 起始等级
  - `to_level`: INTEGER NOT NULL - 目标等级
  - `start_date`: TEXT NOT NULL - 开始日期 YYYY-MM-DD
  - `end_date`: TEXT NOT NULL - 结束日期 YYYY-MM-DD
  - `completed_count`: INTEGER DEFAULT 0 - 已完成次数
  - `streak_base`: INTEGER DEFAULT 0 - Streak基数
  - `status`: TEXT DEFAULT 'in_progress' - 'in_progress'|'succeeded'|'failed'|'cancelled'
  - `finished_at`: TEXT - 结束时间（可空）
  - `created_at`: TEXT - 创建时间
  - `updated_at`: TEXT - 更新时间

### 3. habit_checkins 表
- **表名**: `habit_checkins`
- **主键**: `id` (TEXT)
- **日期字段**: `date` (用于日期查询)
- **时间字段**: 无
- **时间戳**: `created_at` (无 updated_at)
- **外键**: 
  - `habit_id` REFERENCES habits(id)
  - `challenge_id` REFERENCES habit_challenges(id)
- **唯一约束**: UNIQUE(habit_id, date)
- **字段列表**:
  - `id`: TEXT PRIMARY KEY - 打卡记录唯一标识
  - `habit_id`: TEXT NOT NULL - 关联习惯ID
  - `challenge_id`: TEXT NOT NULL - 所属挑战ID
  - `date`: TEXT NOT NULL - 打卡日期 YYYY-MM-DD
  - `completed_at`: TEXT - 实际完成时间戳（可空）
  - `created_at`: TEXT - 创建时间

### 4. habit_chains 表
- **表名**: `habit_chains`
- **主键**: `id` (INTEGER AUTOINCREMENT)
- **日期字段**: 无
- **时间字段**: 无
- **时间戳**: `created_at`, `updated_at`
- **字段列表**:
  - `id`: INTEGER PRIMARY KEY AUTOINCREMENT - 链条自增ID
  - `name`: TEXT NOT NULL - 链条名称
  - `description`: TEXT - 链条描述（可空）
  - `show_in_timeline`: INTEGER DEFAULT 0 - 0=不显示, 1=在Timeline展示
  - `created_at`: TEXT - 创建时间
  - `updated_at`: TEXT - 更新时间

### 5. habit_chain_nodes 表
- **表名**: `habit_chain_nodes`
- **主键**: `id` (INTEGER AUTOINCREMENT)
- **日期字段**: 无
- **时间字段**: `trigger_time` (HH:mm 格式，但不用于范围查询)
- **时间戳**: `created_at`, `updated_at`
- **外键**:
  - `chain_id` REFERENCES habit_chains(id) ON DELETE CASCADE
  - `habit_id` REFERENCES habits(id)
- **字段列表**:
  - `id`: INTEGER PRIMARY KEY AUTOINCREMENT - 节点自增ID
  - `chain_id`: INTEGER NOT NULL - 所属链条ID
  - `sort_order`: INTEGER NOT NULL - 排序顺序（从1开始）
  - `name`: TEXT NOT NULL - 节点名称
  - `habit_id`: TEXT - 关联习惯ID（NULL=纯锚点节点）
  - `trigger_time`: TEXT - 触发时间 HH:mm（可空）
  - `created_at`: TEXT - 创建时间
  - `updated_at`: TEXT - 更新时间

## 依赖关系

```
habits (主表)
  ↓ (1:N)
habit_challenges (挑战记录)
  ↓ (1:N)
habit_checkins (打卡记录)

habit_chains (链条)
  ↓ (1:N)
habit_chain_nodes (链条节点)
  ↓ (N:1)
habits (关联习惯，可空)
```

## 重构策略

### 拆分方案
按照"单表对应一个 Provider"原则，需要创建 5 个独立的 Provider：

1. **HabitProvider** → `habits` 表
2. **HabitChallengeProvider** → `habit_challenges` 表
3. **HabitCheckinProvider** → `habit_checkins` 表
4. **HabitChainProvider** → `habit_chains` 表
5. **HabitChainNodeProvider** → `habit_chain_nodes` 表

### 文件组织
- 前 3 个 Provider 写在 `habit_providers.py` 中（核心业务）
- 后 2 个 Provider 写在 `habit_chain_providers.py` 中（链条功能）

### 白名单字段定义

#### HabitProvider
```python
_TABLE_NAME = "habits"
_PRIMARY_KEY = "id"
_DATE_FIELD = None
_TIME_FIELD = None

_FILTER_FIELDS = {
    'id', 'name', 'status', 'frequency_type', 'current_level',
    'value_id', 'commitment_id', 'created_at', 'updated_at'
}
_ORDER_FIELDS = {'id', 'name', 'current_level', 'created_at'}
_SELECT_FIELDS = {
    'id', 'name', 'description', 'frequency_type', 'frequency_config',
    'current_level', 'status', 'value_id', 'commitment_id', 'paused_at',
    'created_at', 'updated_at'
}
_UPDATE_FIELDS = {
    'name', 'description', 'frequency_type', 'frequency_config',
    'current_level', 'status', 'value_id', 'commitment_id', 'paused_at'
}
```

#### HabitChallengeProvider
```python
_TABLE_NAME = "habit_challenges"
_PRIMARY_KEY = "id"
_DATE_FIELD = "start_date"  # 用于日期范围查询
_TIME_FIELD = None

_FILTER_FIELDS = {
    'id', 'habit_id', 'status', 'from_level', 'to_level',
    'start_date', 'end_date', 'created_at', 'updated_at'
}
_ORDER_FIELDS = {'id', 'start_date', 'end_date', 'created_at'}
_SELECT_FIELDS = {
    'id', 'habit_id', 'challenge_weeks', 'required_completions',
    'from_level', 'to_level', 'start_date', 'end_date',
    'completed_count', 'streak_base', 'status', 'finished_at',
    'created_at', 'updated_at'
}
_UPDATE_FIELDS = {
    'completed_count', 'streak_base', 'status', 'finished_at'
}
```

#### HabitCheckinProvider
```python
_TABLE_NAME = "habit_checkins"
_PRIMARY_KEY = "id"
_DATE_FIELD = "date"  # 用于日期范围查询
_TIME_FIELD = None

_FILTER_FIELDS = {
    'id', 'habit_id', 'challenge_id', 'date', 'created_at'
}
_ORDER_FIELDS = {'id', 'date', 'created_at'}
_SELECT_FIELDS = {
    'id', 'habit_id', 'challenge_id', 'date', 'completed_at', 'created_at'
}
_UPDATE_FIELDS = {
    'completed_at'  # 通常不更新打卡记录，但保留字段
}
```

#### HabitChainProvider
```python
_TABLE_NAME = "habit_chains"
_PRIMARY_KEY = "id"  # INTEGER AUTOINCREMENT
_DATE_FIELD = None
_TIME_FIELD = None

_FILTER_FIELDS = {
    'id', 'name', 'show_in_timeline', 'created_at', 'updated_at'
}
_ORDER_FIELDS = {'id', 'name', 'created_at'}
_SELECT_FIELDS = {
    'id', 'name', 'description', 'show_in_timeline', 'created_at', 'updated_at'
}
_UPDATE_FIELDS = {
    'name', 'description', 'show_in_timeline'
}
```

#### HabitChainNodeProvider
```python
_TABLE_NAME = "habit_chain_nodes"
_PRIMARY_KEY = "id"  # INTEGER AUTOINCREMENT
_DATE_FIELD = None
_TIME_FIELD = None  # trigger_time 不用于范围查询

_FILTER_FIELDS = {
    'id', 'chain_id', 'habit_id', 'sort_order', 'created_at', 'updated_at'
}
_ORDER_FIELDS = {'id', 'sort_order', 'created_at'}
_SELECT_FIELDS = {
    'id', 'chain_id', 'sort_order', 'name', 'habit_id', 'trigger_time',
    'created_at', 'updated_at'
}
_UPDATE_FIELDS = {
    'name', 'habit_id', 'trigger_time', 'sort_order'
}
```

## 特殊处理

### 1. ID 生成
- **habits**: 使用 `generate_id("habit")` 生成 TEXT 主键
- **habit_challenges**: 使用 `_generate_challenge_id()` 生成 TEXT 主键
- **habit_checkins**: 使用 `_generate_checkin_id()` 生成 TEXT 主键
- **habit_chains**: INTEGER AUTOINCREMENT，使用 `cursor.lastrowid` 获取
- **habit_chain_nodes**: INTEGER AUTOINCREMENT，使用 `cursor.lastrowid` 获取

### 2. 唯一约束处理
- **habit_checkins**: UNIQUE(habit_id, date) - 需要捕获 IntegrityError 返回 None

### 3. 跨表查询
- **HabitChainProvider.get_anchor_info_by_habit_ids()**: JOIN habit_chains 和 habit_chain_nodes
- **HabitChainProvider.get_nodes_with_habit_names()**: LEFT JOIN habits 表
- 这些方法保留手写 SQL，不使用通用方法

### 4. 时间戳更新
- 所有表都使用 `datetime.now().strftime("%Y-%m-%d %H:%M:%S")` 格式
- 不使用 SQLite 的 `datetime('now','localtime')`

## 重构顺序

1. ✅ 分析表结构（当前步骤）
2. 编写 habit_service 快照测试
3. 重构 HabitProvider
4. 重构 HabitChallengeProvider
5. 重构 HabitCheckinProvider
6. 拆分并重构 HabitChainProvider（拆分为 2 个 Provider）
7. 更新 habit_service 导入
8. 运行快照测试验证
9. 提交代码
