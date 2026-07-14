# Key 消费方迁移到 SettingsManager 路由

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - API Key 存储

## What to build

将三个 Key 消费方统一走 SettingsManager 的 run_mode 路由，替代各自直接调用 keyring 或 config.yaml 的逻辑。

**ADR 参考**：`docs/adr/2026-07-09-key-fallback-strategy.md` v1.1 读取/写入层级

**需要修改的 3 个消费方**：

1. **同步 API Key**：`sync/sync_config.py`
   - `get_sync_api_key()` → 调用 `settings.get_storage_key("sync_api_key")`
   - `set_sync_api_key()` → 调用 `settings.set_storage_key("sync_api_key", value)`
   - SettingsManager 内部根据 run_mode 路由：本地读 keyring，云端读 storage.yaml

2. **微信 Token**：`llm/channel/wechat/auth.py`
   - `_load_token_from_keyring()` → 调用 `settings.get_storage_key("wechat_token")`
   - 写入 token 的方法 → 调用 `settings.set_storage_key("wechat_token", value)`

3. **LLM Provider API Key**：`config/provider_manager.py`
   - `get_api_key()` → 调用 `settings.get_storage_key(f"providers.{provider_id}")`
   - 云端再加一层 providers.yaml 兜底（已有逻辑保留）
   - `set_api_key()` → 调用 `settings.set_storage_key(f"providers.{provider_id}", value)`

**关键约束**：消费方代码不感知 run_mode，不直接调用 keyring，不直接读 storage.yaml——全部通过 SettingsManager 的 `get_storage_key()` / `set_storage_key()` 接口。`provider_manager.get_keyring_username()` 仅用于本地 keyring username 映射，云端模式下 SettingsManager 内部不调用此方法（直接走 storage.yaml 路由）。

**替代 issue 02**：原 issue 02（Key 读取 Fallback 机制）实现的是 keyring → config.yaml fallback，现被 storage.yaml 分离架构替代。

**CloudConfigGenerator 调用链不受影响**：`cloud_config_generator.py` 的 `_resolve_sync_api_key()` 调用 `get_sync_api_key()` / `set_sync_api_key()`，改造后自动走 SettingsManager 路由（本地模式读 keyring），无需额外改造 CloudConfigGenerator 本身。

## Acceptance criteria

- [ ] `sync_config.py:get_sync_api_key()` 改为调用 `settings.get_storage_key("sync_api_key")`
- [ ] `sync_config.py:set_sync_api_key()` 改为调用 `settings.set_storage_key("sync_api_key", value)`
- [ ] `wechat/auth.py` token 读写改为调用 `settings.get_storage_key/set_storage_key("wechat_token")`
- [ ] `provider_manager.py:get_api_key()` 改为调用 `settings.get_storage_key(f"providers.{provider_id}")`
- [ ] 消费方代码中不再直接调用 `keyring.get_password()` / `keyring.set_password()`
- [ ] 消费方代码中不再直接读 config.yaml 的 Key 字段
- [ ] 单元测试：本地模式通过 SettingsManager 读取 keyring 中的 Key
- [ ] 单元测试：云端模式通过 SettingsManager 读取 storage.yaml 中的 Key
- [ ] 单元测试：Key 不存在时返回 None（不报错）
- [ ] 单元测试：多 provider 场景（anthropic + deepseek 同时存在，各自独立返回）
- [ ] 单元测试：云端模式 providers.yaml 兜底（storage.yaml 无此 provider → 查 providers.yaml）

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/26-storage-yaml-settings-manager.md` - storage.yaml 基础设施必须先就绪
