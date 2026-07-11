# cloud_init.yaml 验证失败：llm.provider(display_name) 与 providers[].name(internal) 不匹配

## 元信息
- **updated_at**: 2026-07-11
- **severity**: HIGH（导致云端启动时 `reinit-config` 命令失败，无法完成配置初始化）

## 问题描述

### 症状
云端执行 `python -m lifeprism.server.main_agent_only reinit-config` 时，`CloudInitializer._validate()` 抛出 `ConfigError`：

```
cloud_init.yaml 配置验证失败: providers 列表中未找到 llm.provider 对应的 provider: Xiaomi MIMO
```

### 触发条件
- 本地 `config.yaml` 中 `provider` 为 display_name（如 `"Xiaomi MIMO"`，含空格和大写）
- `CloudConfigGenerator._build_config()` 直接将 `settings.get("provider")` 写入 `cloud_init.yaml` 的 `llm.provider` 字段
- `cloud_init.yaml` 的 `providers` 列表中 `name` 字段是内部 name（如 `"xiaomi_mimo"`，全小写+下划线）
- `CloudInitializer._validate()` 用 `p.get("name") == provider` 做精确字符串匹配 → 失败

## 根本原因

### 代码位置
`lifeprism/config/cloud_initializer.py:_validate()` 第 189 行

### 问题机制

1. **两端数据语义不一致**：
   - `config.yaml` 中的 `provider` 字段存储的是 **display_name**（前端下拉框写入，供 UI 显示）
   - `providers.yaml` / `cloud_init.yaml` 中 `providers[].name` 存储的是 **内部 name**（全小写+下划线，用于 keyring/env_key 查找、ProviderSpec 匹配）
   - `ProviderManager` 提供了 `get_provider_id(display_name) → name` 的转换方法，但 `CloudInitializer._validate()` 没有使用

2. **数据流断层**：
   ```
   config.yaml: provider="Xiaomi MIMO" (display_name)
        ↓ CloudConfigGenerator._build_config() 直接取
   cloud_init.yaml: llm.provider="Xiaomi MIMO"
        ↓ CloudInitializer._validate() 精确匹配
   cloud_init.yaml: providers[].name="xiaomi_mimo"
        ↓
   匹配失败 ❌ ("Xiaomi MIMO" != "xiaomi_mimo")
   ```

3. **测试未覆盖此场景**：测试用例 `test_cloud_config_generator.py` 中 `settings.get("provider")` mock 返回的是 `"anthropic"`（内部 name），恰好与 `providers[].name` 一致，未覆盖 display_name 场景。

## 正确解决方案

在 `CloudInitializer._validate()` 中匹配 provider 前，用 `provider_manager.get_provider_id()` 将 display_name 转为内部 name：

```python
# 修复前
provider_spec = next((p for p in providers if p.get("name") == provider), None)

# 修复后
from lifeprism.config.provider_manager import provider_manager
provider_id = provider_manager.get_provider_id(provider)
provider_spec = next((p for p in providers if p.get("name") == provider_id), None)
```

### 为什么不用"生成时转 name"方案
- 如果 `CloudConfigGenerator._build_config()` 把 provider 转为内部 name，云端 `config.yaml` 会写入内部 name
- 与本地 `config.yaml` 的语义不一致（本地存 display_name）
- 为保持数据一致性，选择在消费端（验证时）做转换，而非在生成端改变语义

## 关键教训

1. **display_name ≠ name**：项目的 Provider 系统有两层命名（面向用户的 display_name 和内部 name），任何需要跨这两种命名的边界（如 cloud_init 生成/消费、配置验证）都必须显式转换。

2. **测试数据未覆盖 display_name 场景**：mock 数据用的是内部 name（`"anthropic"`），恰好绕过了这个 bug。应该用真实场景的 display_name（如 `"Xiaomi MIMO"`）构造测试用例。

3. **cloud_init.yaml 生成和消费是两条独立的流程**，由不同开发者/阶段实现，容易产生衔接断层。类似的数据序列化→反序列化流程应确保两端对字段语义的理解一致。

## 相关文件
- `lifeprism/config/cloud_initializer.py:_validate()` - 修复位置（验证时加 get_provider_id 转换）
- `lifeprism/config/cloud_config_generator.py:_build_config()` - 生成端（直接取 settings.get("provider")）
- `lifeprism/config/provider_manager.py:get_provider_id()` - 转换方法
- `test/core/unit/config/test_cloud_initializer.py` - 需补充 display_name 场景的测试用例

## 标签
`cloud-init` `provider` `display-name` `validation` `name-mismatch` `p2-sync`
