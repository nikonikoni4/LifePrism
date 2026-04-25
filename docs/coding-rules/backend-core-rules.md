---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 修改数据库操作规范
abstract: 后端开发核心规范，包含类型注解、文档字符串、日志记录、数据库操作、Service层职责、ID生成规范和命名约定，数据库操作规范
---

# 后端核心规范

## 1. 文档字符串规范

使用 Google 风格：

```python
def get_goals(self, status: Optional[str] = None, page: int = 1) -> tuple[List[Dict[str, Any]], int]:
    """
    获取目标列表

    Args:
        status: 按状态筛选（active, completed, archived）
        page: 页码（从1开始）

    Returns:
        tuple: (目标列表, 总数)
    """
```

- ID 参数：`"目标 ID (格式: goal-xxx)"`
- 枚举参数：`"可选值: active, completed, archived"`

## 2. 日志记录规范

```python
from lifeprism.utils import get_logger
logger = get_logger(__name__)

logger.info(f"成功创建目标: {goal_id}")      # 重要操作成功
logger.warning(f"未找到分类 {category_id}")   # 警告
logger.error(f"创建目标失败: {e}")            # 错误
logger.debug(f"刷新缓存成功，共 {count} 个")  # 调试
```


## 4. server模块

### 4.1 Service 层职责

- 调用 `from lifeprism.repository  import xx_store`获取数据、实现业务逻辑、数据转换和聚合、缓存管理

#### 有状态 Service 示例

```python
class GoalService:
    def __init__(self):
        self.goal_store = goal_store
        self.goal_name_map: Dict[str, str] = {}
        self._refresh_cache()

    def _refresh_cache(self):
        try:
            items, _ = self.goal_store.get_goals(page=1, page_size=1000)
            self.goal_name_map = {str(item.get('id', '')): item.get('name', '') for item in items if item.get('id') and item.get('name')}
        except Exception as e:
            logger.error(f"刷新目标缓存失败: {e}")

goal_service = LazySingleton(GoalService)
```

### 4.2 ID 生成规范

- 格式：`{prefix}-{uuid[:8]}`
- 前缀：`goal-` | `cat-` | `sub-` | `journal-` | `todo-`

```python
import uuid
def generate_id(prefix: str) -> str:
    return f"{prefix}-{str(uuid.uuid4())[:8]}"
```

### 4.3 命名约定

| 类型 | 规则 | 示例 |
|------|------|------|
| 映射缓存 | `_xxx_map` | `_category_name_map` |
| DataFrame 缓存 | `_xxx_df` | `_categories_df` |
| 私有方法 | `_` 前缀 | `_refresh_cache()` |
| 常量 | 全大写 | `DEFAULT_PAGE_SIZE = 20` |
| 公共缓存 | 无前缀 | `self.category_name_map` |
| 依赖注入 | 无前缀 | `self.goal_store` |

## 5. 错误处理分层

### repository 层（数据访问层）
- 范围：repository，llm，processor，monitor等大部分外部接口
- 捕获外部异常，转换为业务异常并抛出，必须明确"转换后抛出"，不能返回默认值

### Service 层（业务逻辑层）
- 范围：server/service
- 让异常自然冒泡，不捕获异常

### API 层（路由处理层）
- 范围：server/api
- 使用全局异常处理器统一处理

## 6. 数据路径

**路径统一**：通过 settings_manager，禁止自行解析

## 7 . 数据库操作规范（编写`lifeprism`内的正式代码时需要遵守）



### 核心原则

1. **单一职责**：Provider 只做数据库操作，不包含业务逻辑
2. **统一接口**：所有 Provider 使用 `QueryOptions` 统一查询接口
3. **分层清晰**：Provider（原子操作）→ Aggregator（数据聚合）→ Service（业务逻辑）
4. **类型安全**：使用 Store 统一导出，提供类型提示
5. 不得在非repository的任何位置直接编写sql
6. 只能从`lifeprism.repository`导入数据库store单例对象，比如`from lifeprism.repository import diray_store`
7. 不能直接引用store中provider成员，只能直接使用store单例提供的方法

### 查询接口使用

尽可能使用通用查询方法，不必要不重新创建新的自定义查询函数

**基本使用方法**：

```python
from lifeprism.repository import Store, QueryOptions

# 查询今日活跃 todos
options = QueryOptions(
    date_range=("2026-04-24", "2026-04-24"),
    filters={'state': 'active'}
)
todos, total = Store.todo.query_todos(options)
```
**其他高级查询方法，查看QueryOptions与相关query函数**

### 职责划分

1. `lifeprism.repository.providers`:只负责数据访问，不包含业务逻辑
2. `lifeprism.repository.aggregators`:只负责数据聚合，以及轻量的业务逻辑，不得在aggregators中写入大量重型且不使用数据库等没有必要写在aggregators中的业务逻辑
3. `lifeprism.server.service`：只实现业务逻辑，不得在非repository的任何位置直接编写sql
