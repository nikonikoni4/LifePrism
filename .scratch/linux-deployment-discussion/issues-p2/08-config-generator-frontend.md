# 配置生成器 - 前端 UI

**Status**: ready-for-agent  
**Type**: AFK  
**Created**: 2026-07-08

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案

---

## What to build

实现前端配置生成界面，包括云端地址设置、生成配置按钮、打开文件夹功能。

**实现端到端**：
1. 设置页面（`frontend/apps/settings/`）新增"数据同步"配置区域：
   - **云端地址**输入框（保存到本地 `config.yaml` 的 `sync.remote_url`）
   - "生成云端配置"按钮
2. 点击按钮后：
   - 调用后端 API `POST /api/sync/generate-cloud-config`
   - 接收响应：`{cloud_config_path, key_is_new}`
   - 调用 Electron IPC 打开文件夹并选中文件（`explorer /select,"path\cloud_init.yaml"`）
   - **根据 `key_is_new` 显示不同级别的提示**：
     - 如果 `key_is_new === false`（沿用已有 Key）：
       ```
       ✅ 配置已生成！
       
       使用已有的同步 API Key。
       请将配置文件复制到云端并启动服务。
       
       本地文件：{lifeprism_data_path}\cloud_init.yaml
       云端目标：{云端 lifeprism_data_path}/cloud_init.yaml
       ```
     - 如果 `key_is_new === true`（新生成 Key）：
       ```
       ⚠️ 配置已生成！新的同步 API Key 已生成。
       
       【重要】本地没有检测到已有的同步 Key，已重新生成。
       
       请务必：
       1. 将配置文件复制到云端：{云端 lifeprism_data_path}/cloud_init.yaml
       2. 在云端执行：python -m lifeprism.server.main_agent_only reinit-config
       3. 如果云端之前已配置过，此操作会替换旧的 Key
       
       如果云端使用旧的 Key，同步将无法认证。
       ```
3. Electron IPC 通信（`frontend/electron/main.cjs`）：
   - 新增 IPC 处理器：`open-folder-and-select`
   - Windows: `shell.showItemInFolder(filePath)`
4. UI 测试

---

## Acceptance criteria

- [ ] 设置页面增加"云端地址"输入框，保存到 `config.yaml::sync.remote_url`
- [ ] "生成云端配置"按钮已实现
- [ ] 点击按钮后调用后端 API 生成配置
- [ ] 生成成功后打开文件夹并选中 `cloud_init.yaml`
- [ ] **根据 `key_is_new` 显示不同级别的提示**：
  - `key_is_new === false`：正常提示（使用已有 Key）
  - `key_is_new === true`：警告提示（新 Key 已生成，云端必须 reinit-config）
- [ ] Electron IPC `open-folder-and-select` 已实现
- [ ] UI 测试通过：
  - 测试输入云端地址并保存
  - 测试生成配置按钮
  - 测试打开文件夹功能
  - 测试两种不同的提示信息显示

---

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/07-config-generator-backend.md`
