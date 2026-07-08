# Code Review Report

**审查范围**: 自定义记录模块三个切片（S1 类型管理+LLM、S2 数据录入+查询、S3 Service+API）
**审查时间**: 2026-07-07
**变更文件**: 18 个（6 个新增 + 12 个修改）

> **修复状态（2026-07-07 更新）**
> - Issue 1 ✅ 已修复：8 处 `except Exception as e` 已替换为 `except sqlite3.Error as e`，`create_type` 额外添加 `except sqlite3.IntegrityError` 兜底 UNIQUE 约束
> - Issue 2 ✅ 已修复：`delete_entry` 添加 `cursor.rowcount == 0` 检查，抛出 `EntityNotFoundError`；并将异常抛出移到 `with` 块外，避免连接以未 commit/rollback 状态归还池
> - 新增测试：`test_delete_entry_raises_entity_not_found_for_nonexistent_entry`（24 个测试全部通过）

## 架构上下文

### 相关 ADR
- [ADR 2026-07-06-custom-records-storage](../../docs/adr/2026-07-06-custom-records-storage.md): SQLite 动态建表 + meta 表方案 (decided)
  - 决策：CustomRecordRepository 独立实现，不继承 LWBaseDataProvider
  - 决策：LLM Tool 直接调用 Repository，不经过 Service（避免循环引用）
  - 决策：P1 不支持 schema 演进，字段定义后不可变

### 相关 Spec
- [.scratch/custom-records-module/PRD.md](../../.scratch/custom-records-module/PRD.md): 自定义记录模块产品规格
  - 约束：ValidationError → 422，EntityNotFoundError → 404，DuplicateEntityError → 409
  - 约束：API 层不写 try/except（全局异常处理器统一处理）
  - 约束：Service 层是 API 层薄包装，无核心业务逻辑

### 编码规则
- [backend-core-rules.md](../../docs/coding-rules/backend-core-rules.md): 后端核心规范
  - Section 5 错误处理分层：Repository 层"不能使用 `except Exception as e` 捕获全部错误"
  - Section 5 错误处理分层：Service 层"让异常自然冒泡，不捕获异常"
  - Section 5 错误处理分层：API 层"使用全局异常处理器统一处理"
  - Section 7 数据库操作规范：不得在非 repository 位置直接编写 sql
- [create-table-rules.md](../../docs/coding-rules/create-table-rules.md): 数据库接口创建规则
  - "provider类必须继承自 LWBaseDataProvider"（PRD 已豁免 CustomRecordRepository）
- [backend-api-rules.md](../../docs/coding-rules/backend-api-rules.md): API 设计规范

### 决策覆盖
- 18/18 变更文件有 ADR/PRD 关联
- ADR 豁免说明已记录在 PRD 中

## 审查结果

Found 2 issues:

### Issue 1: Repository 层使用 `except Exception as e` 捕获全部错误

- **类型**: Code Quality / 架构合规
- **置信度**: 85
- **位置**: [custom_record_aggregator.py:177](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L177)（以及 L234, L262, L324, L413, L469, L500, L542，共 8 处）
- **详情**: Repository 层所有方法（`create_type`、`list_types`、`get_type_by_id`、`delete_type`、`create_entry`、`query_entries`、`get_entry`、`delete_entry`）均使用 `except Exception as e` 捕获全部异常，然后包装为 `DataAccessError` 抛出。
- **依据**: 违反 [backend-core-rules.md](../../docs/coding-rules/backend-core-rules.md) Section 5 错误处理分层：
  > 外部接口层（repository）："不能使用 `except Exception as e` 捕获全部错误，避免包含可能都编程错误"

  `except Exception` 会捕获编程错误（如 `AttributeError`、`TypeError`、`KeyError`），这些应该暴露为 500 让开发者发现，而不是被包装为 `DataAccessError` 后静默处理。
- **修复建议**: 改为捕获具体异常类型，如 `sqlite3.Error`、`sqlite3.IntegrityError`：
  ```python
  import sqlite3
  try:
      ...
  except sqlite3.IntegrityError as e:
      # 唯一约束冲突等
      raise DuplicateEntityError(...) from e
  except sqlite3.Error as e:
      # 数据库操作错误
      raise DataAccessError(...) from e
  # 不捕获 Exception，让编程错误自然冒泡
  ```

### Issue 2: `delete_entry` 未校验记录是否存在，API 对不存在的记录返回 200

- **类型**: Code Quality / 行为一致性
- **置信度**: 80
- **位置**: [custom_record_aggregator.py:529-541](../../lifeprism/repository/aggregators/custom_record_aggregator.py#L529-L541)（Repository 层）、[custom_records_api.py:107-117](../../lifeprism/server/api/custom_records_api.py#L107-L117)（API 层）
- **详情**: `delete_entry` 方法执行 `DELETE FROM ... WHERE id = ?` 后无条件返回 `True`，即使该 entry_id 不存在（0 行受影响）也返回成功。API 层直接返回 `{"message": "记录 {entry_id} 已删除"}` 和 200 状态码。
- **依据**: 与项目现有模式不一致。参考 [mood_api.py:146-153](../../lifeprism/server/api/mood_api.py#L146-L153)：
  ```python
  success = mood_service.delete_mood_entry(entry_id)
  if not success:
      raise HTTPException(status_code=404, detail=f"心情记录不存在: {entry_id}")
  ```

  PRD User Story 24："作为用户，我想删除某条具体记录（不删整个类型）"——删除不存在的记录应返回 404 而非 200。
- **修复建议**: Repository 层检查 `cursor.rowcount`：
  ```python
  cursor.execute(f"DELETE FROM {data_table} WHERE id = ?", (entry_id,))
  if cursor.rowcount == 0:
      raise EntityNotFoundError(
          entity_type="CustomRecordEntry", entity_id=entry_id
      )
  ```

## 变更摘要

### 新增文件（6 个）
1. `lifeprism/repository/aggregators/custom_record_aggregator.py` — Repository 层，类型管理 + 记录 CRUD（含动态建表 DDL、slug/field_key 正则校验、事务性 meta+DDL 操作）
2. `lifeprism/llm/agent/tools/custom_records_tool.py` — 4 个 LLM 工具（list_types、create_type、create_entry、query_entries），直接调用 Repository
3. `lifeprism/server/schemas/custom_records_schemas.py` — Pydantic 请求/响应模型（EntryItem 支持 `extra="allow"` 动态字段）
4. `lifeprism/server/services/custom_records_service.py` — Service 层薄包装（8 个纯函数，无业务逻辑）
5. `lifeprism/server/api/custom_records_api.py` — 7 个 REST API 端点（无 try/except，依赖全局异常处理器）
6. `test/core/unit/repository/test_custom_records_repository.py` — 23 个 Repository 层测试（11 类型管理 + 12 记录管理）

### 修改文件（12 个）
1. `lifeprism/config/database.py` — 添加 2 个 meta 表配置到 TABLE_CONFIGS
2. `lifeprism/repository/__init__.py` — 修复循环导入 + 添加 custom_record_repository 导出 + 修复 tokens_usage_repository 命名不一致
3. `lifeprism/repository/aggregators/__init__.py` — 添加 CustomRecordRepository 单例
4. `lifeprism/repository/base_providers/lw_base_data_provider.py` — 移除冗余 QueryOptions 导入（修复循环引用）
5. `lifeprism/llm/agent/tools/__init__.py` — 导出 4 个新工具
6. `lifeprism/llm/agent/loop.py` — CHAT 分支注册 4 个新工具
7. `lifeprism/llm/bus/__init__.py` — 修复 ChannelType/TokensType 导入缺失
8. `lifeprism/server/api/__init__.py` — 导出 custom_records_router
9. `lifeprism/server/services/__init__.py` — 导出 custom_records_service
10. `lifeprism/server/main.py` — 挂载 custom_records_router 到 /api/v2
11. `templates/agent/chat/tool.md` — 添加自定义记录模块提示词
12. `test/core/unit/repository/__init__.py` — 空初始化文件

### 安全审查结论
- **SQL 注入**：✅ 安全。动态表名 `custom_<slug>` 和动态列名 `field_key` 均通过正则 `^[a-z][a-z0-9_]*$` 校验后才写入 meta 表，后续使用从 meta 表读取（不直接使用用户输入）。参数值全部使用参数化查询（`cursor.execute(sql, params)`）。
- **输入校验**：✅ slug 和 field_key 正则校验充分，无已知绕过方式。
- **认证授权**：⚠️ API 端点无认证（与项目现有 API 一致，项目使用其他机制处理认证，非本次变更范围）。
- **数据泄露**：✅ 错误响应不泄露数据库结构，ValidationError 的 details 只含 valid_fields（字段名和显示名），不含表结构信息。

### 测试审查结论
- ✅ 23 个 Repository 层测试覆盖所有核心逻辑（创建/列表/查询/校验/删除/分页/日期筛选）
- ✅ 测试覆盖边界情况（空 fields、重复 slug、错误 field_key、空字典 data、缺失字段）
- ⚠️ 无 Service/API 层测试（PRD 明确不测试，由 Repository 测试覆盖逻辑）
- ⚠️ 无 LLM Tool 层测试（需运行时验证，测试通过导入检查覆盖）
