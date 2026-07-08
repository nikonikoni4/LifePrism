# 测试 - 路径解析

**Status:** ready-for-agent

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md`

## What to build

创建单元测试，验证路径解析逻辑在不同平台和配置下的行为是否正确。

创建 `test/core/unit/config/test_settings_manager_cross_platform.py`，包含以下测试用例：

1. `test_config_base_path_windows`
   - 验证 Windows 平台上配置路径正确解析到 `%LOCALAPPDATA%/LifePrism`
   - Mock `sys.platform` 和 `os.environ`

2. `test_config_base_path_linux`
   - 验证 Linux 平台上配置路径回退到 `localData`（开发环境）
   - Mock `sys.platform`

3. `test_data_path_from_env_var`
   - 验证环境变量 `LIFEPRISM_DATA_PATH` 能正确覆盖默认路径
   - Mock `os.environ`

4. `test_data_path_from_config_yaml`
   - 验证 `config.yaml` 中的 `lifeprism_data_path` 优先级高于默认路径
   - Mock 配置文件存在性

使用 Mock 策略：
- Mock `sys.platform` 测试不同平台
- Mock `os.environ` 测试环境变量
- Mock `Path.exists()` 测试配置文件存在性

## Acceptance criteria

- [ ] 所有测试用例实现完整
- [ ] 测试能验证不同平台的路径解析逻辑
- [ ] 测试能验证配置优先级（yaml > 环境变量 > 默认）
- [ ] 使用 Mock 隔离文件系统和环境
- [ ] 测试独立运行，不依赖其他测试状态

## Blocked by

None - can start immediately

## User stories covered

7. 作为开发者，我想在 Linux 开发环境下运行后端服务，以便使用 Linux 服务器进行开发和调试
13. 作为运维人员，我想使用环境变量配置数据路径，以便灵活管理服务器存储
