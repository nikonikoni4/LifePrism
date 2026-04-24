# Provider 编写规范（v2 - 通用方法版本）

**更新日期**: 2026-04-24  
**版本**: v2.0  
**变更**: 引入基类通用查询方法，减少代码重复

---

## 目录

1. [核心设计理念](#1-核心设计理念)
2. [基类通用方法](#2-基类通用方法)
3. [子类实现规范](#3-子类实现规范)
4. [QueryOptions 使用指南](#4-queryoptions-使用指南)
5. [特殊场景处理](#5-特殊场景处理)
6. [测试规范](#6-测试规范)

---

## 1. 核心设计理念

### 1.1 设计原则

**通用化 + 灵活性**：
- ✅ 在基类中实现通用查询逻辑（减少 70-80% 重复代码）
- ✅ 子类只需定义表元数据（表名、字段白名单）
- ✅ 特殊业务逻辑仍可在子类中实现

### 1.2 架构分层

```
LWBaseDataProvider (基类)
├── _generic_query()          # 通用查询方法（核心）
├── _build_select_clause()    # 构建 SELECT 子句
├── _build_where_clause()     # 构建 WHERE 子句
├── _build_order_clause()     # 构建 ORDER BY 子句
└── _build_limit_clause()     # 构建 LIMIT 子句

TodoProvider (子类)
├── _TABLE_NAME = "todo_list"           # 表名
├── _DATE_FIELD = "date"                # 日期字段名
├── _TIME_FIELD = None                  # 时间字段名（可选）
├── _FILTER_FIELDS = {...}              # 可筛选字段白名单
├── _ORDER_FIELDS = {...}               # 可排序字段白名单
├── _SELECT_FIELDS = {...}              # 可查询字段白名单
└── query_todos(options) -> 调用 _generic_query()
```

---

## 2. 基类通用方法

### 2.1 QueryOptions 定义

```python
# repository/query_options.py
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

### 2.2 基类通用查询方法

```python
# repository/base_providers/lw_base_data_provider.py
from typing import Optional, List, Dict, Any, Tuple, Set
from lifeprism.repository.query_options import QueryOptions

class LWBaseDataProvider:
    """
    数据提供者基类
    
    提供通用的查询方法，子类只需定义表元数据即可使用
    """
    
    # ==================== 子类必须定义的元数据 ====================
    
    _TABLE_NAME: Optional[str] = None           # 表名
    _DATE_FIELD: Optional[str] = None           # 日期字段名（如 'date', 'created_at'）
    _TIME_FIELD: Optional[str] = None           # 时间字段名（如 'time', 'trigger_time'）
    _FILTER_FIELDS: Set[str] = set()            # 可筛选字段白名单
    _ORDER_FIELDS: Set[str] = set()             # 可排序字段白名单
    _SELECT_FIELDS: Set[str] = set()            # 可查询字段白名单
    _UPDATE_FIELDS: Set[str] = set()            # 可更新字段白名单
    
    # ==================== 通用查询方法（核心） ====================
    
    def _generic_query(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询方法
        
        子类只需定义表名和白名单，即可使用此方法
        
        Args:
            options: 查询选项（QueryOptions 对象）
        
        Returns:
            (记录列表, 总记录数)
        
        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 字段白名单验证失败、不支持的查询类型
        """
        if options is None:
            options = QueryOptions()
        
        # 验证子类是否定义了必要属性
        if not self._TABLE_NAME:
            raise NotImplementedError(
                f"{self.__class__.__name__} 必须定义 _TABLE_NAME"
            )
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 构建 SELECT 子句
            select_clause = self._build_select_clause(options)
            
            # 2. 构建 WHERE 子句
            where_clause, params = self._build_where_clause(options)
            
            # 3. 构建 ORDER BY 子句
            order_clause = self._build_order_clause(options)
            
            # 4. 构建 LIMIT 子句
            limit_clause = self._build_limit_clause(options)
            
            # 5. 执行查询
            query = f"""
                SELECT {select_clause}
                FROM {self._TABLE_NAME}
                WHERE {where_clause}
                {order_clause}
                {limit_clause}
            """
            
            cursor.execute(query, params)
            results = [dict(row) for row in cursor.fetchall()]
            
            # 6. 查询总数
            count_query = f"""
                SELECT COUNT(*) as total
                FROM {self._TABLE_NAME}
                WHERE {where_clause}
            """
            cursor.execute(count_query, params)
            total = cursor.fetchone()['total']
            
            return results, total
    
    # ==================== INSERT 通用方法 ====================
    
    def _generic_insert(
        self,
        data: Dict[str, Any],
        id_prefix: Optional[str] = None,
        auto_order_index: bool = False
    ) -> str:
        """
        通用插入方法
        
        Args:
            data: 数据字典
            id_prefix: ID 前缀（如 't-'），None 则不生成 ID
            auto_order_index: 是否自动计算 order_index
        
        Returns:
            新记录的 ID
        
        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 数据验证失败
        
        Examples:
            # 插入 todo（自动生成 ID 和 order_index）
            todo_id = self._generic_insert(
                data={'title': '测试任务', 'state': 'active'},
                id_prefix='t-',
                auto_order_index=True
            )
            
            # 插入 diary（使用自定义 ID）
            diary_id = self._generic_insert(
                data={'date': '2026-04-24', 'content': '日记内容'}
            )
        """
        if not self._TABLE_NAME:
            raise NotImplementedError(
                f"{self.__class__.__name__} 必须定义 _TABLE_NAME"
            )
        
        # 1. 生成 ID（如果需要）
        if id_prefix:
            import uuid
            data['id'] = f"{id_prefix}{uuid.uuid4().hex[:8]}"
        
        # 2. 计算 order_index（如果需要）
        if auto_order_index:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"SELECT MAX(order_index) FROM {self._TABLE_NAME}"
                )
                max_order = cursor.fetchone()[0] or 0
                data['order_index'] = max_order + 1
        
        # 3. 构建 INSERT 语句
        columns = list(data.keys())
        placeholders = ','.join(['?'] * len(columns))
        values = [data[col] for col in columns]
        
        sql = f"""
            INSERT INTO {self._TABLE_NAME} ({', '.join(columns)})
            VALUES ({placeholders})
        """
        
        # 4. 执行插入
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                return data.get('id', str(cursor.lastrowid))
        except Exception as e:
            logger.error(f"Failed to insert into {self._TABLE_NAME}: {e}")
            raise
    
    # ==================== UPDATE 通用方法 ====================
    
    def _generic_update(
        self,
        record_id: str,
        data: Dict[str, Any],
        auto_update: bool = True
    ) -> bool:
        """
        通用更新方法
        
        Args:
            record_id: 记录 ID
            data: 更新数据
            auto_update: 是否自动更新 updated_at
        
        Returns:
            是否成功
        
        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
            ValueError: 字段白名单验证失败
        
        Examples:
            # 更新 todo
            success = self._generic_update(
                record_id='t-12345678',
                data={'title': '新标题', 'state': 'completed'},
                auto_update=True
            )
        """
        if not self._TABLE_NAME:
            raise NotImplementedError(
                f"{self.__class__.__name__} 必须定义 _TABLE_NAME"
            )
        
        if not data:
            return True
        
        # 1. 白名单验证（如果定义了）
        if self._UPDATE_FIELDS:
            invalid_fields = set(data.keys()) - self._UPDATE_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid update fields: {invalid_fields}")
        
        # 2. 自动更新时间戳
        if auto_update and 'updated_at' not in data:
            from datetime import datetime
            data['updated_at'] = datetime.now().isoformat()
        
        # 3. 构建 UPDATE 语句
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        values = list(data.values()) + [record_id]
        
        sql = f"""
            UPDATE {self._TABLE_NAME}
            SET {set_clause}
            WHERE id = ?
        """
        
        # 4. 执行更新
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update {self._TABLE_NAME}: {e}")
            raise
    
    # ==================== DELETE 通用方法 ====================
    
    def _generic_delete(self, record_id: str) -> bool:
        """
        通用删除方法
        
        Args:
            record_id: 记录 ID
        
        Returns:
            是否成功
        
        Raises:
            NotImplementedError: 子类未定义 _TABLE_NAME
        
        Examples:
            # 删除 todo
            success = self._generic_delete('t-12345678')
        """
        if not self._TABLE_NAME:
            raise NotImplementedError(
                f"{self.__class__.__name__} 必须定义 _TABLE_NAME"
            )
        
        sql = f"DELETE FROM {self._TABLE_NAME} WHERE id = ?"
        
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, (record_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to delete from {self._TABLE_NAME}: {e}")
            raise

    
    # ==================== 辅助方法（构建 SQL 子句） ====================
    
    def _build_select_clause(self, options: QueryOptions) -> str:
        """构建 SELECT 子句（白名单验证）"""
        if options.fields:
            invalid_fields = set(options.fields) - self._SELECT_FIELDS
            if invalid_fields:
                raise ValueError(f"Invalid select fields: {invalid_fields}")
            return ", ".join(options.fields)
        return "*"
    
    def _build_where_clause(
        self, 
        options: QueryOptions
    ) -> Tuple[str, List[Any]]:
        """构建 WHERE 子句（动态条件 + 白名单验证）"""
        conditions = []
        params = []
        
        # 日期范围（只有当表有日期字段时才处理）
        if options.date_range:
            if not self._DATE_FIELD:
                raise ValueError(
                    f"{self._TABLE_NAME} 表不支持日期范围查询（未定义 _DATE_FIELD）"
                )
            start_date, end_date = options.date_range
            if start_date:
                conditions.append(f"{self._DATE_FIELD} >= ?")
                params.append(start_date)
            if end_date:
                conditions.append(f"{self._DATE_FIELD} <= ?")
                params.append(end_date)
        
        # 时间范围（只有当表有时间字段时才处理）
        if options.time_range:
            if not self._TIME_FIELD:
                raise ValueError(
                    f"{self._TABLE_NAME} 表不支持时间范围查询（未定义 _TIME_FIELD）"
                )
            start_time, end_time = options.time_range
            if start_time:
                conditions.append(f"{self._TIME_FIELD} >= ?")
                params.append(start_time)
            if end_time:
                conditions.append(f"{self._TIME_FIELD} <= ?")
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
        return where_clause, params
    
    def _build_order_clause(self, options: QueryOptions) -> str:
        """构建 ORDER BY 子句（白名单验证）"""
        if options.order_by not in self._ORDER_FIELDS:
            raise ValueError(f"Invalid order_by field: {options.order_by}")
        order_direction = "DESC" if options.order_desc else "ASC"
        return f"ORDER BY {options.order_by} {order_direction}"
    
    def _build_limit_clause(self, options: QueryOptions) -> str:
        """构建 LIMIT 子句"""
        if options.page and options.page_size:
            offset = (options.page - 1) * options.page_size
            return f"LIMIT {options.page_size} OFFSET {offset}"
        return ""
```


---

## 3. 子类实现规范

### 3.1 标准实现模板

```python
# repository/providers/todo_provider.py
"""
Todo 数据提供者

职责：
- 提供 todo_list 表的所有数据访问接口
- 不包含业务逻辑，只做数据库操作
- 返回原始数据（Dict），不做业务转换
"""
from typing import Optional, List, Dict, Any, Tuple, Set
from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.query_options import QueryOptions
from lifeprism.utils import LazySingleton

class TodoProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """Todo 数据提供者"""
    
    # ==================== 表元数据定义 ====================
    
    _TABLE_NAME = "todo_list"
    _DATE_FIELD = "date"           # ✅ todo_list 表有 date 字段
    _TIME_FIELD = None             # ❌ todo_list 表没有 time 字段
    
    _FILTER_FIELDS: Set[str] = {
        'id', 'date', 'state', 'status', 'goal_id', 'category_id',
        'priority', 'title', 'content', 'created_at', 'updated_at'
    }
    
    _ORDER_FIELDS: Set[str] = {
        'id', 'date', 'created_at', 'updated_at', 'priority', 
        'state', 'order_index'
    }
    
    _SELECT_FIELDS: Set[str] = {
        'id', 'date', 'state', 'status', 'goal_id', 'category_id',
        'priority', 'title', 'content', 'created_at', 'updated_at',
        'order_index', 'cross_day'
    }
    
    _UPDATE_FIELDS: Set[str] = {
        'title', 'content', 'state', 'status', 'priority', 
        'goal_id', 'category_id', 'cross_day'
    }
    
    # ==================== 查询方法 ====================
    
    def query_todos(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口（使用基类方法）
        
        Args:
            options: 查询选项（QueryOptions 对象）
        
        Returns:
            (记录列表, 总记录数)
        
        Examples:
            # 查询今日活跃 todos
            options = QueryOptions(
                date_range=("2026-04-23", "2026-04-23"),
                filters={'state': 'active'}
            )
            todos, total = provider.query_todos(options)
            
            # 查询某个目标的所有 todos，按优先级排序
            options = QueryOptions(
                filters={'goal_id': 'goal_123'},
                order_by='priority',
                order_desc=True
            )
            todos, total = provider.query_todos(options)
            
            # 分页查询
            options = QueryOptions().with_page(page=1, page_size=20)
            todos, total = provider.query_todos(options)
        """
        return self._generic_query(options)  # ✅ 直接调用基类方法
    
    def get_todo_by_id(self, todo_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 查询单条记录（使用基类方法）"""
        options = QueryOptions(filters={'id': todo_id})
        results, _ = self._generic_query(options)
        return results[0] if results else None
    
    # ==================== 插入方法 ====================
    
    def insert_todo(self, data: Dict[str, Any]) -> str:
        """插入新记录（使用基类方法）"""
        return self._generic_insert(
            data=data,
            id_prefix='t-',              # 自动生成 ID：t-xxxxxxxx
            auto_order_index=True        # 自动计算 order_index
        )
    
    # ==================== 更新方法 ====================
    
    def update_todo(self, todo_id: str, data: Dict[str, Any]) -> bool:
        """更新记录（使用基类方法）"""
        return self._generic_update(
            record_id=todo_id,
            data=data,
            auto_update=True          # 自动更新 updated_at
        )
    
    # ==================== 删除方法 ====================
    
    def delete_todo(self, todo_id: str) -> bool:
        """删除记录（使用基类方法）"""
        return self._generic_delete(todo_id)
```

**关键点**：
- ✅ 所有 5 个核心方法都使用基类通用方法
- ✅ 只需定义元数据和调用参数
- ✅ 代码量减少 70-80%




### 3.2 不同表类型的实现示例

#### 示例 1：有日期字段的表（diary）

```python
class DiaryProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """日记数据提供者"""
    
    _TABLE_NAME = "diary"
    _DATE_FIELD = "date"      # ✅ 有日期字段
    _TIME_FIELD = None        # ❌ 没有时间字段
    
    _FILTER_FIELDS = {'date', 'mood', 'weather', 'tags'}
    _ORDER_FIELDS = {'date', 'created_at'}
    _SELECT_FIELDS = {'date', 'content', 'mood', 'weather', 'tags', 'created_at'}
    
    def query_diaries(self, options: Optional[QueryOptions] = None):
        """查询日记（直接使用基类方法）"""
        return self._generic_query(options)
```

#### 示例 2：没有日期字段的表（goal）

```python
class GoalProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """目标数据提供者"""
    
    _TABLE_NAME = "goal"
    _DATE_FIELD = None        # ❌ 没有日期字段
    _TIME_FIELD = None        # ❌ 没有时间字段
    
    _FILTER_FIELDS = {'id', 'status', 'category_id', 'name'}
    _ORDER_FIELDS = {'id', 'created_at', 'order_index'}
    _SELECT_FIELDS = {'id', 'name', 'status', 'category_id', 'created_at'}
    
    def query_goals(self, options: Optional[QueryOptions] = None):
        """查询目标（直接使用基类方法）"""
        return self._generic_query(options)
        # 注意：如果用户传了 date_range，会抛出友好的错误提示
```

#### 示例 3：有日期和时间字段的表（goal_journal）

```python
class JournalProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """目标日志数据提供者"""
    
    _TABLE_NAME = "goal_journal"
    _DATE_FIELD = "date"      # ✅ 有日期字段
    _TIME_FIELD = "time"      # ✅ 有时间字段
    
    _FILTER_FIELDS = {'id', 'date', 'time', 'goal_id', 'content'}
    _ORDER_FIELDS = {'date', 'time', 'created_at'}
    _SELECT_FIELDS = {'id', 'date', 'time', 'goal_id', 'content', 'created_at'}
    
    def query_journals(self, options: Optional[QueryOptions] = None):
        """查询目标日志（支持日期和时间范围）"""
        return self._generic_query(options)
```

### 3.3 方法命名规范

| 操作类型 | 命名模式 | 示例 | 返回值 |
|---------|---------|------|--------|
| **通用查询** | `query_{table}()` | `query_todos()` | `Tuple[List[Dict], int]` |
| **单条查询** | `get_{table}_by_{field}()` | `get_todo_by_id()` | `Optional[Dict]` |
| **插入** | `insert_{table}()` | `insert_todo()` | `str` (新记录ID) |
| **更新** | `update_{table}()` | `update_todo()` | `bool` (是否成功) |
| **删除** | `delete_{table}()` | `delete_todo()` | `bool` (是否成功) |
| **批量操作** | `batch_{action}_{table}()` | `batch_delete_todos()` | `int` (影响行数) |

### 3.4 必须实现的方法（5 个核心方法）

每个 provider 必须实现以下 5 个核心方法：

- [ ] `query_{table}()` - 通用查询接口（调用 `_generic_query()`）
- [ ] `get_{table}_by_id()` - 按 ID 查询（调用 `_generic_query()`）
- [ ] `insert_{table}()` - 插入记录（调用 `_generic_insert()`）
- [ ] `update_{table}()` - 更新记录（调用 `_generic_update()`）
- [ ] `delete_{table}()` - 删除记录（调用 `_generic_delete()`）

**代码量对比**：

| 方法 | 传统实现 | 使用通用方法 | 减少代码量 |
|------|---------|------------|-----------|
| `query_todos()` | ~80 行 | 1 行 | 98% ⬇️ |
| `get_todo_by_id()` | ~10 行 | 3 行 | 70% ⬇️ |
| `insert_todo()` | ~20 行 | 5 行 | 75% ⬇️ |
| `update_todo()` | ~25 行 | 5 行 | 80% ⬇️ |
| `delete_todo()` | ~10 行 | 1 行 | 90% ⬇️ |
| **总计** | **~145 行** | **~15 行** | **90% ⬇️** |


---

## 4. QueryOptions 使用指南

### 4.1 基础用法

```python
# 1. 简单查询（使用默认参数）
options = QueryOptions()
todos, total = provider.query_todos(options)

# 2. 日期范围查询
options = QueryOptions(
    date_range=("2026-04-01", "2026-04-30")
)
todos, total = provider.query_todos(options)

# 3. 条件筛选
options = QueryOptions(
    filters={'state': 'active', 'goal_id': 'goal_123'}
)
todos, total = provider.query_todos(options)

# 4. 排序
options = QueryOptions(
    order_by='priority',
    order_desc=True
)
todos, total = provider.query_todos(options)

# 5. 分页
options = QueryOptions(
    page=1,
    page_size=20
)
todos, total = provider.query_todos(options)
```

### 4.2 链式调用（推荐）

```python
# 基础查询对象
base = QueryOptions(filters={'state': 'active'})

# 查询 4 月的活跃 todos
april_todos, _ = provider.query_todos(
    base.with_date_range("2026-04-01", "2026-04-30")
)

# 查询 5 月的活跃 todos
may_todos, _ = provider.query_todos(
    base.with_date_range("2026-05-01", "2026-05-31")
)

# base 保持不变，可以安全复用
```

### 4.3 复杂查询

```python
# IN 查询
options = QueryOptions(
    filters={'id': ['id1', 'id2', 'id3']}
)

# NULL 查询
options = QueryOptions(
    filters={'deleted_at': None}
)

# 组合查询
options = QueryOptions(
    date_range=("2026-04-01", "2026-04-30"),
    filters={'state': 'active', 'priority': 'high'},
    order_by='created_at',
    order_desc=True,
    page=1,
    page_size=20
)
```

### 4.4 字段选择

```python
# 只查询特定字段（减少数据传输）
options = QueryOptions(
    fields=['id', 'title', 'state']
)
todos, total = provider.query_todos(options)
# 返回：[{'id': '...', 'title': '...', 'state': '...'}, ...]
```

---

## 5. 特殊场景处理

### 5.1 特殊业务逻辑（需要在子类中实现）

对于有特殊业务逻辑的查询，仍需在子类中单独实现：

```python
class TodoProvider(LWBaseDataProvider):
    # ... 元数据定义 ...
    
    def query_todos_with_cross_day(
        self,
        date: str,
        include_cross_day: bool = True
    ) -> List[Dict[str, Any]]:
        """
        查询指定日期的 todos（支持跨天任务）
        
        特殊逻辑：跨天任务会出现在多个日期
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            if include_cross_day:
                sql = """
                SELECT * FROM todo_list 
                WHERE date = ? 
                   OR (cross_day = 1 AND state = 'active' AND date < ?)
                ORDER BY order_index ASC
                """
                cursor.execute(sql, (date, date))
            else:
                sql = "SELECT * FROM todo_list WHERE date = ? ORDER BY order_index ASC"
                cursor.execute(sql, (date,))
            
            return [dict(row) for row in cursor.fetchall()]
```

### 5.2 多表 JOIN 查询

```python
class CommitmentProvider(LWBaseDataProvider):
    # ... 元数据定义 ...
    
    def query_commitments_with_value(
        self,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        查询承诺（LEFT JOIN user_values 获取 value_keywords）
        
        特殊逻辑：需要关联 user_values 表
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            conditions = []
            params = []
            
            if status:
                conditions.append("c.status = ?")
                params.append(status)
            
            where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
            
            sql = f"""
                SELECT c.*, v.keywords AS value_keywords
                FROM commitments c
                LEFT JOIN user_values v ON c.value_id = v.id
                {where}
                ORDER BY c.created_at DESC
            """
            
            cursor.execute(sql, params)
            return [dict(row) for row in cursor.fetchall()]
```

### 5.3 统计聚合查询

```python
class GoalProvider(LWBaseDataProvider):
    # ... 元数据定义 ...
    
    def calculate_time_invested(self, goal_id: str) -> int:
        """
        计算目标的累计投入时间（秒）
        
        特殊逻辑：需要 SUM 聚合
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COALESCE(SUM(duration), 0) as total_seconds
                FROM user_app_behavior_log
                WHERE link_to_goal_id = ?
            """, (goal_id,))
            return cursor.fetchone()['total_seconds']
```


---

## 6. 测试规范

### 6.1 Provider 单元测试

为每个新 provider 编写单元测试，确保方法本身没有问题。

#### 测试数据来源

使用测试数据库文件：`test/localData/dataset/lifewatch_ai.db`

#### 测试流程

1. 在 fixture 中先插入测试数据（insert）
2. 执行测试
3. 测试完成后清理并删除相关数据

#### 测试示例

```python
# test/core/providers/test_todo_provider.py
import pytest
from lifeprism.repository.providers.todo_provider import TodoProvider
from lifeprism.repository.query_options import QueryOptions

@pytest.fixture
def todo_provider():
    """创建 TodoProvider 实例"""
    return TodoProvider()

@pytest.fixture
def sample_todo_data():
    """测试数据"""
    return {
        'date': '2026-04-24',
        'title': '测试任务',
        'state': 'active',
        'priority': 'high'
    }

class TestTodoProvider:
    """TodoProvider 单元测试"""
    
    def test_query_todos_basic(self, todo_provider, sample_todo_data):
        """测试基础查询"""
        # 1. 插入测试数据
        todo_id = todo_provider.insert_todo(sample_todo_data)
        
        try:
            # 2. 查询
            options = QueryOptions(filters={'id': todo_id})
            results, total = todo_provider.query_todos(options)
            
            # 3. 验证
            assert total == 1
            assert results[0]['title'] == '测试任务'
            assert results[0]['state'] == 'active'
        
        finally:
            # 4. 清理
            todo_provider.delete_todo(todo_id)
    
    def test_query_todos_with_date_range(self, todo_provider):
        """测试日期范围查询"""
        options = QueryOptions(
            date_range=("2026-04-01", "2026-04-30")
        )
        results, total = todo_provider.query_todos(options)
        
        # 验证所有结果都在日期范围内
        for todo in results:
            assert "2026-04-01" <= todo['date'] <= "2026-04-30"
    
    def test_query_todos_with_filters(self, todo_provider):
        """测试条件筛选"""
        options = QueryOptions(
            filters={'state': 'active'}
        )
        results, total = todo_provider.query_todos(options)
        
        # 验证所有结果都是 active 状态
        for todo in results:
            assert todo['state'] == 'active'
    
    def test_query_todos_pagination(self, todo_provider):
        """测试分页"""
        options = QueryOptions(
            page=1,
            page_size=10
        )
        results, total = todo_provider.query_todos(options)
        
        # 验证返回数量不超过 page_size
        assert len(results) <= 10
    
    def test_get_todo_by_id(self, todo_provider, sample_todo_data):
        """测试按 ID 查询"""
        # 1. 插入测试数据
        todo_id = todo_provider.insert_todo(sample_todo_data)
        
        try:
            # 2. 查询
            result = todo_provider.get_todo_by_id(todo_id)
            
            # 3. 验证
            assert result is not None
            assert result['id'] == todo_id
            assert result['title'] == '测试任务'
        
        finally:
            # 4. 清理
            todo_provider.delete_todo(todo_id)
```

### 6.2 Service 快照测试

在替换 service 中的 provider 调用后，运行快照测试验证行为一致性。

详见：`docs/temp/refactor-repository-architecture-draft/2026-04-23-provider-migration-testing-guide.md`

---

## 7. 实施步骤

### 7.1 第一步：实现基类通用方法

1. 在 `repository/query_options.py` 中定义 `QueryOptions` 类
2. 在 `repository/base_providers/lw_base_data_provider.py` 中实现 `_generic_query()` 方法
3. 编写基类方法的单元测试

### 7.2 第二步：为每个 provider 编写特定方法

对于每个 provider（如 `diary_provider`）：

1. **定义表元数据**
   ```python
   _TABLE_NAME = "diary"
   _DATE_FIELD = "date"
   _TIME_FIELD = None
   _FILTER_FIELDS = {...}
   _ORDER_FIELDS = {...}
   _SELECT_FIELDS = {...}
   ```

2. **实现 query 方法（使用通用方法）**
   ```python
   def query_diaries(self, options: Optional[QueryOptions] = None):
       return self._generic_query(options)
   ```

3. **实现其他核心方法**
   - `get_diary_by_date()` - 可使用 `_generic_query()`
   - `insert_diary()` - 手动实现
   - `update_diary()` - 手动实现
   - `delete_diary()` - 手动实现

4. **实现特殊业务方法**（如果需要）
   - 跨天任务、多表 JOIN、统计聚合等

5. **编写单元测试**
   - 测试通用查询方法
   - 测试特殊业务方法

### 7.3 第三步：逐步替换 service 中的旧方法

1. 替换部分内容
2. 运行 step-1 中的快照测试
3. 重复 1~2，直到全部内容完成替换

---

## 8. 优势总结

### 8.1 代码复用

- ✅ 减少 **90%** 的重复代码（5 个核心方法）
- ✅ 核心 CRUD 逻辑只写一次
- ✅ 新 provider 开发时间减少 **80%**
- ✅ 每个 provider 从 ~150 行减少到 ~20 行

### 8.2 一致性

- ✅ 统一的错误处理
- ✅ 统一的白名单验证
- ✅ 统一的分页逻辑
- ✅ 统一的 ID 生成规则
- ✅ 统一的时间戳处理

### 8.3 易维护

- ✅ 修改 CRUD 逻辑只需改基类
- ✅ 表结构变更只需更新元数据
- ✅ 易于理解和扩展
- ✅ 减少 bug（一处修改，全局生效）

### 8.4 灵活性

- ✅ 特殊业务逻辑仍可在子类中实现
- ✅ 不强制使用通用方法
- ✅ 向后兼容现有代码
- ✅ 可以覆盖通用方法实现自定义逻辑

---

## 9. 通用方法 vs 手动实现对比

### 9.1 代码量对比

**传统实现（TodoProvider）**：
```python
class TodoProvider(LWBaseDataProvider):
    def insert_todo(self, data: Dict[str, Any]) -> str:
        """插入 todo（传统实现）"""
        # 1. 生成 ID
        import uuid
        todo_id = f"t-{uuid.uuid4().hex[:8]}"
        data['id'] = todo_id
        
        # 2. 计算 order_index
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(order_index) FROM todo_list")
            max_order = cursor.fetchone()[0] or 0
            data['order_index'] = max_order + 1
        
        # 3. 构建 INSERT 语句
        columns = list(data.keys())
        placeholders = ','.join(['?'] * len(columns))
        values = [data[col] for col in columns]
        sql = f"INSERT INTO todo_list ({', '.join(columns)}) VALUES ({placeholders})"
        
        # 4. 执行插入
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, values)
                conn.commit()
                return todo_id
        except Exception as e:
            logger.error(f"Failed to insert todo: {e}")
            raise
    # 总计：~25 行代码
```

**使用通用方法**：
```python
class TodoProvider(LWBaseDataProvider):
    def insert_todo(self, data: Dict[str, Any]) -> str:
        """插入 todo（使用通用方法）"""
        return self._generic_insert(
            data=data,
            id_prefix='t-',
            auto_order_index=True
        )
    # 总计：5 行代码，减少 80%
```

### 9.2 维护成本对比

| 场景 | 传统实现 | 使用通用方法 |
|------|---------|------------|
| **修改 ID 生成规则** | 修改 20+ 个 provider | 修改基类 1 处 |
| **添加错误日志** | 修改 20+ 个 provider | 修改基类 1 处 |
| **修改时间戳格式** | 修改 20+ 个 provider | 修改基类 1 处 |
| **添加新 provider** | 复制粘贴 ~150 行 | 定义元数据 ~20 行 |
| **修复 bug** | 可能遗漏某些 provider | 一次修复，全局生效 |

### 9.3 性能对比

| 操作 | 传统实现 | 通用方法 | 性能差异 |
|------|---------|---------|---------|
| INSERT | 直接 SQL | 通用方法 + SQL | 几乎无差异 |
| UPDATE | 直接 SQL | 通用方法 + SQL | 几乎无差异 |
| DELETE | 直接 SQL | 通用方法 + SQL | 几乎无差异 |
| QUERY | 直接 SQL | 通用方法 + SQL | 几乎无差异 |

**结论**：通用方法的性能开销可忽略不计（< 1ms）

---

## 10. 注意事项

### 10.1 表字段映射

- 确保 `_DATE_FIELD` 和 `_TIME_FIELD` 正确映射到表的实际字段名
- 如果表没有日期/时间字段，设置为 `None`

### 10.2 白名单维护

- 白名单必须与表结构保持同步
- 添加新字段时，记得更新所有相关白名单
- `_UPDATE_FIELDS` 应该只包含允许用户修改的字段（排除 `id`, `created_at` 等）

### 10.3 特殊逻辑

- 复杂的业务逻辑不要强行使用通用方法
- 多表 JOIN、统计聚合等仍需手动实现
- 级联删除等特殊操作在子类中单独实现

### 10.4 性能考虑

- 通用方法适用于大部分场景
- 对于高频查询，可以在子类中优化
- 性能开销可忽略不计（< 1ms）

### 10.5 ID 生成规则

- 使用 `id_prefix` 参数统一 ID 格式：`{prefix}-{uuid[:8]}`
- 例如：`t-12345678`（todo）、`g-abcdef12`（goal）
- 如果表使用自增 ID 或自定义 ID，不传 `id_prefix` 参数

### 10.6 时间戳处理

- `auto_update=True` 会自动更新 `updated_at` 字段
- 时间格式：ISO 8601（`2026-04-24T10:30:00`）
- 如果表没有 `updated_at` 字段，设置 `auto_update=False`

---

## 11. 实施步骤（更新版）

### 11.1 第一步：实现基类通用方法

1. 在 `repository/query_options.py` 中定义 `QueryOptions` 类
2. 在 `repository/base_providers/lw_base_data_provider.py` 中实现：
   - `_generic_query()` - 通用查询方法
   - `_generic_insert()` - 通用插入方法
   - `_generic_update()` - 通用更新方法
   - `_generic_delete()` - 通用删除方法
3. 编写基类方法的单元测试

### 11.2 第二步：为每个 provider 编写特定方法

对于每个 provider（如 `diary_provider`）：

1. **定义表元数据**
   ```python
   _TABLE_NAME = "diary"
   _DATE_FIELD = "date"
   _TIME_FIELD = None
   _FILTER_FIELDS = {...}
   _ORDER_FIELDS = {...}
   _SELECT_FIELDS = {...}
   _UPDATE_FIELDS = {...}  # 新增
   ```

2. **实现 5 个核心方法（使用通用方法）**
   ```python
   def query_diaries(self, options):
       return self._generic_query(options)
   
   def get_diary_by_date(self, date):
       options = QueryOptions(filters={'date': date})
       results, _ = self._generic_query(options)
       return results[0] if results else None
   
   def insert_diary(self, data):
       return self._generic_insert(data)
   
   def update_diary(self, date, data):
       return self._generic_update(date, data)
   
   def delete_diary(self, date):
       return self._generic_delete(date)
   ```

3. **实现特殊业务方法**（如果需要）
   - 跨天任务、多表 JOIN、统计聚合等

4. **编写单元测试**
   - 测试通用查询方法
   - 测试 INSERT/UPDATE/DELETE 方法
   - 测试特殊业务方法

### 11.3 第三步：逐步替换 service 中的旧方法

1. 替换部分内容
2. 运行 step-1 中的快照测试
3. 重复 1~2，直到全部内容完成替换

---

## 12. 参考资料

- `docs/temp/refactor-repository-architecture-draft/2026-04-23-refactor-repository-architecture-draft.md` - 重构方案总览
- `docs/temp/refactor-repository-architecture-draft/2026-04-23-provider-migration-testing-guide.md` - 测试规范

---

## 附录：完整的 Provider 示例

```python
# repository/providers/diary_provider.py
"""
Diary 数据提供者

职责：
- 提供 diary 表的所有数据访问接口
- 不包含业务逻辑，只做数据库操作
- 返回原始数据（Dict），不做业务转换
"""
from typing import Optional, List, Dict, Any, Tuple, Set
from lifeprism.repository.base_providers import LWBaseDataProvider
from lifeprism.repository.query_options import QueryOptions
from lifeprism.utils import LazySingleton

class DiaryProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """Diary 数据提供者"""
    
    # ==================== 表元数据定义 ====================
    
    _TABLE_NAME = "diary"
    _DATE_FIELD = "date"
    _TIME_FIELD = None
    
    _FILTER_FIELDS: Set[str] = {
        'date', 'mood', 'weather', 'tags', 'created_at', 'updated_at'
    }
    
    _ORDER_FIELDS: Set[str] = {
        'date', 'created_at', 'updated_at'
    }
    
    _SELECT_FIELDS: Set[str] = {
        'date', 'content', 'mood', 'weather', 'tags', 
        'created_at', 'updated_at'
    }
    
    _UPDATE_FIELDS: Set[str] = {
        'content', 'mood', 'weather', 'tags'
    }
    
    # ==================== 核心方法（使用通用方法） ====================
    
    def query_diaries(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """查询日记"""
        return self._generic_query(options)
    
    def get_diary_by_date(self, date: str) -> Optional[Dict[str, Any]]:
        """按日期查询日记"""
        options = QueryOptions(filters={'date': date})
        results, _ = self._generic_query(options)
        return results[0] if results else None
    
    def insert_diary(self, data: Dict[str, Any]) -> str:
        """插入日记"""
        return self._generic_insert(data)
    
    def update_diary(self, date: str, data: Dict[str, Any]) -> bool:
        """更新日记"""
        return self._generic_update(date, data)
    
    def delete_diary(self, date: str) -> bool:
        """删除日记"""
        return self._generic_delete(date)
```

**代码量**：~60 行（包含注释和空行）  
**传统实现**：~200 行  
**减少**：70%


## 10. 参考资料

- `docs/temp/refactor-repository-architecture-draft/2026-04-23-refactor-repository-architecture-draft.md` - 重构方案总览
- `docs/temp/refactor-repository-architecture-draft/2026-04-23-provider-migration-testing-guide.md` - 测试规范

