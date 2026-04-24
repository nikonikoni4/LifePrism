---
version: 1.1
created_at: 2026-04-20
updated_at: 2026-04-20
last_updated: 新增打包环境前后端路径配置详细流程图和已知问题说明
abstract: 配置管理模块规格，定义配置的读写流程、路径解析规则（含前后端详细流程图）、API Key 安全存储、Provider 管理、配置迁移机制及前后端交互契约
id: config-spec
title: 配置管理模块规格
status: draft
module: config
sourc_spec: 基于代码实现和 memory 记录整理
related_plan: N/A
code_scope:
  - lifeprism/config/settings_manager.py
  - lifeprism/config/provider_manager.py
  - lifeprism/server/api/setting_api.py
  - lifeprism/server/services/setting_service.py
  - frontend/apps/settings/SettingsApp.tsx
  - frontend/electron/main.cjs
contract_refs:
  - lifeprism/server/schemas/setting_schemas.py
  - lifeprism/config/settings.yaml
  - lifeprism/config/providers.yaml
---

# 配置管理模块规格

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建 config 模块规格初稿 |
| 1.1 | 新增打包环境前后端路径配置详细流程图，明确前端路径配置的已知问题 |

## Overview

配置管理模块负责 LifePrism 系统的全局配置读写、路径解析、API Key 安全存储、LLM Provider 管理和配置迁移。

核心职责：
1. **配置读写**：从 YAML 文件加载配置，支持环境变量覆盖和 keyring 安全存储
2. **路径管理**：区分配置路径（固定）和数据路径（可迁移），支持开发/打包环境差异
3. **Provider 管理**：管理多个 LLM 服务商的配置、API Key、模型历史
4. **配置迁移**：支持数据路径迁移和配置版本升级
5. **前后端交互**：通过 REST API 提供配置的 CRUD 操作

## Scope

**包含**：
- 配置文件的加载、保存、版本迁移
- 配置路径（config_base_path）和数据路径（lifeprism_data_path）的解析规则
- API Key 的 keyring 存储和读取优先级
- Provider 配置的加载、白名单过滤、默认值管理
- 模型历史记录的增删改查
- 配置相关的 REST API 端点
- VLM 能力测试和缓存

**不包含**：
- 具体的 LLM 调用逻辑（属于 llm 模块）
- 数据库连接管理（属于 repository 模块）
- 日志配置的详细实现（属于 utils 模块）

## Core Behavior

### 1. 配置加载优先级

配置值的读取遵循以下优先级（从高到低）：
1. **环境变量**（如 `LIFEWATCH_API_KEY`）
2. **系统密钥管理器 keyring**（仅 API Key）
3. **YAML 配置文件**（config.yaml，开发和打包环境统一使用此命名）
4. **默认值**（SettingsManager.DEFAULTS）

### 2. 路径解析规则

系统区分两类路径：

**配置路径（config_base_path）**：
- 固定位置，不随数据迁移
- 打包环境：`%LOCALAPPDATA%/LifePrism/lifeprismData`
- 开发环境：`localData`
- 配置文件路径：
  - 主配置：`{config_base_path}/config/config.yaml`
  - Provider 配置：`{config_base_path}/config/providers.yaml`
  - 端口配置：`{config_base_path}/config/config.json`

**数据路径（lifeprism_data_path）**：
- 可由用户迁移
- 前端优先级：yaml 配置 > 默认路径
- 后端优先级：yaml 配置 > 环境变量 > 默认路径
- 默认路径：与 config_base_path 相同（用户未主动迁移时）
- 存储内容：`dataset/`, `plan/`, `debug_logs/`, `workflow/`, `external_files/`, `screenshots/`, `docs/`, `diary/`, `session/`, 数据库文件

**关键规则**：
1. **前端必须读取 yaml 配置**：不能硬编码路径，必须从 `{config_base_path}/config/config.yaml` 读取 `lifeprism_data_path`
2. **前后端日志路径统一**：都写入 `{lifeprism_data_path}/debug_logs/`，迁移后自动跟随
3. **环境变量作为后端 fallback**：前端传递的 `LIFEPRISM_DATA_PATH` 仅作为后端的第二优先级

详细的路径配置流程和实现细节见 [路径配置体系](../authority/path-config.md)。

### 3. Provider 管理

**Provider 配置结构**：
- `providers.yaml` 包含 `allowed_providers`（白名单）和 `providers`（完整列表）
- 每个 provider 包含：name, display_name, env_key, default_model, default_api_base, litellm_prefix 等
- 支持 OAuth provider（如 github_copilot）和本地 provider（如 ollama）

**API Key 存储**：
- 每个 provider 有独立的 env_key（如 `api_key_volcengine`）
- 通过 keyring 安全存储，服务名为 `lifeprism`
- 向后兼容：支持通用 API Key 存储

### 4. 模型历史管理

**数据结构**：
```yaml
model_history:
  provider_id:
    api_base: "https://..."
    models: ["model1", "model2"]
```

**行为**：
- 切换模型时自动记录到对应 provider 的历史
- 前端下拉菜单显示历史模型
- 支持删除历史记录

### 5. VLM 能力缓存

**目的**：判断模型是否支持图片理解（Vision Language Model）

**缓存结构**：
```yaml
is_vlm:
  "provider_id/model_name": true/false
```

**校验规则**：
- 开启 `screenshot_monitor` 时，必须确保当前模型的 `is_vlm` 为 `true`
- 若缓存中不存在或为 `false`，返回 `require_vlm_test=true`，前端需调用 `/settings/test-vlm`

### 6. 配置迁移

**数据路径迁移**：
- 仅打包环境可用（开发环境禁止）
- 复制 `lifeprismData/` 下所有内容到新路径
- 更新 `{config_base_path}/config/config.yaml` 中的 `lifeprism_data_path`
- 迁移后需重启程序

**配置版本迁移**：
- 通过配置迁移机制自动检测版本并应用增量迁移
- 迁移前自动备份原配置文件
- 支持配置结构的向后兼容

## Technical Contract

### API 端点

#### GET /settings
获取当前配置（API Key 脱敏）

**Response**:
```json
{
  "settings": {
    "user_name": "string",
    "provider": "string",
    "model": "string",
    "api_base": "string",
    "api_key": "sk-ab...xy",
    "classification_mode": "classify_graph" | "classify_simple",
    "lifeprism_data_path": "string",
    "config_base_path": "string",
    "model_history": {
      "provider_id": {
        "api_base": "string",
        "models": ["string"]
      }
    },
    "is_vlm": {
      "provider_id/model": boolean
    },
    "screenshot_monitor": boolean,
    "provider_list": ["string"],
    "provider_id_map": {"display_name": "provider_id"}
  }
}
```

#### PATCH /settings
部分更新配置（不包含 API Key）

**Request**:
```json
{
  "user_name": "string",
  "provider": "string",
  "model": "string",
  "api_base": "string",
  "classification_mode": "classify_graph" | "classify_simple",
  "screenshot_monitor": boolean
}
```

**Response**:
```json
{
  "settings": {...},
  "message": "string",
  "require_vlm_test": boolean  // 仅当 screenshot_monitor=true 且 VLM 校验失败时返回
}
```

#### PUT /settings/api-key
更新 API Key（存储到 keyring）

**Request**:
```json
{
  "api_key": "string",
  "provider_id": "string"  // 可选，指定服务商
}
```

#### GET /settings/providers
获取所有支持的服务商列表

**Response**:
```json
{
  "providers": [
    {
      "name": "string",
      "display_name": "string",
      "default_model": "string",
      "default_api_base": "string",
      "has_api_key": boolean
    }
  ]
}
```

#### POST /settings/test-connection
测试 LLM 连接

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "model_response": "string"
}
```

#### POST /settings/test-vlm
测试 VLM 图像理解能力

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "is_vlm": boolean,
  "model_response": "string",
  "cache_updated": boolean
}
```

#### POST /settings/validate-path
验证数据路径有效性

**Request**:
```json
{
  "path": "string",
  "path_type": "lifeprism_data" | "aw_db"
}
```

**Response**:
```json
{
  "valid": boolean,
  "message": "string",
  "warnings": ["string"]
}
```

#### POST /settings/migrate-data-path
迁移数据路径

**Request**:
```json
{
  "target_base_path": "string",
  "migrate_data": boolean
}
```

**Response**:
```json
{
  "success": boolean,
  "message": "string",
  "new_path": "string"
}
```

#### DELETE /settings/model-history
删除模型历史记录

**Query Parameters**:
- `provider_id`: string
- `model`: string

### 配置文件结构

#### config.yaml
```yaml
config_version: 3
user_name: string
provider: string
model: string
api_base: string
api_key: null  # 不推荐存储，应使用 keyring
classification_mode: classify_graph | classify_simple
lifeprism_data_path: string
aw_db_path: string
model_history:
  provider_id:
    api_base: string
    models: [string]
is_vlm:
  "provider_id/model": boolean
screenshot_monitor: boolean
```

#### providers.yaml
```yaml
allowed_providers: [string]
providers:
  - name: string
    display_name: string
    env_key: string
    default_model: string
    default_api_base: string
    litellm_prefix: string
    is_gateway: boolean
    is_local: boolean
    is_oauth: boolean
    supports_prompt_caching: boolean
```

### 关键类和方法

#### SettingsManager (单例)
- `get(key, default)`: 按优先级读取配置
- `set(key, value)`: 写入配置到 yaml
- `update(updates)`: 批量更新配置
- `get_api_key(provider_id)`: 从 keyring 读取 API Key
- `set_api_key(api_key, provider_id)`: 写入 API Key 到 keyring
- `add_model_to_history(provider_id, model, api_base)`: 添加模型到历史
- `config_base_path`: 配置文件基础路径（只读）
- `lifeprism_data_path`: 数据路径（可迁移）

#### ProviderManager (单例)
- `get_raw_specs()`: 返回所有 provider 的原始配置
- `get_allowed_providers()`: 返回白名单 provider 列表
- `get_api_key(provider_name)`: 从 keyring 读取 provider 的 API Key
- `set_api_key(provider_name, api_key)`: 写入 provider 的 API Key
- `get_all_providers(allowed_only)`: 返回 provider 展示信息
- `get_provider_id(provider_name)`: 显示名称转 ID

## Interaction / UX Notes

### 前端配置流程

1. **初始加载**：
   - 调用 `GET /settings` 获取完整配置
   - 调用 `GET /settings/providers` 获取服务商列表
   - 根据当前 provider 回填 api_base 和模型历史

2. **切换 Provider**：
   - 从 `provider_id_map` 转换显示名称为 ID
   - 从 `providerDefaults` 获取默认 api_base 和 default_model
   - 从 `model_history[provider_id]` 获取历史模型列表

3. **保存配置**：
   - API Key 单独调用 `PUT /settings/api-key`
   - 其他配置调用 `PATCH /settings`
   - 防抖保存（500ms）

4. **开启截图监控**：
   - 若返回 `require_vlm_test=true`，弹窗提示用户测试 VLM
   - 调用 `POST /settings/test-vlm`
   - 测试通过后重新调用 `PATCH /settings`

5. **数据路径迁移**：
   - 仅打包环境显示迁移按钮
   - 调用 `POST /settings/validate-path` 验证路径
   - 确认后调用 `POST /settings/migrate-data-path`
   - 迁移成功后提示重启

## Acceptance Notes

1. **配置读取优先级正确**：环境变量 > keyring > yaml > 默认值
2. **路径解析正确**：config_base_path 固定，lifeprism_data_path 可迁移
3. **API Key 安全存储**：不在 yaml 中明文存储，使用 keyring
4. **Provider 白名单生效**：只返回 allowed_providers 中的服务商
5. **模型历史自动记录**：切换模型时自动添加到历史
6. **VLM 校验生效**：开启截图监控时强制校验 is_vlm
7. **配置迁移成功**：旧版本配置自动升级到新版本
8. **数据路径迁移成功**：数据完整复制，配置正确更新
9. **前端配置同步**：修改配置后立即生效，无需重启（除数据路径迁移）

## Out of Spec

以下内容不在本 spec 范围内：

1. **LLM 调用实现**：具体的 litellm 调用逻辑、重试机制、流式输出
2. **数据库配置**：数据库连接池、迁移脚本、备份策略
3. **日志配置**：日志级别、日志轮转、日志格式
4. **Electron IPC**：前端与 Electron 主进程的通信细节
5. **配置 UI 设计**：具体的表单布局、样式、动画效果
6. **配置校验规则**：字段的详细校验逻辑（如路径格式、API Key 格式）
