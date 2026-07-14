# storage.yaml 基础设施：SettingsManager 扩展

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - API Key 存储

## What to build

在 SettingsManager 中新增 storage.yaml 的加载、保存、路由逻辑。通过 run_mode 控制读写路径：本地（full）只用 keyring，云端（agent_only/web_demo）用 storage.yaml。

storage.yaml 是新增的专用 Key 存储文件（权限 600），命名避开 keys.yaml/secrets.yaml 以降低文件暴露时的敏感度（深度防御）。文件结构包含 sync_api_key、wechat_token、providers（各 LLM Provider 的 API Key）。

**ADR 参考**：`docs/adr/2026-07-09-key-fallback-strategy.md` v1.2 决策：扩展 SettingsManager（方案 A），不新建独立 StorageManager。消费方通过现有 SettingsManager 接口获取 Key，内部根据 run_mode 自动路由到 keyring 或 storage.yaml。

**实现要点**：

1. 在 SettingsManager `_initialize()` 末尾新增 storage.yaml 加载步骤
2. 新增 `_load_storage()` / `_save_storage()` 方法（读写 `{config_base_path}/storage.yaml`，权限 600）
3. `get()` 方法中，当 run_mode 为云端时，对 Key 类字段（sync_api_key、wechat_token、provider API Keys）从 storage.yaml 读取
4. `set()` / `update()` 方法中，当 run_mode 为云端时，Key 类字段写入 storage.yaml
5. 新增 `get_storage_key(key_name)` / `set_storage_key(key_name, value)` 便捷方法供消费方调用
6. 新增 `save_storage_yaml(data: dict)` public 接口，供 CloudInitializer（issue 28）批量写入 storage.yaml。内部调用 `_save_storage()`，保证权限 600 和文件结构一致。**原则**：SettingsManager 管理所有 storage.yaml 的生命周期，外部模块不直接写文件
7. storage.yaml 不存在时返回 None（云端首次启动时由 CloudInitializer 写入，见 issue 28）
8. `api_key` 字段（LLM 通用 API Key）保持现有 ENV_VAR + keyring 路径不变，**不纳入 storage.yaml**。storage.yaml 仅承载 sync_api_key、wechat_token、providers.* 三类

**storage.yaml 文件结构**：

```yaml
sync_api_key: "N7kX..."
wechat_token: "wx_token_..."
providers:
  anthropic: "sk-ant-..."
  deepseek: "sk-ds-..."
```

## Acceptance criteria

- [ ] SettingsManager 新增 `_load_storage()` / `_save_storage()` 方法，storage.yaml 权限设为 600
- [ ] SettingsManager 新增 `save_storage_yaml(data: dict)` public 接口，供 CloudInitializer 调用
- [ ] `run_mode == "full"` 时：Key 类字段只读写 keyring，不碰 storage.yaml
- [ ] `run_mode == "agent_only"` 或 `"web_demo"` 时：Key 类字段只读写 storage.yaml，不碰 keyring
- [ ] storage.yaml 不存在时 `get_storage_key()` 返回 None（不报错）
- [ ] 单元测试：本地模式只读 keyring，不加载/不创建 storage.yaml 文件
- [ ] 单元测试：云端模式只读 storage.yaml
- [ ] 单元测试：storage.yaml 不存在时返回 None
- [ ] 单元测试：写入 storage.yaml 后文件权限为 600
- [ ] 单元测试：嵌套 key 读取正确（`get_storage_key("providers.anthropic")` 返回 providers.anthropic 的值）

## Blocked by

None - can start immediately
