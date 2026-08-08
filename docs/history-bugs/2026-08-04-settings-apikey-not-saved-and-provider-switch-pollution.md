---
version: 1.0
created_at: 2026-08-04
updated_at: 2026-08-04
last_updated: 创建文档，记录 custom provider api_key 无法保存 + 切换 provider 时脱敏值被误保存的 4 个关联 bug
abstract: 设置界面 API Key 管理存在 4 个关联 bug，导致 custom provider 永远无法使用、切换 provider 时各 provider 的 api_key 互相污染为脱敏值。
---

# 设置界面 API Key 保存失效与 provider 切换污染

## Bug简述

设置界面存在 4 个关联 bug，共同导致：(1) Custom(OpenAI SDK) provider 的 api_key 永远无法保存到 keyring，模型无法使用；(2) 切换 provider 时旧 provider 的脱敏 api_key（如 `sk-c...6yom`）被误保存到新 provider，导致多个 provider 的 key 互相污染。

## 复用场景

- 后端脱敏格式与前端脱敏检测不一致的同类问题（脱敏值被当作真实值回写）
- 配置项 `env_key` 为空导致 keyring 写入被静默跳过的设计缺陷
- Service 层调用底层 set 方法但不检查返回值，导致日志误导排查
- 前端切换配置项时未刷新关联输入框 state，残留旧值触发自动保存
- 任何"前端显示值 + 后端脱敏值 + 自动保存"三者组合的输入框

## 代码位置

| Bug | 位置 | 说明 |
|-----|------|------|
| A | `frontend/apps/settings/SettingsApp.tsx:569-585`（`handleApiKeyBlur`） | 前端掩码检测用 `*` 但后端脱敏用 `...` |
| B | `frontend/apps/settings/SettingsApp.tsx:473-514`（`handleProviderChange`） | 切换 provider 时未刷新 `apiKey` state |
| C | `lifeprism/config/provider_manager.py:38-58`（`DEFAULT_PROVIDER_CONFIG` 中 custom） | `env_key: ""` 为空，keyring 无 username 可用 |
| C | `lifeprism/config/settings_manager.py:659-672`（`_set_api_key_to_keyring_by_provider`） | `username=None` 时直接 `return False` 跳过写入 |
| C | `lifeprism/config/provider_manager.py:618-641`（`get_api_key`） | `env_key` 为空时直接 `return None` |
| D | `lifeprism/server/services/setting_service.py:119-159`（`update_api_key`） | 未检查 `set_api_key` 返回值，失败仍打印"已安全保存" |

## 发生原因

### Bug A：前端掩码检测字符与后端脱敏格式不一致

后端 `settings_manager.py:910-914` 的脱敏格式有两种：

```python
if len(api_key) > 8:
    config["api_key"] = f"{api_key[:4]}...{api_key[-4:]}"  # 如 sk-c...6yom
else:
    config["api_key"] = "***"
```

但前端 `handleApiKeyBlur` 只检测 `*`：

```javascript
if (apiKey && !apiKey.includes('*') && apiKey.length > 0) {
    // 保存
}
```

脱敏值 `sk-c...6yom` 不含 `*`，条件 `!apiKey.includes('*')` 永远为 true，脱敏值被当作"新 key"保存。

### Bug B：切换 provider 时未刷新 apiKey state

`handleProviderChange` 切换 provider 时更新了 `provider`/`modelName`/`apiBase`，但**没有更新 `apiKey`**，输入框仍显示上一个 provider 的脱敏值。结合 Bug A，一旦触发 `onBlur`，旧 provider 的脱敏值就被保存到新 provider。

实际日志证据（`D:\数据文档\lifeprismData\debug_logs\lifeprism.log`）：

```
09:42:32 正在更新 volcengine 的 API Key...  ← 保存了 dashscope 的脱敏值 sk-c...6yom
09:47:06 正在更新 dashscope 的 API Key...   ← 又被 volcengine 的脱敏值覆盖
```

`cloud_init.yaml` 中 `volcengine`、`volcengine_coding_plan`、`dashscope` 三个 provider 的 api_key 全部是 `sk-c...6yom`，互相污染。

### Bug C：custom provider 的 env_key 为空，api_key 无法保存

`DEFAULT_PROVIDER_CONFIG` 中 custom provider 的 `env_key: ""`（其他 provider 如 dashscope 是 `"api_key_dashscope"`）。`env_key` 作为 keyring 的 username，为空时：

- 保存链路：`_set_api_key_to_keyring_by_provider` 中 `username = provider_manager.get_keyring_username("custom")` 返回 `None`，`if username:` 为 false，直接 `return False`，keyring 写入被跳过
- 读取链路：`get_api_key("custom")` 中 `env_key = self._get_env_key("custom")` 返回 `""`，`if not env_key: return None` 直接返回 None
- 调用 LLM 时：`build_llm_client.py:29` 中 `api_key=provider_manager.get_api_key(provider) or "no-key"`，custom 得到 `"no-key"`，调用 API 报 "API key format is incorrect"

### Bug D：update_api_key 未检查返回值，日志误导

`setting_service.update_api_key` 调用 `settings.set_api_key(api_key, actual_provider_id)` 后**没有检查返回值**，无论成功失败都打印：

```python
settings.set_api_key(api_key, actual_provider_id)  # 返回 False
logger.info("%s 的 API Key 已安全保存到系统密钥管理器", actual_provider_id)  # 日志在撒谎
```

用户看到日志显示"保存成功"但实际未保存，严重误导排查。

## 最佳方案

### Bug C 修复：给 custom provider 补充 env_key

1. 修改 `DEFAULT_PROVIDER_CONFIG` 中 custom 的 `env_key` 从 `""` 改为 `"api_key_custom"`，使新安装的用户直接正确
2. 新增迁移脚本 `p003_add_custom_env_key.py`，将现有 providers.yaml 中 custom 的 `env_key` 补为 `"api_key_custom"`，`config_version` 2→3

```python
# lifeprism/config/migrations/scripts/p003_add_custom_env_key.py
def upgrade(data: dict) -> dict:
    providers = data.get("providers", [])
    for p in providers:
        if p.get("name") == "custom":
            p["env_key"] = "api_key_custom"
            break
    data["providers"] = providers
    data["config_version"] = 3
    return data
```

### Bug D 修复：检查返回值并抛异常

`setting_service.update_api_key` 提前校验 `env_key`，并检查 `set_api_key` 返回值，失败时抛 `ValueError`（API 层已有 `ValueError → HTTP 400` 转换）：

```python
env_key = provider_manager.get_keyring_username(actual_provider_id)
if not env_key:
    raise ValueError(f"Provider '{actual_provider_id}' 的 env_key 未配置，无法保存 API Key")
success = settings.set_api_key(api_key, actual_provider_id)
if not success:
    raise ValueError(f"Provider '{actual_provider_id}' 的 API Key 保存失败（keyring 写入错误）")
```

### Bug A 修复：前端掩码检测匹配后端脱敏格式

```javascript
const isMasked = apiKey === '***' || (apiKey.length > 0 && apiKey.includes('...'));
if (apiKey && !isMasked && apiKey.length > 0) {
    // 保存
}
```

### Bug B 修复：切换 provider 时立即保存并从后端加载新 provider 的脱敏 api_key

```javascript
const handleProviderChange = async (newProvider: string) => {
    // ... setProvider/setModelName/setApiBase ...
    // 立即保存（非防抖），确保后端 provider 已切换后再读取 api_key
    await immediateSave({ provider: newProvider, model: nextModel, api_base: nextApiBase });
    // 从后端加载新 provider 的脱敏 api_key
    const settings = await SettingsAPI.getSettings();
    setApiKey(settings.api_key || '');
};
```

## 验证

- 复现测试：`test/core/unit/config/test_custom_provider_apikey_bug.py`（12 个测试，覆盖 Bug C/D）
  - `TestCustomProviderEnvKey`：验证 custom 的 env_key 已正确配置，set/get 往返正常
  - `TestP003Migration`：验证迁移脚本的 check_if_applied / upgrade / 幂等性 / 不影响其他 provider
  - `TestUpdateApiKeyValidation`：验证 env_key 为空或 set_api_key 失败时抛 ValueError
- 回归测试：`test/core/unit/config/` 其他 305 个测试全部通过，无破坏
- 前端 TypeScript：`tsc --noEmit` 无 settings 相关错误（其他 8 个错误为已存在的历史问题）

## 风险与遗留

1. **历史脏数据需手动清理**：p003 迁移脚本只修复 providers.yaml 中的 `env_key` 配置，但**之前被错误保存为脱敏值 `sk-c...6yom` 的 volcengine/dashscope 等 provider 的 api_key 仍存在 keyring 中**，需要用户在设置界面重新输入真实 api_key
2. **Bug A 边界**：`includes('...')` 检测理论上可能误判真实 api_key 中包含 `...` 的情况（极罕见），如担心可改为正则 `/^.{4}\.{3}.{4}$/` 精确匹配
3. **Bug B 网络异常**：`immediateSave` 失败时静默处理，`getSettings` 仍会执行，最坏情况 apiKey 输入框显示为空

## 相关文档

- Spec：`docs/specs/2026-07-06-config-settings-spec.md`
- 迁移脚本注册表：`lifeprism/config/migrations/scripts/__init__.py`
- Provider 配置：`lifeprism/config/provider_manager.py` `DEFAULT_PROVIDER_CONFIG`
