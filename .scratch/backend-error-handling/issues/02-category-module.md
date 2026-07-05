# Issue 2: Category 模块端到端错误处理规范化

Status: ready-for-agent

## 必读文档

1. **PRD**: `.scratch/backend-error-handling/PRD.md`
2. **编码规范**: `docs/coding-rules/backend-error-handling.md`
3. **日志规则**: `lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）

## Parent

`.scratch/backend-error-handling/PRD.md`

## What to build

端到端修复 Category 模块的错误处理路径：从 Provider 层 → Service 层 → API 路由层，确保错误能正确传播到全局 handler 并被映射为正确的 HTTP 状态码。

### Provider 层
- `category_provider.py` 第 113、119、149、275、281 行：`raise ValueError` → `raise ValidationError`（code=`VALIDATION_FAILED`）

### API 路由层
- `category_api.py` 共 15+ 处 `except Exception → HTTPException(500)` 模式改为：
  ```python
  except LWBaseError:
      raise  # 让全局 handler 映射为正确 HTTP 状态码
  except HTTPException:
      raise
  except ValueError as e:
      raise HTTPException(status_code=400, detail=str(e))
  except Exception as e:
      logger.error(f"<操作描述>失败: {e}", exc_info=True)
      raise HTTPException(status_code=500, detail="服务器内部错误")
  ```

### 日志要求
- Provider 层首次发现点（数据验证失败）→ ERROR 日志（含 entity 标识 + 失败原因 + 当前值）
- API 层不再重复记录（Provider 已记录），仅 500 兜底处记录 ERROR
- 遵循：底层记录、上层透传原则

## Acceptance criteria

- [ ] `category_provider.py` 中所有 `ValueError` 替换为 `ValidationError`
- [ ] `category_api.py` 中所有 `except Exception` 替换为分层捕获模式
- [ ] Category 相关端点：NotFoundError → 404（非 500）、ValidationError → 422（非 500）
- [ ] Provider 首次发现点有 ERROR 级别日志（含操作标识 + 上下文）
- [ ] API 层不再对 LWBaseError 子类重复记录日志
- [ ] 不引入新的 linter 错误

## Blocked by

- Issue 1（基础设施修复）
