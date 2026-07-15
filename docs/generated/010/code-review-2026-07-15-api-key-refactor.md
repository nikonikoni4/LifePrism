# Code Review Report

**审查范围**: API Key 重构 — Issue #26-#29 (`.scratch/linux-deployment-discussion/issues-p2/`)
**审查时间**: 2026-07-15
**审查方法**: 8 维并行 Agent 审查 → 置信度评分 → 过滤 (≥80)

## 变更概述

将 API Key 从 config.yaml 分离到专用的 storage.yaml（权限 600），通过 SettingsManager 根据 run_mode 路由读写路径：
- 本地 (full)：keyring
- 云端 (agent_only/web_demo)：storage.yaml

**涉及文件** (7 个源文件 + 3 个测试文件):

| 文件 | 变更类型 | 行数变化 |
|------|---------|----------|
| `lifeprism/config/settings_manager.py` | 新增 storage 管理 (~230行) | +219 |
| `lifeprism/config/cloud_config_generator.py` | 重构配置生成 | +43/-46 |
| `lifeprism/config/cloud_initializer.py` | 重构初始化逻辑 | +103/-117 |
| `lifeprism/config/provider_manager.py` | get/set 改路由 | +17/-12 |
| `lifeprism/sync/sync_config.py` | 消除 keyring 直调 | +20/-20 |
| `lifeprism/llm/channel/wechat/auth.py` | token 读写改路由 | +19/-21 |
| `.gitignore` | 新增 storage.yaml | +1 |

## 架构上下文

### 相关 ADR
- **[ADR 2026-07-09-key-fallback-strategy.md](..\adr\2026-07-09-key-fallback-strategy.md)** v1.2 (decided)
  - 决策：扩展 SettingsManager（方案 A），不新建独立 StorageManager
  - 消费方通过 SettingsManager 接口获取 Key，内部根据 run_mode 自动路由
  - 原则：SettingsManager 管理所有 storage.yaml 的生命周期，外部模块不直接写文件

### 相关 Spec
- 无独立 spec 文档；以 ADR v1.2 作为技术契约

### Issue 覆盖
| Issue | 描述 | 状态 |
|-------|------|------|
| #26 | storage.yaml 基础设施：SettingsManager 扩展 | 已实现 |
| #27 | Key 消费方迁移到 SettingsManager 路由 | 已实现 |
| #28 | cloud_init.yaml storage 段 + CloudInitializer 写入 storage.yaml | 已实现 |
| #29 | config.yaml Key 字段清理 + .gitignore | 已实现 |

## 审查结果

**Found 6 issues** (1 CRITICAL, 2 HIGH, 3 MEDIUM):

---

### Issue 1: delete 操作绕过 SettingsManager 路由 [CRITICAL]

- **类型**: Architecture / Security
- **置信度**: 90
- **位置**:
  - `lifeprism/config/provider_manager.py:659-665` — `delete_api_key()`
  - `lifeprism/llm/channel/wechat/auth.py:107-125` — `delete_token()`
  - `lifeprism/config/settings_manager.py` — 缺少 `delete_storage_key()` 方法
- **详情**:

  `get_api_key()` 和 `set_api_key()` 已通过 SettingsManager 路由（云端模式读写 storage.yaml），但 `delete_api_key()` 仍直接调用 `keyring.delete_password()`。同样，`wechat/auth.py` 的 `delete_token()` 也直接调用 `keyring.delete_password()`。

  **根因**: SettingsManager 有 `get_storage_key()` / `set_storage_key()` 但没有对应 的 `delete_storage_key()` 方法，迫使删除操作绕过抽象层。

  **影响**: 云端模式下 (agent_only/web_demo)，provider Key 和 wechat_token 存储在 storage.yaml 中，但 `delete_api_key()` / `delete_token()` 仅操作 keyring → 删除实际无效 → 用户产生"Key已删除"的假安全感。

- **依据**: ADR v1.2 决策 "消费方通过现有 SettingsManager 接口获取 Key"、"SettingsManager 管理所有 storage.yaml 的生命周期"。Security Agent、Architecture Agent、Best Practices Agent、Code Quality Agent 四个维度独立确认。

- **修复建议**:
  1. 在 SettingsManager 新增 `delete_storage_key(key_name: str) -> bool` public 方法（run_mode 路由：本地删 keyring、云端从 `_storage_config` pop + `_save_storage()`）
  2. `provider_manager.delete_api_key()` 调用 `settings.delete_storage_key(f"providers.{provider_name}")`
  3. `wechat/auth.py:delete_token()` 调用 `settings.delete_storage_key("wechat_token")`

---

### Issue 2: get()/set()/update() 在 full 模式下 STORAGE_KEY_FIELDS 路由遗漏 [HIGH]

- **类型**: Architecture / Bug
- **置信度**: 85
- **位置**: `lifeprism/config/settings_manager.py:521, 668-671, 724-729`
- **详情**:

  `get()`, `set()`, `update()` 三个 public API 在 full 模式下对 STORAGE_KEY_FIELDS 处理均有缺陷：

  | API | full 模式行为 | 问题 |
  |-----|-------------|------|
  | `get("sync_api_key")` | 跳过 step 2.5 → yaml config 中无 → 返回 None | **keyring 中有值但返回 None** |
  | `set("sync_api_key", value)` | 跳过 step 2.5 → 写入 `_config` → `_save_config()` | **Key 回到 config.yaml，违反 ADR** |
  | `update({"sync_api_key": v})` | 弹出 → 非云端模式跳过写入 | **Key 被静默丢弃** |

  **缓解因素**: 当前所有消费方（sync_config、auth、provider_manager）都使用 `get_storage_key()`/`set_storage_key()` 而非 `get()`/`set()`，暂时未被触发。但这是 API 语义的定时炸弹——新代码调用 `settings.get("sync_api_key")` 会静默失败。

- **依据**: ADR v1.2 声明 "config.yaml 不再包含任何 Key 字段"。Architecture Agent 和 Performance Agent 独立确认。

- **修复建议**:
  1. `get()` 的 step 2.5 改为 `if key in self.STORAGE_KEY_FIELDS:`（去掉 `self.run_mode != "full"` 条件），让 `get_storage_key()` 内部 run_mode 路由处理
  2. `set()` 同样去掉条件，让 `set_storage_key()` 内部路由
  3. `update()` 中 STORAGE_KEY_FIELDS 总是在 extracted 后调用 `set_storage_key()`（让 run_mode 路由决定写 keyring 还是 storage.yaml）

---

### Issue 3: cloud_init.yaml 未设置 600 权限 [HIGH]

- **类型**: Security
- **置信度**: 85
- **位置**: `lifeprism/config/cloud_config_generator.py:192-199` — `_save_config()`
- **详情**:

  `CloudConfigGenerator._save_config()` 将包含所有 LLM Provider Key、sync_api_key、wechat_token 的完整字典明文写入 `cloud_init.yaml`，但写入后未调用 `os.chmod(path, 0o600)`。

  对比：`cloud_initializer.py` 写入 config.yaml 后设置 600，`settings_manager._save_storage()` 写入 storage.yaml 后设置 600，此处缺失是一致性缺口。

- **依据**: ADR v1.2 "storage.yaml 和 providers.yaml 的文件权限必须为 600"。Security Agent 独立确认。

- **修复建议**: `_save_config()` 末尾添加：
  ```python
  if sys.platform != "win32":
      os.chmod(config_path, 0o600)
  ```

---

### Issue 4: warnings 属性类型注解错误 [MEDIUM]

- **类型**: Code Quality
- **置信度**: 90
- **位置**: `lifeprism/config/settings_manager.py:238-240`
- **详情**:

  ```python
  @property
  def warnings(self) -> list[str]:          # 声明 list[str]
      return list(self._warnings)            # _warnings 是 list[dict[str, str]]
  ```

  `_warnings` 在 L228-233 存储 `{"type": ..., "message": ...}` 字典，返回类型应为 `list[dict[str, str]]`。类型检查器会产生误报，调用方代码提示也会被误导。

- **依据**: CLAUDE.md 后端编码规则要求类型注解准确。Code Quality Agent 和 Best Practices Agent 独立确认。

- **修复建议**: 改为 `def warnings(self) -> list[dict[str, str]]:`

---

### Issue 5: 使用 print() 输出错误而非 logger [MEDIUM]

- **类型**: Code Quality / Best Practices
- **置信度**: 85
- **位置**: `lifeprism/config/settings_manager.py:559, 574`
- **详情**:

  `_set_api_key_to_keyring` 和 `_set_api_key_to_keyring_by_provider` 在 keyring 写入失败时使用 `print(f"Warning: ...")` 而非 `logger.warning()`。

  影响：(1) 日志不会被 FileHandler 捕获写入文件；(2) 无时间戳和日志级别；(3) 无法通过日志配置控制输出。

- **依据**: CLAUDE.md "Logger uses delayed FileHandler"，项目所有模块统一使用 `logger = get_logger(__name__)`。Code Quality Agent 和 Best Practices Agent 独立确认。

- **修复建议**: 改为 `logger.warning("Failed to save API key for %s to keyring: %s", provider_id, e)`

---

### Issue 6: YAML 写入非原子操作 [MEDIUM]

- **类型**: Performance / Reliability
- **置信度**: 80
- **位置**:
  - `lifeprism/config/settings_manager.py:258-266` — `_save_config()`
  - `lifeprism/config/settings_manager.py:293-306` — `_save_storage()`
- **详情**:

  `_save_config()` 和 `_save_storage()` 直接用 `open(path, "w")` 覆写文件。若在 `yaml.dump()` 期间进程崩溃或磁盘满，原文件内容已丢失而新内容未写完，导致配置文件损坏。

  对于 `_save_config()` 影响尤其大——config.yaml 包含数十个配置项，损坏后用户需重新配置。

- **依据**: 原子文件写入是最佳实践（先写临时文件再 `os.replace()`）。Performance Agent 和 Best Practices Agent 独立确认。

- **修复建议**:
  ```python
  import tempfile, os
  fd, tmp = tempfile.mkstemp(dir=storage_path.parent, suffix=".tmp")
  try:
      with os.fdopen(fd, "w", encoding="utf-8") as f:
          yaml.dump(data, f, ...)
      os.replace(tmp, storage_path)
  finally:
      if os.path.exists(tmp):
          os.unlink(tmp)
  ```

---

## 正面发现 (Positive Findings)

以下审查维度未发现高置信度问题：

- **测试覆盖**: 全部 18 项验收标准均有测试覆盖（Issue 26: 6/6, Issue 27: 4/4, Issue 28: 4/4, Issue 29: 4/4），零遗漏
- **ADR 合规**: 核心架构决策执行到位——SettingsManager 全生命周期管理 storage.yaml、CloudInitializer 通过 `save_storage_yaml()` public 接口写入、消费方 (sync_config / auth) 零感知 run_mode
- **代码清理**: 旧代码（`_write_providers_yaml`、`_get_providers_yaml_path`、keyring 直调）已彻底清除
- **类型注解**: 所有新增 public 方法参数和返回值类型注解完整
- **异常处理**: `cloud_initializer._read_cloud_init()` 正确区分 `ConfigError`（重抛）和 `OSError`/`YAMLError`（转换）
- **config.yaml DEFAULTS**: 已移除 `sync_api_key`、`wechat_token`，`api_key` 保留是有意设计（ENV_VAR + keyring 旧路径）

## 变更摘要

**API Key 重构**实现了 ADR v1.2 的 storage.yaml 分离架构。核心实现质量高——SettingsManager 的 run_mode 路由内聚、消费方解耦干净、测试覆盖完整。主要问题集中在两方面：(1) **删除路径**未跟随 get/set 迁移到 SettingsManager 路由（缺少 `delete_storage_key()`）；(2) **public API 的 STORAGE_KEY_FIELDS 路由不完整**——`get()/set()/update()` 在 full 模式下有语义缺陷。

## 总体评估

| 维度 | 评分 |
|------|------|
| 架构合规 | ✅ 符合 ADR v1.2 |
| 安全 | ⚠️ 2 个 HIGH (cloud_init 权限 + delete 绕过) |
| 代码质量 | ⚠️ 2 个 MEDIUM (类型注解 + print 替代 logger) |
| 可靠性 | ⚠️ 1 个 MEDIUM (非原子写入) |
| 测试覆盖 | ✅ 18/18 项标准已覆盖 |
| 文档/注释 | ⚠️ 多个 docstring/method name 需要更新 (低置信度，已排除) |

**建议**: 修复 Issue 1-3（CRITICAL + HIGH）后可进入合并流程。MEDIUM 级别问题可后续迭代修复。
