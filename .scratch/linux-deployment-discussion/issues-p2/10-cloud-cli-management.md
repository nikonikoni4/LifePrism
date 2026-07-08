# 云端 CLI 管理

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

为 `main_agent_only.py` 增加命令行参数支持，实现配置管理和测试命令。

**实现端到端**：
1. 修改 `main_agent_only.py`，使用 `argparse` 解析命令行参数
2. 实现 4 个子命令：
   - `start`（默认）：正常启动 Agent Loop
   - `reinit-config`：重新初始化配置
     - 读取 `cloud_init.yaml`
     - 写入 `config.yaml` 和 `providers.yaml`
     - 删除 `cloud_init.yaml`
     - **不自动重启服务**（提示用户手动 `systemctl restart`）
   - `show-config`：查看当前配置（脱敏显示）
     - 显示 provider、model、API Base
     - API Key 只显示后 8 位（`***...abcd1234`）
     - monitor_type、sync enabled 等
   - `test-llm`：测试 LLM 连接
     - 发送测试消息："Hello, please reply 'OK' if you receive this."
     - 显示连接状态（成功/失败）
3. CLI 测试

---

## Acceptance criteria

- [ ] `main_agent_only.py` 支持 `argparse` 解析命令行参数
- [ ] `start` 命令（默认）正常启动 Agent Loop
- [ ] `reinit-config` 命令：
  - 读取 `cloud_init.yaml` 并写入配置
  - 删除临时文件
  - 提示用户手动重启服务
- [ ] `show-config` 命令：
  - 显示当前配置
  - API Key 脱敏（只显示后 8 位）
- [ ] `test-llm` 命令：
  - 发送测试消息
  - 显示连接状态
- [ ] CLI 测试通过：
  - 测试 4 个子命令
  - 测试 `reinit-config` 覆盖配置
  - 测试 `show-config` 脱敏显示
  - 测试 `test-llm` 连接测试

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/09-cloud-initializer.md`
