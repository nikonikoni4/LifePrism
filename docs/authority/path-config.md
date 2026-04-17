---
version: 1.0
created_at: 2026-04-15
updated_at: 2026-04-15
last_updated: 初始版本
abstract: 路径配置体系权威参考，定义 config_base_path（固定）、lifeprism_data_path（可迁移）、数据库路径（自动推算）的解析规则和优先级，以及配置文件固定路径设计和数据迁移机制
---

# 路径配置体系

## 路径总览

| 路径 | 访问方式 | 来源 | 说明 |
|------|---------|------|------|
| `config_base_path` | `settings.config_base_path` | 固定推算 | 配置文件根目录，不随数据迁移 |
| `lifeprism_data_path` | `settings.lifeprism_data_path` | yaml 配置 / 环境变量 / 默认推算 | 数据根目录，可迁移 |
| `lw_db_path` | `settings.lw_db_path` | 自动推算 | `{data_path}/dataset/lifewatch_ai.db` |
| `chat_db_path` | `settings.chat_db_path` | 自动推算 | `{data_path}/dataset/chat_history.db` |
| `aw_db_path` | `settings.aw_db_path` | yaml 配置 | ActivityWatch 数据库，独立配置 |
| 日志目录 | `_setup_logging()` 内部 | 自动推算 | 打包：`{data_path}/debug_logs/`，开发：项目根目录 |

**关键规则**：`lw_db_path` / `chat_db_path` 不在 yaml 中配置，是从 `lifeprism_data_path` 计算得出的只读属性。

---

## 配置文件固定路径设计

配置文件（config/）始终固定在默认路径，不随数据迁移。这解决了 Electron 通过环境变量始终指向默认路径导致迁移后配置文件无法被读取的问题。

### `config_base_path` 解析（`_resolve_config_base_path()`）

固定路径，不依赖 yaml 或环境变量：

| 环境 | 路径 |
|------|------|
| 打包 | `%LOCALAPPDATA%/LifePrism/lifeprismData` |
| 开发 | `localData`（项目根目录） |

### `lifeprism_data_path` 解析流程

`_initialize()` 中的解析顺序：

1. **yaml 配置**：加载 `config_base_path/config/config.yaml`，如果其中 `lifeprism_data_path` 非空，使用该值
2. **环境变量** `LIFEPRISM_DATA_PATH`（Electron 启动后端时传入）
3. **默认路径**：与 `config_base_path` 相同

### 最终处理

解析完成后写入 `os.environ['LIFEPRISM_DATA_PATH']`，供 Electron 等外部进程读取。

---

## `aw_db_path` — 独立配置

- 存储在 yaml 中，由用户手动配置
- 读取时会做 `os.path.expanduser()` 展开 `~` 前缀
- 默认值：`~/AppData/Local/activitywatch/activitywatch/aw-server/peewee-sqlite.v2.db`
- 前端设置页可通过文件选择器修改

---

## 配置文件本身的路径

| 环境 | 配置文件位置 |
|------|-------------|
| 开发 | `lifeprism/config/settings.yaml` |
| 打包 | `{config_base_path}/config/config.yaml`（固定在默认路径） |

判断逻辑：`getattr(sys, 'frozen', False)` 区分打包/开发环境。

---

## 目录结构

配置文件和数据文件分离存放：

```
%LOCALAPPDATA%/LifePrism/lifeprismData/     ← config_base_path（固定）
└── config/
    ├── config.yaml        # 后端主配置（含 lifeprism_data_path 指向数据路径）
    ├── providers.yaml     # LLM 服务商配置
    └── config.json        # 端口配置（前后端共用）

{lifeprism_data_path}/                 ← 数据路径（可迁移）
├── dataset/          # 数据库文件 (lifewatch_ai.db, chat_history.db)
├── plan/             # PlanDoc Markdown 文件
├── debug_logs/       # 日志文件（打包环境）
├── workflow/         # 工作流数据
└── external_files/   # 外部导入文件
```

未迁移时，`config_base_path` 和 `lifeprism_data_path` 指向同一目录。

开发环境日志写入项目根目录，不写入 `debug_logs/`。

---

## 日志路径

由 `settings_manager._setup_logging()` 在初始化末尾配置，调用 `logger.setup_file_logging(log_dir)`：

| 环境 | 日志目录 | 说明 |
|------|---------|------|
| 打包 | `{lifeprism_data_path}/debug_logs/` | 随数据目录迁移 |
| 开发 | 项目根目录（`Path(__file__).parent.parent.parent`） | 即 `LifeWatch-AI/` |

日志文件由 `setup_file_logging()` 创建 `FileHandler` 添加到 root logger，所有通过 `get_logger(__name__)` 创建的 logger 自动继承。

---

## 数据迁移 API

`POST /settings/migrate-data-path` 支持将数据迁移到新路径。

### 流程

1. 开发模式检查（开发模式下禁用）
2. 计算新路径：`{用户选择的目录}/lifeprismData`
3. 验证：不能与当前路径相同、不能在安装目录内
4. 关闭数据库连接池
5. 复制数据子目录（`dataset`, `plan`, `debug_logs`, `workflow`, `external_files`，**不含 `config`**）
6. 更新 yaml 配置中的 `lifeprism_data_path`（写入固定路径的 config.yaml）
7. 需要重启程序生效

### 路径验证 API

`POST /settings/validate-path` 验证路径有效性：
- `lifeprism_data` 类型：检查不与安装路径冲突、是目录
- `aw_db` 类型：检查文件存在、是 `.db` 文件

---

## 编码注意事项

1. **禁止**在 `settings_manager` 以外的模块自行解析路径或读取路径相关环境变量
2. **禁止**在 yaml 中单独配置 `lw_db_path` / `chat_db_path`，它们是计算属性
3. 新增数据子目录时，需同步更新 `setting_service._DATA_SUBDIRS` 列表（迁移用）
4. 路径相关的前端设置变更通过 `PATCH /settings` 提交，后端 `settings.update()` 会同步更新内部 `_lifeprism_data_path` 和环境变量
5. **配置文件路径**使用 `settings.config_base_path`，**数据路径**使用 `settings.lifeprism_data_path`，两者在迁移后不同
