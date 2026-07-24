---
version: 1.1
created_at: 2026-07-06
updated_at: 2026-07-08
last_updated: 移除已弃用的 chat_history_db_manager 和 chat_db_path 引用
abstract: Repository 数据访问层核心契约 — DatabaseManager 连接管理、LWTableManager 建表、BaseProvider 通用 CRUD、迁移系统、异常体系
status: draft
module: repository
---

# Repository 数据访问层核心契约

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |
| 1.1 | 移除已弃用的 chat_history_db_manager 和 chat_db_path 引用 |

## Overview

**业务问题**：LifeWatch-AI 需要管理多个 SQLite 数据库（LifeWatch 主库、ActivityWatch 外部数据、聊天历史），它们具有不同的读写权限和并发需求。同时上层业务模块（Provider/Aggregator）需要一套统一的 CRUD 范式来操作单表，避免每个模块重复实现相同的查询、插入、更新、删除逻辑。

**核心职责**：
- **DatabaseManager**：统一的 SQLite 连接管理，支持连接池模式（多线程安全）和只读模式（外部数据库隔离），通过上下文管理器自动提交/回滚
- **LWTableManager**：从配置驱动创建 LifeWatch 数据库的所有表和索引
- **LWBaseDataProvider**：通过类级元数据（`_TABLE_NAME`、`_PRIMARY_KEY`、`_DATE_FIELD` 等）驱动的通用 CRUD 基类，子类只需定义元数据即可获得完整的单表增删改查能力
- **AWBaseDataProvider**：ActivityWatch 数据库只读访问基类，提供 UTC/本地时区转换工具
- **迁移系统**：版本号递增的数据库迁移运行器，每个迁移独立提交，迁移前自动备份
- **异常体系**：RepositoryError / EntityNotFoundError / DuplicateEntityError，通过全局异常处理器统一映射为 HTTP 状态码

## Scope

### 范围内

- DatabaseManager 的连接池创建、获取/归还、自动关闭（atexit），只读 URI 模式
- DatabaseManager 的通用 CRUD 方法（`query`、`insert`、`update`、`delete`、`upsert` 及批量版本）
- LWTableManager 的 `init_database()` 建表流程
- LWBaseDataProvider 的通用 CRUD 契约（`_generic_query`、`_generic_insert`、`_generic_update`、`_generic_delete`）及元数据约定
- AWBaseDataProvider 的只读查询基础能力（`_parse_timestamp`、`_utc_to_local`、`_local_to_utc`、`get_window_events`）
- 迁移运行器 `run_migrations(db_path)` 的版本检测、备份、顺序执行、独立提交
- 异常体系及其与 HTTP 状态码的映射关系
- `__init__.py` 中三个数据库全局实例的契约（读写/只读、连接池大小）
- QueryOptions 不可变查询参数对象（date_range、time_range、filters、order_by、分页、字段白名单）

### 范围外

- 具体 Provider/Aggregator 的业务逻辑（如 diary_provider、habit_aggregator 等 22 个模块）— 它们遵循本 spec 定义的 BaseProvider 统一模式，各自在内部实现具体业务方法
- API 路由层如何使用 repository — 见 `docs/flows/` 下的数据访问流文档
- config.database 中的 TABLE_CONFIGS 定义 — 见 config 模块相关 spec

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 数据库实例管理

- [ ] lw_db 数据库文件不存在时，`__init__.py` 自动创建空文件和父目录
- [ ] lw_db_manager 以读写模式创建，连接池大小为 5，程序退出时自动关闭所有连接
- [ ] aw_db_manager 以只读模式（`mode=ro` URI）创建，连接池大小为 1

### 连接池

- [ ] 连接池预创建 pool_size 个连接，放入 Queue
- [ ] `get_connection()` 从池中获取连接时执行 `SELECT 1` 健康检查，连接失效则创建新连接
- [ ] 池中无可用连接时（1 秒超时），创建临时连接不阻塞
- [ ] 上下文管理器正常退出时自动 commit，异常时自动 rollback 并抛出 DataAccessError
- [ ] 非连接池模式下，连接在使用后直接关闭（不归还池）

### 通用 CRUD（DatabaseManager 层）

- [ ] `query(table_name, columns, where, order_by, limit)` 返回 pd.DataFrame，空结果返回空 DataFrame
- [ ] `query_advanced(table_name, conditions, ...)` 支持 =、!=、>、<、>=、<=、LIKE、IN、NOT IN、BETWEEN 操作符
- [ ] `insert(table_name, data)` 返回受影响行数
- [ ] `insert_many(table_name, data_list)` 批量插入，空列表返回 0
- [ ] `upsert(table_name, data, conflict_columns)` 存在则更新、不存在则插入
- [ ] `upsert_many` 批量 upsert，对配置了 timestamps 的表自动更新 updated_at
- [ ] `update(table_name, data, where)` 返回受影响行数
- [ ] `update_by_id(table_name, id_column, id_value, data)` 等价于按 ID 的 update
- [ ] `delete(table_name, where)` 返回受影响行数
- [ ] `delete_by_id(table_name, id_column, id_value)` 等价于按 ID 的 delete
- [ ] `get_by_id(table_name, id_column, id_value)` 返回单条记录 dict，不存在返回 None
- [ ] `truncate(table_name)` 清空表所有记录，以 INFO 级别记录影响行数
- [ ] 所有 CRUD 方法在 sqlite3.Error 时转换为 DataAccessError 并携带 db_path、table_name、error 上下文

### LWTableManager 建表

- [ ] `init_database()` 遍历 TABLE_CONFIGS 中所有表配置，使用 `CREATE TABLE IF NOT EXISTS` 创建
- [ ] 根据配置中的 timestamps/update_at 自动添加 `created_at` / `updated_at` 列
- [ ] 根据配置中的 indexes 自动创建 `CREATE INDEX IF NOT EXISTS`
- [ ] 根据配置中的 table_constraints 添加表级约束（PRIMARY KEY、UNIQUE 等）

### LWBaseDataProvider 通用 CRUD

- [ ] `_generic_query(options)` 根据 `_TABLE_NAME`、`_DATE_FIELD`、`_TIME_FIELD`、`_FILTER_FIELDS` 元数据构建完整查询
- [ ] `_generic_query` 支持 date_range（需定义 `_DATE_FIELD`）、time_range（需定义 `_TIME_FIELD`）、通用 filters（需定义 `_FILTER_FIELDS` 白名单）
- [ ] `_generic_query` 支持 order_by（需定义 `_ORDER_FIELDS` 白名单）、分页（page/page_size 优先于 limit）、字段选择（需定义 `_SELECT_FIELDS` 白名单）
- [ ] `_generic_insert(data, id_prefix, auto_order_index, on_conflict)` 支持 abort/ignore/replace 三种冲突策略
- [ ] `_generic_insert` 使用 `id_prefix + uuid4().hex[:8]` 自动生成 ID
- [ ] `_generic_insert` 使用 `auto_order_index=True` 时自动计算 `MAX(order_index) + 1`
- [ ] `_generic_update(record_id, data)` 按 `_PRIMARY_KEY` 更新，自动添加 `updated_at`（仅对配置了 update_at 的表）
- [ ] `_generic_update` 对 `_UPDATE_FIELDS` 白名单进行字段验证
- [ ] `_generic_delete(record_id)` 按 `_PRIMARY_KEY` 删除
- [ ] `_validate_table_name()` 在每次 CRUD 操作前验证表名格式（`^[a-zA-Z_][a-zA-Z0-9_]*$`），防止 SQL 注入
- [ ] 子类未定义 `_TABLE_NAME` 时抛出 NotImplementedError

### AWBaseDataProvider 只读查询

- [ ] 初始化时验证 AW 数据库文件是否存在，不存在抛出 FileNotFoundError 并提示检查配置
- [ ] `_parse_timestamp(timestamp_str)` 解析 ISO 时间戳，自动处理 UTC 后缀（`+00:00` / `Z`）和无时区字符串
- [ ] `_utc_to_local(utc_dt)` 将 UTC 时间转换为 local_tz 时区
- [ ] `_local_to_utc(local_dt)` 将本地时间转换为 UTC，支持 str 输入
- [ ] `get_window_events(start_time, end_time, hours, limit)` 将本地时间转为 UTC 后查询 AW 的 eventmodel 表
- [ ] `get_buckets(bucket_type)` 返回 AW 的 bucketmodel 表数据，支持按 type 过滤

### 数据库迁移

- [ ] `run_migrations(db_path)` 在数据库文件不存在时跳过（由 init_database 创建）
- [ ] 迁移前自动检测当前 schema_version 版本号，只执行 version > current_version 的迁移
- [ ] 有迁移待执行时先备份数据库（WAL checkpoint 后 copy2），备份命名格式 `{stem}.backup-v{version}-{timestamp}{suffix}`
- [ ] 每个迁移独立 commit，单个迁移失败则 rollback 该迁移并抛出 RuntimeError
- [ ] 迁移脚本的 `check_if_applied()` 返回 True 时跳过 upgrade 但补录版本记录（幂等）
- [ ] 迁移成功后插入 schema_version 记录（INSERT OR IGNORE）
- [ ] 旧备份自动清理，只保留最近 3 个

### 异常映射

- [ ] `EntityNotFoundError(code="ENTITY_NOT_FOUND")` 由全局异常处理器映射为 HTTP 404
- [ ] `DuplicateEntityError(code="ENTITY_ALREADY_EXISTS")` 由全局异常处理器映射为 HTTP 409
- [ ] `RepositoryError(DataAccessError)` 及其他未显式映射的 LWBaseError 子类由全局异常处理器映射为 HTTP 500

## Technical Contract

### DatabaseManager

<key_function>
- lifeprism/repository/database_manager.py
  - database_manager.DatabaseManager.__init__:31
  - database_manager.DatabaseManager.get_connection:136
  - database_manager.DatabaseManager.query:205
  - database_manager.DatabaseManager.query_advanced:609
  - database_manager.DatabaseManager.insert:288
  - database_manager.DatabaseManager.insert_many:318
  - database_manager.DatabaseManager.upsert:356
  - database_manager.DatabaseManager.upsert_many:424
  - database_manager.DatabaseManager.update:504
  - database_manager.DatabaseManager.update_by_id:542
  - database_manager.DatabaseManager.delete:561
  - database_manager.DatabaseManager.delete_by_id:593
  - database_manager.DatabaseManager.get_by_id:269
  - database_manager.DatabaseManager.execute_raw:703
  - database_manager.DatabaseManager.truncate:710
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `__init__(DB_PATH, use_pool, pool_size, readonly)` | 初始化数据库管理器 | use_pool=True 时预创建 pool_size 个连接并注册 atexit 清理；readonly=True 时以 `mode=ro` URI 打开 |
| `get_connection()` | 上下文管理器，获取数据库连接 | 连接池模式：池中获取，健康检查，用后归还；非池模式：每次创建新连接并关闭。正常退出 commit，异常 rollback 并抛 DataAccessError |
| `query(table_name, columns, where, order_by, limit)` | 通用查询，返回 pd.DataFrame | 空结果返回空 DataFrame |
| `query_advanced(table_name, conditions, order_by, limit)` | 高级查询，支持多操作符 | 支持 =、!=、>、<、>=、<=、LIKE、IN、NOT IN、BETWEEN |
| `insert(table_name, data)` | 插入单条记录 | 返回受影响行数 |
| `insert_many(table_name, data_list)` | 批量插入 | 空列表返回 0；使用 executemany |
| `upsert(table_name, data, conflict_columns)` | 存在则更新，不存在则插入 | 需要 UNIQUE 或 PRIMARY KEY 约束；对特定表自动更新 updated_at |
| `upsert_many(table_name, data_list, conflict_columns)` | 批量 upsert | 对特定表自动更新 updated_at |
| `update(table_name, data, where)` | 按条件更新 | 返回受影响行数 |
| `update_by_id(table_name, id_column, id_value, data)` | 按 ID 更新 | 等价于 `update(table, data, {id_column: id_value})` |
| `delete(table_name, where)` | 按条件删除 | 返回受影响行数 |
| `delete_by_id(table_name, id_column, id_value)` | 按 ID 删除 | 等价于 `delete(table, {id_column: id_value})` |
| `get_by_id(table_name, id_column, id_value)` | 按 ID 查询单条 | 返回 dict 或 None |
| `execute_raw(sql, params, fetch)` | 执行原始 SQL | fetch=True 返回 DataFrame，fetch=False 返回 None |
| `truncate(table_name)` | 清空表 | INFO 级别记录影响行数 |

**连接池行为**：
- 从 `Queue` 获取连接，超时 1 秒
- 获取后执行 `SELECT 1` 健康检查，失效则创建新连接
- 池空时创建临时连接（不阻塞调用方）
- 归还时池满则关闭连接
- 程序退出时通过 `atexit` 关闭所有池化连接

### LWTableManager

<key_function>
- lifeprism/repository/lw_table_manager.py
  - lw_table_manager.LWTableManager.init_database:36
  - lw_table_manager.init_database:115
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `init_database()` | 遍历 TABLE_CONFIGS 创建所有表 | 使用 `CREATE TABLE IF NOT EXISTS`；自动处理 timestamps、update_at、indexes、table_constraints |

### LWBaseDataProvider

<key_function>
- lifeprism/repository/base_providers/lw_base_data_provider.py
  - lw_base_data_provider.LWBaseDataProvider._generic_query:967
  - lw_base_data_provider.LWBaseDataProvider._generic_insert:1032
  - lw_base_data_provider.LWBaseDataProvider._generic_update:1141
  - lw_base_data_provider.LWBaseDataProvider._generic_delete:1211
  - lw_base_data_provider.LWBaseDataProvider._validate_table_name:947
  - lw_base_data_provider.LWBaseDataProvider.get_activity_logs:129
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `_generic_query(options)` | 通用查询，返回 `(记录列表, 总数)` | 需定义 `_TABLE_NAME`；date_range 需 `_DATE_FIELD`；time_range 需 `_TIME_FIELD`；filters 需 `_FILTER_FIELDS` 白名单；order_by 需 `_ORDER_FIELDS` 白名单 |
| `_generic_insert(data, id_prefix, auto_order_index, on_conflict)` | 通用插入，返回新记录 ID | id_prefix 非 None 时自动生成 `{prefix}{uuid4().hex[:8]}` 格式 ID；auto_order_index=True 时自动计算 order_index；on_conflict 支持 abort/ignore/replace |
| `_generic_update(record_id, data)` | 通用更新，返回是否成功 | 按 `_PRIMARY_KEY` 匹配；`_UPDATE_FIELDS` 白名单验证；对配置了 update_at 的表自动设置 updated_at |
| `_generic_delete(record_id)` | 通用删除，返回是否成功 | 按 `_PRIMARY_KEY` 匹配 |
| `get_activity_logs(date, start_time, end_time, ...)` | 统一的活动日志查询 | 支持按日期或时间范围、分类过滤、分页、字段白名单 |

**子类元数据约定**：

| 元数据 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `_TABLE_NAME` | `str \| None` | `None` | 表名（必须定义） |
| `_PRIMARY_KEY` | `str` | `"id"` | 主键字段名 |
| `_DATE_FIELD` | `str \| None` | `None` | 日期字段名（如 `"date"`） |
| `_TIME_FIELD` | `str \| None` | `None` | 时间字段名（如 `"trigger_time"`） |
| `_ON_CONFLICT` | `str` | `"replace"` | 默认冲突策略 |
| `_FILTER_FIELDS` | `set[str]` | `set()` | 可筛选字段白名单 |
| `_ORDER_FIELDS` | `set[str]` | `set()` | 可排序字段白名单 |
| `_SELECT_FIELDS` | `set[str]` | `set()` | 可选择字段白名单 |
| `_UPDATE_FIELDS` | `set[str]` | `set()` | 可更新字段白名单 |

子类通过定义上述元数据即可获得完整的单表 CRUD 能力，无需编写 SQL。白名单机制同时提供了 SQL 注入防护。

### AWBaseDataProvider

<key_function>
- lifeprism/repository/base_providers/aw_base_data_provider.py
  - aw_base_data_provider.AWBaseDataProvider._parse_timestamp:60
  - aw_base_data_provider.AWBaseDataProvider._utc_to_local:70
  - aw_base_data_provider.AWBaseDataProvider._local_to_utc:76
  - aw_base_data_provider.AWBaseDataProvider.get_buckets:88
  - aw_base_data_provider.AWBaseDataProvider.get_window_events:123
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `_parse_timestamp(timestamp_str)` | 解析 ISO 时间戳为 datetime | 自动处理 `+00:00` / `Z` 后缀和无时区字符串 |
| `_utc_to_local(utc_dt)` | UTC 转本地时间 | 输入无时区时自动附加 UTC |
| `_local_to_utc(local_dt)` | 本地时间转 UTC | 支持 str 输入 |
| `get_buckets(bucket_type)` | 获取 AW 存储桶列表 | bucket_type 为 None 时返回全部 |
| `get_window_events(start_time, end_time, hours, limit)` | 获取窗口切换事件 | 本地时间输入自动转 UTC 查询；默认 limit=500000 |

**初始化行为**：构造时验证 AW 数据库文件存在性，不存在抛出 `FileNotFoundError` 并提示检查配置。

### 数据库实例契约

`__init__.py` 模块加载时创建三个全局 DatabaseManager 实例：

| 实例名 | DB 路径 | 读写模式 | 连接池 | 用途 |
|--------|---------|----------|--------|------|
| `lw_db_manager` | `settings.lw_db_path` | 读写 | 池大小 5 | LifeWatch 主数据库 |
| `aw_db_manager` | `settings.aw_db_path` | 只读 (`mode=ro`) | 池大小 1 | ActivityWatch 外部数据 |

**数据库文件自动创建**：对于 lw_db_path，若文件不存在则在模块加载时自动创建空文件和父目录，防止只读模式下因文件不存在导致连接失败。

### 异常体系

<key_function>
- lifeprism/repository/exceptions.py
  - exceptions.RepositoryError:10
  - exceptions.EntityNotFoundError:16
  - exceptions.DuplicateEntityError:38
</key_function>

**继承链**：

```
LWBaseError (lifeprism.utils.exceptions)
├── DataAccessError
│   └── RepositoryError          — repository 模块基础异常
├── NotFoundError
│   └── EntityNotFoundError      — code="ENTITY_NOT_FOUND" → HTTP 404
├── ConflictError
│   └── DuplicateEntityError     — code="ENTITY_ALREADY_EXISTS" → HTTP 409
├── ValidationError
└── ExternalServiceError
```

**异常类契约**：

| 异常类 | 父类 | code | HTTP 映射 | 构造参数 |
|--------|------|------|-----------|----------|
| `RepositoryError` | `DataAccessError` | — | 500 | 继承自 LWBaseError（message, code, details, cause） |
| `EntityNotFoundError` | `NotFoundError` | `ENTITY_NOT_FOUND` | 404 | `entity_type: str, entity_id: str, **extra_details` |
| `DuplicateEntityError` | `ConflictError` | `ENTITY_ALREADY_EXISTS` | 409 | `entity_type: str, entity_id: str, conflict_field: str` |

所有异常通过 `lifeprism.utils.exceptions.LWBaseError` 提供的 `to_dict()` 序列化，API 层通过全局异常处理器（`api_error_mapping.map_app_error()`）统一转换为 HTTP 响应。

### 迁移系统

<key_function>
- lifeprism/repository/migrations/migration_runner.py
  - migration_runner.run_migrations:22
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `run_migrations(db_path)` | 执行所有待运行的迁移 | 数据库文件不存在时跳过；按 VERSION 递增顺序执行；迁移前备份；每个迁移独立提交 |

**迁移执行流程**：

1. 连接数据库（独立 sqlite3 连接，不走连接池）
2. 查询 `schema_version` 表获取当前版本（表不存在返回 0）
3. 筛选 `VERSION > current_version` 的迁移脚本
4. 有待执行迁移时：WAL checkpoint → 备份数据库文件 → 逐个执行迁移
5. 每个迁移：`check_if_applied()`（幂等检查）→ `upgrade()`（仅未应用时执行）→ 插入 schema_version 记录 → 独立 commit
6. 单个迁移失败则 rollback 该迁移，抛出 RuntimeError
7. 清理旧备份，只保留最近 3 个

### QueryOptions

<key_function>
- lifeprism/repository/providers/common_query_options.py
  - common_query_options.QueryOptions:6
  - common_query_options.QueryOptions.with_date_range:56
  - common_query_options.QueryOptions.with_time_range:60
  - common_query_options.QueryOptions.with_filters:64
  - common_query_options.QueryOptions.with_order:69
  - common_query_options.QueryOptions.with_page:73
  - common_query_options.QueryOptions.with_limit:77
  - common_query_options.QueryOptions.with_fields:81
</key_function>

**不可变查询参数对象**（`@dataclass(frozen=True)`）：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `date_range` | `tuple[str, str] \| None` | `None` | 日期范围（闭区间） |
| `time_range` | `tuple[str, str] \| None` | `None` | 时间范围（闭区间） |
| `filters` | `dict[str, Any] \| None` | `None` | 通用筛选条件 |
| `order_by` | `str \| None` | `None` | 排序字段 |
| `order_desc` | `bool` | `True` | 是否降序 |
| `page` | `int \| None` | `None` | 页码（从 1 开始） |
| `page_size` | `int \| None` | `None` | 每页条数（1-1000） |
| `limit` | `int \| None` | `None` | 结果数量限制（page 未设置时生效） |
| `fields` | `list[str] \| None` | `None` | 返回字段列表 |

提供 `with_*()` 方法链式创建新对象（不可变，使用 `dataclasses.replace`）。

### 模块导出清单

`lifeprism/repository/__init__.py` 对外导出：

| 符号 | 类型 | 说明 |
|------|------|------|
| `QueryOptions` | 类 | 查询选项 |
| `DatabaseManager` | 类 | 数据库管理器 |
| `lw_db_manager` | DatabaseManager 实例 | LW 主库（读写，池5） |
| `aw_db_manager` | DatabaseManager 实例 | AW 外部库（只读，池1） |
| `LWBaseDataProvider` | 类 | LW 通用 CRUD 基类 |
| `AWBaseDataProvider` | 类 | AW 只读基类 |
| `*_repository` (15 个) | Provider/Aggregator 实例 | 单表和多表数据访问入口 |

## Design Rationale

**为什么 Provider-Aggregator 分离？**
- Provider 负责单表 CRUD，Aggregator 负责多表聚合查询
- 职责单一：单表操作不关心跨表 JOIN，多表聚合不关心底层 CRUD 实现
- Aggregator 内部组合多个 Provider，通过依赖注入使用 DatabaseManager 实例
- 对调用方透明：无论是 Provider 还是 Aggregator，统一以 `*_repository` 导出

**为什么连接池模式是可选的？**
- `use_pool=False` 保持向后兼容，每次操作创建新连接
- 只读数据库（AW）仅需少量连接，池大小 1 即可满足
- 读写数据库（LW）需要池大小 5 支持多线程并发写入

**为什么 aw_db 是只读的？**
- ActivityWatch 是外部应用生成的数据库，修改它可能导致 AW 数据损坏或 AW 自身行为异常
- 只读模式通过 SQLite URI `mode=ro` 在数据库层面强制执行，防止误写

**为什么迁移系统使用独立 sqlite3 连接？**
- 迁移是启动时的"管理操作"，不走连接池，避免占用业务连接的池化资源
- 每个迁移独立 commit，单个失败只回滚当前迁移，不影响已成功执行的迁移
- 迁移执行期间其他模块尚未初始化，不存在并发竞争

**为什么用元数据驱动通用 CRUD？**
- 避免 22 个 Provider 中重复实现相同的 `INSERT` / `UPDATE` / `DELETE` / `SELECT` 逻辑
- 白名单机制（`_FILTER_FIELDS`、`_ORDER_FIELDS` 等）在提供灵活性的同时防止 SQL 注入和非法字段访问
- 子类只需定义表名和字段约束即可使用，新增 Provider 成本极低

**为什么 lw_db 文件要自动创建？**
- 数据库文件在首次启动时可能不存在（新用户或数据迁移后的干净状态）
- 模块加载时在连接池创建前检查文件存在性，创建空文件后连接池才能正常初始化

**有哪些约束？**
- 所有数据库均为 SQLite，不支持其他数据库引擎（参见 `LWBaseDataProvider` 中的 SQLite 限制说明）
- `database_manager.py` 从 `lifeprism.utils.exceptions` 导入 `DataAccessError`，未使用本模块的 `RepositoryError`，存在异常类型不一致（技术债）
- `LWTableManager` 使用标准 `logging.getLogger` 而非项目统一的 `get_logger`
- 连接池使用 `Queue` 实现，归还连接非阻塞（`put_nowait`），池满时直接关闭连接

**有哪些已知限制？**
- `lw_db_manager` 创建后连接池即初始化，如果 `init_database()` 之后需要执行迁移，需要确保数据库文件已存在
- 连接池健康检查仅执行 `SELECT 1`，不检测 WAL 文件损坏等深层问题
- `DatabaseManager` 的通用 CRUD 方法直接暴露表名参数，调用方需自行保证表名正确性

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **Repository 初始化流程**：[`docs/flows/2026-07-06-repository-initialization-flow.md`](../flows/2026-07-06-repository-initialization-flow.md) — 模块加载时的数据库文件创建、连接池初始化、迁移执行、建表的完整时序
- **数据访问流**：[`docs/flows/2026-07-06-repository-data-access-flow.md`](../flows/2026-07-06-repository-data-access-flow.md) — Provider/Aggregator 通过 BaseProvider 和 DatabaseManager 完成数据操作的完整调用链
- **具体 Provider/Aggregator 业务逻辑**：各 repository 实例的内部方法（如 `diary_repository.query_diaries()`）遵循本 spec 定义的 BaseProvider 模式，各自在对应模块中实现
- **TABLE_CONFIGS 表结构定义**：`lifeprism/config/database.py` 中的表配置，属于 config 模块的数据库 schema 范畴
