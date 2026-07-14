# 同步 API Key 无法重新生成 + config.yaml fallback 导致 Key 固化

## 元信息

- **发生时间**: 2026-07-14
- **修复状态**: ❌ 待修复
- **影响范围**: 同步 API Key 的生成与读取链路、前端生成云端配置功能
- **bug 类型**: 设计缺陷（缺少用户选择权 + Key 读取链路污染）
- **严重程度**: 中

## 触发规则

在以下场景时阅读此文档：
- 修改云端配置生成逻辑（`cloud_config_generator.py`、`cloud_config_api.py`）
- 修改同步 API Key 读取逻辑（`sync_config.py`）
- 用户反馈"生成的同步 Key 始终是同一个测试值"
- 讨论同步 API Key 的生成/更新/轮换策略
- 排查 config.yaml 中的 `sync_api_key` 字段如何被消费

## Bug 简述

**Bug 1（前端）**：生成云端配置时无确认键，用户无法选择"保留当前 Key"还是"更换 Key"。用户误点击"生成云端配置"时会意外更换已有的有效 Key；或反之，用户想更换一个已泄露的 Key 时发现无法主动更换。

**Bug 2（后端）**：`get_sync_api_key()` 从 `config.yaml` fallback 读取同步 API Key（`sync_config.py:34`），导致 config.yaml 中手动写入的弱 Key 会被永久固化为同步 API Key，即使 `cloud_config_generator.py:85` 使用了 `secrets.token_urlsafe(32)` 也永远不会被触发。

## 代码位置

### Bug 1：前端缺确认键

**API 端点**：[lifeprism/server/api/cloud_config_api.py:21](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/cloud_config_api.py#L21)

```python
@router.post("/generate-cloud-config", summary="生成云端配置文件")
async def generate_cloud_config():
    generator = CloudConfigGenerator()
    cloud_config_path, key_is_new = generator.generate_cloud_config()
    return {
        "cloud_config_path": cloud_config_path,
        "key_is_new": key_is_new,
    }
```

当前 API 返回 `key_is_new` 字段，但前端没有利用这个信息弹确认框。用户点击按钮后立即生成并覆盖，无法选择行为。

### Bug 2：config.yaml fallback 污染 Key 读取链

**Key 生成器**：[lifeprism/config/cloud_config_generator.py:72-87](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/cloud_config_generator.py#L72-L87)

```python
def _resolve_sync_api_key(self) -> tuple[str, bool]:
    existing_key = get_sync_api_key()    # ← 从 keyring 或 config.yaml 读取
    if existing_key:
        return existing_key, False       # ← 已有不生成
    new_key = secrets.token_urlsafe(32)  # ← 这里才是随机生成（但永远走不到）
    set_sync_api_key(new_key)
    return new_key, True
```

**Key 读取函数**：[lifeprism/sync/sync_config.py:31-37](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_config.py#L31-L37)

```python
# Fallback: 从 config.yaml 读取 sync_api_key 字段（云端 Linux 部署）
from lifeprism.config.settings_manager import get_setting

config_key = get_setting("sync_api_key")   # ← 从 config.yaml 读
if config_key:
    logger.debug("keyring 未找到 sync_api_key，已从 config fallback")
    return str(config_key)
return None
```

**污染链路**：

```
1. 开发时手动写入 config.yaml: sync_api_key = test_heartbeat_key_abc123xyz
2. 用户点击"生成云端配置"
3. _resolve_sync_api_key() → get_sync_api_key()
4. keyring 无值 → fallback 到 config.yaml → 返回 "test_heartbeat_key_abc123xyz"
5. existing_key 非空 → key_is_new = False → 不生成新 Key
6. cloud_init.yaml 中永远写入 test_heartbeat_key_abc123xyz
```

## 发生原因

### Bug 1 根因：功能未完成

`cloud_config_generator` 返回了 `key_is_new` 字段，说明设计时已考虑"新生成 vs 已有"的场景，但前端没有基于这个字段做交互确认。这是一个**前后端未对齐**的未完成功能。

### Bug 2 根因：sync_api_key 的存储语义混乱

`sync_config.py` 的目标是"统一 Key 读取入口"，但它没有区分"读取的目的是什么"：
- 在 `verify_sync_api_key`（[sync_cloud_api.py:105](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L105)）中，fallback 到 config.yaml 是**合理的**（云端部署时 keyring 不可用，必须从 config.yaml 验证）
- 在 `_resolve_sync_api_key`（[cloud_config_generator.py:82](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/cloud_config_generator.py#L82)）中，fallback 到 config.yaml 是**不该发生的**（生成新配置时，应该只看 keyring，config.yaml 的值不应该被当作"现有的 Key"）

同一个函数 `get_sync_api_key()` 在两个场景被复用，语义冲突。

## 最佳方案

### Bug 1 修复：前端增加确认键

**后端改动**：API 拆分或增加参数

```python
# cloud_config_api.py
@router.post("/generate-cloud-config")
async def generate_cloud_config(replace_key: bool = False):
    """生成云端配置文件。

    Args:
        replace_key: 是否更换同步 API Key。
                     True = 重新生成 Key 并写入配置
                     False = 仅生成配置文档，保留当前 Key（新 Key 为 None 时自动生成）
    """
    generator = CloudConfigGenerator()
    if replace_key:
        cloud_config_path, _ = generator.generate_cloud_config(replace_key=True)
    else:
        cloud_config_path, key_is_new = generator.generate_cloud_config(replace_key=False)
    return {"cloud_config_path": cloud_config_path, "key_is_new": key_is_new}
```

**前端改动**：生成前弹确认框

```
生成云端配置
├─ [ 保留当前 Key，仅生成配置文档 ]
│   适用于：测试配置内容、更新 LLM 提供商信息等不涉及 Key 的场景
│
└─ [ 更换 Key 并生成配置 ]
    适用于：Key 可能已泄露、需要轮换的场景
    ⚠ 更换后需重新部署云端 storage.yaml 并重启服务
```

### Bug 2 修复：Key 统一存储 + run_mode 隔离读写

#### 设计目标

将所有 Key 从 `config.yaml` 中分离，统一到专用存储文件 `storage.yaml`。通过 `run_mode`（运行时配置，仅内存，不持久化，见 `settings_manager.py:531-537`）控制读写行为：本地只用 keyring，云端才用文件 fallback。

#### Key 存储文件

新增 `storage.yaml`，位置：`{config_base_path}/storage.yaml`，权限 600。

```yaml
# storage.yaml（仅 Key，文件权限 600）
sync_api_key: "N7kX..."
wechat_token: "wx_token_..."
providers:
  anthropic: "sk-ant-..."
  deepseek: "sk-ds-..."
```

**命名说明**：不使用 `keys.yaml`（太明显），使用 `storage.yaml`（看起来像普通存储配置）。

#### 读取层级

```
本地 (run_mode == "full")：
  sync_api_key       → keyring（没有就 None，不读任何文件）
  wechat_token        → keyring（没有就 None，不读任何文件）
  Provider API Key    → keyring（没有就 None，不读任何文件）

云端 (run_mode == "agent_only" | "web_demo")：
  sync_api_key       → storage.yaml
  wechat_token        → storage.yaml
  Provider API Key    → storage.yaml → providers.yaml
```

#### 写入层级

```
本地 (run_mode == "full")：
  所有 Key → 写入 keyring（不写任何文件）

云端 (run_mode == "agent_only" | "web_demo")：
  所有 Key → 写入 storage.yaml（keyring 不可用，不尝试写入）
```

#### 具体改动

| 文件 | 改动 |
|------|------|
| 新增 `storage.yaml` | `{config_base_path}/storage.yaml`，权限 600 |
| `sync_config.py:get_sync_api_key()` | `run_mode == "full"` → 只读 keyring；云端 → 读 storage.yaml |
| `wechat/auth.py:_load_token_from_keyring()` | 同上 |
| `provider_manager.py:get_api_key()` | 同上，云端再加一层 providers.yaml 兜底 |
| `cloud_config_generator.py` | cloud_init.yaml 输出 storage 段 |
| `cloud_initializer.py` | 初始化时 Key 写入 storage.yaml 而非 config.yaml |
| `config.yaml` | 移除 sync_api_key、wechat_token 字段（从 DEFAULTS 和现有文件中清理） |

**`providers.yaml` 不动**，它已有自己的结构和 fallback 层级。

> ⚠ **待讨论**：keyring 包在 Linux headless 环境中可能不可用（缺少 D-Bus/SecretService 等系统组件）。当前方案依赖 keyring 作为本地 Windows 的存储方式，如果 keyring 在 Linux 上 import 失败会导致模块无法加载。三个候选方向：
> - A) keyring import 改为懒加载（仅本地 Windows 场景调用）
> - B) 本地也放弃 keyring，所有 Key 统一走 storage.yaml
> - C) keyring 配置为 Windows-only 可选依赖
>
> 见已知限制 [cloud-security-limitations.md](../known-limitations/cloud-security-limitations.md) 限制 5。

### Bug 4：keyring 顶层 import 导致 Linux 模块加载崩溃

#### 问题描述

当前 4 个文件在模块顶层 `import keyring`：

| 文件 | 行号 | keyring 调用数 |
|------|------|---------------|
| `settings_manager.py` | L16 | 8 处（get/set/delete） |
| `provider_manager.py` | L17 | 3 处（get/set/delete） |
| `sync_config.py` | L6 | 2 处（get/set） |
| `wechat/auth.py` | L12 | 4 处（get/set/delete） |

所有 keyring 运行时调用已有 try/except 包裹，但如果 `import keyring` 本身在模块顶层执行时 ImportError（Linux headless 环境缺少 D-Bus/SecretService），整个模块都无法加载。即使 `cloud_config_generator.py` 等调用方使用了延迟导入，只要有任何代码触发模块加载就会崩溃。

#### 修复方案：keyring 懒加载（方案 3，已评审为"可行"）

**核心思路**：将 `import keyring` 从模块顶层移到函数内部，仅在需要时导入。通过 subagent 评估确认可行，改造规模 5 个文件约 64 行。

**统一辅助函数**（每个文件各一份，或提取到 `lifeprism/utils/` 共用）：

```python
def _get_keyring():
    """懒加载 keyring 模块，仅在 Windows 上首次调用时导入。
    
    Returns:
        keyring 模块，或 None（非 Windows 或导入失败）
    """
    import sys
    if sys.platform != "win32":
        return None
    try:
        import keyring
        return keyring
    except ImportError:
        return None
```

**各文件改动详情**：

##### 文件 1：[settings_manager.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/settings_manager.py)（~20 行）

1. L16：删除 `import keyring`
2. 新增 `_get_keyring()` 辅助函数
3. 6 个方法适配（`_get_api_key_from_keyring`、`_get_api_key_from_keyring_by_provider`、`_set_api_key_to_keyring`、`_set_api_key_to_keyring_by_provider`、`_delete_api_key_from_keyring`、`_delete_api_key_from_keyring_by_provider`）：

```python
# 改前
try:
    api_key = keyring.get_password(...)
except Exception:
    ...

# 改后
kr = _get_keyring()
if kr is None:
    return None
try:
    api_key = kr.get_password(...)
except Exception:
    ...
```

##### 文件 2：[provider_manager.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/config/provider_manager.py)（~15 行）

1. L17：删除 `import keyring`
2. 新增 `_get_keyring()` 辅助函数
3. `get_api_key()`（L620-638）：当前**无** try/except，需新增判空 + try/except
4. `set_api_key()`（L640-646）：同上
5. `delete_api_key()`（L648-654）：`contextlib.suppress(keyring.errors.PasswordDeleteError)` 改为 `contextlib.suppress(kr.errors.PasswordDeleteError)`

```python
# get_api_key 改后
def get_api_key(self, provider_name: str) -> str | None:
    kr = _get_keyring()
    if kr is None:
        return self._fallback_get_api_key(provider_name)
    try:
        env_key = self._get_env_key(provider_name)
        return kr.get_password(_KEYRING_SERVICE, env_key)
    except Exception:
        return self._fallback_get_api_key(provider_name)
```

##### 文件 3：[sync_config.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_config.py)（~10 行）

1. L6：删除 `import keyring`
2. 新增 `_get_keyring()` 辅助函数
3. `get_sync_api_key()`（L16-38）：已有 try/except，只需加 `kr = _get_keyring()` 判空
4. `set_sync_api_key()`（L41-47）：当前**无** try/except，需新增

```python
# set_sync_api_key 改后
def set_sync_api_key(key: str) -> None:
    kr = _get_keyring()
    if kr is None:
        return
    try:
        kr.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, key)
    except Exception as e:
        logger.debug("写入 keyring 失败: %s", e)
```

##### 文件 4：[wechat/auth.py](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/channel/wechat/auth.py)（~18 行）

1. L12：删除 `import keyring`
2. 新增 `_get_keyring()` 辅助函数
3. `_load_token_from_keyring()`：`except (kr.errors.KeyringError, OSError)` 运行时解析
4. `_save_token_to_keyring()`：同上
5. `delete_token()`：`except kr.errors.PasswordDeleteError` 运行时解析

##### 文件 5：[pyproject.toml](file:///d:/desktop/软件开发/LifeWatch-AI/pyproject.toml)（1 行）

```toml
# 改前
"keyring",

# 改后
"keyring>=24.0; platform_system=='Windows'",
```

#### 验证结果（subagent 确认）

- **循环导入**：不会新增（移除 import 只会减少依赖链）
- **测试兼容**：现有 `patch("keyring.get_password", ...)` 字符串 mock 方式在懒加载后仍正常
- **PyInstaller 打包**：无影响（只在 Windows 上打包，keyring 正常安装和收集）
- **Python 版本**：Python 3.8+ 全部兼容
- **异常类引用**：`kr.errors.PasswordDeleteError`、`kr.errors.KeyringError` 运行时解析，完全合法

#### 为什么选择方案 3 而不是方案 B/C

| 方案 | 优缺点 |
|------|--------|
| A) keyring 懒加载 | ✅ 本地 Windows 保持 OS 级加密存储；✅ 云端不 import keyring 不崩溃；⚠ 每个文件 8 行重复代码 |
| B) 统一 storage.yaml | ⚠ 本地丢失 OS 级安全（Windows 凭据管理器不可替代）|
| C) Windows-only 依赖 | ⚠ 只解决安装问题，不解决运行时 backend 不可用的问题 |

方案 3 在安全性和兼容性之间取最佳平衡：本地保持 keyring 安全级别不变，云端彻底不受 keyring 影响。

### Bug 3（关联）：本地 config.yaml 不应出现 Key 字段

当前 `config.yaml` 中混合了普通配置与敏感 Key（`sync_api_key`、`wechat_token`）。这是"Key 被当作已有的值"污染的根源——本地不应该有文件形式的 Key fallback。

Bug 2 的存储方案从架构上解决了此问题：本地 `run_mode == "full"` 时所有 Key 函数都只读 keyring，不会 fallback 到任何文件，config.yaml 中即使存在旧字段也不会被读取。

## 复用场景

此 bug 记录可供以下场景复用：

1. **云端配置生成流程**：任何"生成配置"的功能都应有确认键，区分"仅生成文档"和"更换凭据"两种意图
2. **Key 读取链设计**：`get_xxx_key()` 函数应明确区分"验证用"和"生成用"两种调用场景，避免同一个 fallback 逻辑在不该使用的地方被复用
3. **前后端未对齐的功能**：当后端 API 返回了某个状态字段（如 `key_is_new`）但前端未使用时，说明功能未完成

## 相关文档

- 安全限制（已知限制）：[cloud-security-limitations.md](docs/authority/cloud-security-limitations.md) 限制 3
- 云端配置生成 PRD：`.scratch/linux-deployment-discussion/linux-deployment-prd.md`（P2 第 6-7 节）
- 相关代码文件：
  - `lifeprism/config/cloud_config_generator.py`
  - `lifeprism/sync/sync_config.py`
  - `lifeprism/server/api/cloud_config_api.py`
  - `lifeprism/server/api/sync_cloud_api.py`（`verify_sync_api_key`）
  - `lifeprism/config/settings_manager.py`（`run_mode`、`set_runtime_config`）
  - `lifeprism/config/provider_manager.py`（`get_api_key`）
  - `lifeprism/llm/channel/wechat/auth.py`（`_load_token_from_keyring`）
  - `lifeprism/config/cloud_initializer.py`（Key 写入目标）
