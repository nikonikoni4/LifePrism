# 后端代码风格指南

本文档包含后端代码的完整规范和示例。在新建或修改后端模块时参考。

## API 设计规范

### 路由定义
- 使用 `APIRouter` 创建路由组
- 前缀格式：`/{module_name}`（如 `/goal`, `/category`）
- 标签格式：`{Module}`（如 `Goal`, `Category`）
- 使用 `summary` 参数描述端点功能

### HTTP 方法
- `GET`: 获取资源（幂等）| `POST`: 创建资源 | `PATCH`: 部分更新 | `DELETE`: 删除

### 参数验证
- 查询参数：`Query()` | 路径参数：`Path()` | 请求体：Pydantic 模型
- 提供详细的 `description` 参数说明

### 错误响应
- 404: 资源不存在 | 400: 参数验证失败 | 500: 服务器内部错误

### API 示例

```python
from fastapi import APIRouter, Query, HTTPException, Path

router = APIRouter(prefix="/goal", tags=["Goal"])

@router.get("/goals", response_model=GoalListResponse, summary="获取目标列表")
async def get_goals(
    status: Optional[str] = Query(default=None, description="按状态筛选 (active, completed, archived)"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量")
):
    return goal_service.get_goals(status, page, page_size)

@router.get("/goals/{goal_id}", response_model=GoalItem, summary="获取目标详情")
async def get_goal_detail(
    goal_id: str = Path(..., description="目标 ID (格式: goal-xxx)")
):
    result = goal_service.get_goal_detail(goal_id)
    if not result:
        raise HTTPException(status_code=404, detail="目标不存在")
    return result
```

## 增量更新规范（PATCH 语义）

### 适用范围

所有「编辑已有资源」的接口使用增量更新，只处理前端实际传入的字段。创建接口（POST）不适用。

### 三态语义

Update 接口的每个可选字段必须区分三种状态：

| 前端传值 | 含义 | 后端行为 |
|---------|------|---------|
| 字段不在请求 JSON 中 | 不修改 | 跳过该字段 |
| `"field": null` | 清空该字段 | 写入 NULL（仅限 nullable 字段） |
| `"field": value` | 更新为新值 | 写入新值 |

列表字段额外区分：`null` 清空、`[]` 设为空列表。

### 实现约束

- Update Schema 所有字段声明为 `Optional[T] = None`
- 使用 `schema.model_dump(exclude_unset=True)` 获取实际传入字段
  - `exclude_unset=True`：只输出前端实际传入的字段。未传的字段不会出现在 dict 中（不修改），传了 `null` 的字段以 `None` 出现（清空）。这是三态语义的实现基础
  - 普通 `model_dump()` 会把所有字段都输出（未传的字段也会以默认值 `None` 出现），无法区分"未传"和"传了 null"
- **禁止** `exclude_none=True`（会将"显式传 null"与"未传"混为一谈，破坏三态语义）
- **禁止** `model_fields_set` + `getattr` 手动遍历（统一用 `model_dump`）
- Provider 层用 `allowed_fields` 白名单过滤 dict key，动态构建 SQL SET 子句

### 字段可空性

需求阶段必须明确每个字段是否允许清空（nullable）。不可清空字段传入 `null` 时，Service 层抛出错误而非静默写入。

### 示例

```python
# Schema
class UpdateCustomBlockRequest(BaseModel):
    content: Optional[str] = Field(default=None, description="内容")
    category_id: Optional[str] = Field(default=None, description="关联分类 ID")
    todo_id: Optional[str] = Field(default=None, description="关联 Todo ID")

# Service
def update_custom_block(self, block_id: str, request: UpdateCustomBlockRequest) -> ...:
    update_data = request.model_dump(exclude_unset=True)
    # update_data 只包含前端实际传入的字段
    # {"category_id": None} 表示清空绑定
    # {} 表示什么都没改
    return self.provider.update_custom_block(block_id, update_data)

# Provider
def update_custom_block(self, block_id: str, update_data: Dict[str, Any]) -> bool:
    allowed_fields = {"content", "category_id", "todo_id"}
    filtered = {k: v for k, v in update_data.items() if k in allowed_fields}
    if not filtered:
        return True
    set_clause = ", ".join(f"{k} = ?" for k in filtered)
    values = list(filtered.values())
    # None 值会被写入为 NULL（清空语义）
    self.execute(f"UPDATE custom_blocks SET {set_clause} WHERE id = ?", [*values, block_id])
    return True
```

## Schema 设计规范

### 命名规则
- 请求：`Create{Entity}Request`, `Update{Entity}Request`
- 响应：`{Entity}Item`, `{Entity}ListResponse`
- 部分更新：所有字段 `Optional[T]`

### 示例

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class CreateGoalRequest(BaseModel):
    name: str = Field(..., description="目标名称")
    content: str = Field(default="", description="目标内容")
    color: str = Field(default="#5B8FF9", description="目标颜色")
    link_to_category_id: Optional[str] = Field(default=None, description="关联分类 ID")

class UpdateGoalRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="目标名称")
    content: Optional[str] = Field(default=None, description="目标内容")
    status: Optional[str] = Field(default=None, description="目标状态")

class GoalItem(BaseModel):
    id: str = Field(..., description="唯一标识符")
    name: str = Field(..., description="目标名称")
    created_at: str = Field(..., description="创建时间")

class GoalListResponse(BaseModel):
    items: List[GoalItem] = Field(default=[], description="目标列表")
    total: int = Field(default=0, description="总数")
```

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

## 错误处理分层

### Provider 层（数据访问层）
- 返回 `None` 表示失败或不存在，空列表 `[]` 表示无结果
- 捕获异常并记录日志，不向上抛出

### Service 层（业务逻辑层）
- 可抛出 `ValueError` 等业务异常，可返回 `None` 表示失败

### API 层（路由处理层）
- 必须抛出 `HTTPException`（404/400/500）

### 分层示例

```python
# Provider 层
def get_goal_by_id(self, goal_id: str) -> Optional[Dict[str, Any]]:
    try:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM goal WHERE id = ?", (goal_id,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
    except Exception as e:
        logger.error(f"获取目标 {goal_id} 失败: {e}")
        return None

# Service 层
def create_goal(self, request: CreateGoalRequest) -> Optional[GoalItem]:
    try:
        new_id = self.goal_provider.create_goal(data)
        if new_id is None:
            return None
        self._refresh_cache()
        return self.get_goal_detail(new_id)
    except Exception as e:
        logger.error(f"创建目标失败: {e}")
        return None

# API 层
@router.post("/goals", response_model=GoalItem)
async def create_goal(request: CreateGoalRequest):
    try:
        result = goal_service.create_goal(request)
        if not result:
            raise HTTPException(status_code=500, detail="创建目标失败")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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

## Service 层职责

- 调用 Provider 获取数据、实现业务逻辑、数据转换和聚合、缓存管理

### 有状态 Service 示例

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

## Provider 层职责

- 只负责数据库操作，不涉及业务逻辑，继承 `LWBaseDataProvider`
- 方法命名：`get_xxx_by_id()` | `get_xxxs()` | `create_xxx()` | `update_xxx()` | `delete_xxx()`
- 返回值：单个 `Optional[Dict]` | 多个 `tuple[List[Dict], int]` | 操作 `bool`

## ID 生成规范

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
