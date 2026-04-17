---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 初始版本
abstract: 后端开发核心规范，包含类型注解、文档字符串、日志记录、数据库操作、Service/Provider层职责划分、ID生成规范和命名约定
---

# 后端核心规范

本文档包含后端开发的核心规范，包括数据库操作、配置管理、日志记录、代码风格等通用规则。

## 类型注解规范

- 所有函数必须有返回类型注解，所有参数必须有类型注解
- 单个对象：`Optional[Dict[str, Any]]`
- 对象列表：`List[Dict[str, Any]]`
- 列表 + 总数：`tuple[List[Dict[str, Any]], int]`

## 文档字符串规范

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

## 日志记录规范

```python
from lifeprism.utils import get_logger
logger = get_logger(__name__)

logger.info(f"成功创建目标: {goal_id}")      # 重要操作成功
logger.warning(f"未找到分类 {category_id}")   # 警告
logger.error(f"创建目标失败: {e}")            # 错误
logger.debug(f"刷新缓存成功，共 {count} 个")  # 调试
```

## 数据库操作规范

### 基本要求
- 不能直接创建数据库对象，使用 `lifeprism/storage` 中的基础类
- 连接管理：`with self.db.get_connection() as conn:`
- 参数化查询：`cursor.execute(sql, (param1, param2))`，防止 SQL 注入
- `with` 语句自动提交事务

### 结果转换

```python
columns = [description[0] for description in cursor.description]
rows = cursor.fetchall()
items = [dict(zip(columns, row)) for row in rows]
```

## server模块

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

### Provider 层职责

- 只负责数据库操作，不涉及业务逻辑，继承 `LWBaseDataProvider`
- 方法命名：`get_xxx_by_id()` | `get_xxxs()` | `create_xxx()` | `update_xxx()` | `delete_xxx()`
- 返回值：单个 `Optional[Dict]` | 多个 `tuple[List[Dict], int]` | 操作 `bool`

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

## 错误处理分层

### Provider 层（数据访问层）
- 范围：server/provider，llm，processor，monitor等大部分外部接口
- 捕获外部异常，转换为业务异常并抛出

### Service 层（业务逻辑层）
- 范围：server/service
- 让异常自然冒泡，不捕获异常

### API 层（路由处理层）
- 范围：server/api
- 使用全局异常处理器统一处理

## 数据路径

**路径统一**：通过 settings_manager，禁止自行解析
