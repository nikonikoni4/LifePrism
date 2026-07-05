# Issue 1: 修复异常基类动态 code bug + 数据库层异常规范化

Status: ready-for-agent

## 必读文档

1. **PRD**: `.scratch/backend-error-handling/PRD.md`
2. **编码规范**: `docs/coding-rules/backend-error-handling.md`
3. **日志规则**: `lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）

## Parent

无（这是基础设施修复，其他 issue 依赖此 issue）

## What to build

修复错误处理基础设施的两个严重 bug，让后续模块端到端修复能正常工作。

### 1. 修复 EntityNotFoundError/DuplicateEntityError 动态 code bug

当前 `repository/exceptions.py` 中这两个异常用 `f"{entity_type.upper()}_NOT_FOUND"` 动态生成 code（如 `"TODO_NOT_FOUND"`），但 `api_error_mapping.py` 的 `ERROR_CODE_TO_STATUS` 字典中只有静态常量 `"ENTITY_NOT_FOUND"`。动态 code 找不到 → 回退到 500，导致"未找到"返回 500 而非 404。

**修复方案**：改为使用 `error_codes.py` 中的静态常量 `ENTITY_NOT_FOUND` 和 `ENTITY_ALREADY_EXISTS` 作为默认 code，同时在 details 中保留 `entity_type` 信息供前端区分具体实体类型。

### 2. 数据库层异常规范化

`database_manager.py` 的 12 个 CRUD 方法全部使用 `except Exception as e: logger.error(...); raise`。这有两个问题：
- 捕获了不该捕获的 `KeyboardInterrupt`、`SystemExit` 等
- 没有转换为 `DataAccessError`，调用方无法统一捕获

`lw_base_data_provider.py` 中第 585、769 行已正确使用 `except sqlite3.Error: raise DataAccessError(...) from e`，但第 672、810、850、899、1096、1163、1195 行仍使用裸 `except Exception`。

**修复方案**：
- `database_manager.py` 所有方法：`except Exception` → `except sqlite3.Error` + 转换为 `DataAccessError`
- `lw_base_data_provider.py` 剩余 `except Exception` 块同步修复
- 所有异常转换必须在首次发现点记录 ERROR 级别日志（含操作标识 + 失败原因 + 上下文）

## Acceptance criteria

- [ ] `EntityNotFoundError` 默认 code 为 `ENTITY_NOT_FOUND`（404），而非动态字符串
- [ ] `DuplicateEntityError` 默认 code 为 `ENTITY_ALREADY_EXISTS`（409），而非动态字符串
- [ ] 请求一个不存在的实体时，API 返回 404（而非 500）
- [ ] `database_manager.py` 所有 CRUD 方法捕获 `sqlite3.Error` 并转为 `DataAccessError`
- [ ] `lw_base_data_provider.py` 中所有 `except Exception` 改为 `except sqlite3.Error`
- [ ] 每次异常转换处有 ERROR 级别日志（含操作标识 + 上下文）
- [ ] 使用 `raise DataAccessError(...) from e` 保留异常链
- [ ] 不引入新的 linter 错误

## Blocked by

None - 可立即开始
