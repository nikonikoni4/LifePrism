# 云端配置初始化

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现云端启动时的配置初始化逻辑，读取 `cloud_init.yaml` 并写入 `config.yaml` 和 `providers.yaml`。

**实现端到端**：
1. 新增 `lifeprism/config/cloud_initializer.py`
2. 实现 `CloudInitializer` 类：
   - `should_initialize()` - 检测 `{lifeprism_data_path}/cloud_init.yaml` 是否存在
   - `initialize()` - 执行初始化：
     - 读取 `cloud_init.yaml`
     - **验证配置完整性**：
       - 检查必需字段：`wechat_token`、`sync_api_key`、`llm.provider`、`llm.model`
       - 检查 `providers.yaml` 中对应 provider 的 `api_key` 是否存在
       - 如果验证失败，抛出 `ConfigError` 并记录详细错误信息
       - **验证失败时不删除 `cloud_init.yaml`**（方便用户修复后重试）
     - 写入 `config.yaml`（包含 `wechat_token`、`sync_api_key` 等新增字段）
     - 写入 `providers.yaml`（为对应 provider 注入 `api_key` 字段）
     - **只有全部成功才删除 `cloud_init.yaml`**
3. 云端启动校验：
   - 强制检查 `monitor_type` 必须为 `none`
   - 如果不是，自动修正并记录 WARNING
4. 集成到 `main_agent_only.py` 启动流程：
   - 启动时检测 `should_initialize()`
   - 如果是，执行 `initialize()`
   - 继续正常启动
5. **日志记录**（INFO 级别）：
   - 初始化开始：检测到 `cloud_init.yaml`
   - 初始化完成：写入的配置项
   - 校验修正：`monitor_type` 强制设为 `none`
6. 集成测试

---

## Acceptance criteria

- [ ] `CloudInitializer` 类已实现
- [ ] 启动时检测 `cloud_init.yaml` 是否存在
- [ ] **配置验证逻辑正确**：
  - 检查必需字段：`wechat_token`、`sync_api_key`、`llm.provider`、`llm.model`
  - 检查 `providers.yaml` 中对应 provider 的 `api_key`
  - 验证失败时抛出 `ConfigError` 并记录详细错误
  - **验证失败时不删除 `cloud_init.yaml`**（方便用户修复）
- [ ] 初始化流程正确：
  - 读取 `cloud_init.yaml`
  - 验证配置
  - 写入 `config.yaml` 和 `providers.yaml`
  - **只有全部成功才删除 `cloud_init.yaml`**
- [ ] 强制校验 `monitor_type: none`（自动修正并记录 WARNING）
- [ ] 集成到 `main_agent_only.py` 启动流程
- [ ] **日志记录完整**（INFO 级别）：
  - 初始化开始：检测到 `cloud_init.yaml`
  - 初始化完成：写入的配置项
  - 校验修正：`monitor_type` 强制设为 `none`
- [ ] 集成测试通过：
  - 测试检测 `cloud_init.yaml`
  - **测试配置验证（缺少必需字段时抛出 ConfigError）**
  - 测试初始化流程
  - **测试验证失败时不删除文件**
  - 测试文件删除（成功时）
  - 测试 `monitor_type` 校验
  - 测试日志记录

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/02-key-fallback-mechanism.md`
