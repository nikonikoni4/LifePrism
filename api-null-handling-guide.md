## 背景问题

在 PATCH/PUT 更新接口中，需要区分三种情况：

| 意图 | 描述 |
|------|------|
| **不更新** | 前端没传这个字段，保持数据库原值 |
| **清空** | 前端想把这个字段设为 NULL |
| **更新** | 前端想把这个字段改为新值 |

---

## 方案一：JSON Body 请求（推荐）

### 原理

使用 Pydantic 的 `model_dump(exclude_unset=True)` 来区分"未传递"和"传了 null"。

### 前端处理

```typescript
// types.ts
interface UpdateRequest {
    field1?: string | null;  // 可选字段
    field2?: string | null;
}

// api.ts
async function update(id: string, data: UpdateRequest) {
    // 直接传递，保留 undefined 和 null 的区别
    // undefined 字段不会出现在 JSON 中
    // null 字段会作为 null 发送
    const response = await fetch(`/api/item/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),  // undefined 字段会被忽略，null 会保留
    });
    return response.json();
}

// 使用示例
update('123', { field1: 'new value' });           // 只更新 field1
update('123', { field1: null });                  // 清空 field1
update('123', { field1: 'new', field2: null });   // 更新 field1，清空 field2
```

### 后端处理（FastAPI + Pydantic）

```python
from pydantic import BaseModel
from typing import Optional

class UpdateRequest(BaseModel):
    field1: Optional[str] = None
    field2: Optional[str] = None

@router.put("/item/{item_id}")
async def update_item(item_id: str, request: UpdateRequest):
    # 使用 exclude_unset=True 只获取前端实际传递的字段
    update_fields = request.model_dump(exclude_unset=True)
    
    # update_fields 只包含前端显式传递的字段
    # - 传了 null：字段存在，值为 None
    # - 没传：字段不存在
    
    # 校验：至少需要一个可更新字段
    if not update_fields:
        raise HTTPException(status_code=400, detail="至少需要一个更新字段")
    
    # 调用 service 层
    success = service.update_item(item_id, update_fields)
    return {"success": success}
```

### Service 层处理

```python
def update_item(self, item_id: str, update_fields: dict) -> bool:
    """
    更新记录
    
    Args:
        item_id: 记录ID
        update_fields: 需要更新的字段字典
            - 字段存在且值为 None：将该字段设为 NULL（清空）
            - 字段存在且值非 None：更新为新值
            - 字段不存在：不更新该字段
    """
    # 动态构建 SQL
    set_parts = []
    params = []
    
    for field in ['field1', 'field2', 'field3']:
        if field in update_fields:  # 使用 'in' 而不是 'is not None'
            set_parts.append(f"{field} = ?")
            params.append(update_fields[field])  # 值可以是 None
    
    if not set_parts:
        return False
    
    sql = f"UPDATE table SET {', '.join(set_parts)} WHERE id = ?"
    params.append(item_id)
    
    cursor.execute(sql, params)
    return cursor.rowcount > 0
```

### 数据流示例

| 前端发送 | JSON Body | `exclude_unset=True` 结果 | 后端行为 |
|---------|-----------|---------------------------|---------|
| `{ field1: 'new' }` | `{"field1": "new"}` | `{'field1': 'new'}` | field1 更新为 'new' |
| `{ field1: null }` | `{"field1": null}` | `{'field1': None}` | field1 清空（设为 NULL） |
| `{}` | `{}` | `{}` | 返回 400 错误 |
| `{ field1: 'new', field2: null }` | `{"field1": "new", "field2": null}` | `{'field1': 'new', 'field2': None}` | field1 更新，field2 清空 |

---

## 方案二：Query 参数请求

### 原理

Query 参数的默认值机制与 JSON Body 不同，无法使用 `exclude_unset`。
需要使用**约定值**来区分三种情况：

| 约定 | 描述 |
|------|------|
| **不传参数** | 不更新（后端收到 `None`） |
| **传空字符串 `""`** | 清空（后端收到 `""`） |
| **传有效值** | 更新为新值 |

### 前端处理

```typescript
// api.ts
async function update(params: {
    app: string;
    category_id: string;
    goal_id?: string | null;  // undefined=不修改, ""=清空, "goal-xxx"=设置
}) {
    const searchParams = new URLSearchParams();
    searchParams.set('app', params.app);
    searchParams.set('category_id', params.category_id);
    
    // goal_id 的特殊处理
    // - undefined/null: 不传参数 → 后端不修改
    // - "": 传空字符串 → 后端清空
    // - "goal-xxx": 传值 → 后端设置
    if (params.goal_id !== null && params.goal_id !== undefined) {
        searchParams.set('goal_id', params.goal_id);
    }
    
    const response = await fetch(`/api/update?${searchParams.toString()}`, {
        method: 'POST',
    });
    return response.json();
}

// 使用示例
update({ app: 'chrome', category_id: 'work' });                    // goal_id 不修改
update({ app: 'chrome', category_id: 'work', goal_id: '' });       // goal_id 清空
update({ app: 'chrome', category_id: 'work', goal_id: 'goal-1' }); // goal_id 设置
```

### 后端处理（FastAPI）

```python
@router.post("/update")
async def update_by_query(
    app: str = Query(...),
    category_id: str = Query(...),
    goal_id: Optional[str] = Query(None)  # None=不传参数（不修改）
):
    # goal_id 的三种情况：
    # - None: 前端没传这个参数 → 不修改
    # - "": 前端传了空字符串 → 清空
    # - "goal-xxx": 前端传了值 → 设置
    
    set_parts = ["category_id = ?"]
    params = [category_id]
    
    # 只有当 goal_id 不是 None 时才处理
    if goal_id is not None:
        set_parts.append("link_to_goal_id = ?")
        # 空字符串转换为 None（数据库存 NULL）
        params.append(goal_id if goal_id else None)
    
    # 执行更新 SQL...
```

### 数据流示例

| 前端调用 | URL Query | 后端收到 | 后端行为 |
|---------|-----------|---------|---------|
| `{ goal_id: undefined }` | `/api?app=x&cat=y` | `goal_id=None` | 不修改 goal_id |
| `{ goal_id: null }` | `/api?app=x&cat=y` | `goal_id=None` | 不修改 goal_id |
| `{ goal_id: '' }` | `/api?app=x&cat=y&goal_id=` | `goal_id=""` | 清空 goal_id（设为 NULL） |
| `{ goal_id: 'goal-1' }` | `/api?app=x&cat=y&goal_id=goal-1` | `goal_id="goal-1"` | 设置为 "goal-1" |

---

## 方案对比

| 特性 | JSON Body + exclude_unset | Query 参数 + 约定值 |
|------|---------------------------|---------------------|
| **适用场景** | 更新接口（PUT/PATCH） | 简单操作、过滤条件 |
| **清空表示** | 传 `null` | 传空字符串 `""` |
| **不更新表示** | 不传字段 | 不传参数 |
| **代码复杂度** | 后端需要 `exclude_unset` | 后端需要判断 `None` vs `""` |
| **推荐程度** | ⭐⭐⭐⭐⭐ 强烈推荐 | ⭐⭐⭐ 特定场景使用 |

---

## 统一处理模式

### 前端统一规范

```typescript
/**
 * 更新字段的值类型
 * - undefined: 不传递（不更新）
 * - null: 清空（JSON Body 场景）
 * - "": 清空（Query 参数场景）
 * - 其他值: 更新为该值
 */
type UpdateFieldValue<T> = T | null | undefined;

// JSON Body 场景
function buildJsonBody<T extends object>(data: T): string {
    // undefined 字段会被 JSON.stringify 自动忽略
    // null 字段会保留
    return JSON.stringify(data);
}

// Query 参数场景
function buildQueryParams(params: Record<string, string | null | undefined>): URLSearchParams {
    const searchParams = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value !== null && value !== undefined) {
            searchParams.set(key, value);
            // value="" 表示清空，searchParams.set 会正确处理
        }
        // value=null/undefined 不添加到 URL
    }
    return searchParams;
}
```

### 后端统一模式

```python
# JSON Body 场景
def process_json_update(update_fields: dict, updatable_fields: list[str]) -> tuple[list, list]:
    """处理 JSON Body 的更新字段"""
    set_parts = []
    params = []
    
    for field in updatable_fields:
        if field in update_fields:  # 关键：使用 'in' 检查
            set_parts.append(f"{field} = ?")
            params.append(update_fields[field])  # None 会写入 NULL
    
    return set_parts, params


# Query 参数场景  
def process_query_update(goal_id: str | None) -> tuple[str | None, bool]:
    """
    处理 Query 参数的 goal_id
    
    Returns:
        (value, should_update): (要写入的值, 是否需要更新)
    """
    if goal_id is None:
        # 参数未传递 → 不更新
        return None, False
    elif goal_id == "":
        # 传了空字符串 → 清空（写入 NULL）
        return None, True
    else:
        # 传了有效值 → 更新
        return goal_id, True
```

---

## 本项目最佳实践

1. **更新接口统一使用 JSON Body**，配合 `model_dump(exclude_unset=True)`
2. **Query 参数仅用于**：
   - GET 请求的过滤条件
   - 简单的操作参数（非可选的必填字段）
3. **约定**：
   - JSON Body: `null` = 清空，不传 = 不更新
   - Query: `""` = 清空，不传 = 不更新
4. **命名规范**：更新接口的 Service/Provider 层接收 `update_fields: dict`
