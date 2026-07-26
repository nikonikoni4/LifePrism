# Code Review Report

**审查范围**: SSH 隧道集成工作区改动（19 个修改文件 + 7 个新增文件，+2513/-152 行）
**审查时间**: 2026-07-26
**变更文件**:
- 后端: `lifeprism/config/settings_manager.py`, `lifeprism/server/api/ssh_tunnel_api.py`(新增), `lifeprism/server/api/__init__.py`, `lifeprism/server/main.py`, `lifeprism/server/main_agent_only.py`, `lifeprism/sync/ssh_tunnel.py`(新增), `lifeprism/sync/sync_client.py`, `pyproject.toml`
- 前端: `frontend/apps/settings/components/SyncConfigSection.tsx`, `frontend/apps/settings/syncApi.ts`, `frontend/apps/settings/syncTypes.ts`
- 测试: `test/core/unit/sync/test_ssh_tunnel.py`(新增), `test/core/integration/api/test_ssh_tunnel_api.py`(新增), `test/core/integration/sync/test_sync_startup.py`, `test/core/integration/sync/test_scheduled_sync.py`, `test/core/integration/test_agent_only_mode.py`, `test/core/unit/config/test_settings_storage.py`
- 文档: `docs/coding-rules/sync-remote-url-access-rules.md`(新增), `docs/deployment/cloud-https-setup.md`, `docs/known-limitations/ssh-tunnel-limitations.md`(新增) 等

## 架构上下文

### 相关 CLAUDE.md
- `CLAUDE.md`（项目根目录）: 先方案后编码、ADR 驱动、修改超 3 文件需拆分任务
- `lifeprism/CLAUDE.md`: 类型注解禁止 `Any` 返回类型、异常继承 `LWBaseError`、API 层禁止 try/except、`except Exception` 默认禁止

### 相关 ADR
- `docs/adr/2026-07-09-key-fallback-strategy.md` (decided, v1.2): 密钥存储策略，SSH 私钥复用 keyring/storage.yaml 路由
- `docs/adr/2026-07-25-global-task-state.md` (decided, v2.2): 全局任务状态互斥，SSH 隧道启用后 ping 端点也走 localhost
- `docs/adr/2026-07-22-deletion-sync-tombstone.md` (decided): 墓碑同步端点，SSH 隧道启用后走 localhost
- **注意**: SSH 隧道集成无专属 ADR（决策记录在 `.scratch/ssh-tunnel-integration/prd.md`）

### 相关 Spec / coding-rules
- `docs/coding-rules/sync-remote-url-access-rules.md` (v1.0, 新增): remote_url 访问规则，审计表标注 3 处待审计位置
- `docs/coding-rules/backend-core-rules.md`: 类型注解、日志规范、Service 层职责
- `docs/coding-rules/backend-error-handling.md`: 异常分层、`except Exception` 限制
- `docs/coding-rules/backend-api-rules.md`: 路由设计、response_model、Schema 命名
- `docs/coding-rules/frontend-core-rule.md`: 禁止 `window.alert/confirm/prompt`

### 决策覆盖
- 26 个变更文件中 12 个代码文件有 PRD/Issue 决策关联（覆盖 100%）
- SSH 隧道决策记录在 `.scratch/ssh-tunnel-integration/prd.md` v1.2（35 个 User Story + 12 个关键决策）
- **缺口**: SSH 隧道集成未升格为 ADR（见 Issue 4 相关说明）

## 审查结果

Found 8 issues:

### Issue 1: SSH 隧道生命周期方法未在生产代码中接入（P0 致命）
- **类型**: Architecture / Security / Performance
- **置信度**: 90
- **位置**: `lifeprism/sync/sync_client.py:287` (`_start_ssh_tunnel`), `lifeprism/sync/sync_client.py:339` (`_stop_ssh_tunnel`)
- **详情**: `_start_ssh_tunnel()` 和 `_stop_ssh_tunnel()` 已定义但仅在测试文件 `test/core/integration/sync/test_sync_startup.py:506` 中被调用。生产代码（`main.py` 启动流程、`start_scheduled_sync`、`lifespan`）从未调用它们。
  
  **后果**：用户在前端切换到 SSH 模式后，`_should_use_ssh_tunnel()` 返回 True，但 `_is_tunnel_ready()` 永远返回 False（`_ssh_tunnel` 始终为 None），导致 `_read_remote_url()` 永远返回空字符串，所有同步静默跳过。用户可能误以为已安全加密，实际同步完全失效；若用户为"修复"问题切回 HTTP 模式，反而暴露真实服务器 IP，违背 SSH 隧道集成的安全初衷。
  
  同时，即使接入 `_start_ssh_tunnel`，若不同时在 `lifespan` 的 shutdown 阶段调用 `_stop_ssh_tunnel`，将导致 SSH 连接、端口转发、keep-alive 后台任务在应用关闭时不被清理，产生孤儿进程。
- **依据**: PRD Issue 05 明确要求 `_start_ssh_tunnel()` 作为 SyncClient 启动步骤；`docs/coding-rules/sync-remote-url-access-rules.md` 规则 5 指出"SSH 隧道模式下连接失败"是违反约束的后果；CLAUDE.md "先方案后编码"原则要求功能完整可运行

### Issue 2: _reconnect_with_backoff 成功日志永远显示"经过 0 次尝试"（P1 正确性）
- **类型**: Best Practices / Code Quality
- **置信度**: 95
- **位置**: `lifeprism/sync/ssh_tunnel.py:329-332`
- **详情**: `_reconnect_with_backoff()` 在 `connect()` 成功后记录日志 `"SSH 隧道 reconnect 成功（经过 %d 次尝试）"`，使用 `self._reconnect_attempts` 作为参数。但 `connect()` 在成功时（第 238 行）已经将 `_reconnect_attempts` 重置为 0，所以这条日志永远输出"经过 0 次尝试"，完全失去了调试价值。代码注释甚至承认了这一点（第 327 行），但仍然打印了被重置后的值。
- **依据**: `connect()` 第 238 行 `self._reconnect_attempts = 0`；正确做法是在调用 `connect()` 前用局部变量保存 `self._reconnect_attempts + 1`

### Issue 3: sync-remote-url-access-rules.md 审计表行号与方法名已过期（P1 文档）
- **类型**: Documentation / Architecture
- **置信度**: 90
- **位置**: `docs/coding-rules/sync-remote-url-access-rules.md:143-151`
- **详情**: 审计参考表中多处行号和方法名与当前代码不符：
  - Line 147: `sync_client.py:149` 标注 `_check_cloud_ready` 方法——该方法不存在，实际方法名为 `send_ping`（line 141）
  - Line 148: `sync_client.py:206-208`——实际 `_run_sync_loop` 中 `_read_remote_url()` 调用在 line 213
  - Line 150: `sync_client.py:269`——实际 `sync_once` 中 `_read_remote_url()` 调用在 line 421
  - 表格未包含 `sync_status_api.py:58` 和 `main.py:292` 两处直接读取 `sync.remote_url` 的位置
  
  审计表是预防性规则的关键参考，过期会导致后续开发者误判。
- **依据**: CLAUDE.md 文档规则要求文档与代码同步；`sync-remote-url-access-rules.md` 规则 6 要求 `_read_remote_url()` 相关注释保持准确

### Issue 4: _ensure_tunnel_ready() 为死代码，偏离 PRD 设计（P2 架构）
- **类型**: Architecture
- **置信度**: 85
- **位置**: `lifeprism/sync/sync_client.py:274-285`
- **详情**: `_ensure_tunnel_ready()` 方法已定义但未在任何生产代码中调用（仅 test 文件引用）。PRD 明确要求："修改 `_run_sync_loop` / `sync_once` 入口：调用 `_ensure_tunnel_ready()` 判断是否继续"。实际实现中，`sync_once` (line 438) 直接调用 `_is_tunnel_ready()` 进行判断，`_run_sync_loop` 完全没有隧道就绪检查。这偏离了 PRD 设计的"统一入口判断"意图，导致就绪检查逻辑分散在多处。
- **依据**: PRD Issue 05 设计意图 vs 实际实现不一致；CLAUDE.md "先方案后编码"原则

### Issue 5: SSH 隧道实例属性缺少类型注解（P2 代码质量）
- **类型**: Code Quality
- **置信度**: 85
- **位置**: `lifeprism/sync/sync_client.py:111,114`
- **详情**: 
  ```python
  self._ssh_tunnel = None  # 应为: SSHTunnel | None = None
  self._ssh_tunnel_keep_alive_task = None  # 应为: asyncio.Task | None = None
  ```
  两个属性均声明为 `None` 但未标注类型。这违反了 `backend-core-rules.md` 的类型注解要求，且与文件中其他属性的注解风格不一致（如 `self._is_syncing: bool = False`、`self._template_hashes: set[str] | None = None`）。由于 `SSHTunnel` 是延迟导入（避免循环依赖），可在 `if TYPE_CHECKING:` 块下导入类型用于注解。
- **依据**: `backend-core-rules.md` 类型注解规范；文件内已有的类型注解风格

### Issue 6: _stop_ssh_tunnel() 完全无行为测试（P2 测试）
- **类型**: Testing
- **置信度**: 85
- **位置**: `test/core/integration/sync/test_sync_startup.py`
- **详情**: `_stop_ssh_tunnel()` 是 SyncClient 中最复杂的 SSH 方法之一，包含多个分支：隧道存在/不存在、keep-alive 任务超时（5s）→强制取消、`CancelledError` 处理、其他异常兜底。但测试中只有 `test_sync_client_has_ssh_tunnel_methods`（第 674-678 行）通过 `hasattr` 检查方法存在性，没有任何测试验证其关闭行为、超时取消逻辑或异常处理路径。
- **依据**: `_start_ssh_tunnel` 至少有失败路径测试，但 `_stop_ssh_tunnel` 的 keep-alive 等待超时→cancel 分支、tunnel.close() 异常兜底分支完全未覆盖

### Issue 7: known_hosts=None 禁用主机密钥验证，存在 MITM 风险（P1 安全）
- **类型**: Security
- **置信度**: 80
- **位置**: `lifeprism/sync/ssh_tunnel.py:172`
- **详情**: `asyncssh.connect()` 调用时设置 `known_hosts=None`，完全禁用了 SSH 主机密钥验证。这使得 SSH 隧道容易受到中间人攻击（MITM）——攻击者可以在客户端和云端之间劫持连接。代码注释虽已承认此问题（"生产应使用 known_hosts 文件"），但该安全权衡未记录在 `docs/known-limitations/` 中，也未在 ADR 中说明。
- **依据**: SSH 安全通信的基本前提是主机密钥验证；`docs/coding-rules/sync-remote-url-access-rules.md` 强调安全风险但隧道自身的主机密钥验证缺失未被同等对待

### Issue 8: 同一条件在不同位置使用不同日志级别（P2 代码质量）
- **类型**: Code Quality
- **置信度**: 80
- **位置**: `lifeprism/sync/sync_client.py:394`（DEBUG）vs `lifeprism/sync/sync_client.py:439`（WARNING）
- **详情**: "SSH 隧道未就绪"这一条件在两处被检测并记录日志：
  - `_read_remote_url()` line 394: `logger.debug("跳过本次同步：SSH 隧道未就绪")`
  - `sync_once()` line 439: `logger.warning("SSH 隧道未就绪，跳过本次同步")`
  
  同一事件产生两个不同级别的日志，且 `sync_once` 中的 WARNING 会触发但 `_read_remote_url` 中的 DEBUG 在生产环境默认不输出。这导致运维监控可能只看到 WARNING 而无法关联到 `_read_remote_url` 的 DEBUG 信息，排查困难。
- **依据**: `backend-core-rules.md` 日志记录规范——日志级别应一致反映事件严重性

## 变更摘要

本次变更为 LifePrism 项目新增 SSH 隧道集成功能，作为 HTTP/HTTPS 之外的可选云端连接方式（模式 C，无域名场景）。

**后端**：
- Slice 1: `main_agent_only.py` 将 8102 端口默认绑定 127.0.0.1，环境变量 `LIFEPRISM_API_HOST` 可覆盖
- Slice 2: `settings_manager.py` 新增 7 个配置字段（`sync.connection_mode` + `sync.ssh_tunnel.*`）+ `ssh_tunnel_private_key` storage key 路由
- Slice 3: 新增 `lifeprism/sync/ssh_tunnel.py`，实现 SSHTunnel 类（5 态状态机 + 指数退避重连 + test_connection 一次性测试方法）
- Slice 4: 新增 `lifeprism/server/api/ssh_tunnel_api.py`，3 个 API 端点（enable 自动生成 ed25519 密钥 / public-key 实时派生 / test 测试连接）
- Slice 5: `sync_client.py` 新增 5 个 SSH 方法 + `_read_remote_url()` 拦截逻辑（SSH 模式返回 localhost）

**前端**：
- Slice 6: `SyncConfigSection.tsx` 新增连接方式切换 UI + SSH 选项卡（10 个 UI 元素）+ 5 个 API 函数 + 6 个 TS 接口

**文档**：
- Slice 7: 部署文档新增"模式 C：SSH 隧道"章节 + 7 项已知限制文档 + remote_url 访问规则文档

**测试**：110+ 个新测试，全部通过；前后端测试套件无回归（前端 225/225）。

**关键设计**：非侵入式原则（HTTP 模式行为完全不变）+ 三层守卫（run_mode + connection_mode + 私钥存在性）+ remote_url 统一拦截点（`_read_remote_url()`）。

**最关键问题**：Issue 1（生命周期未接入）使整个 SSH 隧道功能在当前提交中不可用，需优先在 `main.py` / `main_agent_only.py` 中 SyncClient 启动/关闭时调用 `_start_ssh_tunnel()` / `_stop_ssh_tunnel()`。
