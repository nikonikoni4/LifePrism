# 错误处理体系问题修复总结

**日期**: 2026-07-06  
**范围**: 引入 agents-hub 错误处理体系后的隐藏问题修复

---

## 修复的问题

### 🔴 严重问题

#### 1. ConfigError 映射缺失 ✅ 已修复

**问题**: `ConfigError` 直接继承 `LWBaseError`，但 `_fallback_code()` 中缺少处理逻辑

**影响**: `ConfigError` 及其子类抛出时会走到 fallback 的 `return INTERNAL_ERROR`，映射不明确

**修复**:
- `lifeprism/server/errors/api_error_mapping.py:34`: 新增 `from lifeprism.config.exceptions import ConfigError`
- `lifeprism/server/errors/api_error_mapping.py:86`: 在 `_fallback_code()` 中新增 `if isinstance(error, ConfigError): return INVALID_CONFIG`

---

#### 2. PromptNotFoundError 继承错误 ✅ 已修复

**问题**: `PromptNotFoundError` 继承自 `LLMError(ExternalServiceError)`，返回 503，但 Prompt 文件缺失是**配置问题**（持久性错误），不是外部服务故障（临时性错误）

**影响**: 客户端收到 503 后会误以为是临时故障并重试，但 Prompt 缺失是持久性问题，重试无意义

**修复**:
- `lifeprism/llm/exceptions.py:8`: 新增 `from lifeprism.utils.exceptions import NotFoundError`
- `lifeprism/llm/exceptions.py:44`: 改为 `class PromptNotFoundError(NotFoundError)`，添加详细注释说明原因
- 现在返回 **HTTP 404** 而非 503

---

### ⚠️ 次要问题

#### 3. wechat/channel.py 的 except 范围调整 ✅ 已修复

**问题**: 
- **日志记录失败**（L322）：改为 `except (OSError, ValueError, TypeError)` 后，如果抛出其他异常（如 `AttributeError`）会导致消息处理中断
- **发送错误消息失败**（L365）：改为 `except WechatAPIError` 后，如果微信 API 抛出未知异常会导致无限错误循环

**修复**:
- L322: 恢复 `except Exception`，添加注释 `# ✅ 日志记录是辅助操作，允许 except Exception 防止影响主流程`
- L365: 改为 `except Exception`，添加注释 `# ✅ 发送错误消息失败时，允许 except Exception（未知的第三方 API 错误）`

---

#### 4. e.message 可能为 None ✅ 已修复

**问题**: `lifeprism/llm/channel/wechat/channel.py:359` 直接访问 `e.message`，但 `LWBaseError.message` 可能为 `None`

**修复**: 改为 `e.message or str(e)` 作为 fallback

---

## 新增规则

### `except Exception` 合法场景（详见 `backend-error-handling.md` 第 4 章）

**基本原则**: 默认禁止，仅以下场景合法：

#### 场景一：API 边界的最外层兜底
- 位置：全局异常处理器（`main.py`）
- 目的：捕获所有未被 `LWBaseError` 处理的未知异常

#### 场景二：辅助操作的兜底（不影响主流程）
- **判断标准**: 操作失败不应导致主流程中断
- **适用场景**:
  - ✅ 日志记录失败
  - ✅ 指标上报失败
  - ✅ 缓存预热失败
- **不适用场景**:
  - ❌ 数据持久化（主流程）
  - ❌ API 调用（主流程）
  - ❌ 状态变更（主流程）

#### 场景三：第三方库未知错误（可能影响系统稳定性）
- **判断标准**: 第三方库可能抛出**未知类型**的异常，且失败会导致系统不可用
- **适用范围**:
  - ✅ 外部服务 API（微信 API、支付接口、推送服务）
  - ✅ 第三方 SDK（日志上报、监控 SDK）
  - ✅ 用户自定义扩展插件
- **不适用范围**:
  - ❌ 标准库（`os`、`json`、`sqlite3` 等有明确异常类型）
  - ❌ 知名框架（FastAPI、SQLAlchemy 等有文档化的异常）
- **使用要求**:
  1. 必须记录 `exc_info=True`（保留完整异常栈）
  2. 必须转换为领域异常后抛出（不得吞掉）
  3. 必须在注释中说明为何使用 `except Exception`

---

## 修改的文件

### 代码文件
1. `lifeprism/server/errors/api_error_mapping.py` - 新增 ConfigError 映射
2. `lifeprism/llm/exceptions.py` - 修正 PromptNotFoundError 继承关系
3. `lifeprism/llm/channel/wechat/channel.py` - 调整异常捕获范围 + 修复 message fallback

### 规则文档
1. `docs/coding-rules/backend-error-handling.md` - 新增 `except Exception` 合法场景详细说明（版本 1.0 → 1.1）
2. `lifeprism/CLAUDE.md` - 新增 `except Exception` 合法场景简要说明

---

## 未修复的问题（不影响运行）

### 1. 新增异常类未被实际使用
- `lifeprism/config/exceptions.py`
- `lifeprism/llm/exceptions.py`
- `lifeprism/repository/exceptions.py`
- `lifeprism/processors/exceptions.py`

**说明**: 这些是体系引入的第一步，后续 PR 会逐步迁移旧代码使用这些异常类。

### 2. LWBaseError.to_dict() 与 API 响应不一致
- `to_dict()` 包含 `error_type` 和 `cause` 字段
- 实际 API 响应只包含 `error_code`、`message`、`details`

**建议**: 在文档中明确说明 `to_dict()` 用于调试/日志，不用于 API 响应。

---

## 验证建议

1. 运行项目，测试配置文件缺失场景，确认返回 500 且 error_code 为 `INVALID_CONFIG`
2. 测试微信消息处理，确认日志记录失败不影响消息发送
3. 测试 Prompt 文件缺失场景，确认返回 404 而非 503
