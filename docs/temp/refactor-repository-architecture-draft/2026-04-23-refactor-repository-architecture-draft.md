# 数据访问层架构重构方案

**日期**: 2026-04-23  
**状态**: 草案 (Draft)  
**类型**: 架构重构  

## 1. 当前现状

### 1.1 架构问题

**问题描述**：
- Provider分散在`server/providers/`和`llm/providers/dataset_providers/`两个位置
- 当多个模块（server、llm）需要访问相同的数据库表时，存在代码重复
- 表结构变更时需要在多个位置同步修改，维护成本高
- Provider的物理位置与逻辑职责不匹配（数据访问层却放在业务模块中）

**当前目录结构**：
```
lifeprism/
├── config/
│   └── database.py              # 表结构定义
├── repository/
│   ├── database_manager.py      # 数据库连接管理
│   ├── base_providers/
│   │   └── lw_base_data_provider.py  # 基类
│   └── migrations/              # 数据库迁移
├── server/
│   ├── providers/               # ❌ 20+ provider类（应该在repository）
│   │   ├── goal_provider.py
│   │   ├── todo_provider.py
│   │   └── ...
│   ├── services/                # 业务逻辑层
│   └── schemas/                 # API schemas (Pydantic)
└── llm/
    └── providers/
        └── dataset_providers/   # ❌ 重复的数据访问代码
            └── llm_dataset_provider.py
```

### 1.2 代码分析结果

通过对现有provider的分析，发现：

**查询类型分布**（共73个方法）：
- 单表CRUD：56个 (76.7%)
- 多表联合查询：11个 (15.1%)
- 统计查询：21个 (28.8%)

**常见JOIN模式**：
- `goal ← category + sub_category`
- `user_app_behavior_log ← category + sub_category`
- `goal_stats ← user_app_behavior_log + todo_list`

**统计查询集中地**：
- `statistical_data_providers.py`: 8个统计方法（时间统计、分组聚合）
- `goal_stats_provider.py`: 4个统计方法（累积统计）
- `report_provider.py`: 2个统计方法（环比对比）

**重复查询逻辑**：
- 日期范围查询：出现在diary、focus、report、habit_checkin等多个provider
- 按ID查询：几乎所有provider都有
- 批量操作：todo、statistical_data等有较多批量方法

---

## 2. 新架构设计

### 2.1 目标架构

**三层数据访问模式**：Provider（原子操作）→ Aggregator（数据聚合）→ Service（业务逻辑）

```
lifeprism/
├── config/
│   ├── settings_manager.py      # 用户设置（保持不变）
│   └── providers.yaml            # LLM提供商配置（保持不变）
│
├── repository/                      # 🎯 数据存储层（核心重构区域）
│   ├── schemas.py                # ✅ 表结构定义（从config/database.py迁移）
│   ├── database_manager.py       # 数据库连接管理（保持不变）
│   │
│   ├── providers/                # ✅ 所有provider集中在这里
│   │   ├── __init__.py
│   │   ├── todo_provider.py
│   │   ├── goal_provider.py
│   │   ├── diary_provider.py
│   │   ├── activity_provider.py
│   │   ├── habit_provider.py
│   │   └── ...（所有数据访问provider）
│   │
│   ├── aggregators/              # 🆕 数据聚合层
│   │   ├── __init__.py
│   │   ├── activity_aggregator.py
│   │   ├── todo_aggregator.py
│   │   ├── goal_aggregator.py
│   │   └── ...
│   │
│   └── migrations/               # 数据库迁移（保持不变）
│       └── scripts/
│
├── server/                       # 业务模块
│   ├── services/                 # 业务逻辑层（调用provider和aggregator）
│   ├── api/                      # API路由（保持不变）
│   └── schemas/                  # API schemas（保持不变，不移动）
│
└── llm/                          # LLM模块
    ├── services/                 # 🆕 LLM业务逻辑（直接使用repository.providers）
    └── ...                       # 删除llm/providers/dataset_providers/
```

### 2.2 三层职责划分

| 层级 | 位置 | 职责 | 示例 |
|------|------|------|------|
| **Provider** | `repository/providers/` | 原子的数据库操作，通用、可复用 | `query_todos(filters, sort, page)` |
| **Aggregator** | `repository/aggregators/` | 组合多个provider调用，数据聚合计算 | `aggregate_daily_stats()` 调用多个provider |
| **Service** | `server/services/` 或 `llm/services/` | 业务逻辑、事务协调、外部调用 | `complete_todo()` 更新数据库 + 发送通知 |

### 2.3 schemas.py迁移说明

**迁移原因**：
- 表结构定义是存储层的一部分，不是应用配置
- 与migrations、providers在同一模块，内聚性更高
- 修改表结构时，在repository模块内完成所有相关修改（schema + migration + provider）

**迁移步骤**：

1. 创建`repository/schemas.py`，复制`config/database.py`的表结构定义部分
3. 更新repository模块内的导入（migrations、providers）
4. 验证后删除`config/database.py`

---

## 3. Provider编写规范草案

### 3.1 文件组织规范

```python
# repository/providers/todo_provider.py
"""
Todo数据提供者

职责：
- 提供todo_list表的所有数据访问接口
- 不包含业务逻辑，只做数据库操作
- 返回原始数据（Dict），不做业务转换
"""
from typing import Optional, List, Dict, Any, Tuple
from lifeprism.repository import LWBaseDataProvider
from lifeprism.utils import LazySingleton

class TodoProvider(LWBaseDataProvider, metaclass=LazySingleton):
    """Todo数据提供者"""
    
    # ==================== 查询方法 ====================
    
    def query_todos(self, ...) -> Tuple[List[Dict[str, Any]], int]:
        """通用查询接口（支持多条件筛选、排序、分页）"""
        pass
    
    def get_todo_by_id(self, todo_id: str) -> Optional[Dict[str, Any]]:
        """按ID查询单条记录"""
        pass
    
    # ==================== 插入方法 ====================
    
    def insert_todo(self, data: Dict[str, Any]) -> str:
        """插入新记录，返回新记录的ID"""
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

### 3.2 方法命名规范

| 操作类型 | 命名模式 | 示例 | 返回值 |
|---------|---------|------|--------|
| **通用查询** | `query_{table}()` | `query_todos()` | `Tuple[List[Dict], int]` (数据, 总数) |
| **单条查询** | `get_{table}_by_{field}()` | `get_todo_by_id()` | `Optional[Dict]` |
| **插入** | `insert_{table}()` | `insert_todo()` | `str` (新记录ID) |
| **更新** | `update_{table}()` | `update_todo()` | `bool` (是否成功) |
| **删除** | `delete_{table}()` | `delete_todo()` | `bool` (是否成功) |
| **批量操作** | `batch_{action}_{table}()` | `batch_delete_todos()` | `int` (影响行数) |
| **多表联合** | `query_{main}_with_{joined}()` | `query_goals_with_category()` | `Tuple[List[Dict], int]` |
| **统计查询** | `aggregate_{metric}_by_{dimension}()` | `aggregate_duration_by_category()` | `List[Dict]` 或 `Dict` |

### 3.3 通用查询接口规范（核心）

**所有provider必须实现的标准查询接口**：

```python
from dataclasses import dataclass, replace
from typing import Optional, List, Dict, Any, Tuple, Set

@dataclass(frozen=True)
class QueryOptions:
    """
    查询选项（通用的不可变查询参数类）
    
    设计原则：
    1. 不可变：使用 frozen=True，避免参数复用导致的 bug
    2. 通用：使用 filters 统一处理所有筛选条件，适配任何表结构
    3. 便捷：提供 with_*() 方法，方便创建新对象
    
    注意：
    - 白名单验证在各个 Provider 的类属性中定义，不在此类中
    - 所有 Provider 共用此类，保持接口一致
    """
    
    # 时间范围
    date_range: Optional[Tuple[str, str]] = None  # (start_date, end_date)
    time_range: Optional[Tuple[str, str]] = None  # (start_time, end_time)
    
    # 通用筛选（替代 state/status/related_ids）
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


class TodoProvider(LWBaseDataProvider):
    """
    Todo数据提供者
    
    职责：提供 todo_list 表的所有数据访问接口
    """
    
    # 白名单：类属性，集中管理（防止SQL注入）
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
    
    def query_todos(
        self,
        options: Optional[QueryOptions] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        通用查询接口
        
        Args:
            options: 查询选项（QueryOptions对象）
        
        Returns:
            (记录列表, 总记录数)
        
        Examples:
            # 查询今日活跃todos
            options = QueryOptions(
                date_range=("2026-04-23", "2026-04-23"),
                filters={'state': 'active'}
            )
            todos, total = provider.query_todos(options)
            
            # 查询某个目标的所有todos，按优先级排序
            options = QueryOptions(
                filters={'goal_id': 'goal_123'},
                order_by='priority',
                order_desc=True
            )
            todos, total = provider.query_todos(options)
            
            # 链式调用（安全，不会影响原对象）
            base = QueryOptions(filters={'state': 'active'})
            april_todos, _ = provider.query_todos(
                base.with_date_range("2026-04-01", "2026-04-30")
            )
            may_todos, _ = provider.query_todos(
                base.with_date_range("2026-05-01", "2026-05-31")
            )
            # base 保持不变，可以安全复用
            
            # 分页查询
            options = QueryOptions().with_page(page=1, page_size=20)
            todos, total = provider.query_todos(options)
        """
        if options is None:
            options = QueryOptions()
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. 构建SELECT子句（白名单验证）
            if options.fields:
                invalid_fields = set(options.fields) - self._SELECT_FIELDS
                if invalid_fields:
                    raise ValueError(f"Invalid select fields: {invalid_fields}")
                select_clause = ", ".join(options.fields)
            else:
                select_clause = "*"
            
            # 2. 构建WHERE子句（动态条件）
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
            
            # 3. 构建ORDER BY子句（白名单验证）
            if options.order_by not in self._ORDER_FIELDS:
                raise ValueError(f"Invalid order_by field: {options.order_by}")
            order_direction = "DESC" if options.order_desc else "ASC"
            order_clause = f"ORDER BY {options.order_by} {order_direction}"
            
            # 4. 构建LIMIT子句（参数验证在 __post_init__ 中已完成）
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

**关键设计说明**：

1. **QueryOptions 是不可变的**（`frozen=True`）
   - 避免参数复用导致的 bug
   - 使用 `with_*()` 方法创建新对象

2. **白名单在 Provider 类属性中**
   - `_FILTER_FIELDS`：允许筛选的字段
   - `_ORDER_FIELDS`：允许排序的字段
   - `_SELECT_FIELDS`：允许返回的字段

3. **统一使用 filters**
   - 不再有 `state`、`status`、`related_ids` 等独立字段
   - 所有筛选条件都通过 `filters` 字典传递
   - 例如：`filters={'state': 'active', 'goal_id': 'xxx'}`

4. **支持复杂查询**
   - IN 查询：`filters={'id': ['id1', 'id2', 'id3']}`
   - NULL 查询：`filters={'deleted_at': None}`
   - 等值查询：`filters={'state': 'active'}`

### 3.4 必须实现的方法（5个核心方法）

每个provider必须实现以下5个核心方法：

- [ ] `query_{table}()` - 通用查询接口
- [ ] `get_{table}_by_id()` - 按ID查询
- [ ] `insert_{table}()` - 插入记录
- [ ] `update_{table}()` - 更新记录
- [ ] `delete_{table}()` - 删除记录

### 3.5 可选方法（根据业务需要）

- [ ] `batch_insert_{table}()` - 批量插入
- [ ] `batch_update_{table}()` - 批量更新
- [ ] `batch_delete_{table}()` - 批量删除
- [ ] `upsert_{table}()` - 插入或更新（INSERT OR REPLACE）
- [ ] `query_{table}_with_{joined_table}()` - 多表联合查询
- [ ] `aggregate_{metric}_by_{dimension}()` - 统计查询
- [ ] 特殊业务方法（如`reorder_todos()`）

### 3.6 参数验证规范

```python
def query_todos(self, ...):
    """通用查询接口"""
    
    # 1. 参数验证
    if page and page < 1:
        raise ValueError("page must be >= 1")
    
    if page_size and page_size < 1:
        raise ValueError("page_size must be >= 1")
    
    if order_by not in ['created_at', 'updated_at', 'date', 'priority']:
        raise ValueError(f"Invalid order_by field: {order_by}")
    
    # 2. 日期格式验证
    if start_date:
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("start_date must be in YYYY-MM-DD format")
    
    # 3. 执行查询
    ...
```

### 3.7 错误处理规范

```python
def insert_todo(self, data: Dict[str, Any]) -> str:
    """插入todo"""
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

### 3.8 文档规范

```python
def query_todos(self, ...) -> Tuple[List[Dict[str, Any]], int]:
    """
    通用的Todo查询接口
    
    支持多条件筛选、排序、分页，一个方法覆盖所有查询场景。
    
    Args:
        start_date: 开始日期 (YYYY-MM-DD格式)
        end_date: 结束日期 (YYYY-MM-DD格式)
        state: 状态筛选 ('active', 'completed', 'archived')
        goal_id: 关联目标ID
        filters: 自定义筛选条件，如 {'priority': 'high'}
        order_by: 排序字段，默认'created_at'
        order_desc: 是否降序，默认True
        page: 页码（从1开始），None表示不分页
        page_size: 每页数量，None表示不分页
        fields: 返回字段列表，None表示返回所有字段
    
    Returns:
        Tuple[List[Dict], int]: (记录列表, 总记录数)
    
    Raises:
        ValueError: 参数验证失败
        RuntimeError: 数据库操作失败
    
    Examples:
        >>> # 查询今日活跃todos
        >>> todos, total = provider.query_todos(
        ...     start_date="2026-04-23",
        ...     end_date="2026-04-23",
        ...     state="active"
        ... )
        >>> print(f"Found {total} todos")
        
        >>> # 分页查询
        >>> todos, total = provider.query_todos(page=1, page_size=20)
        >>> print(f"Page 1 of {total // 20 + 1}")
    
    Notes:
        - 所有筛选条件都是可选的，不传则不筛选
        - 时间范围是闭区间 [start_date, end_date]
        - 分页从1开始，不是0
    """
    pass
```

---

## 4. Provider依赖分析与迁移优先级

### 4.1 依赖分析结果

通过分析所有provider的使用情况，按照耦合度和复杂度进行排序：

| Provider | 方法数 | 被使用情况 | 耦合度 | 迁移优先级 |
|---------|--------|-----------|--------|-----------|
| **diary_provider** | 5 | 仅diary_service | 1分（低） | ⭐⭐⭐⭐⭐ 最高 |
| **mood_provider** | 15 | 仅mood_service | 1分（低） | ⭐⭐⭐⭐⭐ 最高 |
| **habit_provider** | 6 | habit_service + 3个相关provider | 2分（低-中） | ⭐⭐⭐⭐ 高 |
| **goal_provider** | 13 | 3个service + LLM分类 | 2分（低-中） | ⭐⭐⭐⭐ 高 |
| **todo_provider** | 22 | 4个service，无LLM | 3分（中） | ⭐⭐⭐ 中 |
| **statistical_data_providers** | 21 | 6个service + LLM集成 | 5分（高） | ⭐⭐ 最低 |

**迁移策略**：
- **第一阶段（试点）**：diary + mood（最简单、最独立、验证流程）
- **第二阶段（生态）**：habit系列（保持内部一致性）
- **第三阶段（LLM前置）**：goal（在LLM迁移前完成）
- **第四阶段（核心业务）**：todo（充分测试后迁移）
- **第五阶段（最后）**：statistical_data（最复杂，需完整回归测试）

详细的依赖分析见agent分析结果。

---

## 5. 测试规范

### 5.1 测试策略

**核心原则**：重构前后，service的输出必须完全一致

**测试方法**：快照测试（Snapshot Testing）
- 在重构前捕获service的输出作为"黄金标准"
- 重构后运行相同测试，对比输出是否一致
- 任何差异都需要人工审查

### 5.2 测试流程

```
1. 确认迁移目标provider
   ↓
2. 识别依赖该provider的所有service
   ↓
3. 为每个service编写快照测试（必须有真实数据输出）
   ↓
4. 运行测试，生成快照
   ↓
5. 重构provider
   ↓
6. 逐步替换service中的provider调用
   ↓
7. 运行测试，验证快照一致
   ↓
8. 如有差异，分析原因（bug修复 or 预期变更）
```

### 5.3 快照测试关键规则

1. **数据非空原则**：快照测试必须基于真实数据，空数据应skip测试
2. **排除动态字段**：时间戳、自动生成ID等不应包含在快照中
3. **排序一致性**：列表数据必须排序后再对比
4. **人工审查**：快照不匹配时，必须人工确认差异是否合理

### 5.4 测试示例

```python
# tests/services/test_diary_service_snapshot.py
def test_get_diary_by_date_snapshot(diary_service, test_date, snapshot):
    """测试get_diary_by_date方法的输出"""
    result = diary_service.get_diary_by_date(test_date)
    
    # 验证数据非空（快照测试的前提）
    if result is None or not result:
        pytest.skip("数据为空，无法生成快照。请先创建测试数据。")
    
    # 排除动态字段
    result_clean = {k: v for k, v in result.items() 
                   if k not in ['created_at', 'updated_at']}
    
    # 生成快照
    snapshot.assert_match(result_clean, "get_diary_by_date.json")
```

**完整测试规范**：详见 `docs/temp/2026-04-23-provider-migration-testing-guide.md`

---

## 6. 实施计划

### 6.1 阶段划分

| 阶段 | 时间 | 任务 | 产出 |
|------|------|------|------|
| **阶段0** | 1天 | 制定标准文档 + 测试规范 | `docs/coding-rules/provider-standards.md`<br>`docs/temp/provider-migration-testing-guide.md` |
| **阶段1** | 3天 | 试点重构（diary + mood） | 验证迁移流程和测试方法 |
| **阶段2** | 1周 | 生态迁移（habit系列） | 迁移habit相关的4个provider |
| **阶段3** | 1周 | LLM前置（goal） | 确保LLM分类功能可用 |
| **阶段4** | 1周 | 核心业务（todo） | 充分测试后迁移 |
| **阶段5** | 1周 | 复杂provider（statistical_data） | 完整回归测试 |
| **阶段6** | 3天 | 提取aggregator | 创建repository/aggregators/ |
| **阶段7** | 3天 | LLM模块集成 + 清理 | 删除旧代码，全量测试 |

**总计**：约5-6周

### 6.2 每个provider的迁移步骤

**步骤1：测试准备**（1天）
- [ ] 识别依赖该provider的所有service
- [ ] 为每个service编写快照测试
- [ ] 准备测试数据（确保非空）
- [ ] 运行测试，生成快照文件
- [ ] 提交快照到git

**步骤2：重构provider**（1-2天）
- [ ] 在`repository/providers/`创建新provider
- [ ] 实现5个核心方法（query/get/create/update/delete）
- [ ] 实现特殊方法（批量操作、统计查询等）
- [ ] 编写provider单元测试

**步骤3：替换调用**（1-2天）
- [ ] 在service中逐步替换provider调用
- [ ] 每替换一个方法，运行快照测试
- [ ] 如有差异，分析并修复
- [ ] 确认所有快照测试通过

**步骤4：清理验证**（0.5天）
- [ ] 删除旧provider
- [ ] 运行完整测试套件
- [ ] 手动测试关键功能
- [ ] 更新文档

### 6.3 试点provider详细计划

**试点1：diary_provider**（3天）

| 天数 | 任务 | 产出 |
|------|------|------|
| Day 1 | 编写diary_service快照测试 | `tests/services/test_diary_service_snapshot.py` |
| Day 2 | 重构diary_provider | `repository/providers/diary_provider.py` |
| Day 3 | 替换调用 + 验证 | 所有快照测试通过 |

**试点2：mood_provider**（2天，流程已熟悉）

| 天数 | 任务 | 产出 |
|------|------|------|
| Day 1 | 快照测试 + 重构provider | 测试 + 新provider |
| Day 2 | 替换调用 + 验证 | 完成迁移 |

---

## 7. 预期收益

### 7.1 维护成本降低

**场景：修改todos表结构（添加priority字段）**

| 架构 | 需要修改的位置 | 维护成本 |
|------|--------------|---------|
| **当前** | 1. 数据库迁移脚本<br>2. `server/providers/todo_provider.py`<br>3. `llm/providers/dataset_providers/llm_dataset_provider.py`<br>4. 各自的schemas | 🔴 高：需要在多个模块中搜索 |
| **优化后** | 1. 数据库迁移脚本<br>2. `repository/providers/todo_provider.py`<br>3. 共享的schemas | 🟢 低：只需修改一处 |

### 7.2 代码复用提升

- LLM模块零成本复用所有数据访问
- 新模块接入数据库的成本极低
- 统计查询逻辑可在aggregator中复用

### 7.3 架构清晰度提升

- 模块职责清晰：repository（数据层）、server（业务层）、llm（AI层）
- 依赖方向正确：业务层 → 数据层
- 符合主流实践：与Django、SQLAlchemy等框架一致

---

## 8. 风险和缓解措施

### 8.1 风险

1. **迁移工作量大**：20+ provider，73个方法
2. **测试覆盖不足**：部分provider可能缺少测试
3. **导入路径变更**：可能影响现有代码
4. **快照测试数据准备**：需要确保测试数据非空且有效

### 8.2 缓解措施

1. **渐进式迁移**：按优先级排序，从简单到复杂
2. **快照测试保障**：重构前为所有service编写快照测试
3. **兼容层**：保留旧导入路径，逐步过渡
4. **测试数据生成器**：编写fixtures自动生成测试数据
5. **回滚机制**：使用git分支管理，确保可回滚

---

## 9. 下一步行动

1. **评审本草案**：团队讨论，确认方案可行性
2. **编写详细规范**：
   - `docs/coding-rules/provider-standards.md`（provider编写规范）
   - `docs/temp/provider-migration-testing-guide.md`（测试规范，已完成）
3. **准备测试环境**：
   - 安装pytest-snapshot
   - 创建测试数据库
   - 编写测试数据生成器
4. **启动试点重构**：
   - diary_provider（3天）
   - mood_provider（2天）
5. **评估试点结果**：验证规范的可行性，调整方案
6. **全面推进**：按照优先级批量迁移所有provider

---

## 10. 附录

### 10.1 参考资料

- 《Architecture Patterns with Python》- Repository模式
- SQLAlchemy官方文档 - 数据访问层组织
- Anki、Joplin、Calibre等开源项目的架构实践

### 10.2 相关文档

- `docs/ARCHITECTURE.md` - 项目架构文档（需更新）
- `docs/coding-rules/` - 编码规范（需新增provider规范）
- `docs/design-decisions/` - 架构决策记录（本次重构完成后记录）
- `docs/temp/2026-04-23-provider-migration-testing-guide.md` - 测试规范（已完成）

### 10.3 Provider依赖详细分析

详细的依赖分析结果（由explore agent生成）：

**低耦合provider（优先迁移）**：
- diary_provider: 5个方法，仅被diary_service使用
- mood_provider: 15个方法，仅被mood_service使用
- habit_provider: 6个方法，被habit_service使用，有3个相关provider依赖

**中等耦合provider**：
- goal_provider: 13个方法，被3个service使用，有LLM集成
- todo_provider: 22个方法，被4个service使用，无LLM依赖

**高耦合provider（最后迁移）**：
- statistical_data_providers: 21个方法，被6个service使用，有复杂统计查询和LLM集成

完整分析见agent输出结果。
