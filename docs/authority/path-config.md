---
version: 2.3
created_at: 2026-04-15
updated_at: 2026-04-20
last_updated: 重构前端路径配置章节，新增完整的前后端路径解析流程图和对比表
abstract: 路径配置体系权威参考，定义 config_base_path（固定）、lifeprism_data_path（可迁移）、数据库路径（自动推算）的解析规则和优先级，以及配置文件固定路径设计和数据迁移机制，包含前后端完整的路径配置流程图
---

## 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-04-15 | 初始版本 |
| 2.0 | 2026-04-18 | 更新 _DATA_SUBDIRS 列表；新增 session 子目录说明；标注 custom_data_path 已废弃 |
| 2.1 | 2026-04-18 | 数据迁移和资源初始化内容移至 resource-init.md |
| 2.2 | 2026-04-20 | 新增前端打包路径配置章节 |
| 2.3 | 2026-04-20 | 重构前端路径配置章节，新增完整的前后端路径解析流程图和对比表，明确前端必须读取 yaml 配置 |

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
| `session_path` | `settings.session_path` | 自动推算 | `{data_path}/session/` |

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
├── external_files/   # 外部导入文件
├── screenshots/     # 截图数据
├── docs/             # 文档数据
├── diary/            # 日记数据
└── session/          # 会话临时数据
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

## 前端打包路径配置

前端 Electron 通过 `frontend/electron/main.cjs` 管理路径配置，与后端保持一致。

### 路径解析函数

前端需要实现两个路径解析函数：

#### `getConfigBasePath()` - 配置基础路径（固定）

```javascript
function getConfigBasePath() {
    if (app.isPackaged) {
        // 打包后：%LOCALAPPDATA%/LifePrism/lifeprismData
        return path.join(process.env.LOCALAPPDATA || app.getPath('appData'), 'LifePrism', 'lifeprismData');
    } else {
        // 开发时：项目根目录/localData
        return path.join(__dirname, '..', '..', 'localData');
    }
}
```

#### `getLifeprismDataPath()` - 数据路径（可迁移）

```javascript
function getLifeprismDataPath() {
    const configBasePath = getConfigBasePath();
    const configPath = path.join(configBasePath, 'config', 'config.yaml');
    
    // 优先级 1: 读取 yaml 配置
    if (fs.existsSync(configPath)) {
        try {
            const yaml = require('js-yaml');
            const config = yaml.load(fs.readFileSync(configPath, 'utf8'));
            if (config.lifeprism_data_path) {
                return config.lifeprism_data_path;
            }
        } catch (e) {
            console.error('读取 yaml 配置失败:', e);
        }
    }
    
    // 优先级 2: 使用默认路径（与 configBasePath 相同）
    return configBasePath;
}
```

### 打包环境路径配置完整流程

#### 阶段 1：前端启动（Electron）

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Electron 主进程启动                                       │
│    app.whenReady()                                          │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 解析配置基础路径（固定）                                  │
│    getConfigBasePath()                                      │
│    ├─ 读取系统环境变量: process.env.LOCALAPPDATA           │
│    │  (如: C:\Users\xxx\AppData\Local)                     │
│    └─ 拼接固定路径: LifePrism/lifeprismData                │
│    结果: C:\Users\xxx\AppData\Local\LifePrism\lifeprismData│
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 读取数据路径配置（两级优先级）                            │
│    getLifeprismDataPath()                                   │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 优先级 1: 读取 yaml 配置                         │    │
│    │   configPath = {configBasePath}/config/config.yaml│   │
│    │   if (fs.existsSync(configPath)) {               │    │
│    │     config = yaml.load(configPath)               │    │
│    │     if (config.lifeprism_data_path) {            │    │
│    │       return config.lifeprism_data_path          │    │
│    │     }                                             │    │
│    │   }                                               │    │
│    └──────────────────┬───────────────────────────────┘    │
│                       │ 如果为空或不存在                    │
│                       ▼                                     │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 优先级 2: 使用默认路径（与 configBasePath 相同） │    │
│    │   return configBasePath                          │    │
│    └──────────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 初始化前端日志                                            │
│    initFrontendLog()                                        │
│    日志路径: {lifeprismDataPath}/debug_logs/electron.log   │
│    ✅ 遵循 yaml 配置，迁移后日志在新路径                    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 启动后端进程                                              │
│    spawn(backendPath, [], {                                │
│      env: {                                                 │
│        ...process.env,                                      │
│        LIFEPRISM_DATA_PATH: lifeprismDataPath  ◄─ 传递路径 │
│      }                                                      │
│    })                                                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
                 后端启动
```

#### 阶段 2：后端初始化（Python）

```
┌─────────────────────────────────────────────────────────────┐
│ 1. SettingsManager 单例初始化                                │
│    _initialize()                                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 解析配置基础路径（固定，不读取环境变量）                  │
│    _resolve_config_base_path()                              │
│    ├─ 读取系统环境变量: os.environ.get('LOCALAPPDATA')     │
│    └─ 拼接固定路径: LifePrism/lifeprismData                │
│    结果: C:\Users\xxx\AppData\Local\LifePrism\lifeprismData│
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 加载 yaml 配置                                            │
│    配置文件: {config_base_path}/config/config.yaml         │
│    读取字段: lifeprism_data_path                            │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 解析数据路径（三级优先级）                                │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 优先级 1: yaml 配置的 lifeprism_data_path        │    │
│    │   if configured_path:                            │    │
│    │     return Path(configured_path)                 │    │
│    └──────────────────┬───────────────────────────────┘    │
│                       │ 如果为空                            │
│                       ▼                                     │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 优先级 2: 环境变量 LIFEPRISM_DATA_PATH           │    │
│    │   (由 Electron 传入)                             │    │
│    │   data_env = os.environ.get('LIFEPRISM_DATA_PATH')│   │
│    │   if data_env:                                   │    │
│    │     return Path(data_env)                        │    │
│    └──────────────────┬───────────────────────────────┘    │
│                       │ 如果不存在                          │
│                       ▼                                     │
│    ┌──────────────────────────────────────────────────┐    │
│    │ 优先级 3: 默认路径（与 config_base_path 相同）   │    │
│    │   return self._config_base_path                  │    │
│    └──────────────────────────────────────────────────┘    │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 设置环境变量（供外部进程读取）                            │
│    os.environ['LIFEPRISM_DATA_PATH'] = str(lifeprism_data_path)│
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. 配置后端日志                                              │
│    setup_file_logging(lifeprism_data_path / 'debug_logs')  │
│    日志路径: {lifeprism_data_path}/debug_logs/backend.log  │
│    ✅ 遵循 yaml 配置，迁移后日志在新路径                    │
└─────────────────────────────────────────────────────────────┘
```

### 路径配置对比表

| 场景 | config_base_path | lifeprism_data_path | 前端日志路径 | 后端日志路径 |
|------|------------------|---------------------|-------------|-------------|
| **未迁移** | `%LOCALAPPDATA%/LifePrism/lifeprismData` | `%LOCALAPPDATA%/LifePrism/lifeprismData` | `%LOCALAPPDATA%/LifePrism/lifeprismData/debug_logs/electron.log` | `%LOCALAPPDATA%/LifePrism/lifeprismData/debug_logs/backend.log` |
| **迁移后** | `%LOCALAPPDATA%/LifePrism/lifeprismData`（固定） | `D:/MyData/lifeprism`（yaml 配置） | `D:/MyData/lifeprism/debug_logs/electron.log` ✅ | `D:/MyData/lifeprism/debug_logs/backend.log` ✅ |

### 环境变量传递

启动后端时，前端通过环境变量 `LIFEPRISM_DATA_PATH` 传递数据路径（`main.cjs:74, 82`）：

```javascript
backendProcess = spawn(backendPath, [], {
    env: { ...process.env, LIFEPRISM_DATA_PATH: lifeprismDataPath },
    stdio: 'pipe'
});
```

后端 `settings_manager._initialize()` 会读取该环境变量作为数据路径的第二优先级（仅次于 yaml 配置）。

### IPC 接口

前端暴露以下 IPC 接口供渲染进程使用：

| IPC Handler | 返回值 | 说明 |
|------------|--------|------|
| `get-lifeprism-data-path` | `string` | 返回 `getLifeprismDataPath()` 结果 |
| `get-custom-data-path` | `string` | 已废弃，向后兼容，等同于 `get-lifeprism-data-path` |
| `get-install-path` | `string \| null` | 打包环境返回 exe 所在目录，开发环境返回 `null` |

### 前端日志路径

前端日志由 `electron-log` 管理，路径为 `{lifeprismDataPath}/debug_logs/electron.log`（`main.cjs:16-48`）：

```javascript
function initFrontendLog() {
    const logDir = path.join(getLifeprismDataPath(), 'debug_logs');
    const logPath = path.join(logDir, 'electron.log');
    log.transports.file.resolvePathFn = () => logPath;
}
```

启动时会清空旧日志文件，所有 `console.log/error/warn` 被劫持到 `electron-log`。

### 前端资源路径

打包环境下，后端可执行文件位于 `process.resourcesPath/backend/lifeprism-backend.exe`（`main.cjs:71`）。

---

## 数据迁移

详细说明见 [资源初始化与迁移](resource-init.md)。

---

## 约束规则

1. **禁止**在 `settings_manager` 以外的模块自行解析路径或读取路径相关环境变量
2. **禁止**在 yaml 中单独配置 `lw_db_path` / `chat_db_path`，它们是计算属性
3. 新增数据子目录时，会自动被迁移（黑名单机制，仅排除 `config/`）
4. 路径相关的前端设置变更通过 `PATCH /settings` 提交，后端 `settings.update()` 会同步更新内部 `_lifeprism_data_path` 和环境变量
5. **配置文件路径**使用 `settings.config_base_path`，**数据路径**使用 `settings.lifeprism_data_path`，两者在迁移后不同
6. `settings.custom_data_path` 已废弃，请使用 `settings.lifeprism_data_path`
7. **前端路径解析规则**：
   - 必须实现 `getConfigBasePath()` 和 `getLifeprismDataPath()` 两个独立函数
   - `getLifeprismDataPath()` 必须读取 `{config_base_path}/config/config.yaml` 中的 `lifeprism_data_path` 字段
   - 禁止硬编码数据路径，必须遵循 yaml 配置优先的原则
8. **前端启动后端规则**：
   - 必须传递 `LIFEPRISM_DATA_PATH` 环境变量
   - 环境变量值为 `getLifeprismDataPath()` 的返回值
   - 确保前后端路径一致
9. **日志路径规则**：
   - 前后端日志都必须写入 `{lifeprism_data_path}/debug_logs/`
   - 前端日志：`electron.log`
   - 后端日志：`backend.log`
   - 迁移后日志自动跟随数据路径
