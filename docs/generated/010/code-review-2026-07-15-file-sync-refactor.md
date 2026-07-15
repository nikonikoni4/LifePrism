# Code Review Report

**审查范围**: 文档同步重构 — Issue #30-#36 (`.scratch/linux-deployment-discussion/issues-p2/`)
**审查时间**: 2026-07-15
**审查方法**: 8 维并行 Agent 审查 → 置信度评分 → 过滤 (≥80)

## 变更概述

将文件同步从纯 LWW mtime 比较改为 per-file hash tracking + 11 状态矩阵 + 三阶段 API 协议：

- **Issue #30**: `file_sync_state` 表 + `FileSyncStateProvider` + `compute_file_hash()`
- **Issue #31**: 云端四端点 `check` → `fetch` → `verify` → `commit`
- **Issue #32**: `push-files` 改造（新增 parent_hash + current_hash）
- **Issue #33**: `SyncClient` 完整同步流程（11 状态矩阵 + Phase 1-3）
- **Issue #34**: `CONFLICT_RESOLVE` 消息类型 + `AgentLoop` 集成 + `bus` 桥接
- **Issue #35**: `wechat_account_state` 表 + `account.json` 迁移
- **Issue #36**: 启动同步 + 定时同步

**涉及文件** (12 源码 + 8 测试 + 12 新增文件):

| 文件 | 变更类型 | 行数变化 |
|------|---------|----------|
| `lifeprism/config/database.py` | TABLE_CONFIGS 新增 2 表 | +68 |
| `lifeprism/repository/providers/__init__.py` | 新增 Provider 导出 | +10 |
| `lifeprism/repository/providers/file_sync_state_provider.py` | **新增** | +124 |
| `lifeprism/repository/providers/wechat_account_state_provider.py` | **新增** | +148 |
| `lifeprism/sync/hash_utils.py` | **新增** | +28 |
| `lifeprism/sync/sync_client.py` | 全流程重构 | +871/-... |
| `lifeprism/server/api/sync_cloud_api.py` | 四端点 + push 改造 | +371 |
| `lifeprism/llm/agent/loop.py` | CONFLICT_RESOLVE 分支 | +26 |
| `lifeprism/llm/bus/events.py` | MessageType 新增 | +2 |
| `lifeprism/llm/channel/wechat/channel.py` | DB 迁移 + 读写 | +172 |
| `lifeprism/server/main.py` | 启动/定时同步 | +63 |

## 架构上下文

### 相关 ADR
- **[ADR 2026-07-14-file-sync-conflict-resolution.md](..\adr\2026-07-14-file-sync-conflict-resolution.md)** v2.1 (decided)
  - 决策 1: per-file version tracking (parent_hash + current_hash + 11 状态矩阵)
  - 决策 2: 同步白名单对齐 Agent 工具白名单 (4 目录)
  - 决策 3: MD 冲突由 AI 驱动解决 (CONFLICT_RESOLVE 消息类型)
  - 决策 4: account.json 改为数据库存储
  - 决策 5: 三阶段 API 协议 (check → fetch/push → verify)
- **[ADR 2026-07-14-sync-full-sync-strategy.md](..\adr\2026-07-14-sync-full-sync-strategy.md)** (decided)
  - 全量同步通过"重置同步进度按钮"实现

### 决策覆盖
- 5/5 ADR 决策有对应实现
- 新增 3 个 ADR 引用标注良好的模块 (hash_utils, database DDL, channel migration)
- 2 个文件缺少 ADR 引用 (loop.py, events.py)

## 审查结果

**Found 8 issues** (1 HIGH, 5 MEDIUM, 2 LOW):

---

### Issue 1: compute_file_hash 过度规范化导致 hash 碰撞风险 [HIGH]

- **类型**: Best Practices / Correctness
- **置信度**: 85
- **位置**: `lifeprism/sync/hash_utils.py:27`
- **详情**:

  `"".join(text.split())` 移除**所有**空白字符（空格、制表符、换行），导致语义不同的内容产生相同 hash：
  - `"hello world"` → `"helloworld"`
  - `"helloworld"` → `"helloworld"`
  - `"**bold**"` → `"**bold**"`
  - `"** bold **"` → `"**bold**"`

  虽然 ADR 决策 5 明确要求 "去除所有空白字符后计算 SHA-256" 以回避 OS 换行差异，但 `.split()` 无参数时的行为粒度过粗——它会合并连续空白并完全删除词语间的空格分隔符。这意味着"两个分开的词"和"一个合并的词"会被判定为相同内容而跳过同步。

- **依据**: ADR 决策 5 "hash 规范化策略"。Performance/Best Practices Agent 独立确认。

- **修复建议**: 仅规范化行尾符（`\r\n` → `\n`）和行首/行尾空白，保留词语间的空格：
  ```python
  normalized = text.replace("\r\n", "\n").replace("\r", "\n")
  normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
  return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
  ```

---

### Issue 2: 文件写入非原子操作 [MEDIUM]

- **类型**: Reliability / Best Practices
- **置信度**: 85
- **位置**:
  - `lifeprism/sync/sync_client.py:684` — `file_path.write_bytes(content_bytes)`
  - `lifeprism/sync/sync_client.py:1041` — `local_file.write_text(merged_content)`
- **详情**:

  SyncClient 在 Phase 2b (fetch) 和 CONFLICT_RESOLVE (merge) 中直接覆写目标文件。若同步过程中进程崩溃或断电，文件可能处于半写入状态（损坏），丢失原始内容。

  对比：`settings_manager._save_config()` / `_save_storage()` 已使用原子写入（临时文件 + `os.replace()`），此处应保持一致。

- **依据**: ADR "hash 时效性原则" 要求写入后立即计算 hash，原子写入确保 hash 计算的输入完整。Performance Agent 独立确认。

- **修复建议**: 封装 `_safe_write_file(path, content_bytes)` 使用临时文件 + `os.replace()` 模式。

---

### Issue 3: gzip 解压无大小限制 — zip bomb 风险 [MEDIUM]

- **类型**: Security
- **置信度**: 80
- **位置**:
  - `lifeprism/server/api/sync_cloud_api.py:752` — push-files 端点
  - `lifeprism/sync/sync_client.py:678` — _pull_files_fetch
  - `lifeprism/sync/sync_client.py:932` — _fetch_remote_file_content
- **详情**:

  三处 `gzip.decompress(compressed)` 均未对解压后数据大小设限。gzip 最大压缩比 ~1032:1，10MB base64 输入可解压至 ~10GB 导致 OOM。云端 push-files 端点风险最高（攻击者持有 API Key 即可利用）。

- **依据**: OWASP 大文件上传防护。Security Agent 独立确认。

- **修复建议**: 三处统一添加 `max_size=50*1024*1024` 限制：
  ```python
  content_bytes = gzip.decompress(compressed)
  if len(content_bytes) > 50 * 1024 * 1024:
      raise ValueError("解压后文件超过 50MB 限制")
  ```

---

### Issue 4: sync_cloud_api.py 直接导入 providers 单例违反导入纪律 [MEDIUM]

- **类型**: Code Quality
- **置信度**: 80
- **位置**: `lifeprism/server/api/sync_cloud_api.py:30`
- **详情**:

  ```python
  from lifeprism.repository.providers import file_sync_state_provider
  ```

  API 层应通过 `from lifeprism.repository import file_sync_state_repository` 导入（走 `repository/__init__.py` 统一出口），当前绕过了统一出口直接依赖内部模块。

- **依据**: `docs/coding-rules/repository-module-rules.md` Section 2.2 "导入纪律——外部只能从 lifeprism.repository 导入"。Code Quality Agent 独立确认。

---

### Issue 5: Channel 层直接导入 Provider 类并调用私有方法 [MEDIUM]

- **类型**: Code Quality
- **置信度**: 80
- **位置**:
  - `lifeprism/llm/channel/wechat/channel.py:81-85` — 直接导入 `WechatAccountStateProvider` 类
  - `lifeprism/llm/channel/wechat/channel.py:192` — 直接导入 `QueryOptions`
  - `lifeprism/llm/channel/wechat/channel.py:195` — 调用 `self._account_state_provider._generic_query(options)`
- **详情**:

  Channel 层 (`llm/channel/wechat/`) 不属于 repository 模块，但直接依赖了 providers 内部实现和私有基类方法 `_generic_query`（protected 方法）。`WechatAccountStateProvider` 缺少 `get_all_states()` 公共方法导致调用方被迫直调私有方法。

- **依据**: `docs/coding-rules/repository-module-rules.md`。Code Quality Agent 独立确认。

- **修复建议**: 在 `WechatAccountStateProvider` 新增 `get_all_states()` public 方法封装 `_generic_query`，Channel 层通过 `from lifeprism.repository import wechat_account_state_repository` 导入。

---

### Issue 6: _EXCLUDED_FILENAMES 重复定义 [MEDIUM]

- **类型**: Code Quality
- **置信度**: 80
- **位置**:
  - `lifeprism/sync/sync_client.py:25`
  - `lifeprism/server/api/sync_cloud_api.py:46`
- **详情**:

  ```python
  _EXCLUDED_FILENAMES = {"chat_history.json"}
  ```

  在客户端和云端各自独立定义同一常量。如果未来排除列表变更，需要同时修改两处，容易遗漏。

- **依据**: DRY 原则。Code Quality Agent 独立确认。

- **修复建议**: 提取到 `lifeprism/sync/sync_config.py`（或 `lifeprism/sync/hash_utils.py`），两端共享。
  
  注意：sync_cloud_api 在服务端部署时不依赖 sync_client，建议将常量放在 `lifeprism/config/` 或新建 `lifeprism/sync/constants.py`。

---

### Issue 7: _refresh_current_hashes 逐文件 DB 读写 [LOW]

- **类型**: Performance
- **置信度**: 80
- **位置**: `lifeprism/sync/sync_client.py:454-489`
- **详情**:

  Pre-sync 阶段对每个文件执行独立的 `get_state()` + `upsert_state()` DB 操作。若目录下有 500+ 文件（session JSONL 持续时间增长），pre-sync 产生 1000 次独立 DB 往返。

  当前实际影响可能不大（启动时执行一次），但 session/ 目录随时间增长会逐步恶化。

- **依据**: Performance Agent 独立确认。

- **修复建议**: `FileSyncStateProvider` 新增 `batch_get_states(directory)` 和 `batch_upsert_states(states)` 方法，参考 `SyncRepository.batch_get_existing_updated_at()` 的批量实现。

---

### Issue 8: _scan_sync_files 被重复调用 [LOW]

- **类型**: Performance
- **置信度**: 80
- **位置**: `lifeprism/sync/sync_client.py:414-452` (定义), `:473` (第一次调用), `:1113` (第二次调用)
- **详情**:

  `_scan_sync_files()` 在 `_refresh_current_hashes()`（line 473）和 `_sync_files_full_flow()`（line 1113）中各调用一次。两次调用间仅有 HTTP check 请求，无本地文件变更，第二次遍历为纯冗余 I/O。

- **依据**: Performance Agent 独立确认。

- **修复建议**: `_refresh_current_hashes()` 返回扫描结果（`list[Path]`），`_sync_files_full_flow()` 复用而非再次扫描。

---

## 正面发现 (Positive Findings)

### 架构合规 (ADR v2.1)
- ✅ **决策 1**: per-file version tracking 完整实现 — file_sync_state 表 4 列匹配 ADR、11 状态矩阵实现全部 11 行
- ✅ **决策 2**: 白名单对齐 — SYNC_DIRECTORIES 4 目录、chat_history.json 排除
- ✅ **决策 3**: AI 冲突解决 — CONFLICT_RESOLVE 消息 + bus 桥接 + 工具权限正确（仅文件工具、无 DB 工具）
- ✅ **决策 4**: account.json → DB — 表结构匹配、迁移策略（→ .bak）、SYNC_TABLES 注册正确
- ✅ **决策 5**: 三阶段协议 — check/fetch/verify/commit 完整实现、hash 时效性保证、compute_file_hash 规范正确
- ✅ **file_sync_state 不在 SYNC_TABLES** (同步元数据通过 API 字段传递)
- ✅ **wechat_account_state 在 SYNC_TABLES** (记录级 LWW 同步)
- ✅ **原子锁并发控制**: `try_start_sync()` + `finish_sync()` 使用 `threading.Lock()` 正确保护

### 测试覆盖
- ✅ **Issue #30**: 8 项标准全部覆盖（DDL 注册、Provider CRUD、各种 hash 场景）
- ✅ **Issue #31**: 6 项标准全部覆盖（check/fetch/verify/commit 各场景）
- ✅ **Issue #32**: 3 项标准全部覆盖（hash 字段、file_sync_state 更新、不推进 parent）
- ✅ **Issue #33**: 9 项标准全部覆盖（PULL/PUSH/CONFLICT/SKIP/换电脑/空文档/Phase 3）
- ✅ **Issue #34**: 5 项标准全部覆盖（消息构建、桥接、全流程、超时/空内容）
- ✅ **Issue #35**: 3 项标准全部覆盖（CRUD、迁移、stop 保存）
- ✅ **Issue #36**: 4 项标准全部覆盖（启动同步、定时同步、run_mode 限制、并发控制）
- **总计：38/38 项验收标准全部有测试覆盖，零遗漏**

### 代码注释一致性
- ✅ 13/13 审查点注释与实现完全一致
- compute_file_hash "去除所有空白字符" → 实现一致
- CONFLICT_RESOLVE "仅文件工具" → 工具注册一致
- check 排除 chat_history.json → 排除逻辑一致
- verify "纯只读" → 无任何写操作

### 文档质量
- 新增模块 (hash_utils, file_sync_state_provider, wechat_account_state_provider) docstring 清晰
- database.py DDL 注释引用 ADR 决策良好
- main.py 启动/定时同步注释详细

## 变更摘要

**文件同步重构**实现了 ADR v2.1 的全部 5 个决策。架构合规度极高——11 状态矩阵、三阶段 API、AI 冲突解决、account.json DB 迁移全部与 ADR 一致。测试覆盖 38/38 项验收标准零遗漏。主要问题集中在三个领域：(1) **hash 碰撞风险** — `compute_file_hash` 过度规范化；(2) **数据可靠性** — 文件写入非原子操作 + gzip 无大小限制；(3) **导入纪律** — 3 处违反 repository-module-rules 导入规范。

## 总体评估

| 维度 | 评分 |
|------|------|
| 架构合规 | ✅ 完全符合 ADR v2.1 (5/5 决策) |
| 安全 | ⚠️ 1 个 MEDIUM (gzip zip bomb) |
| 可靠性 | ⚠️ 1 个 MEDIUM (非原子写入) |
| 正确性 | ⚠️ 1 个 HIGH (hash 碰撞) |
| 代码质量 | ⚠️ 3 个 MEDIUM (导入纪律) |
| 性能 | ⚠️ 2 个 LOW (DB 批量 + 重复扫描) |
| 测试覆盖 | ✅ 38/38 标准全部覆盖 |
| 注释合规 | ✅ 13/13 点注释与实现一致 |

**建议**: 优先修复 Issue 1 (HIGH hash 碰撞) 和 Issue 2-3 (MEDIUM 原子写入 + gzip 限制)，其他问题可后续迭代。
