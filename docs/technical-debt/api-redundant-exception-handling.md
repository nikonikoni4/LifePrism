---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated: 初始版本，记录 API 层冗余异常处理技术债
abstract: 记录当前 API 路由中存在大量冗余 try/except 代码的技术债问题，说明正确做法和清理计划
---

# API 层冗余异常处理

**优先级**: 中  
**影响范围**: `lifeprism/server/api/*.py`（所有 API 路由文件）

---

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0  | 创建文档初稿，记录技术债问题和清理计划 |

---

## 问题描述

当前 API 路由中存在大量冗余的 `try/except` 代码，与全局异常处理器重复。

### 典型模式

```python
@router.get("/activity/stats")
async def get_activity_stats(...):
    try:
        return activity_service.get_activity_stats(...)
    except LWBaseError:
        raise  # ← 冗余：全局处理器会处理
    except HTTPException:
        raise  # ← 冗余：FastAPI 自动处理
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))  # ← 应在 Service 层转换
    except Exception as e:
        logger.error("...")
        raise HTTPException(status_code=500, detail="...")  # ← 冗余：全局处理器会处理
```

### 统计数据

- 受影响文件：`lifeprism/server/api/*.py`（约 19 个文件）
- `try:` 语句数量：74 处

---

## 为什么是技术债

1. **违反 DRY 原则** - 全局异常处理器已经存在，每个路由重复处理
2. **维护成本高** - 修改错误处理逻辑需要改动所有 API 文件
3. **不一致风险** - 不同 API 可能使用不同的错误处理模式
4. **违反规范** - `docs/coding-rules/backend-error-handling.md` 明确禁止 API 路由单独 try/except

---

## 正确做法

### API 层：完全不需要 try/except

```python
@router.get("/activity/stats")
async def get_activity_stats(...):
    # 直接调用，让异常自然向上冒泡
    return activity_service.get_activity_stats(...)
```

### Service 层：负责转换外部异常

```python
def get_activity_stats(self, ...):
    if not date:
        raise ValidationError(message="日期参数不能为空", code="INVALID_DATE")
    
    try:
        result = self.repository.query(...)
    except sqlite3.Error as e:
        raise DataAccessError(...) from e
    
    return result
```

### 全局处理器：统一映射到 HTTP 响应

```python
# main.py
@app.exception_handler(LWBaseError)
async def lw_base_error_handler(request: Request, exc: LWBaseError):
    http_exc = to_http_exception(exc)
    return JSONResponse(status_code=http_exc.status_code, content=http_exc.detail)
```

---

## 清理计划

### 阶段一：停止新增冗余代码
- ✅ 在 `lifeprism/CLAUDE.md` 中明确说明正确做法
- ✅ 在 code review 中拒绝新增冗余的 try/except

### 阶段二：逐步清理现有代码
1. 移除所有 `except LWBaseError: raise`
2. 移除所有 `except HTTPException: raise`
3. 移除所有 `except Exception` 兜底（由全局处理器处理）
4. 将 `ValueError` 等转换逻辑下沉到 Service 层

### 阶段三：验证
- 运行完整测试套件，确认所有 API 仍然返回正确的错误码
- 补充集成测试，覆盖各种异常场景

---

## 预期收益

- **代码量减少** - 每个 API 路由减少 5-10 行冗余代码
- **维护性提升** - 错误处理逻辑集中在一处
- **一致性保证** - 所有 API 使用统一的错误响应格式
