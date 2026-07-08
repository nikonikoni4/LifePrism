# 配置生成器 - 后端逻辑

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现云端配置生成的后端逻辑，从 keyring 读取所有 Key 并生成完整的 `cloud_init.yaml`。

**实现端到端**：
1. 新增 `lifeprism/config/cloud_config_generator.py`
2. 实现 `CloudConfigGenerator` 类：
   - `generate_cloud_config()` - 生成完整配置
   - **生成或读取同步 API Key**：
     - 先尝试从 keyring 读取 `sync_api_key`
     - 如果不存在，生成新的（`secrets.token_urlsafe(32)`）并保存到 keyring
     - 返回 `key_is_new: bool`（告诉前端是否是新生成的）
   - 从 keyring 读取所有 LLM Provider 的 API Key：
     - 从 `providers.yaml` 遍历所有 provider.name
     - 对每个 provider 调用 `provider_manager.get_api_key(provider_name)`
   - 从 keyring 读取微信 Token（通过 `WechatAuth._load_token_from_keyring()`）
   - 生成包含 Key 的完整配置（config.yaml 和 providers.yaml）
   - 保存到 `{lifeprism_data_path}/cloud_init.yaml`
3. 新增 API 端点：`POST /api/sync/generate-cloud-config`
   - 返回：`{cloud_config_path, key_is_new}`
4. 单元测试（读取 keyring、生成完整配置、保存文件、Key 生成逻辑）

---

## Acceptance criteria

- [ ] `CloudConfigGenerator` 类已实现
- [ ] 同步 API Key 生成逻辑正确：
  - 优先从 keyring 读取已有 Key
  - 如果不存在，生成新 Key（32 字节随机）并保存到 keyring
  - 返回 `key_is_new: bool` 标志
- [ ] 能从 keyring 读取所有 LLM Provider 的 API Key（遍历 `providers.yaml`）
- [ ] 能从 keyring 读取微信 Token
- [ ] 生成的 `cloud_init.yaml` 包含完整配置和所有 Key
- [ ] 强制覆盖 `monitor_type: none`（云端必须禁用 Monitor）
- [ ] 文件保存到 `{lifeprism_data_path}/cloud_init.yaml`
- [ ] API 端点 `POST /api/sync/generate-cloud-config` 返回 `{cloud_config_path, key_is_new}`
- [ ] 单元测试通过：
  - 测试从 keyring 读取已有 Key（key_is_new = false）
  - 测试 keyring 无 Key 时生成新 Key（key_is_new = true）
  - 测试生成完整配置（包含所有 Provider）
  - 测试 `monitor_type` 强制覆盖
  - 测试文件保存路径

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/02-key-fallback-mechanism.md`
