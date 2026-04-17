---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 初始版本
abstract: 后端 API 设计规范，包含路由定义、HTTP方法、参数验证、错误响应、增量更新规范（PATCH三态语义）和Schema设计规范
---

# 后端 API 规范

本文档包含 API 设计规范、增量更新规范（PATCH 语义）和Schema 设计规范等 API 相关规范。

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