---
version: 1.1
created_at: 2026-07-06
updated_at: 2026-07-08
last_updated: 移除已弃用的 chat_db_path 派生路径
abstract: config 模块路径体系 spec — 定义 config_base_path（配置文件固定路径）和 lifeprism_data_path（数据路径，可迁移）的解析规则、优先级、派生路径体系，以及环境差异和安全检查契约
module: config
status: draft
---

# Config 模块路径体系

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |
| 1.1 | 移除已弃用的 chat_db_path 派生路径 |

## Overview

**业务问题**：LifeWatch-AI 在打包环境和开发环境中运行，配置文件和用户数据的存储位置需要满足以下需求：

1. **配置文件与数据分离** — 配置文件（config.yaml、providers.yaml 等）需要固定位置，不受用户数据迁移影响；用户数据（截图、日志、数据库等）需要支持迁移到其他磁盘
2. **打包/开发环境差异** — 打包后安装到 `%LOCALAPPDATA%`，开发时在项目根目录，两者路径体系不同
3. **数据路径迁移安全** — 用户通过设置界面迁移数据路径时，不能丢失历史数据，且不能将数据放到安装目录内（卸载时会丢失）

**核心职责**：定义两个核心路径的解析规则、优先级和派生体系，确保所有模块通过统一入口获取路径，不各自计算。

## Scope

### 范围内

- `config_base_path` 的定义和解析规则（打包/开发环境差异，不可迁移）
- `lifeprism_data_path` 的定义和解析优先级（yaml 配置 > 环境变量 > 默认值）
- 数据路径迁移时的环境变量同步行为
- 基于 `lifeprism_data_path` 的派生路径规则（lw_db_path、channel_path、session_path）
- `allowed_dir_path` 的白名单目录和扩展目录规则
- 打包环境数据路径安全检查（安装目录内警告）
- 开发环境使用 `localData` 的行为

### 范围外

- 具体配置项的读写逻辑（get/set/update/reload）— 属于 config-settings-spec
- API Key 的存储和获取（keyring / 环境变量）— 属于 config-settings-spec
- Provider 管理 — 属于 config-provider-spec
- 配置迁移脚本 — 属于 config-migration-spec

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 配置文件基础路径（config_base_path）

- [ ] 开发环境（非 frozen）：`config_base_path` = `Path("localData")`（项目根目录下的 localData）
- [ ] 打包环境（frozen）：`config_base_path` = `%LOCALAPPDATA%/LifePrism/lifeprismData`
- [ ] 打包环境 `%LOCALAPPDATA%` 为空时，基于 `sys.executable` 推算后备路径
- [ ] `config_base_path` 固定不变，不受数据路径迁移影响
- [ ] 配置文件 `config.yaml` 始终位于 `{config_base_path}/config/config.yaml`

### 数据路径（lifeprism_data_path）

- [ ] 初始解析优先级：yaml 中 `lifeprism_data_path` 配置 > 环境变量 `LIFEPRISM_DATA_PATH` > 默认（= config_base_path）
- [ ] yaml 中 `lifeprism_data_path` 为空字符串时，视为未配置，走默认
- [ ] yaml 中 `lifeprism_data_path` 有值时，直接使用该路径（不做额外校验）
- [ ] 环境变量 `LIFEPRISM_DATA_PATH` 未设置且 yaml 未配置时，数据路径 = config_base_path
- [ ] 初始化完成后，环境变量 `LIFEPRISM_DATA_PATH` 自动更新为当前数据路径
- [ ] 通过 `update()` 或 `set()` 修改 `lifeprism_data_path` 后，内部 `_lifeprism_data_path` 同步更新
- [ ] 通过 `update()` 修改 `lifeprism_data_path` 为空字符串时，回退到 `_resolve_default_data_path()`

### 派生路径

- [ ] `lw_db_path` = `{lifeprism_data_path}/dataset/lifewatch_ai.db`
- [ ] `channel_path` = `{lifeprism_data_path}/channel`
- [ ] `session_path` = `{lifeprism_data_path}/session`
- [ ] 以上所有派生路径自动跟随 `lifeprism_data_path` 变化，无需手动更新
- [ ] `aw_db_path` 独立于数据路径体系，从配置项 `aw_db_path` 读取并做 `expanduser` 展开

### 允许目录（allowed_dir_path）

- [ ] 固定白名单目录：`{lifeprism_data_path}/user`、`{lifeprism_data_path}/diary`、`{lifeprism_data_path}/agent`
- [ ] 扩展目录：从 `{lifeprism_data_path}/expand_dir/expand_meta_data.json` 读取 `expand_dirs` 列表
- [ ] `expand_meta_data.json` 不存在或解析失败时不阻塞启动
- [ ] 返回的所有路径均为 `resolve()` 后的绝对路径

### 安全检查

- [ ] 开发环境：跳过数据路径安全检查
- [ ] 打包环境：数据路径位于安装目录内时，系统警告列表新增 `data_path` 类型警告
- [ ] 打包环境：数据路径不在安装目录内时，无警告
- [ ] `warnings` 属性返回系统警告列表的副本

### 日志配置

- [ ] 文件日志写入 `{lifeprism_data_path}/debug_logs/`
- [ ] 日志目录不存在时自动创建（由 `setup_file_logging` 保证）

## Technical Contract

### config_base_path — 配置文件基础路径

<key_function>
- lifeprism/config/settings_manager.py
  - settings_manager.SettingsManager.config_base_path:684
</key_function>

**解析规则**：

| 环境 | 判断条件 | config_base_path 值 | 说明 |
|------|---------|-------------------|------|
| 开发环境 | `sys.frozen` = False | `Path("localData")` | 项目根目录下的 localData |
| 打包环境 | `sys.frozen` = True, `%LOCALAPPDATA%` 存在 | `%LOCALAPPDATA%/LifePrism/lifeprismData` | Windows 标准本地应用数据目录 |
| 打包环境（后备） | `sys.frozen` = True, `%LOCALAPPDATA%` 为空 | 基于 `sys.executable` 推算 | 极端情况的后备路径 |

**契约**：
- `config_base_path` 在 `SettingsManager` 单例初始化时确定，之后**不可修改**
- 配置文件目录 `config/` 始终位于 `config_base_path` 下
- 此路径不受数据迁移影响，NSIS 卸载器不会清理此路径下的配置文件

### lifeprism_data_path — 数据路径

<key_function>
- lifeprism/config/settings_manager.py
  - settings_manager.SettingsManager.lifeprism_data_path:679
</key_function>

**解析优先级**（仅在初始化时计算，之后通过 `update()` 可动态修改）：

```
1. yaml 配置中的 lifeprism_data_path（非空时直接使用）
      ↓ 为空或不存在
2. 环境变量 LIFEPRISM_DATA_PATH
      ↓ 不存在
3. 默认 = config_base_path
```

**动态修改契约**（通过 `set()` 或 `update()`）：
- 修改 `lifeprism_data_path` 为非空字符串时，`_lifeprism_data_path` 更新为新路径
- 修改 `lifeprism_data_path` 为空字符串时，回退调用 `_resolve_default_data_path()`（环境变量 > 默认）
- 修改后同步更新环境变量 `LIFEPRISM_DATA_PATH`，供 Electron 等外部进程读取

### 派生路径规则表

| Property | 基于路径 | 最终路径 |
|----------|---------|---------|
| `lw_db_path` | `lifeprism_data_path` | `{lifeprism_data_path}/dataset/lifewatch_ai.db` |
| `channel_path` | `lifeprism_data_path` | `{lifeprism_data_path}/channel` |
| `session_path` | `lifeprism_data_path` | `{lifeprism_data_path}/session` |
| `allowed_dir_path` | `lifeprism_data_path` | 见下方 allowed_dir_path 规则 |
| `aw_db_path` | 配置项 `aw_db_path`（独立） | `expanduser(aw_db_path 配置值)` |

<key_function>
- lifeprism/config/settings_manager.py
  - settings_manager.SettingsManager.lw_db_path:665
  - settings_manager.SettingsManager.channel_path:704
  - settings_manager.SettingsManager.session_path:709
  - settings_manager.SettingsManager.allowed_dir_path:694
  - settings_manager.SettingsManager.aw_db_path:660
</key_function>

**派生路径契约**：
- 所有基于 `lifeprism_data_path` 的派生路径均为**计算属性**，读取时实时计算，不存储
- 派生路径不保证目录存在，调用方需自行确保目录创建
- `aw_db_path` 不随数据路径迁移而改变，它指向 ActivityWatch 数据库的固定位置

### allowed_dir_path — 允许目录规则

<key_function>
- lifeprism/config/settings_manager.py
  - settings_manager.SettingsManager.allowed_dir_path:694
</key_function>

**白名单固定目录**（始终包含）：
- `{lifeprism_data_path}/user`
- `{lifeprism_data_path}/diary`
- `{lifeprism_data_path}/agent`

**扩展目录**（可选）：
- 从 `{lifeprism_data_path}/expand_dir/expand_meta_data.json` 读取
- JSON 结构：`{"expand_dirs": [{"path": "/absolute/path"}, ...]}`
- 文件不存在或解析失败时：静默跳过，不影响启动

**返回类型**：`list[Path]`，所有路径均为 `resolve()` 后的绝对路径。

### 数据路径安全检查

**触发条件**：仅打包环境（`sys.frozen` = True）

**检查逻辑**：判断 `lifeprism_data_path` 是否为安装目录的子目录。

**检查方法**：尝试 `resolved_data.relative_to(resolved_install)`，若不抛 `ValueError` / `OSError` 则说明数据路径在安装目录内。

**警告处理**：发现不安全时，向 `self._warnings` 添加一条 `type: "data_path"` 的警告记录。warnings 通过 `settings.warnings` 对外暴露，前端设置页面展示。

## Design Rationale

**为什么 config_base_path 固定？**
- 配置文件（config.yaml、providers.yaml 等）是应用运行的前提，必须保证在任何情况下都存在。
- 打包环境下使用 `%LOCALAPPDATA%` 而非 `%APPDATA%`，目的是避免 NSIS 卸载器清理 `%APPDATA%\LifePrism` 时误删配置文件。
- 配置文件不应随用户数据迁移，否则用户在设置界面迁移数据路径后，下次启动找不到配置。

**为什么 lifeprism_data_path 可迁移？**
- 用户截图、日志、数据库等数据量可能很大，需要支持存放到其他磁盘（如 D 盘）。
- 迁移通过设置界面修改 yaml 中的 `lifeprism_data_path` 配置项实现，修改后环境变量同步更新，Electron 和子进程均可感知。

**为什么开发环境用 localData？**
- 开发时不污染系统目录（`%LOCALAPPDATA%`），所有数据放在项目根目录的 `localData` 下。
- 与打包环境的路径体系保持一致的目录结构（都有 `config/`、`dataset/`、`debug_logs/` 等子目录）。

**为什么配置文件目录名是 `config/` 而非沿用旧名？**
- 打包环境和开发环境统一使用 `config/` 目录名，简化路径逻辑，不再区分 `settings/` 和 `config/`。

**相关 ADR**：
- 路径体系相关 ADR 待补充

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **Config Settings Spec**：[`docs/specs/2026-07-06-config-settings-spec.md`](./2026-07-06-config-settings-spec.md) — 具体配置项的读写（get/set/update）、API Key 管理、配置验证
- **Config Initialization Flow**：[`docs/flows/2026-07-06-config-initialization-flow.md`](../flows/2026-07-06-config-initialization-flow.md) — 配置系统启动初始化全链路
