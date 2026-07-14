# 数据同步链路未打通 + 文件 LWW 空文档反向覆盖风险

## 元信息

- **发生时间**: 2026-07-14
- **修复状态**: ❌ 待修复（严重生产级 bug，链路未打通 + 潜在数据丢失风险）
- **影响范围**: 数据同步全部链路（启动同步、定时同步、文件同步 LWW 冲突解决）
- **bug 类型**: 链路断开（启动流程缺失调用）+ LWW 算法设计缺陷
- **严重程度**: 严重（P0）
  - 链路断开：本地与云端数据无法自动同步，Spec 要求的"启动时同步"和"每 10 分钟定时同步"完全失效
  - 空文档覆盖：一旦打通链路，云端新部署自动创建的空文档会反向覆盖本地有内容的文档，造成数据丢失

## 触发规则

在以下场景时阅读此文档：
- 排查"本地与云端数据不一致"、"定时同步不执行"、"启动时未拉取云端新增数据"
- 检查 `SyncClient`、`start_scheduled_sync`、`sync_once` 是否被实际调用
- 任何"代码已实现但运行时不执行"的链路断开类 bug（实例化但未启动）
- 云端首次部署/新初始化后，本地文档被空文档反向覆盖
- 基于 `mtime` 的 LWW 文件冲突解决在"空文件 vs 有内容文件"场景下失效
- 涉及 `lifeprism/server/main.py` lifespan 启动顺序的修改
- 涉及 `lifeprism/sync/sync_client.py` 文件同步 LWW 逻辑的修改

## 问题描述

本 bug 由两个关联问题组成，必须**一起修复**：

### Bug 1: 数据同步链路未打通（启动/定时同步完全不执行）

**用户现象**：
- 本地启动后不会自动拉取云端新增数据
- 每 10 分钟的定时同步从未执行
- Spec 明确要求的"本地启动后自动执行一次完整同步"完全未实现
- 数据同步只能通过两个途径触发：
  1. 应用关闭时（[main.py:389](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L389)）
  2. 前端手动点击"同步"按钮（[sync_status_api.py:171](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_status_api.py#L171)）

**Spec 要求 vs 实际状态对照**（`docs/specs/2026-07-11-data-sync-spec.md:76-85`）：

| Spec 要求 | 实际状态 |
|-----------|---------|
| 本地启动后自动执行一次完整同步（pull → push） | ❌ 未实现 |
| 定时同步每 10 分钟执行一次 | ❌ 未实现 |
| 并发控制：同步中的新请求被跳过 | ✅ 已实现 |
| Pull：按表分批拉取，应用 LWW | ✅ 已实现 |
| Push：增量查询推送 | ✅ 已实现 |
| 无 updated_at 列的表直接全量覆盖 | ✅ 已实现 |
| 动态表自动发现 | ✅ 已实现 |
| 所有步骤成功后更新 last_sync_time | ✅ 已实现 |

### Bug 2: 文件 LWW 空文档反向覆盖风险（潜在数据丢失）

**用户现象（如果链路被打通后）**：
- 云端服务器重新拉取仓库首次运行 → 系统自动创建空文档（如 `diary/`、`docs/`、`plan/` 下的空文件）
- 这些空文档的 `mtime` 是**当前时间**（刚创建）
- 本地有内容的文档 `mtime` 是**历史时间**（更早）
- 按 LWW 逻辑：`local_mtime(旧) > remote_mtime(新)` 为 False → **云端空文档覆盖本地实文档** → 数据丢失

**风险触发条件**：
- Bug 1 修复后（链路打通）会立刻暴露此 bug
- 云端新部署 + 本地有内容 → 数据丢失
- 当前因 Bug 1 链路未打通，此 bug 被掩盖未暴露

## 代码位置

### Bug 1: 链路断点

**断点位置**：[lifeprism/server/main.py:324-335](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L324-L335)

```python
# 创建 SyncClient 实例（用于同步状态查询和手动触发同步）
try:
    from lifeprism.repository import lw_db_manager
    from lifeprism.repository.sync_repository import SyncRepository
    from lifeprism.sync.sync_client import SyncClient

    sync_repo = SyncRepository()
    app.state.sync_client = SyncClient(db_manager=lw_db_manager, sync_repository=sync_repo)
    logger.info("[STARTUP] SyncClient created")
    # ← 断点：此处缺失两行关键调用
except Exception as e:
    logger.warning("创建 SyncClient 失败: error=%s", e)
    app.state.sync_client = None
```

**缺失的两行代码**：

```python
# 1. 启动后台定时同步任务（每 10 分钟）
app.state.sync_client.start_scheduled_sync(600)
# 2. 启动时首次同步（异步执行，不阻塞启动）
asyncio.create_task(asyncio.to_thread(app.state.sync_client.sync_once))
```

**全仓库调用验证**：

| 方法 | 定义位置 | 生产代码调用次数 | 测试代码调用次数 |
|------|---------|---------------|---------------|
| `start_scheduled_sync` | `sync_client.py:132` | **0 次** | 1 次（test_scheduled_sync.py） |
| `sync_once`（启动时） | - | **0 次** | - |
| `sync_once`（关闭时） | - | 1 次（`main.py:389`） | - |
| `sync_once`（手动触发） | - | 1 次（`sync_status_api.py:171`） | - |

### Bug 2: LWW 文件冲突逻辑

**问题代码位置**：[lifeprism/sync/sync_client.py:611-618](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L611-L618)（客户端 pull）+ [lifeprism/server/api/sync_cloud_api.py:450-455](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L450-L455)（云端 push 接收）

```python
# sync_client.py: _write_file() 方法
if file_path.exists():
    local_mtime_ts = file_path.stat().st_mtime
    if local_mtime_ts > remote_mtime_ts:
        # 本地更新，跳过
        return False
# 否则用远程覆盖本地 ← Bug 2: 云端空文档 mtime 更晚时会反向覆盖本地有内容的文档
```

**问题根源**：LWW 只比较 `mtime`，不比较内容。`mtime` 反映"文件系统操作时间"而非"业务内容更新时间"。

## 发生原因

### Bug 1 根因：开发遗漏

`SyncClient` 类已实现 `start_scheduled_sync()` 和 `sync_once()`，但 `main.py` 的 lifespan 只完成了实例化，**忘记调用启动方法**。

可能的原因：
1. 开发时分阶段实现：先实现类，后接入启动流程，但接入步骤被遗漏
2. 测试代码只验证类的方法本身（`test_scheduled_sync.py` 直接调用 `start_scheduled_sync`），未验证 `main.py` 是否真的调用了
3. 现有的关闭时同步（`main.py:389`）和前端手动触发（`sync_status_api.py:171`）掩盖了"链路未打通"的体感，导致问题未暴露

### Bug 2 根因：LWW 算法对"空文件 vs 实文件"场景设计不周

LWW 文件冲突解决策略假设：
- mtime 晚 = 内容新

但在"云端新部署自动创建空文档"场景下，该假设不成立：
- mtime 晚（刚创建）但内容空
- 本地 mtime 早（历史创建）但内容完整

PRD 第 820-827 行已识别此风险（"为什么简单策略足够"）：
```
1. 云端 agent-only 不启动 dreaming（已确认）
2. 文件修改只来自会话（agent 处理消息）
3. 同一时间只有一端的 agent 在工作（本地在线则云端跳过）
4. 不会同时修改同一个文件
```

但 PRD 忽略了一个场景：**云端首次部署时系统初始化自动创建的空文档**（如 `data_initializer.py` 创建的空目录骨架、默认配置文件等），这些文件 mtime 是当前时间，会被当作"最新的云端修改"反向覆盖本地。

## 最佳方案

### Bug 1 修复方案（已确定）

在 [main.py:332](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/main.py#L332) 之后插入：

```python
# 启动后台定时同步（每 10 分钟）
try:
    sync_task = app.state.sync_client.start_scheduled_sync(600)
    logger.info("[STARTUP] Scheduled sync started (interval=600s)")
except Exception as e:
    logger.warning("[STARTUP] 启动定时同步失败: error=%s", e)

# 启动时首次同步（异步执行，不阻塞应用启动）
asyncio.create_task(asyncio.to_thread(app.state.sync_client.sync_once))
logger.info("[STARTUP] Initial sync triggered")
```

**注意事项**：
- 启动时同步必须用 `asyncio.create_task` 异步执行，否则会阻塞 lifespan 启动
- `start_scheduled_sync` 内部已用 `asyncio.create_task`，不需要再包一层
- 修复 Bug 1 前必须先修复 Bug 2，否则会立刻触发数据丢失

### Bug 2 修复方案（候选，待讨论）

⚠️ **以下方案需要讨论后选择**，不要直接实施。

#### 方案 A：云端首次部署不创建空文档（推荐）

修改 `lifeprism/repository/data_initializer.py` 和 `resource_initializer.py`：
- 云端（`main_agent_only.py`）启动时跳过文件型文档的初始化
- 改为：从本地首次同步拉取时自动创建目录结构

**优点**：
- 治本，从源头避免空文档
- 不修改 LWW 算法本身

**缺点**：
- 需要区分"云端首次启动"和"云端正常运行"
- 文件同步的目录自动创建逻辑已存在（`_write_file` 中 `file_path.parent.mkdir(parents=True, exist_ok=True)`），理论上不需要预创建

#### 方案 B：LWW 改为"mtime + 内容大小"双判断

修改 `_write_file` 和 `sync_push_files`：

```python
if file_path.exists():
    local_mtime_ts = file_path.stat().st_mtime
    local_size = file_path.stat().st_size

    if local_mtime_ts > remote_mtime_ts:
        return False  # 本地更新，跳过

    # 新增：本地内容比远程大时不覆盖（防止空文档覆盖实文档）
    remote_size = len(gzip.decompress(base64.b64decode(file_item["content"])))
    if local_size > remote_size:
        logger.warning("LWW 跳过（本地内容更大，疑似远程空文档）: %s", file_item["path"])
        return False
```

**优点**：
- 修改集中，只在 LWW 判断点加一层

**缺点**：
- 内容大小不等于内容质量，可能误判（如本地文档被精简但内容更优）
- 性能开销：每个文件都要解压计算大小

#### 方案 C：首次同步排除云端空文档

在 SyncClient 端识别"云端首次同步"场景（`last_sync_time` 为空）：
- 首次同步时只 push 本地到云端，不 pull 云端到本地
- 后续同步恢复正常双向

**优点**：
- 简单直接
- 符合"主备模式"语义：本地是主，首次部署时本地数据先推送到云端

**缺点**：
- 需要定义"首次同步"的判定逻辑
- 如果本地也是新部署，会丢失云端已有的数据（但本场景是主备模式，本地一定是主）

#### 方案 D：云端首次部署标记 + 本地拉取时识别

云端 `main_agent_only.py` 启动时写入一个 `.cloud_initialized` 标记文件，记录初始化时间。本地首次 pull 时识别此标记，跳过该时间点之前创建的云端文件。

**优点**：精确识别

**缺点**：实现复杂，需要修改协议

### 推荐组合

**Bug 1 + Bug 2 方案 A（云端不创建空文档）+ 方案 C（首次同步只 push）**

理由：
1. 方案 A 从源头消除问题
2. 方案 C 作为兜底，即使方案 A 漏掉某些文件也能保护本地数据
3. 两个方案都不修改 LWW 算法本身，影响范围可控

## 附录：业界参考方案调研（思源笔记）

为评估 Bug 2 修复方案，调研了思源笔记（`D:\desktop\软件开发\siyuan`）的文件同步机制。

### 思源同步架构总览

思源**完全不是 LWW**，而是基于 **git-like 内容寻址快照（snapshot）+ 3-way merge** 的设计。核心算法在外部 Go 模块 `github.com/siyuan-note/dejavu` 中。

### 与 LifePrism 的根本差异

| 维度 | LifePrism（当前） | 思源笔记 |
|------|------------------|---------|
| 同步模型 | LWW（最后写入获胜） | git-like 内容寻址快照 + 3-way merge |
| 比较依据 | mtime（文件修改时间） | 内容 hash |
| 冲突处理 | 直接覆盖（无冲突概念） | 保留双方版本，标记为 Conflict |
| 增量识别 | mtime > last_sync_time | 快照 diff（内容 hash 变化）|
| 加密保护 | HTTPS + API Key | 32 字节 AES 密钥 + 内容加密 |

### 思源为什么不会出现"空文档覆盖"问题

四重保护机制：

1. **基于内容 hash**：空文档与本地实文档 hash 不同，会触发合并逻辑而非直接覆盖
2. **3-way merge**：检测到"双方都修改"时会标记为冲突，而非用一方覆盖另一方
3. **加密密钥隔离**：新部署的 workspace 密钥不同，解密失败时同步直接终止
4. **快照 ID 校验**：即使 merge 完成也通过快照 ID 二次验证数据是否真变化

### 思源冲突处理核心设计

```
冲突判定 → 双方都修改同一文件且内容 hash 不同
   ↓
两种处理模式（由 GenerateConflictDoc 配置项控制）：
   ├─ 生成冲突副本（true）：冲突文件作为新文档插入，标题加 "Conflicted" 前缀
   └─ 仅备份历史（false，默认）：冲突文件备份到 history/{timestamp}-sync/
   ↓
两种模式都保留双方版本，绝不静默覆盖
```

冲突文档机制对应 issue：`https://github.com/siyuan-note/siyuan/issues/5687`，是正式设计而非补丁。

### 思源同步流程核心调用链

```
SyncData → syncData → syncRepoWithDNSRetry → syncRepo
  ↓
Step 1: newRepository() 创建 dejavu.Repo 实例
Step 2: indexRepoBeforeCloudSync()
        ├─ beforeIndex = repo.Latest()       // 同步前快照
        └─ afterIndex = repo.Index(...)      // 创建新快照（计算内容 hash）
Step 3: mergeResult = repo.Sync(ctx)
        └─ dejavu 内部 3-way merge
Step 4: dataChanged = beforeIndex.ID != afterIndex.ID || mergeResult.DataChanged()
Step 5: processSyncMergeResult()
        ├─ 处理 Conflicts（保留双方版本）
        ├─ 处理 Upserts（拉取的新文件）
        └─ 处理 Removes（删除的文件）
```

### 对 LifePrism 的启示（按改造成本递增）

#### 短期方案（1-2 天，最小改动）

**A. 加入内容 hash 比较**：LWW 判定前先比较内容 hash，若本地非空而云端为空则触发冲突而非覆盖

**B. "空文件保护"硬规则**：若云端文件 size 为 0 但本地有内容，直接拒绝写入并记录冲突

伪代码（参考思源 `repository.go:1823` 的 `mergeResult.DataChanged()` 思路）：

```python
local_hash = sha256(local_content)
cloud_hash = sha256(cloud_content)
if local_hash == cloud_hash:
    return  # 内容相同，跳过
if len(cloud_content) == 0 and len(local_content) > 0:
    # 云端空、本地非空 - 思源会触发冲突
    return mark_conflict()
# 仅当双方都有内容且 mtime 不同时才走 LWW
```

#### 中期方案（1-2 周）

**引入 sync point + 双向变更检测**：借鉴思源 `indexRepoBeforeCloudSync` 的 before/after index 设计：
- 每次成功同步后记录 `lastSyncToken`（本地与云端当时的 hash 列表）
- 下次同步时计算：
  - `localChanges = diff(lastSyncToken.localHashes, current.localHashes)`
  - `cloudChanges = diff(lastSyncToken.cloudHashes, current.cloudHashes)`
- 若某文件同时在 `localChanges` 和 `cloudChanges` 中 → 冲突
- 若仅在 `cloudChanges` 中 → 拉取
- 若仅在 `localChanges` 中 → 推送
- 若都不在 → 跳过

#### 长期方案（1-2 月）

**引入内容寻址存储**：直接采用类似 dejavu 的 git-like 快照机制：
- 文件内容 → SHA-256 hash → blob 存储
- 快照 = (文件路径 → hash) 映射树
- 同步 = 快照树 diff
- 冲突 = 同一文件路径在两棵快照树中指向不同 hash

可考虑直接复用 `github.com/siyuan-note/dejavu` 库（BSD-3-Clause 协议友好），或自研轻量版。

### 思源可借鉴的配套机制

1. **同步前打快照**：借鉴 `indexRepoBeforeCloudSync` (repository.go:2188)，每次同步前对本地数据打 hash 快照，便于回滚和冲突检测
2. **指数退避**：借鉴 `syncSameCount` (sync.go:1921-1934)，无变更时延长同步间隔，节省资源
3. **历史备份**：借鉴 `history/{timestamp}-sync/` (repository.go:1917)，每次同步前备份即将被覆盖的文件，作为最后兜底
4. **全局同步锁**：借鉴 `syncLock` + `isSyncing` (sync.go:519-522)，避免并发同步导致状态错乱
5. **错误退避**：借鉴 `autoSyncErrCount > 7` 时延迟 64 分钟 (sync.go:276-281)，避免持续失败打满云端

### 不建议照搬的点

- **WebSocket 感知同步** (sync.go:869-963)：需要专门的云端 WS 服务，LifePrism 若无此基础设施可暂缓
- **多 provider 支持**：思源支持 4 种云存储（SiYuan官方/S3/WebDAV/Local），LifePrism 当前架构若单一 provider 则无需此抽象
- **chunk-based 传输**：基于 `restic/chunker` 的分块传输对大文件友好，但小笔记类数据可暂不需要

### 思源调研相关文件路径

- 同步入口与调度：`D:\desktop\软件开发\siyuan\kernel\model\sync.go`
- 数据仓库核心逻辑：`D:\desktop\软件开发\siyuan\kernel\model\repository.go`
  - `syncRepo` 主同步函数：第 1748-1844 行
  - `syncRepoDownload` 仅下载：第 1463-1535 行
  - `syncRepoUpload` 仅上传：第 1537-1606 行
  - `bootSyncRepo` 启动同步：第 1610-1746 行
  - `indexRepoBeforeCloudSync` 同步前索引：第 2188-2239 行
  - `processSyncMergeResult` 合并结果处理：第 1870-2140 行
  - `newRepository` 仓库实例化：第 2241-2279 行
  - 冲突文档生成逻辑：第 1880-1919 行
- 同步配置：`D:\desktop\软件开发\siyuan\kernel\conf\sync.go`
- 同步 API：`D:\desktop\软件开发\siyuan\kernel\api\sync.go`
- AES 加密工具：`D:\desktop\软件开发\siyuan\kernel\util\crypt.go`
- 工作空间路径定义：`D:\desktop\软件开发\siyuan\kernel\util\working.go:356-358`
- 外部算法库：`github.com/siyuan-note/dejavu`（源码需从 GitHub 获取）

### 思源 hash 基础单位确认

经代码验证，思源的 hash 基础单位是**文件**，不是块：

- `file.Path` 是文件路径（如 `/20210808180117-6v0mkxr/data.sy`），见 `repository.go:215-216`、`266`
- 一个 `.sy` 文件 = 一个文档 = 一个 hash 单元
- 思源编辑器内部的"块"（block）是编辑器逻辑概念，不参与同步层 hash
- 代码里的 `checkChunks` 是**传输优化**（大文件分块传输，类似 git 的 packfile），不影响合并逻辑

**结论**：LifePrism 做文件级 hash 就够了，不需要块级。LifePrism 也没有块的概念，只能做文件级。

## 最终修复方案：per-file version tracking

基于思源方案的简化和讨论结论，采用 **per-file version tracking**（每文件版本追踪）方案。相对于完整 git-like snapshot 树，该方案改造范围更小，适合 LifePrism 主备模式。

### 设计核心

引入 `parent_hash` 和 `current_hash` 两个字段，每文件独立追踪版本：

- `parent_hash`：上次同步成功时的文件内容 hash（NULL 表示从未同步过）
- `current_hash`：最近一次本地计算的文件内容 hash

**关键不变量**：同步成功后，双方 `parent_hash` 必须一致且等于双方 `current_hash`。若不一致则不推进 parent，下次同步重试。

### 数据表设计

新建本地表 `file_sync_state`：

```sql
CREATE TABLE file_sync_state (
    file_path     TEXT PRIMARY KEY,        -- 相对 lifeprism_data_path 的路径
    parent_hash   TEXT,                    -- 上次同步成功时的文件内容 hash（NULL 表示从未同步过）
    current_hash  TEXT,                    -- 最近一次本地计算的文件内容 hash
    updated_at    TEXT                      -- 本地表记录更新时间
);
```

**注意**：这张表只在本地维护，云端也需要对称维护一张（云端也需要记录自己的 parent/current 状态）。

### hash 更新逻辑

**两个时机**：

#### 时机 A：同步前刷新 current_hash（被动扫描）

不需要实时监听文件系统。在每次同步开始前扫描 `SYNC_DIRECTORIES` 下所有文件，计算 current_hash，对比表中已有的 current_hash，更新变化的行。

```python
def refresh_current_hashes():
    """同步前刷新本地 current_hash"""
    for file_path in scan_all_sync_files():
        content_hash = sha256(read_bytes(file_path))
        existing = db.query("SELECT current_hash FROM file_sync_state WHERE file_path=?", [file_path])
        if not existing:
            # 新文件：parent=NULL, current=hash
            db.execute(
                "INSERT INTO file_sync_state (file_path, parent_hash, current_hash) VALUES (?, NULL, ?)",
                [file_path, content_hash]
            )
        elif existing.current_hash != content_hash:
            # 文件改了：更新 current_hash（parent_hash 不动）
            db.execute(
                "UPDATE file_sync_state SET current_hash=? WHERE file_path=?",
                [content_hash, file_path]
            )
```

#### 时机 B：同步成功后推进 parent_hash（带一致性校验）

```python
def commit_sync(file_path, final_content):
    """同步成功后，把 parent_hash 推进到 current_hash（需校验一致性）"""
    # 1. 校验双方数据一致
    local_verify = read_local(file_path)
    remote_verify = read_remote(file_path)
    if hash(local_verify) != hash(remote_verify):
        raise SyncInconsistencyError("同步后双方数据不一致，不推进 parent")
    
    # 2. 一致才推进 parent
    new_hash = hash(final_content)
    db_local.update(file_path, parent=new_hash, current=new_hash)
    db_remote.update(file_path, parent=new_hash, current=new_hash)
```

### 完整决策矩阵

覆盖所有可能的状态组合：

| # | 本地 parent | 本地 current | 云端 parent | 云端 current | 判定 | 处理 |
|---|-------------|-------------|-------------|--------------|------|------|
| 1 | NULL | A1 | 不存在 | - | PUSH | 推送本地到云端（本地新文件） |
| 2 | 不存在 | - | NULL | A2 | PULL | 拉取云端到本地（云端新文件） |
| 3 | NULL | A1 | NULL | A2 | CONFLICT | 双方都新建，冲突 |
| 4 | NULL | A1 | A | A | PULL | 本地从未同步，云端有历史 |
| 5 | A | A | NULL | A2 | PUSH | 云端从未同步，本地有历史 |
| 6 | A | A | A | A | SKIP | 双方都没改 |
| 7 | A | A1 | A | A | PUSH | 仅本地改 |
| 8 | A | A | A | A1 | PULL | 仅云端改 |
| 9 | A | A1 | A | A2 | CONFLICT | 双方都改且不同 |
| 10 | A1 | A1 | A2 | A2 | CONFLICT | parent 不一致，安全兜底 |
| 11 | A | A1 | A2 | A2 | CONFLICT | parent 不一致，安全兜底 |

**矩阵覆盖的边界场景验证**：

- **Bug 2 场景**（云端新部署空文档覆盖本地）= 情况 5：云端 NULL parent，本地有 A parent → PUSH，本地推送到云端，不会反向覆盖 ✅
- **换电脑场景**（新机器绑定云端拉数据）= 情况 4：本地 NULL parent，云端有 A parent → PULL，拉取云端到本地 ✅
- **parent 不一致**（网络中断或用户越界）= 情况 10/11 → CONFLICT 兜底 ✅

### 边缘场景分析

#### 场景"云端有 parent，本地没 parent，本地数据是正确的"

**结论：不存在**。原因：

如果本地没 parent，说明本地从未成功同步过。如果本地从未同步过，云端怎么会有 parent？云端的 parent 一定是某次同步时写入的，而那次同步必然涉及本地（双方同步）。所以"云端有 parent + 本地没 parent + 本地数据正确"这个组合自相矛盾。

**唯一可能的边缘场景**：用户手动把旧数据文件拷到新机器的 `lifeprism_data_path/`，跳过同步直接覆盖本地。这种属于用户越界操作，应由用户自负责任，系统不必保护。

#### 场景"云端和本地 parent 不一致"

**结论：理论上不存在，实际可能存在**。

- **理论上不存在**：每次同步成功后会同时推进两端的 parent，parent 应该始终一致
- **实际可能存在**：
  - 同步中途网络断开：本地 parent 已推进，云端 parent 未推进（或反过来）
  - 用户在云端直接修改文件（绕过同步机制），导致云端 parent 没更新但 current 变了

**处理策略**：parent 不一致时直接判定为 CONFLICT，安全兜底。因为 parent 不一致意味着"双方对'上次同步状态'的认知不一致"，无法做可靠的 3-way 合并。

### 冲突解决策略

推荐**策略 A：保留本地版 + 备份云端版到 history**：

```python
def resolve_conflict(file_path, local_content, remote_content):
    """冲突解决：本地为主，云端备份"""
    # 1. 备份云端版本到 history 目录
    backup_path = f"history/sync_conflict/{timestamp}/{file_path}"
    write_file(backup_path, remote_content)
    
    # 2. 本地版本保持不变（不覆盖）
    logger.warning("文件冲突，保留本地版，云端版备份至 %s", backup_path)
    
    # 3. 更新 parent_hash 为云端 current_hash（标记已处理，避免下次还报冲突）
    db.execute(
        "UPDATE file_sync_state SET parent_hash=? WHERE file_path=?",
        [remote_hash, file_path]
    )
```

**理由**：
- LifePrism 是主备模式（本地主，云端备），本地版应优先
- 备份云端版不丢数据，用户可手动恢复
- 不需要前端 UI 介入

### 空文件兜底检查

冲突判定已能覆盖空文档场景，但作为防御性编程，在 PULL 写入前加一道硬规则：

```python
def safe_pull_write(file_path, remote_content):
    """PULL 时写入前的兜底检查"""
    if file_path.exists():
        local_size = file_path.stat().st_size
        remote_size = len(remote_content)
        # 本地有内容，云端是空文件 → 拒绝覆盖，记日志
        if local_size > 0 and remote_size == 0:
            logger.warning(
                "拒绝空文件覆盖实文件: %s (local=%d bytes, remote=%d bytes)",
                file_path, local_size, remote_size
            )
            return False
    write_file(file_path, remote_content)
    return True
```

### 云端需要配合的改动

云端 `sync_cloud_api.py` 的 `pull-files` 和 `push-files` 需要返回/接收 hash 字段：

```python
# 云端 pull-files 响应增加 hash 字段
{
    "files": [
        {
            "path": "docs/diary.md",
            "content": "...",
            "mtime": "...",
            "parent_hash": "abc",   # 新增：云端记录的上次同步 hash
            "current_hash": "def"   # 新增：云端当前内容 hash
        }
    ]
}
```

云端也需要维护一张 `file_sync_state` 表（对称设计）。

### 同步主流程

```python
def sync_once_with_version_tracking():
    """带版本追踪的同步主流程"""
    # 1. 同步前刷新本地 current_hash
    refresh_current_hashes()
    
    # 2. 拉取云端文件列表（含 parent_hash 和 current_hash）
    remote_files = pull_remote_file_list()
    
    # 3. 对每个文件分类并执行
    for file_path in all_files:
        local_state = db.query(file_path)
        remote_state = remote_files.get(file_path)
        
        action = classify_change(local_state, remote_state)
        
        if action == "SKIP":
            continue
        elif action == "PUSH":
            push_file_to_remote(file_path)
            commit_sync(file_path, local_content)
        elif action == "PULL":
            if safe_pull_write(file_path, remote_content):
                commit_sync(file_path, remote_content)
        elif action == "CONFLICT":
            resolve_conflict(file_path, local_content, remote_content)
            commit_sync(file_path, local_content)  # 保留本地版
    
    # 4. 数据库表同步（原 SYNC_TABLES 逻辑保持不变）
    sync_database_tables()
```

### 方案优点

1. ✅ 彻底解决 Bug 2（空文档覆盖）— 通过 parent_hash 不一致识别为 CONFLICT
2. ✅ 解决换电脑场景 — 本地 NULL + 云端有 parent 时正确 PULL
3. ✅ parent 不一致时兜底 — 一律 CONFLICT
4. ✅ 同步后一致性校验 — 不一致时不推进 parent
5. ✅ 改造范围可控 — 新增一张表 + 修改 sync_client.py + 云端 API 加 hash 字段
6. ✅ 与现有 LWW mtime 逻辑兼容 — 可作为前置过滤，LWW 作为兜底

## 复用场景

此 bug 记录可供以下场景复用：

1. **链路断开类 bug 排查**：任何"代码已实现但运行时不执行"的问题，都应验证：
   - 实例化是否在启动流程中
   - 启动方法是否被调用
   - 全仓库搜索调用次数（排除测试代码）
   - 不要只看类是否定义，要看调用链是否打通

2. **LWW 类算法设计**：任何基于时间戳的冲突解决策略，需要考虑：
   - 时间戳是否反映"业务更新时间"（而非"文件系统操作时间"）
   - 空值/默认值场景（新建空对象 vs 旧实对象）
   - 是否需要内容比对作为兜底

3. **Spec 验收对照**：开发完成后必须对照 Spec 验收清单逐项验证，不能仅凭"代码已写"认为功能已实现

4. **PRD 风险识别**：PRD 中"为什么简单策略足够"的论证需要包含"首次部署/初始化"场景，不能只考虑稳态运行

## 相关文档

- PRD：`.scratch/linux-deployment-discussion/linux-deployment-prd.md`（P2 同步方案）
- Spec：`docs/specs/2026-07-11-data-sync-spec.md`
- Flow：`docs/flows/2026-07-11-data-sync-flow.md`
- 计划草稿：`.scratch/linux-deployment-discussion/issues-p2/06-scheduled-sync.md`

## 相关代码文件

- `lifeprism/server/main.py` — 本地启动入口（Bug 1 断点位置）
- `lifeprism/server/main_agent_only.py` — 云端启动入口（链路正确）
- `lifeprism/sync/sync_client.py` — SyncClient 实现（Bug 2 LWW 逻辑位置）
- `lifeprism/server/api/sync_cloud_api.py` — 云端同步 API（Bug 2 服务端 LWW 逻辑位置）
- `lifeprism/server/api/sync_status_api.py` — 状态查询和手动触发 API
- `lifeprism/repository/data_initializer.py` — 数据初始化器（Bug 2 方案 A 修改点）
- `lifeprism/repository/resource_initializer.py` — 资源初始化器（Bug 2 方案 A 修改点）

## 经验教训

### 为什么链路没打通却没被发现

1. **关闭时同步掩盖了问题**：`main.py:389` 的关闭时同步让用户在关闭应用时数据会被推送，给人一种"同步在工作"的错觉
2. **前端手动触发掩盖了问题**：用户可以通过前端按钮手动同步，进一步掩盖了"自动同步不工作"
3. **测试代码不验证启动流程**：`test_scheduled_sync.py` 直接调用 `start_scheduled_sync()`，没有验证 `main.py` 是否调用了它
4. **Spec 验收未对照实际**：Spec 写了"启动时自动同步"，但没有验收测试验证这一点

### 如何预防

1. **启动流程必须有调用链验证测试**：集成测试应启动真实 `main.py` 的 lifespan，验证 `SyncClient.start_scheduled_sync` 被调用
2. **Spec 验收必须对照实际代码**：每个验收点都要追溯到具体代码行
3. **LWW 算法设计必须考虑"空值/默认值"场景**：不能只考虑稳态
4. **PRD 风险论证必须包含"首次部署"场景**：不能只考虑正常运行场景
