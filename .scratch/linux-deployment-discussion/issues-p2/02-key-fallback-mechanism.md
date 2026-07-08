# Key 读取 Fallback 机制

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现统一的 Key 读取逻辑：优先从 keyring 读取（本地 Windows），fallback 到 config.yaml（云端 Linux）。

**需要修改的 3 个地方**：

1. **LLM Provider API Key**：`provider_manager.py::get_api_key()`
   - 优先从 keyring 读取
   - Fallback：从 `providers.yaml` 的对应 provider 中读取 `api_key` 字段（新增字段）

2. **微信 Token**：`llm/channel/wechat/auth.py::_load_token_from_keyring()`
   - 优先从 keyring 读取
   - Fallback：从 `config.yaml` 读取 `wechat_token` 字段（新增字段）

3. **同步 API Key**：新增 `sync/sync_config.py`
   - `get_sync_api_key()` 函数
   - 优先从 keyring 读取（`sync_api_key`）
   - Fallback：从 `config.yaml` 读取 `sync_api_key` 字段（新增字段）

**代码修改点集中在数据返回层，其他代码零感知云端/本地差异。**

---

## Acceptance criteria

- [ ] `provider_manager.get_api_key()` 增加 config fallback 逻辑（约 +10 行）
- [ ] `WechatAuth._load_token_from_keyring()` 增加 config fallback 逻辑（约 +8 行）
- [ ] 新增 `sync/sync_config.py`，实现 `get_sync_api_key()` 和 `set_sync_api_key()`（约 +20 行）
- [ ] 单元测试通过：
  - 测试优先从 keyring 读取
  - 测试 keyring 失败时 fallback 到 config
  - 测试 keyring 和 config 都不存在时返回 None

---

## Blocked by

None - can start immediately
