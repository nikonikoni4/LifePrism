# Issue 6: Config 模块 + 其余 API 路由 + 注释标记

Status: ready-for-agent

## 必读文档

1. **PRD**: `.scratch/backend-error-handling/PRD.md`
2. **编码规范**: `docs/coding-rules/backend-error-handling.md`
3. **日志规则**: `lifeprism/CLAUDE.md`（错误处理 + 日志记录章节）
4. **Config 异常定义**: `lifeprism/config/exceptions.py`

## Parent

`.scratch/backend-error-handling/PRD.md`

## What to build

收尾修复：Config 模块接入新异常 + 其余 API 路由的 `except Exception` 修复 + 合法 `except Exception` 添加注释标记。

### Config 模块
- `settings_manager.py` 第 468 行：`raise ValueError(f"截图保留天数不能小于3天...")` → `raise InvalidConfigError(key="screenshot_retention_days", expected=">=3", actual=days)`
- `settings_manager.py` 第 474 行：`raise ValueError(f"频率等级必须是1、2或3...")` → `raise InvalidConfigError(key="active_screenshot_frequency_level", expected="1, 2, or 3", actual=level)`
- `database.py` 第 1677 行：`raise ValueError(f"未找到表...")` → `raise InvalidConfigError`
- 配置验证失败在首次发现点记录 ERROR 日志

### 其余 API 路由
以下文件中有 `except Exception → HTTPException(500)` 模式需改为分层捕获（同 Issue 2 模式）：
- `chatbot_api.py`：特别注意第 61 行 `except Exception → HTTPException(404)` 错误地将所有异常映射为 404
- `setting_api.py`
- `timeline_api.py`
- `usage.py`
- `value_api.py`：第 101 行捕获 `ConflictError` 是正确模式，但改用 `to_http_exception()` 替代手动 `HTTPException`
- `add_on_api.py`
- `report_api.py`
- `commitment_api.py`

### 注释标记
为合法 `except Exception` 添加 `# LEGITIMATE:` 注释，标记合法场景类型：
- `logger.py` 第 35、79 行 → `# LEGITIMATE: 辅助操作兜底 — 日志配置失败不影响主流程`
- `windows_api.py` 7 处 → `# LEGITIMATE: 第三方未知错误 — Windows API 可能抛非预期异常`
- `monitor.py` 第 128 行 → `# LEGITIMATE: API 边界兜底 — 监控主循环异常退出`
- `config_migrator.py` → `# LEGITIMATE: 辅助操作兜底 — 迁移失败不阻塞启动`
- `provider_manager.py` 第 601 行 → `# LEGITIMATE: 辅助操作兜底 — 回退到默认 provider 配置`

### Repository 聚合器
- `map_cache_aggregator.py`、`goal_aggregator.py`、`habit_aggregator.py`、`category_aggregator.py`、`habit_chain_aggregator.py`：
  - 数据库错误首次发现点 → ERROR 日志 + `raise DataAccessError`
  - 不再静默返回 `None`/`[]`/`0`

## Acceptance criteria

- [ ] `settings_manager.py` 配置验证使用 `InvalidConfigError`（非 `ValueError`）
- [ ] `database.py` 表配置缺失使用 `InvalidConfigError`
- [ ] `chatbot_api.py` 所有异常不再错误映射为 404
- [ ] 所有 API 路由使用统一的分层捕获模式
- [ ] 合法 `except Exception` 处有 `# LEGITIMATE:` 注释
- [ ] 聚合器数据库故障不再静默返回空值
- [ ] 首次发现点有 ERROR 日志（含配置项/entity 标识 + 上下文）
- [ ] 前端能通过 `error_code` 字段区分配置错误 vs 内部错误
- [ ] 不引入新的 linter 错误

## Blocked by

- Issue 1（基础设施修复）
