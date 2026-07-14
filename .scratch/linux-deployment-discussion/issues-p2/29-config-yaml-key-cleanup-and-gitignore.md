# config.yaml Key 字段清理 + .gitignore

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - API Key 存储

## What to build

从 config.yaml 的 DEFAULTS 中移除所有 Key 字段（sync_api_key、wechat_token、provider API Keys），更新 .gitignore 排除 storage.yaml。

**ADR 参考**：`docs/adr/2026-07-09-key-fallback-strategy.md` v1.1 涉及改动表

**需要做的 3 件事**：

1. **config.yaml DEFAULTS 清理**：
   - 移除 `sync_api_key` 字段
   - 移除 `wechat_token` 字段
   - 移除 Provider API Key 字段（如 `anthropic_api_key` 等）
   - 保留非 Key 配置字段（llm provider/model、sync config 等）
   - 更新 `get_config_schema()` 等相关方法，移除 Key 字段的 schema 定义

2. **.gitignore 更新**：
   - 新增 `storage.yaml` 排除规则
   - 确认 `config.yaml` 已被排除（应该已有）
   - 新增 `cloud_init.yaml` 排除规则（如果还没有）

3. **SettingsManager 迁移逻辑**（向后兼容）：
   - 首次启动时检测 config.yaml 中是否残留 Key 字段
   - 若残留且 storage.yaml 不存在 → 读取 config.yaml 的 Key → 写入 storage.yaml（或 keyring，根据 run_mode）→ 从 config.yaml 中移除 Key 字段 → 保存 config.yaml
   - 若 storage.yaml 已存在 → 跳过迁移，仅清理 config.yaml 中的残留 Key
   - 迁移后 config.yaml 中其他配置（如 llm.provider）保持不变
   - 本地模式迁移到 keyring 时，sync_api_key 和 wechat_token 的 keyring username 分别为 `"sync_api_key"`、`"wechat_token"`（与 storage.yaml 的 key name 一致）

**与 issue 28 的时序协作**：云端场景下，CloudInitializer（issue 28）先写 storage.yaml，然后 SettingsManager 加载时迁移逻辑发现 storage.yaml 已存在 → 跳过迁移，仅清理 config.yaml 残留。本地场景下，SettingsManager 迁移逻辑直接写入 keyring。

## Acceptance criteria

- [ ] config.yaml DEFAULTS 中不再包含 sync_api_key、wechat_token、provider API Key 字段
- [ ] .gitignore 排除 storage.yaml
- [ ] .gitignore 排除 cloud_init.yaml
- [ ] SettingsManager 迁移逻辑：config.yaml 残留 Key → storage.yaml/keyring → 清理 config.yaml
- [ ] 迁移后 config.yaml 不再包含 Key 字段
- [ ] 迁移后 storage.yaml 或 keyring 中包含迁移的 Key
- [ ] 迁移后 config.yaml 中其他配置（llm.provider 等）保持不变
- [ ] cloud_config_generator 中 config 段的 schema 定义移除 Key 字段
- [ ] 单元测试：本地模式迁移（config.yaml 残留 Key → keyring）
- [ ] 单元测试：云端模式迁移（config.yaml 残留 Key → storage.yaml）
- [ ] 单元测试：storage.yaml 已存在时跳过迁移，仅清理 config.yaml
- [ ] 单元测试：迁移后其他配置字段保持不变

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/27-key-consumers-migrate-to-settings-manager.md` - 消费方迁移完成后才能清理 config.yaml（否则消费方找不到 Key）
