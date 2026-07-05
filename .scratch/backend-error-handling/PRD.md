# PRD: 后端错误处理体系完善

## Status

ready-for-agent

## Problem Statement

2026-07-06 完成了错误处理基础设施重构（`fd4cd9a`）：
- `LWBaseError` 增强（`cause` 参数 + `to_dict()`）
- 4 个新模块异常文件（config/llm/processors/repository）
- `to_http_exception()` 统一映射
- 错误码按模块分组

但审查发现：**新基础设施已建好，上层代码基本没接入。**

核心问题：
1. API 路由层 `except Exception → HTTPException(500)` 覆盖全局 handler，导致 `NotFoundError` 等被错误映射为 500
2. 9 个新异常类已定义但 0 引用（死代码）
3. Repository 层大量 `except Exception` + `return None`，掩盖数据库故障
4. `EntityNotFoundError`/`DuplicateEntityError` 动态 code 在映射表中找不到 → 500 bug

## Solution

按模块端到端修复错误处理路径：底层抛正确异常 → API 层透传 → 全局 handler 统一映射。

## Implementation Decisions

1. **API 路由统一模式**：`except LWBaseError: raise`（让全局 handler 映射）+ `except HTTPException: raise` + `except ValueError: 400` + `except Exception: 500` 兜底
2. **Repository 层**：`except Exception` → `except sqlite3.Error` + 转换为 `DataAccessError`（带 `cause` 链）
3. **`return None` → 抛异常**：使用 `EntityNotFoundError` / `DuplicateEntityError`
4. **日志规则**：遵循 `lifeprism/CLAUDE.md` 日志规范——首次发现点 ERROR 级别 + 完整上下文

## Related Documents

- 编码规范：`docs/coding-rules/backend-error-handling.md`
- 日志规则：`lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）
- 审查报告：`docs/temp/error-handling-fixes-2026-07-06.md`
