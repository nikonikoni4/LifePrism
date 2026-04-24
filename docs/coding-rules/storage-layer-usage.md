# Storage 层使用规范

**版本**: 1.0  
**创建日期**: 2026-04-24  
**状态**: 正式  

## 概述

本文档规定了 `lifeprism/storage/` 模块的使用规范，包括 Provider、Aggregator 和 Store 的使用方式、编码规范和最佳实践。

### 核心原则

1. **单一职责**：Provider 只做数据库操作，不包含业务逻辑
2. **统一接口**：所有 Provider 使用 `QueryOptions` 统一查询接口
3. **分层清晰**：Provider（原子操作）→ Aggregator（数据聚合）→ Service（业务逻辑）
4. **类型安全**：使用 Store 统一导出，提供类型提示

## 架构设计

### 目录结构

```
lifeprism/storage/
├── __init__.py              # 统一导出 Store
├── schemas.py               # 表结构定义
├── database_manager.py      # 数据库连接管理
├── providers/               # 数据访问层（原子操作）
│   ├── __init__.py
│   ├── diary_provider.py
│   ├── todo_provider.py
│   ├── goal_provider.py
│   └── ...
├── aggregators/             # 数据聚合层（组合多个 Provider）
│   ├── __init__.py
│   ├── habit_aggregator.py
│   ├── mood_aggregator.py
│   └── ...
└── migrations/              # 数据库迁移脚本
```

### 三层职责划分

| 层级 | 位置 | 职责 | 示例 |
|------|------|------|------|
| **Provider** | `storage/providers/` | 原子的数据库操作，通用、可复用 | `query_todos(options)` |
| **Aggregator** | `storage/aggregators/` | 组合多个 Provider 调用，数据聚合计算 | `get_habit_with_stats()` |
| **Service** | `server/services/` 或 `llm/services/` | 业务逻辑、事务协调、外部调用 | `complete_todo()` 更新数据库 + 发送通知 |

## 使用方式

### 1. 导入 Store

**推荐方式**（使用 Store 统一导出）：

```python
from lifeprism.storage import Store

# 使用 Provider
todos, total = Store.todo.query_todos(options)

# 使用 Aggregator
habit_data = Store.habit_aggregator.get_habit_with_checkins(habit_id)
```

**不推荐方式**（直接导入 Provider）：

```python
# ❌ 不推荐：绕过 Store，失去类型提示
from lifeprism.storage.providers import TodoProvider
provider = TodoProvider()
```

### 2. 使用 QueryOptions 查询

**基本查询**：

```python
from lifeprism.storage import Store, QueryOptions

# 查询今日活跃 todos
options = QueryOptions(
    date_range=("2026-04-24", "2026-04-24"),
    filters={'state': 'active'}
)
todos, total = Store.todo.query_todos(options)
```

**链式调用**：

```python
# 创建基础查询选项
base = QueryOptions(filters={'state': 'active'})

# 查询 4 月数据
april_todos, _ = Store.todo.query_todos(
    base.with_date_range("2026-04-01", "2026-04-30")
)

# 查询 5 月数据（base 保持不变）
may_todos, _ = Store.todo.query_todos(
    base.with_date_range("2026-05-01", "2026-05-31")
)
```

**分页查询**：

```python
# 第一页，每页 20 条
options = QueryOptions().with_page(page=1, page_size=20)
todos, total = Store.todo.query_todos(options)

# 计算总页数
total_pages = (total + 19) // 20
```

**复杂筛选**：

```python
# IN 查询
options = QueryOptions(
    filters={'id': ['id1', 'id2', 'id3']}
)

# NULL 查询
options = QueryOptions(
    filters={'deleted_at': None}
)

# 多条件组合
options = QueryOptions(
    date_range=("2026-04-01", "2026-04-30"),
    filters={'state': 'active', 'priority': 'high'},
    order_by='created_at',
    order_desc=True
).with_page(1, 20)
```

### 3. 使用 Aggregator

**获取聚合数据**：

```python
from lifeprism.storage import Store

# 获取习惯及其打卡记录
habit_data = Store.habit_aggregator.get_habit_with_checkins(
    habit_id="habit_123",
    start_date="2026-04-01",
    end_date="2026-04-30"
)

# 获取目标及其统计数据
goal_data = Store.goal_aggregator.get_goal_with_stats(goal_id="goal_456")
```

**批量操作**：

```python
# 批量获取习惯链数据
chains = Store.habit_chain_aggregator.get_chains_with_nodes(
    chain_ids=["chain1", "chain2", "chain3"]
)
```

## Store 列表

### Provider Store

| Store 属性 | Provider 类 | 对应表 | 主要方法 |
|-----------|------------|--------|---------|
| `Store.diary` | `DiaryProvider` | `diary` | `query_diaries()`, `get_diary_by_date()` |
| `Store.mood_type` | `MoodTypeProvider` | `mood_types` | `query_mood_types()`, `get_mood_type_by_id()` |
| `Store.mood_entry` | `MoodEntryProvider` | `mood_entries` | `query_mood_entries()`, `insert_mood_entry()` |
| `Store.mood_impact` | `MoodImpactProvider` | `mood_impacts` | `query_mood_impacts()` |
| `Store.habit` | `HabitProvider` | `habits` | `query_habits()`, `update_habit()` |
| `Store.habit_challenge` | `HabitChallengeProvider` | `habit_challenges` | `query_challenges()` |
| `Store.habit_checkin` | `HabitCheckinProvider` | `habit_checkins` | `query_checkins()`, `insert_checkin()` |
| `Store.habit_chain` | `HabitChainProvider` | `habit_chains` | `query_chains()` |
| `Store.habit_chain_node` | `HabitChainNodeProvider` | `habit_chain_nodes` | `query_nodes()` |
| `Store.goal` | `GoalProvider` | `goals` | `query_goals()`, `update_goal()` |
| `Store.goal_stats` | `GoalStatsProvider` | `goal_stats` | `query_goal_stats()` |
| `Store.todo` | `TodoProvider` | `todo_list` | `query_todos()`, `update_todo()` |
| `Store.timeline` | `TimelineProvider` | `timeline` | `query_timeline()` |
| `Store.plan_doc` | `PlanDocProvider` | `plan_docs` | `query_plan_docs()` |
| `Store.category` | `CategoryProvider` | `categories` | `query_categories()` |
| `Store.sub_category` | `SubCategoryProvider` | `sub_categories` | `query_sub_categories()` |
| `Store.tokens_usage` | `TokensUsageProvider` | `tokens_usage_log` | `save_tokens_usage()` |
| `Store.multi_purpose_cache` | `MultiPurposeMapCacheProvider` | `multi_purpose_map_cache` | `load_cache()`, `save_cache()` |
| `Store.single_purpose_cache` | `SinglePurposeMapCacheProvider` | `single_purpose_map_cache` | `load_cache()`, `save_cache()` |

### Aggregator Store

| Store 属性 | Aggregator 类 | 聚合的 Provider | 主要方法 |
|-----------|--------------|----------------|---------|
| `Store.habit_aggregator` | `HabitAggregator` | habit, habit_challenge, habit_checkin | `get_habit_with_checkins()` |
| `Store.mood_aggregator` | `MoodAggregator` | mood_type, mood_entry, mood_impact | `get_mood_entries_with_types()` |
| `Store.goal_aggregator` | `GoalAggregator` | goal, goal_stats | `get_goal_with_stats()` |
| `Store.habit_chain_aggregator` | `HabitChainAggregator` | habit_chain, habit_chain_node | `get_chain_with_nodes()` |
| `Store.category_aggregator` | `CategoryAggregator` | category, sub_category | `get_categories_with_subs()` |
| `Store.map_cache_aggregator` | `MapCacheAggregator` | multi_purpose_cache, single_purpose_cache | `load_all_caches()` |

## 编码规范

### 1. Provider 编写规范

#### 1.1 文件组织

```python
# storage/providers/todo_provider.py
"""
Todo 数据提供者

职责：
- 提供 todo_list 表的所有数据访问接口
- 不包含业务逻辑，只做数据库操作
- 返回原始数据（Dict），不做业务转换
"""
from typing import Optional, List, Dict, Any, Tuple, Set
from lifeprism.storage.base_providers import LWBaseDataProvider
from lifeprism.storage.providers.query_options import QueryOptions
from lifeprism.utils import LazySingleton

class TodoProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """Todo 数据提供者"""
    
    # 白名单：类属性，集中管理（防止 SQL 注入）
    _FILTER_FIELDS: Set[str] = {
        'id', 'date', 'state', 'status', 'goal_id', 'category_id',
        'priority', 'title', 'content', 'created_at', 'updated_at'
    }
    _ORDER_FIELDS: Set[str] = {
        'id', 'date', 'created_at', 'updated_at', 'priority', 'state'
    }
    _SELECT_FIELDS: Set[str] = {
        'id', 'date', 'state', 'status', 'goal_id', 'category_id',
        'priority', 'title', 'content', 'created_at', 'updated_at'
    }
    
    # ==================== 查询方法 ====================
    
    def query_todos(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """通用查询接口（支持多条件筛选、排序、分页）"""
        pass
    
    def get_todo_by_id(self, todo_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询单条记录"""
        pass
    
    # ==================== 插入方法 ====================
    
    def insert_todo(self, data: Dict[str, Any]) -> str:
        """插入新记录，返回新记录的 ID"""
        pass
    
    # ==================== 更新方法 ====================
    
    def update_todo(self, todo_id: str, data: Dict[str, Any]) -> bool:
        """更新记录，返回是否成功"""
        pass
    
    # ==================== 删除方法 ====================
    
    def delete_todo(self, todo_id: str) -> bool:
        """删除记录，返回是否成功"""
        pass
```

#### 1.2 方法命名规范

| 操作类型 | 命名模式 | 示例 | 返回值 |
|---------|---------|------|--------|
| **通用查询** | `query_{table}()` | `query_todos()` | `Tuple[List[Dict], int]` (数据, 总数) |
| **单条查询** | `get_{table}_by_{field}()` | `get_todo_by_id()` | `Optional[Dict]` |
| **插入** | `insert_{table}()` | `insert_todo()` | `str` (新记录 ID) |
| **更新** | `update_{table}()` | `update_todo()` | `bool` (是否成功) |
| **删除** | `delete_{table}()` | `delete_todo()` | `bool` (是否成功) |
| **批量操作** | `batch_{action}_{table}()` | `batch_delete_todos()` | `int` (影响行数) |
| **多表联合** | `query_{main}_with_{joined}()` | `query_goals_with_category()` | `Tuple[List[Dict], int]` |
| **统计查询** | `aggregate_{metric}_by_{dimension}()` | `aggregate_duration_by_category()` | `List[Dict]` 或 `Dict` |

#### 1.3 必须实现的核心方法

每个 Provider 必须实现以下 5 个核心方法：

- `query_{table}()` - 通用查询接口（使用 QueryOptions）
- `get_{table}_by_id()` - 按 ID 查询
- `insert_{table}()` - 插入记录
- `update_{table}()` - 更新记录
- `delete_{table}()` - 删除记录

#### 1.4 可选方法（根据业务需要）

- `batch_insert_{table}()` - 批量插入
- `batch_update_{table}()` - 批量更新
- `batch_delete_{table}()` - 批量删除
- `upsert_{table}()` - 插入或更新（INSERT OR REPLACE）
- `query_{table}_with_{joined_table}()` - 多表联合查询
- `aggregate_{metric}_by_{dimension}()` - 统计查询
- 特殊业务方法（如 `reorder_todos()`）

#### 1.5 参数验证

```python
def query_todos(self, options: Optional[QueryOptions] = None):
    """通用查询接口"""
    if options is None:
        options = QueryOptions()
    
    # QueryOptions 内部已做参数验证
    # Provider 只需验证白名单
    
    if options.order_by not in self._ORDER_FIELDS:
        raise ValueError(f"Invalid order_by field: {options.order_by}")
    
    if options.filters:
        invalid_fields = set(options.filters.keys()) - self._FILTER_FIELDS
        if invalid_fields:
            raise ValueError(f"Invalid filter fields: {invalid_fields}")
    
    # 执行查询...
```

#### 1.6 错误处理

```python
import sqlite3
from lifeprism.utils.logger import get_logger

logger = get_logger(__name__)

def insert_todo(self, data: Dict[str, Any]) -> str:
    """插入 todo"""
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # ... 执行插入
            return new_id
    
    except sqlite3.IntegrityError as e:
        # 唯一约束冲突
        logger.error(f"Failed to insert todo: {e}")
        raise ValueError(f"Todo already exists or violates constraints: {e}")
    
    except sqlite3.OperationalError as e:
        # 数据库锁定等操作错误
        logger.error(f"Database operation failed: {e}")
        raise RuntimeError(f"Database error: {e}")
    
    except Exception as e:
        # 其他未预期错误
        logger.exception(f"Unexpected error inserting todo: {e}")
        raise
```

#### 1.7 文档规范

```python
def query_todos(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用的 Todo 查询接口
    
    支持多条件筛选、排序、分页，一个方法覆盖所有查询场景。
    
    Args:
        options: 查询选项（QueryOptions 对象）
    
    Returns:
        Tuple[List[Dict], int]: (记录列表, 总记录数)
    
    Raises:
        ValueError: 参数验证失败
        RuntimeError: 数据库操作失败
    
    Examples:
        >>> # 查询今日活跃 todos
        >>> options = QueryOptions(
        ...     date_range=("2026-04-24", "2026-04-24"),
        ...     filters={'state': 'active'}
        ... )
        >>> todos, total = Store.todo.query_todos(options)
        >>> print(f"Found {total} todos")
        
        >>> # 分页查询
        >>> options = QueryOptions().with_page(page=1, page_size=20)
        >>> todos, total = Store.todo.query_todos(options)
        >>> print(f"Page 1 of {(total + 19) // 20}")
    
    Notes:
        - 所有筛选条件都是可选的，不传则不筛选
        - 时间范围是闭区间 [start_date, end_date]
        - 分页从 1 开始，不是 0
    """
    pass
```

### 2. Aggregator 编写规范

#### 2.1 文件组织

```python
# storage/aggregators/habit_aggregator.py
"""
Habit 数据聚合器

职责：
- 组合多个 Provider 调用，提供聚合数据
- 不包含业务逻辑，只做数据聚合
- 返回组合后的数据结构
"""
from typing import Optional, List, Dict, Any
from lifeprism.storage.providers import (
    HabitProvider,
    HabitChallengeProvider,
    HabitCheckinProvider
)

class HabitAggregator:
    """Habit 数据聚合器"""
    
    def __init__(self):
        self.habit = HabitProvider()
        self.challenge = HabitChallengeProvider()
        self.checkin = HabitCheckinProvider()
    
    def get_habit_with_checkins(
        self,
        habit_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        获取习惯及其打卡记录
        
        Args:
            habit_id: 习惯 ID
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            包含习惯信息和打卡记录的字典，如果习惯不存在则返回 None
        """
        # 获取习惯基本信息
        habit = self.habit.get_habit_by_id(habit_id)
        if not habit:
            return None
        
        # 获取打卡记录
        from lifeprism.storage.providers.query_options import QueryOptions
        options = QueryOptions(
            date_range=(start_date, end_date) if start_date and end_date else None,
            filters={'habit_id': habit_id}
        )
        checkins, _ = self.checkin.query_checkins(options)
        
        # 组合数据
        return {
            **habit,
            'checkins': checkins
        }
```

#### 2.2 命名规范

- 类名：`{Domain}Aggregator`（如 `HabitAggregator`）
- 方法名：`get_{main}_with_{related}()`（如 `get_habit_with_checkins()`）
- 返回值：组合后的字典或列表

#### 2.3 职责边界

**Aggregator 应该做的**：
- 组合多个 Provider 调用
- 数据结构转换（如列表转字典）
- 简单的数据计算（如统计数量）

**Aggregator 不应该做的**：
- 业务逻辑判断
- 外部 API 调用
- 事务管理
- 数据验证

### 3. QueryOptions 使用规范

#### 3.1 QueryOptions 设计原则

1. **不可变**：使用 `frozen=True`，避免参数复用导致的 bug
2. **通用**：使用 `filters` 统一处理所有筛选条件
3. **便捷**：提供 `with_*()` 方法，方便创建新对象

#### 3.2 QueryOptions 参数说明

```python
@dataclass(frozen=True)
class QueryOptions:
    # 时间范围
    date_range: Optional[Tuple[str, str]] = None  # (start_date, end_date)
    time_range: Optional[Tuple[str, str]] = None  # (start_time, end_time)
    
    # 通用筛选
    filters: Optional[Dict[str, Any]] = None
    
    # 排序
    order_by: str = "created_at"
    order_desc: bool = True
    
    # 分页
    page: Optional[int] = None
    page_size: Optional[int] = None
    
    # 字段选择
    fields: Optional[List[str]] = None
```

#### 3.3 使用示例

**基本查询**：

```python
from lifeprism.storage import Store, QueryOptions

# 查询今日活跃 todos
options = QueryOptions(
    date_range=("2026-04-24", "2026-04-24"),
    filters={'state': 'active'}
)
todos, total = Store.todo.query_todos(options)
```

**链式调用**（推荐）：

```python
# 创建基础查询选项
base = QueryOptions(filters={'state': 'active'})

# 查询不同月份的数据（base 保持不变）
april_todos, _ = Store.todo.query_todos(
    base.with_date_range("2026-04-01", "2026-04-30")
)
may_todos, _ = Store.todo.query_todos(
    base.with_date_range("2026-05-01", "2026-05-31")
)
```

**复杂查询**：

```python
# 多条件组合
options = QueryOptions(
    date_range=("2026-04-01", "2026-04-30"),
    filters={'state': 'active', 'priority': 'high'},
    order_by='created_at',
    order_desc=True
).with_page(1, 20)

todos, total = Store.todo.query_todos(options)
```

**IN 查询**：

```python
# 查询多个 ID
options = QueryOptions(
    filters={'id': ['id1', 'id2', 'id3']}
)
todos, total = Store.todo.query_todos(options)
```

**NULL 查询**：

```python
# 查询未删除的记录
options = QueryOptions(
    filters={'deleted_at': None}
)
todos, total = Store.todo.query_todos(options)
```

### 4. Service 层使用规范

#### 4.1 导入方式

```python
# server/services/todo_service.py
from lifeprism.storage import Store, QueryOptions

class TodoService:
    def get_active_todos(self, date: str):
        """获取指定日期的活跃 todos"""
        options = QueryOptions(
            date_range=(date, date),
            filters={'state': 'active'}
        )
        todos, total = Store.todo.query_todos(options)
        
        # 业务逻辑处理
        return self._process_todos(todos)
```

#### 4.2 职责边界

**Service 应该做的**：
- 业务逻辑判断
- 事务协调（调用多个 Provider/Aggregator）
- 外部 API 调用
- 数据验证和转换
- 权限检查

**Service 不应该做的**：
- 直接写 SQL 语句
- 绕过 Provider 直接操作数据库
- 在 Service 中实现数据聚合逻辑（应该在 Aggregator 中）

## 内部实现说明

### 1. QueryOptions 实现

```python
from dataclasses import dataclass, replace
from typing import Optional, List, Dict, Any, Tuple

@dataclass(frozen=True)
class QueryOptions:
    """
    查询选项（通用的不可变查询参数类）
    
    设计原则：
    1. 不可变：使用 frozen=True，避免参数复用导致的 bug
    2. 通用：使用 filters 统一处理所有筛选条件，适配任何表结构
    3. 便捷：提供 with_*() 方法，方便创建新对象
    """
    
    date_range: Optional[Tuple[str, str]] = None
    time_range: Optional[Tuple[str, str]] = None
    filters: Optional[Dict[str, Any]] = None
    order_by: str = "created_at"
    order_desc: bool = True
    page: Optional[int] = None
    page_size: Optional[int] = None
    fields: Optional[List[str]] = None
    
    def __post_init__(self):
        """参数验证"""
        if self.page is not None and self.page < 1:
            raise ValueError("page must be >= 1")
        if self.page_size is not None:
            if self.page_size < 1 or self.page_size > 1000:
                raise ValueError("page_size must be between 1 and 1000")
    
    def with_date_range(self, start: str, end: str) -> 'QueryOptions':
        """返回新对象，修改日期范围"""
        return replace(self, date_range=(start, end))
    
    def with_time_range(self, start: str, end: str) -> 'QueryOptions':
        """返回新对象，修改时间范围"""
        return replace(self, time_range=(start, end))
    
    def with_filters(self, **filters) -> 'QueryOptions':
        """返回新对象，合并筛选条件"""
        new_filters = {**(self.filters or {}), **filters}
        return replace(self, filters=new_filters)
    
    def with_order(self, field: str, desc: bool = True) -> 'QueryOptions':
        """返回新对象，修改排序"""
        return replace(self, order_by=field, order_desc=desc)
    
    def with_page(self, page: int, page_size: int = 20) -> 'QueryOptions':
        """返回新对象，设置分页"""
        return replace(self, page=page, page_size=page_size)
    
    def with_fields(self, *fields: str) -> 'QueryOptions':
        """返回新对象，设置返回字段"""
        return replace(self, fields=list(fields))
```

### 2. Provider 查询实现模板

```python
def query_todos(
    self,
    options: Optional[QueryOptions] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """通用查询接口"""
    if options is None:
        options = QueryOptions()
    
    with self.db.get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. 构建 SELECT 子句（白名单验证）
        if options.fields:
            invalid_fields = set(options.fields) - self._SELECT_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid select fields: {invalid_fields}")
            select_clause = ", ".join(options.fields)
        else:
            select_clause = "*"
        
        # 2. 构建 WHERE 子句（动态条件）
        conditions = []
        params = []
        
        # 日期范围
        if options.date_range:
            start_date, end_date = options.date_range
            if start_date:
                conditions.append("date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("date <= ?")
                params.append(end_date)
        
        # 时间范围
        if options.time_range:
            start_time, end_time = options.time_range
            if start_time:
                conditions.append("time >= ?")
                params.append(start_time)
            if end_time:
                conditions.append("time <= ?")
                params.append(end_time)
        
        # 通用筛选（白名单验证）
        if options.filters:
            for field, value in options.filters.items():
                if field not in self._FILTER_FIELDS:
                    raise ValueError(f"Invalid filter field: {field}")
                
                if value is None:
                    conditions.append(f"{field} IS NULL")
                elif isinstance(value, (list, tuple)):
                    placeholders = ','.join('?' * len(value))
                    conditions.append(f"{field} IN ({placeholders})")
                    params.extend(value)
                else:
                    conditions.append(f"{field} = ?")
                    params.append(value)
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        # 3. 构建 ORDER BY 子句（白名单验证）
        if options.order_by not in self._ORDER_FIELDS:
            raise ValueError(f"Invalid order_by field: {options.order_by}")
        order_direction = "DESC" if options.order_desc else "ASC"
        order_clause = f"ORDER BY {options.order_by} {order_direction}"
        
        # 4. 构建 LIMIT 子句
        limit_clause = ""
        if options.page and options.page_size:
            offset = (options.page - 1) * options.page_size
            limit_clause = f"LIMIT {options.page_size} OFFSET {offset}"
        
        # 5. 执行查询
        query = f"""
            SELECT {select_clause}
            FROM todo_list
            WHERE {where_clause}
            {order_clause}
            {limit_clause}
        """
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        
        # 6. 查询总数
        count_query = f"""
            SELECT COUNT(*) as total
            FROM todo_list
            WHERE {where_clause}
        """
        cursor.execute(count_query, params)
        total = cursor.fetchone()['total']
        
        return results, total
```

### 3. Store 统一导出实现

```python
# storage/__init__.py
from lifeprism.storage.providers import (
    DiaryProvider,
    TodoProvider,
    GoalProvider,
    # ... 其他 Provider
)
from lifeprism.storage.aggregators import (
    HabitAggregator,
    MoodAggregator,
    # ... 其他 Aggregator
)

class _Store:
    """Storage 层统一访问入口"""
    
    # Provider 实例
    diary = DiaryProvider()
    todo = TodoProvider()
    goal = GoalProvider()
    # ... 其他 Provider
    
    # Aggregator 实例
    habit_aggregator = HabitAggregator()
    mood_aggregator = MoodAggregator()
    # ... 其他 Aggregator

Store = _Store()
```

## 参考文档

- `docs/temp/refactor-repository-architecture-draft/2026-04-23-refactor-repository-architecture-draft.md` - 架构重构方案
- `docs/temp/refactor-repository-architecture-draft/reason-and-new-archiecture.md` - 重构原因和新架构
- `docs/ARCHITECTURE.md` - 项目架构文档

## 常见问题

### Q1: 为什么使用 Store 而不是直接导入 Provider？

**A**: Store 提供统一的访问入口，具有以下优势：
1. 类型提示：IDE 可以自动补全所有可用的 Provider 和 Aggregator
2. 单例管理：确保每个 Provider 只有一个实例
3. 易于测试：可以方便地 mock Store 进行单元测试
4. 易于维护：修改 Provider 实现时，不需要修改导入语句

### Q2: QueryOptions 为什么是不可变的？

**A**: 不可变设计避免了参数复用导致的 bug。例如：

```python
# 错误示例（如果 QueryOptions 可变）
options = QueryOptions(filters={'state': 'active'})
todos1, _ = Store.todo.query_todos(options)
options.filters['priority'] = 'high'  # 修改了原对象
todos2, _ = Store.todo.query_todos(options)  # 意外地包含了 priority 筛选

# 正确示例（不可变设计）
base = QueryOptions(filters={'state': 'active'})
todos1, _ = Store.todo.query_todos(base)
todos2, _ = Store.todo.query_todos(
    base.with_filters(priority='high')  # 创建新对象
)
# base 保持不变，可以安全复用
```

### Q3: 什么时候使用 Provider，什么时候使用 Aggregator？

**A**: 
- **使用 Provider**：单表操作，如查询、插入、更新、删除
- **使用 Aggregator**：需要组合多个表的数据，如获取习惯及其打卡记录

### Q4: Service 层可以直接写 SQL 吗？

**A**: 不可以。所有数据库操作必须通过 Provider 或 Aggregator。这样可以：
1. 避免 SQL 注入风险
2. 保持代码一致性
3. 便于测试和维护
4. 复用数据访问逻辑

### Q5: 如何处理复杂的统计查询？

**A**: 
1. 如果是单表统计，在 Provider 中实现 `aggregate_*()` 方法
2. 如果是多表统计，在 Aggregator 中实现
3. 如果涉及复杂的业务逻辑，在 Service 中组合多个 Provider/Aggregator 调用

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| 1.0 | 2026-04-24 | 初始版本，基于架构重构方案创建 |
