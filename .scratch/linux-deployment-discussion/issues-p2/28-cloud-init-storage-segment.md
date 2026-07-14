# cloud_init.yaml storage 段 + CloudInitializer 写入 storage.yaml

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - API Key 存储

## What to build

更新 CloudConfigGenerator 和 CloudInitializer，使 cloud_init.yaml 输出 storage 段，CloudInitializer 初始化时将 Key 写入 storage.yaml 而非 config.yaml。

**ADR 参考**：`docs/adr/2026-07-09-key-fallback-strategy.md` v1.1 涉及改动表

**需要修改的 2 个组件**：

1. **CloudConfigGenerator**（`lifeprism/config/cloud_config_generator.py`）：
   - `generate_cloud_config()` 输出的 cloud_init.yaml 新增 `storage` 段
   - storage 段包含 sync_api_key、wechat_token、providers（各 LLM Provider 的 API Key）
   - 从 keyring 读取所有 Key（本地生成配置时 keyring 可用）
   - 生成或读取同步 API Key 的逻辑保留，但输出到 storage 段而非 config 段

2. **CloudInitializer**（`lifeprism/config/cloud_initializer.py`）：
   - `initialize()` 时读取 cloud_init.yaml 的 storage 段
   - 将 Key 写入 `storage.yaml`（权限 600），而非 config.yaml
   - 验证配置完整性时检查 storage 段的必需字段
   - 验证失败时不删除 cloud_init.yaml（保留方便重试，已有逻辑保留）

**cloud_init.yaml 结构（storage 段）**：

```yaml
# cloud_init.yaml
storage:
  sync_api_key: "N7kX..."
  wechat_token: "wx_token_..."
  providers:
    anthropic: "sk-ant-..."
    deepseek: "sk-ds-..."
config:
  # 普通配置（不含 Key）
  llm:
    provider: "anthropic"
    model: "claude-3-5-sonnet"
  ...
```

**替代 issue 07/09 的 Key 部分**：原 issue 07（配置生成器）和 09（云端初始化器）将 Key 写入 config.yaml，现改为写入 storage.yaml。

**验证路径变化**：CloudInitializer 现有验证逻辑检查 `wechat_token`（顶层）、`sync.api_key`（嵌套），改为检查 `storage.wechat_token`、`storage.sync_api_key`。验证路径从顶层/嵌套变为统一在 storage 段下。

**复用 SettingsManager 写入**：CloudInitializer 写入 storage.yaml 时应调用 SettingsManager 的 public 接口 `save_storage_yaml(data: dict)` 方法（issue 26 新增），保证权限 600 和文件结构一致，而非独立写入。**原则**：SettingsManager 管理所有 storage.yaml 的生命周期，外部模块不直接写文件。

## Acceptance criteria

- [ ] CloudConfigGenerator 输出的 cloud_init.yaml 包含 storage 段（sync_api_key、wechat_token、providers）
- [ ] CloudInitializer 读取 storage 段并写入 storage.yaml（权限 600）
- [ ] CloudInitializer 不再将 Key 写入 config.yaml
- [ ] 验证配置完整性时检查 storage 段的必需字段（storage.sync_api_key、storage.wechat_token）
- [ ] 验证失败时不删除 cloud_init.yaml
- [ ] CloudInitializer 写入 storage.yaml 复用 SettingsManager 的 `save_storage_yaml()` public 接口
- [ ] 单元测试：storage 段缺失 sync_api_key 时验证失败
- [ ] 单元测试：storage 段缺失 wechat_token 时验证失败
- [ ] 单元测试：storage 段 providers 为空字典时正常处理（不报错）
- [ ] 单元测试：cloud_init.yaml 中 config 段和 storage 段同时存在时正确分离写入
- [ ] 单元测试：cloud_init.yaml 输出包含 storage 段
- [ ] 单元测试：CloudInitializer 正确写入 storage.yaml
- [ ] 单元测试：storage.yaml 文件权限为 600
- [ ] 单元测试：验证失败时 cloud_init.yaml 保留

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/26-storage-yaml-settings-manager.md` - storage.yaml 基础设施必须先就绪（确保 SettingsManager 能读取 CloudInitializer 写入的 storage.yaml）
