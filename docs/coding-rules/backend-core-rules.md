---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 修改数据库操作规范
abstract: 后端开发核心规范，包含类型注解、文档字符串、日志记录、数据库操作、Service层职责、ID生成规范和命名约定，数据库操作规范
---

# 后端核心规范

本文档包含后端开发的核心规范，包括数据库操作、配置管理、日志记录、代码风格等通用规则。

## 1. 类型注解规范

- 所有函数必须有返回类型注解，所有参数必须有类型注解
- 单个对象：`Optional[Dict[str, Any]]`
- 对象列表：`List[Dict[str, Any]]`
- 列表 + 总数：`tuple[List[Dict[str, Any]], int]`

## 2. 文档字符串规范

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

## 3. 日志记录规范

```python
from lifeprism.utils import get_logger
logger = get_logger(__name__)

logger.info(f"成功创建目标: {goal_id}")      # 重要操作成功
logger.warning(f"未找到分类 {category_id}")   # 警告
logger.error(f"创建目标失败: {e}")            # 错误
logger.debug(f"刷新缓存成功，共 {count} 个")  # 调试
```


## 4. server模块

### Service 层职责

- 调用 Provider 获取数据、实现业务逻辑、数据转换和聚合、缓存管理

#### 有状态 Service 示例

```python
class GoalService:
    def __init__(self):
        self.goal_provider = goal_provider
        self.goal_name_map: Dict[str, str] = {}
        self._refresh_cache()

    def _refresh_cache(self):
        try:
            items, _ = self.goal_provider.get_goals(page=1, page_size=1000)
            self.goal_name_map = {str(item.get('id', '')): item.get('name', '') for item in items if item.get('id') and item.get('name')}
        except Exception as e:
            logger.error(f"刷新目标缓存失败: {e}")

goal_service = LazySingleton(GoalService)
```

### server/Provider(已经弃用)

`server/provider`已经转移至`storage/provider`,具体使用查看《数据库操作规范》章节

### ID 生成规范

- 格式：`{prefix}-{uuid[:8]}`
- 前缀：`goal-` | `cat-` | `sub-` | `journal-` | `todo-`

```python
import uuid
def generate_id(prefix: str) -> str:
    return f"{prefix}-{str(uuid.uuid4())[:8]}"
```

## 命名约定

| 类型 | 规则 | 示例 |
|------|------|------|
| 映射缓存 | `_xxx_map` | `_category_name_map` |
| DataFrame 缓存 | `_xxx_df` | `_categories_df` |
| 私有方法 | `_` 前缀 | `_refresh_cache()` |
| 常量 | 全大写 | `DEFAULT_PAGE_SIZE = 20` |
| 公共缓存 | 无前缀 | `self.category_name_map` |
| 依赖注入 | 无前缀 | `self.goal_provider` |

## 5. 错误处理分层

### Provider 层（数据访问层）
- 范围：server/provider，llm，processor，monitor等大部分外部接口
- 捕获外部异常，转换为业务异常并抛出

### Service 层（业务逻辑层）
- 范围：server/service
- 让异常自然冒泡，不捕获异常

### API 层（路由处理层）
- 范围：server/api
- 使用全局异常处理器统一处理

## 6. 数据路径

**路径统一**：通过 settings_manager，禁止自行解析

## 数据库操作规范（编写`lifeprism`内的正式代码时需要遵守）

### 基本要求
- 不能直接创建数据库对象，继承`LWBaseDataProvider`类，在provider中编写数据库操作
- 连接管理：`with self.db.get_connection() as conn:`
- 参数化查询：`cursor.execute(sql, (param1, param2))`，防止 SQL 注入
- `with` 语句自动提交事务

### 结果转换

```python
columns = [description[0] for description in cursor.description]
rows = cursor.fetchall()
items = [dict(zip(columns, row)) for row in rows]
```

## provider管理

1. 一个数据表对应`lifeprism/storage/providers/__init__.py`中的一个provider，当需要操作对应数据表时，只能使用这里导出的单例，禁止直接编写sql在非provider类之外

2. 使用provider时，**优先使用通用方法**（`_generic_query/insert/update/delete`）,只有在通用方法无法满足时才创建自定义方法,自定义方法必须注释说明为什么需要自定义。通用方法位置`lifeprism/storage/base_providers/lw_base_data_provider.py L878~L1228`

3. 需要创建新的provider时，需要优先实现通用方法，参考`lifeprism/storage/providers/diary_provider.py`的实现

4. provider仅负责简单操作数据库，不负责任何业务逻辑