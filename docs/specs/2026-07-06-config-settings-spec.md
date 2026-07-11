---
version: 1.0
created_at: 2026-07-06
updated_at: 2026-07-06
last_updated:
abstract: config 模块的配置管理体系 spec，定义用户配置读写、API Key 生命周期、模型历史管理、LLM 服务商配置的技术契约
status: draft
module: config
---

# Config 模块配置管理体系

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 spec 初稿 |

## Overview

**业务问题**：LifeWatch-AI 需要统一管理用户偏好配置（截图频率、数据保留天数、LLM 模型选择等）和 LLM 服务商配置（API Base、默认模型、OAuth/API Key 模式等）。同时需要安全地存储 API Key 等敏感信息，避免明文泄漏到配置文件或版本控制中。

**核心职责**：
- **SettingsManager**：用户级配置的读写、验证、持久化，API Key 的安全存储（系统 keyring），模型使用历史的记录与查询
- **ProviderManager**：LLM 服务商元数据的加载、白名单过滤、keyring 读写，为 LLM 模块提供原始 provider spec 数据
- **异常定义**：ConfigError / ConfigFileNotFoundError / InvalidConfigError，统一配置模块的错误类型

## Scope

### 范围内

- SettingsManager 的配置读写（get / set / update / reload / get_all / get_for_display）
- API Key 的生命周期管理：读取优先级（环境变量 > keyring > yaml）、写入 keyring、删除、显示脱敏
- 模型历史管理：按服务商隔离、最多保留 10 个、最近使用排在首位
- ProviderManager 的服务商元数据加载、白名单过滤与排序、keyring 读写
- 配置验证规则（screenshot_retention_days >= 3、active_screenshot_frequency_level in {1,2,3}）
- config.yaml 与 providers.yaml 的默认值创建

### 范围外

- 路径解析规则（config_base_path / lifeprism_data_path 的解析和计算）— 见 `docs/specs/2026-07-06-config-path-spec.md`
- 配置系统初始化流程 — 见 `docs/flows/2026-07-06-config-initialization-flow.md`
- 数据库 schema 定义 — 见 `docs/technical-debt/config-database-misplacement.md`

## Functional Checklist

> 本模块已实现的功能完整性清单。修改代码后，对照此清单做回归验证，确保已有功能未被破坏。

### 配置读写

- [ ] 配置值通过 `set(key, value)` 写入后，`get(key)` 可以读取到最新值
- [ ] 未显式设置的配置项，`get(key)` 返回 DEFAULTS 中的默认值
- [ ] `get_all()` 返回合并后的完整配置字典（DEFAULTS + yaml + 环境变量覆盖 + keyring 覆盖）
- [ ] `reload()` 重新从磁盘加载 config.yaml，丢弃内存中未保存的修改

### API Key 安全存储

- [ ] `set(key="api_key", value=...)` 将 API Key 写入系统 keyring，不写入 config.yaml
- [ ] `get(key="api_key")` 读取优先级：环境变量 LIFEWATCH_API_KEY > keyring > yaml
- [ ] `get_for_display()` 返回的 api_key 值被脱敏（如 `sk-a...b1c2`），不暴露完整明文
- [ ] `set_api_key(api_key, provider_id)` 按服务商将 API Key 存储到 keyring 的不同 username 下
- [ ] `get_api_key(provider_id)` 先尝试按服务商读取，fallback 到通用 keyring，最后 fallback 到环境变量

### 批量更新与验证

- [ ] `update(updates)` 中若包含 `api_key`，自动分离：api_key 写入 keyring，其余字段写入 yaml
- [ ] `update` 验证 `screenshot_retention_days >= 3`，不满足时抛出 `InvalidConfigError`
- [ ] `update` 验证 `active_screenshot_frequency_level` 取值必须为 1、2 或 3，不满足时抛出 `InvalidConfigError`
- [ ] `update` 更新 `lifeprism_data_path` 后，同步更新环境变量 `LIFEPRISM_DATA_PATH` 和内部路径变量

### 模型历史管理

- [ ] `add_model_to_history(provider_id, model)` 将模型添加到对应服务商的历史列表头部
- [ ] 同一服务商的模型历史最多保留 10 条，超出时移除最早添加的
- [ ] 重复添加同一模型时，该模型被移到列表头部（去重后重新插入）
- [ ] `get_model_history_for_provider(provider_id)` 返回指定服务商的模型名称列表（按最近使用排序）
- [ ] `remove_model_from_history(provider_id, model)` 删除指定模型记录，返回是否成功删除
- [ ] `set_provider_api_base(provider_id, api_base)` 更新服务商的 api_base，不影响已有模型列表
- [ ] 模型历史数据与 api_base 以 `{provider_id: {api_base: '', models: [...]}}` 结构存储在 config.yaml 的 `model_history` 字段中

### Provider 服务商配置

- [ ] `providers.yaml` 文件不存在时，`ProviderManager._initialize()` 自动从 `DEFAULT_PROVIDER_CONFIG` 创建默认配置文件
- [ ] `get_raw_specs()` 返回完整的 provider 原始元数据列表（所有字段）
- [ ] `get_allowed_providers()` 返回白名单中的 provider name 列表（有序）
- [ ] `get_all_providers(allowed_only=True)` 只返回白名单中的 provider，并按 allowed_providers 顺序排序
- [ ] `get_all_providers(allowed_only=False)` 返回所有 provider
- [ ] `get_provider_id(display_name)` 将显示名称（如 "阿里云百炼 (Aliyun)"）正确转换为 provider id（如 "aliyun"）
- [ ] `get_default_model(provider_id)` 返回 provider 的默认模型名，若无则返回空字符串
- [ ] `get_default_api_base(provider_id)` 返回 provider 的默认 API Base，若无则返回空字符串
- [ ] `provider_manager.set_api_key(provider_name, api_key)` 将 API Key 写入 keyring（使用 provider 的 env_key 作为 username）
- [ ] `provider_manager.delete_api_key(provider_name)` 从 keyring 删除 API Key，key 不存在时不抛异常
- [ ] env_key 为空的 provider（如 custom）调用 set_api_key 时仅打 warning 日志，不写入 keyring

## Technical Contract

### SettingsManager

<key_function>
- lifeprism/config/settings_manager.py
  - settings_manager.SettingsManager.get:291
  - settings_manager.SettingsManager.set:439
  - settings_manager.SettingsManager.update:463
  - settings_manager.SettingsManager.reload:524
  - settings_manager.SettingsManager.get_all:528
  - settings_manager.SettingsManager.get_for_display:558
  - settings_manager.SettingsManager.get_api_key:395
  - settings_manager.SettingsManager.set_api_key:424
  - settings_manager.SettingsManager.add_model_to_history:763
  - settings_manager.SettingsManager.remove_model_from_history:794
  - settings_manager.SettingsManager.get_model_history_for_provider:733
  - settings_manager.SettingsManager.get_provider_api_base:746
  - settings_manager.SettingsManager.set_provider_api_base:752
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `get(key, default)` | 获取单个配置值 | 优先级：环境变量 > keyring(仅api_key) > yaml > 默认值 |
| `set(key, value, save=True)` | 设置单个配置值 | api_key 写入 keyring 而非 yaml；save=False 时不持久化 |
| `update(updates, save=True)` | 批量更新配置 | 自动分离 api_key 到 keyring；验证 screenshot_retention_days >= 3、active_screenshot_frequency_level in {1,2,3}；更新 lifeprism_data_path 时同步环境变量 |
| `reload()` | 重新从磁盘加载 config.yaml | 丢弃内存中未保存的修改 |
| `get_all()` | 获取完整配置字典 | 合并 DEFAULTS + yaml + 环境变量覆盖 + keyring api_key |
| `get_for_display()` | 获取用于前端展示的配置 | api_key 中间字符替换为 `...`（长度 > 8 时显示首尾各 4 字符，否则显示 `***`） |
| `get_api_key(provider_id=None)` | 获取 API Key | 优先级：环境变量 > 按服务商 keyring > 通用 keyring |
| `set_api_key(api_key, provider_id=None)` | 设置 API Key | 写入系统 keyring；返回 bool 表示成功与否 |
| `add_model_to_history(provider_id, model, api_base=None)` | 添加模型到历史 | 去重后插入头部；每服务商最多保留 10 条；可选更新 api_base |
| `remove_model_from_history(provider_id, model)` | 从历史删除模型 | 返回 bool 表示是否找到并删除 |
| `get_model_history_for_provider(provider_id)` | 获取服务商模型历史列表 | 返回 `list[str]`，按最近使用排序 |
| `get_provider_api_base(provider_id)` | 获取服务商最近使用的 api_base | 返回 str，无记录时返回 "" |
| `set_provider_api_base(provider_id, api_base)` | 更新服务商的 api_base | 不影响已有模型列表 |

### ProviderManager

<key_function>
- lifeprism/config/provider_manager.py
  - provider_manager.ProviderManager.get_raw_specs:608
  - provider_manager.ProviderManager.get_allowed_providers:612
  - provider_manager.ProviderManager.get_all_providers:657
  - provider_manager.ProviderManager.get_api_key:620
  - provider_manager.ProviderManager.set_api_key:630
  - provider_manager.ProviderManager.delete_api_key:638
  - provider_manager.ProviderManager.get_provider_id:700
  - provider_manager.ProviderManager.get_default_model:707
  - provider_manager.ProviderManager.get_default_api_base:715
  - provider_manager.ProviderManager.get_keyring_username:723
</key_function>

**对外接口**：

| 接口 | 说明 | 约束 |
|------|------|------|
| `get_raw_specs()` | 返回全部 provider 原始 dict 列表 | 供 registry.py 构建 ProviderSpec 使用 |
| `get_allowed_providers()` | 返回白名单 provider name 列表 | 有序，来源于 providers.yaml 的 allowed_providers |
| `get_all_providers(allowed_only=True)` | 返回前端展示用的 provider 列表 | allowed_only=True 时按白名单过滤并排序；返回精简字段（name/display_name/default_model/default_api_base/has_api_key） |
| `get_api_key(provider_name)` | 从 keyring 读取 API Key | env_key 为空时返回 None |
| `set_api_key(provider_name, api_key)` | 写入 API Key 到 keyring | env_key 为空时仅打 warning 日志，不写入 |
| `delete_api_key(provider_name)` | 从 keyring 删除 API Key | key 不存在时不抛异常（suppress PasswordDeleteError） |
| `get_provider_id(provider_name)` | 显示名称转 provider id | 已是 id 则原样返回 |
| `get_default_model(provider_id)` | 获取 provider 默认模型 | 无配置时返回 "" |
| `get_default_api_base(provider_id)` | 获取 provider 默认 API Base | 无配置时返回 "" |
| `get_keyring_username(provider_id)` | 获取 provider 的 keyring username (env_key) | env_key 为空时返回 None |

### 异常定义

<key_function>
- lifeprism/config/exceptions.py
  - exceptions.ConfigError:13
  - exceptions.ConfigFileNotFoundError:19
  - exceptions.InvalidConfigError:31
</key_function>

| 异常类 | 说明 | 字段 |
|--------|------|------|
| `ConfigError` | 配置模块基础异常，继承 LWBaseError | — |
| `ConfigFileNotFoundError` | 配置文件不存在 | config_path, cause |
| `InvalidConfigError` | 配置值无效或格式错误 | key, expected, actual |

### 数据模型

#### config.yaml 核心配置项（DEFAULTS 中定义的关键字段）

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `user_name` | str | `"默认用户"` | 用户名称 |
| `api_key` | str or None | `None` | API Key（优先从 keyring/环境变量读取） |
| `provider` | str | `""` | 当前选择的服务商显示名称 |
| `model` | str | `""` | 当前选择的模型名称 |
| `api_base` | str | `""` | 当前 API Base URL |
| `input_tokens_cost` | float | `0.0` | 输入 tokens 单价 |
| `output_tokens_cost` | float | `0.0` | 输出 tokens 单价 |
| `classification_mode` | str | `"classify_graph"` | 分类模式 |
| `long_log_threshold` | int | `600` | 长日志阈值（秒） |
| `poll_time` | float | `1.0` | 轮询间隔（秒） |
| `afk_timeout` | float | `180.0` | AFK 超时（秒） |
| `scheduled_screenshot_interval_seconds` | int | `60` | 定时截图间隔（秒） |
| `active_screenshot_frequency_level` | int | `2` | 主动截图频率等级（1/2/3） |
| `screenshot_retention_days` | int | `3` | 截图保留天数（最小 3） |
| `monitor_type` | str | `"lifeprism"` | 监控类型 |
| `model_history` | dict | `{}` | 模型历史，结构见下方 |
| `is_vlm` | dict | `{}` | VLM 能力缓存，key=`"provider_id/model_name"` |
| `screen_analysis_ignore` | list | `[]` | 截图分析忽略的分类 ID 列表 |
| `auto_diary_summary` | bool | `True` | 每日自动总结日记 |
| `llm_call_logger_enabled` | bool | `True` | LLM 调用记录器开关 |
| `auto_summary_session` | bool | `True` | 自动总结会话 |
| `auto_update_memory` | bool | `True` | 自动更新记忆 |

**model_history 结构**：

```yaml
# 新结构
model_history:
  aliyun:
    api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
    models:
      - "qwen3.5-plus"
      - "qwen-max"
  openai:
    api_base: ""
    models:
      - "gpt-4o"
```

每个 provider_id 对应的值包含 `api_base`（str）和 `models`（list[str]），models 最多保留 10 条。

#### providers.yaml 中每个 provider 对象的字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | str | provider 唯一标识（id），如 `"dashscope"`、`"openai"` |
| `keywords` | list[str] | 用于自动检测的关键词列表 |
| `env_key` | str | keyring 中存储 API Key 的 username，为空表示不需要 API Key |
| `display_name` | str | 前端展示名称，如 `"DashScope"` |
| `litellm_prefix` | str | LiteLLM 路由前缀 |
| `skip_prefixes` | list[str] | 需要跳过的模型名前缀 |
| `env_extras` | list | 额外的环境变量设置 |
| `is_gateway` | bool | 是否为网关型服务商（聚合多个底层模型） |
| `is_local` | bool | 是否为本地部署服务商 |
| `detect_by_key_prefix` | str | 通过 API Key 前缀自动检测 |
| `detect_by_base_keyword` | str | 通过 API Base 关键词自动检测 |
| `default_api_base` | str | 默认 API Base URL |
| `strip_model_prefix` | bool | 是否剥离模型名前缀 |
| `litellm_kwargs` | dict | 传递给 LiteLLM 的额外参数 |
| `model_overrides` | list | 模型级别的参数覆盖 |
| `is_oauth` | bool | 是否使用 OAuth 认证 |
| `is_direct` | bool | 是否直接调用 |
| `supports_prompt_caching` | bool | 是否支持 prompt caching |
| `default_model` | str | 默认模型名 |

#### providers.yaml 顶层结构

```yaml
allowed_providers:  # list[str] — 白名单，决定 provider 可用性和前端展示顺序
  - "custom"
  - "dashscope"
  - "deepseek"
  # ...
providers:  # list[dict] — 全部 provider 元数据
  - name: "dashscope"
    display_name: "DashScope"
    # ...
```

### Provider 双层命名体系（display_name ↔ name）

Provider 系统使用两层命名来区分"用户可见名称"和"系统内部标识符"。**任何跨越这两层命名的代码边界（如 cloud_init 生成/消费、配置验证）都必须显式转换。**

#### 两层命名的定义

| 维度 | `name`（内部标识符） | `display_name`（显示名称） |
|------|---------------------|--------------------------|
| **格式** | 全小写 + 下划线，如 `"xiaomi_mimo"` | 含大小写、空格，如 `"Xiaomi MIMO"` |
| **存储位置** | `providers.yaml` 的 `providers[].name` | `config.yaml` 的 `provider` 字段 |
| **用途** | keyring username（env_key）、ProviderSpec 匹配、model_history key、is_vlm key | 前端下拉框选项、用户配置文件 |
| **消费方** | `get_api_key(name)`、`find_by_name(name)`、`get_provider_id(display_name)` | `settings.get("provider")` |

#### 转换方法

| 方法 | 方向 | 行为 |
|------|------|------|
| `provider_manager.get_provider_id(provider_name)` | display_name → name | 遍历 raw_specs 按 display_name 匹配返回 name；已是 name 则原样返回 |
| `provider_manager.name_to_id_map` | display_name → name | 返回 `{display_name: name}` 映射字典（仅含 display_name 非空的 provider） |

#### config.yaml 的 provider 字段契约

**`config.yaml` 的 `provider` 字段存储的是 display_name**（如 `"Xiaomi MIMO"`），原因：
1. 该字段由前端下拉框 `provider_list`（返回 display_name 列表）写入
2. 所有后端消费 `settings.provider` 的代码都先调用 `get_provider_id()` 转为内部 name

**消费方期望（所有位置都必须先转换）**：

| 消费位置 | 传入 | 转换方式 |
|----------|------|----------|
| `build_llm_client.py:create_llm_client()` | `settings.provider` | `provider_manager.get_provider_id(settings.provider)` |
| `setting_service.py:save_api_key()` | 前端传来的 provider | `provider_manager.get_provider_id(provider)` |
| `main_agent_only.py:cmd_show_config()` | `settings.provider` | `provider_manager.get_provider_id(provider)` |
| `settings_manager.py:is_visual()` | `settings.provider` | `_get_provider_id_from_name()`（仅接受 display_name） |

#### cloud_init.yaml 边界注意事项

`cloud_init.yaml` 是 display_name 和 name 共存的典型边界：

```yaml
llm:
  provider: "Xiaomi MIMO"    # ← display_name，来自 settings.get("provider")
providers:
  - name: xiaomi_mimo        # ← 内部 name，来自 provider spec
```

- `CloudInitializer._validate()` 匹配 provider 时，必须通过 `get_provider_id()` 将 display_name 转为内部 name 后再匹配 `providers[].name`
- 历史 bug：验证时直接用 `p.get("name") == provider` 做精确字符串匹配，导致 `"Xiaomi MIMO" != "xiaomi_mimo"` 失败 → 见 `docs/history-bugs/2026-07-11-cloud-init-provider-display-name-mismatch.md`

### 配置优先级状态机

```
读取单个配置值 get(key):

┌──────────────────────────────────────────────┐
│ 1. key 在 ENV_VAR_MAPPING 中？                │
│    YES → 环境变量有值？ → 返回环境变量值        │
│    NO  → 继续                                 │
└────────────────┬─────────────────────────────┘
                 ▼
┌──────────────────────────────────────────────┐
│ 2. key == "api_key"？                        │
│    YES → keyring 有值？ → 返回 keyring 值     │
│    NO  → 继续                                 │
└────────────────┬─────────────────────────────┘
                 ▼
┌──────────────────────────────────────────────┐
│ 3. key 在 yaml 配置中存在且非 None？           │
│    YES → 返回 yaml 值                         │
│    NO  → 继续                                 │
└────────────────┬─────────────────────────────┘
                 ▼
┌──────────────────────────────────────────────┐
│ 4. 返回 default 参数（若提供）或 DEFAULTS 值   │
└──────────────────────────────────────────────┘
```

**API Key 特殊优先级**（`get_api_key(provider_id)`）：

```
环境变量 LIFEWATCH_API_KEY
    → 按服务商 keyring（username = provider.env_key）
        → 通用 keyring（username = "api_key"，向后兼容）
```

### 导出清单

模块通过 `lifeprism/config/__init__.py` 对外导出以下符号：

| 符号 | 类型 | 说明 |
|------|------|------|
| `settings` | SettingsManager 实例 | 全局单例，用户配置读写入口 |
| `provider_manager` | ProviderManager 实例 | 全局单例，服务商配置读写入口 |
| `SettingsManager` | 类 | 供类型标注使用 |
| `ProviderManager` | 类 | 供类型标注使用 |
| `get_setting(key, default)` | 便捷函数 | 等价于 `settings.get(key, default)` |
| `set_setting(key, value)` | 便捷函数 | 等价于 `settings.set(key, value)` |
| `get_api_key()` | 便捷函数 | 等价于 `settings.api_key` |
| `get_all_settings()` | 便捷函数 | 等价于 `settings.get_all()` |
| `ALLOWED_DIRS` | 常量 | `["user", "diary", "agent"]` |

## Design Rationale

**为什么 api_key 存 keyring 不存 yaml？**
- yaml 文件可能被误提交到版本控制，或在日志/错误报告中泄漏
- 系统 keyring（Windows Credential Manager / macOS Keychain / Linux Secret Service）是操作系统级的安全存储，应用间隔离
- `set("api_key", value)` 自动路由到 keyring，对调用方透明

**为什么 ProviderManager 和 SettingsManager 分开？**
- 职责单一：SettingsManager 管用户配置，ProviderManager 管服务商元数据
- 依赖方向单向：ProviderManager 依赖 SettingsManager（读取 config_base_path），SettingsManager 依赖 ProviderManager（name_to_id_map 做显示名转换）。两者通过延迟导入避免循环依赖
- 各自可独立测试和演进

**为什么 DEFAULT_PROVIDER_CONFIG 硬编码在 provider_manager.py？**
- 启动兜底：当 providers.yaml 文件丢失或损坏时，系统仍能提供基础的服务商列表
- 无需外部文件：避免因缺少配置文件导致整个配置系统不可用
- 该数据是应用级的「内置知识」，不是用户数据，适合放在代码中

**为什么模型历史限制 10 条？**
- 防止 model_history 无限增长导致 config.yaml 膨胀
- 10 条对绝大多数用户足够覆盖常用模型
- 最近使用排在最前，配合前端下拉框实现便捷选择

**有哪些约束？**
- SettingsManager 和 ProviderManager 均为模块级单例，构造时即完成初始化（`__new__` 中调用 `_initialize`）
- 模块导入顺序敏感：`main.py` 必须首先导入 `settings_manager`，确保日志文件输出在其余模块加载前完成配置
- keyring 读写可能因操作系统限制而失败（如 headless 环境），此时仅打 warning 不阻塞启动

**有哪些已知限制？**
- 当前 API Key 向后兼容的通用 keyring（username=`"api_key"`）与新按服务商的 keyring 并存，存在冗余存储的可能
- Environment variable mapping 目前仅覆盖 `api_key`，其他配置项不支持环境变量覆盖
- ProviderManager 的 `get_api_key` 使用 `provider_name`（即 name/id）而非 display_name，与 `get_provider_id` 的参数命名不一致，调用方需注意

## Out of Scope

本 spec 不覆盖以下内容，请参考相应文档：

- **路径体系与解析规则**：[`docs/specs/2026-07-06-config-path-spec.md`](./2026-07-06-config-path-spec.md) — config_base_path / lifeprism_data_path 的解析规则、派生路径、安全检查
- **配置初始化流程**：[`docs/flows/2026-07-06-config-initialization-flow.md`](../flows/2026-07-06-config-initialization-flow.md) — SettingsManager + ProviderManager 启动全链路
- **数据库 schema**：[`docs/technical-debt/config-database-misplacement.md`](../technical-debt/config-database-misplacement.md) — 数据库表结构和字段定义
