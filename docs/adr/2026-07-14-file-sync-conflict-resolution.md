---
version: 2.1
created_at: 2026-07-14
updated_at: 2026-07-15
last_updated: v2.1——新增决策 5（API 协议设计）+ hash 规范化策略
abstract: 文件同步采用 per-file version tracking（parent_hash + current_hash）替代纯 LWW mtime 比较。同步白名单对齐 Agent 工具白名单（ALLOWED_DIRS + session），chat_history.json 明确排除。MD 冲突由 AI 驱动解决（CONFLICT_RESOLVE 消息类型），替代用户手动处理。account.json 改为数据库存储从白名单移除。API 协议采用三阶段设计（check → fetch/push → verify），mtime 作为第一重过滤 + hash 作为精确判断。hash 计算去除所有空白字符以避免格式差异干扰。所有决策基于主备模式前提（同一时间只有一端 Agent 工作）。
status: decided
---

# 文件同步冲突处理方案：per-file version tracking + 白名单对齐 + 分流策略

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 2.1 | 新增决策 5：API 协议设计（三阶段 check/fetch/push/verify + hash 规范化策略） |
| 2.0 | 决策 3：MD 冲突改为 AI 驱动（CONFLICT_RESOLVE 消息类型）。决策 2：chat_history.json 明确排除同步。新增前提 7（user/ MD 由 AI 生成）、前提 8（chat_history.json 仅定时任务改写） |
| 1.0 | 创建文档初稿 |

## 问题界定

### 问题简述

当前文件同步使用纯 LWW（Last-Write-Wins）策略，只比较文件 mtime，存在严重缺陷：

1. **空文档覆盖**：云端新部署自动创建的空文档 mtime 为当前时间（比本地旧文档更新），按 LWW 规则会反向覆盖本地有内容的文档
2. **无法区分变更方向**：mtime 只能判断"时间先后"，无法区分"仅一方改"还是"双方都改"
3. **同步白名单过宽**：原 `SYNC_DIRECTORIES` 包含 Agent 不会变更的目录（docs/、assets/、prompts/、plan/、workflow/），浪费传输带宽且增加风险面
4. **account.json 文件同步脆弱**：微信对话状态（context_token、last_session_id）以文件形式同步，需要额外冲突处理

### 讨论范围

- 文件同步的增量识别机制（从 mtime 到 content hash）
- 同步白名单的确定（哪些目录需要同步，为什么）
- 冲突处理策略（不同文件类型的处理方式）
- account.json 的存储方式（文件 vs 数据库）

### 非讨论范围

- 数据库表同步（30 张静态表 + 动态表，已在 `2026-07-09-lww-conflict-resolution.md` 中决定）
- 同步启动和定时同步（属于 Bug 修复，见 `docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md`）
- 同步 API Key 安全（见 `docs/known-limitations/cloud-security-limitations.md`）

### 模糊信息的明确定义

- `per-file version tracking`：每文件独立追踪 parent_hash 和 current_hash，通过比较四个变量（本地 parent、本地 current、云端 parent、云端 current）做 3-way 判定。相对于完整 git-like snapshot 树，该方案改造范围更小。
- `content hash`：对文件内容做 SHA-256 哈希，用于判断文件内容是否变更。与 mtime 不同，hash 反映的是"业务内容"而非"文件系统操作时间"。
- `主备模式`：同一时间只有一个端的 Agent 在工作（本地在线则云端跳过消息处理）。不是 active-active 双写模式。

## 现状

- 文件同步当前使用纯 LWW mtime 比较（`sync_client.py:611-618`、`sync_cloud_api.py:450-455`）
- 原 `SYNC_DIRECTORIES` 包含 11 个目录/文件
- 已确认当前同步链路未打通（`main.py` SyncClient 实例化后未调用启动方法）
- 已调研思源笔记的 git-like snapshot + 3-way merge 方案作为参考

## 决策前提

列出做出本次决策所依据的前提条件。

- **前提 1 — 主备使用模式**：同一时间只有一个端的 Agent 在工作。本机在线时，云端 Agent 不处理微信消息；云端所有数据变更都经过 Agent。并发写入不存在。

- **前提 2 — Agent 文件工具白名单不可绕过**：Agent 的 `write_file`、`edit_file` 等文件操作都经过 `_check_workspace_permission`，只允许操作 `ALLOWED_DIRS = ["user", "diary", "agent"]`。这意味着：
  - `session/` 目录的文件变更是 Agent 会话层产生的（间接写入，不走文件工具）
  - `docs/`、`assets/`、`prompts/`、`plan/`、`external_files/`、`workflow/` 等目录不会被 Agent 修改
  - **校验方式**：查看 `filesystem.py` 中 `_check_workspace_permission` 的调用

- **前提 3 — 云端 agent_only 无前端 API**：云端 `main_agent_only.py` 只注册 `sync_cloud_router`，不注册任何业务 API（如 plan API、diary API）。因此 `plan/` 目录在云端不会被前端修改。

- **前提 4 — 云端 agent_only 无 dreaming task**：云端 agent_only 没有 `ScheduleService`，不执行 dreaming task。`chat_history.json` 由 dreaming task 写入，云端不会产生变更。

- **前提 5 — 主备切换间隔大于时钟偏差**：本机关闭到云端 Agent 实际开始处理数据之间的真实时间间隔，大于云端与本机的系统时钟偏差（继承自 `2026-07-09-lww-conflict-resolution.md` 前提 3）。

- **前提 6 — 冲突只能在本地解决**：云端 agent_only 无前端 UI，用户无法在云端对比两个版本的文件。本地有前端 UI，用户可以打开文件夹对比并手动合并。

- **前提 7 — user/ 下 MD 文件均由 AI 生成**：`user.md`、`behavior.md`、`recent_state.md`、`psychological_model/**/*.md`、`narrative/*.md` 均由 Agent（CHAT 或 DREAM_TASK）通过 write_file/edit_file 工具写入，用户不直接编辑这些文件。冲突内容本质上都是"AI 生成的"，AI 最理解内容语义。
  - **校验方式**：ALLOWED_DIRS 为 `["user", "diary", "agent"]`，用户无前端编辑器可直接编辑这些目录下的 MD 文件。所有文件变更只能通过 Agent 工具。

- **前提 8 — chat_history.json 仅由定时任务改写**：`chat_history.json` 由 dreaming task（`MessageType.DREAM_TASK`）定时写入。云端 agent_only 不启动 dreaming task（已有前提 4），不会产生变更。因此不需要纳入同步范围。

## 可选方案

### 方案 A：纯 LWW mtime（当前方案，否决）

每个文件只比较 mtime，谁更新谁保留。

**优势**
- 实现极简
- 不需要额外存储

**劣势**
- 无法区分"仅一方改"还是"双方都改"
- 空文档（mtime 新）会反向覆盖实文档（mtime 旧）
- mtime 反映文件系统操作时间而非业务内容更新时间
- 换电脑场景（新机器本地空，云端有数据）判定不准确

### 方案 B：完整 git-like snapshot 树（参考思源笔记，否决）

引入类似 git 的内容寻址快照系统，每个快照有 parent 指针，通过快照树 diff 做 3-way merge。

**优势**
- 冲突检测最准确
- 可以做到行级 diff 自动合并

**劣势**
- 改造成本极大（引入 dejavu 库或自研类似系统）
- 对主备模式过度设计
- 思源的核心算法在外部 Go 库中，无法直接复用

### 方案 C：per-file version tracking（选中）

每文件独立追踪 parent_hash 和 current_hash，通过四个变量做 3-way 判定。同步白名单对齐 Agent 工具白名单。冲突按文件类型分流。

**优势**
- 彻底解决空文档覆盖问题（parent_hash 不一致时立即识别为 CONFLICT）
- 改装范围可控（新增 `file_sync_state` 表 + 云端 API 加 hash 字段）
- 冲突检测比纯 LWW 准确得多
- 白名单收紧减少传输量

**劣势**
- 需要维护 `file_sync_state` 表（两端各一张）
- 每次同步前需要扫描文件计算 hash
- 不做行级 diff 自动合并，冲突需要用户手动处理

## 决策逻辑

以下展开各决策点与前提的映射关系。

---

### 决策 1：采用 per-file version tracking（parent_hash + current_hash）

**前提依赖**：前提 1（主备模式）、前提 5（时钟偏差）

**选择逻辑**：在主备模式下（并发写入不存在），不需要完整的 snapshot 树（方案 B）。但纯 LWW（方案 A）依赖 mtime，无法处理"空文档覆盖"这种 mtime 不可信场景。方案 C 用 content hash 替代 mtime，通过比较两端 parent_hash 是否一致判断变更方向，准确度和改造成本之间取平衡。

**完整决策矩阵**（11 种状态组合）：

| # | 本地 parent | 本地 current | 云端 parent | 云端 current | 判定 | 处理 |
|---|-------------|-------------|-------------|--------------|------|------|
| 1 | NULL | A1 | 不存在 | - | PUSH | 本地新文件，推送到云端 |
| 2 | 不存在 | - | NULL | A2 | PULL | 云端新文件，拉取到本地 |
| 3 | NULL | A1 | NULL | A2 | CONFLICT | 双方都新建同路径文件 |
| 4 | NULL | A1 | A | A | PULL | 本地从未同步（如换电脑），云端有历史 |
| 5 | A | A | NULL | A2 | PUSH | 云端从未同步（如新部署），本地有历史 |
| 6 | A | A | A | A | SKIP | 双方都没改 |
| 7 | A | A1 | A | A | PUSH | 仅本地改 |
| 8 | A | A | A | A1 | PULL | 仅云端改 |
| 9 | A | A1 | A | A2 | CONFLICT | 双方都改且内容不同 |
| 10 | A1 | A1 | A2 | A2 | CONFLICT | parent 不一致（网络中断导致） |
| 11 | A | A1 | A2 | A2 | CONFLICT | parent 不一致（用户越界操作） |

**关键边界场景**：

| 场景 | 矩阵行 | 判定 | 说明 |
|------|-------|------|------|
| **Bug 场景**：云端新部署空文档覆盖本地 | #5 | PUSH | 云端 parent=NULL，本地 parent=A → 本地推送，不会反向覆盖 ✅ |
| **换电脑**：新机器绑定云端拉数据 | #4 | PULL | 本地 parent=NULL，云端 parent=A → 拉取 ✅ |
| **parent 不一致**：网络中断或用户越界 | #10/11 | CONFLICT | 兜底策略 ✅ |
| **新文件无冲突**：本地新建，云端无此文件 | #1 | PUSH | 正常推送 |
| **新文件冲突**：双方都新建了同路径 | #3 | CONFLICT | UUID 碰撞等极端情况 |

**边缘场景分析**：

- **"云端有 parent，本地没 parent，本地数据是正确的"**：**不存在**。如果本地从未同步过（没 parent），云端不可能有 parent（parent 是成功同步时写入的）。唯一例外是用户手动拷贝文件跳过同步——属于越界操作，系统不保护。
- **"云端和本地 parent 不一致"**：理论上不应存在（同步成功时两端同时推进），但实际可能发生（同步中断、用户越界修改云端文件）。直接判 CONFLICT。
- **"文件被删除"**：当前 Agent 没有通用 delete_file 工具（前提 2 的延伸——Agent 文件工具只有 write_file、edit_file、read_file 等，不含删除）。因此 11 状态矩阵不覆盖"文件之前同步过（parent 有值）但现在文件不存在"的场景。如果未来 Agent 新增删除文件能力，或 session 清理逻辑删除文件，需要扩展矩阵覆盖"parent 有值但文件不存在"的状态组合（如：本地删 → 通知云端删 + 清理 file_sync_state；云端删 → 通知本地删 + 清理 file_sync_state）。

**hash 更新逻辑**：

- **同步前**：扫描 `SYNC_DIRECTORIES` 下所有文件，刷新 `current_hash`。新文件 parent=NULL，已存在但内容变化的只更新 current_hash（parent 不动）。
- **同步后**：校验双方内容一致后才推进 `parent_hash = current_hash`。不一致则不推进，下次同步重试。

**数据表存储位置**：

`file_sync_state` 存储在 `localData/dataset/lifewatch_ai.db` 中，与业务表同一个数据库。本地和云端均需对称维护。**不加入 `SYNC_TABLES`**（[sync_client.py:25](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L25)）——它是同步元数据，`parent_hash` 和 `current_hash` 通过 pull-files/push-files API 扩展字段传递，不在数据库同步链路中传输。

**职责分层**：

- **Repository 层**：在 `lifeprism/repository/providers/` 下新建 `file_sync_state_provider.py`，继承 `LWBaseDataProvider`，**只做纯 CRUD**——定义 `_TABLE_NAME = "file_sync_state"`、`_PRIMARY_KEY = "file_path"` 等元数据。方法仅包含 `get_state()`、`get_all_states()`、`upsert_state()`、`delete_state()`。不包含 hash 计算、矩阵判定等同步业务逻辑。
- **Sync 层**：hash 刷新、11 状态矩阵判定、parent_hash 推进等同步业务逻辑内联在 `SyncClient` 中（作为 private 方法），调用 `FileSyncStateProvider` 做 CRUD，调用 `compute_file_hash()` 工具函数算 hash。不新建独立的 `FileSyncManager` 类——SyncClient 是文件同步的唯一入口，这些逻辑是同步流程的内联步骤，不是独立可复用的模块。
- **`compute_file_hash()`** 作为独立工具函数，放在 `lifeprism/sync/` 或 `lifeprism/utils/`。Provider、SyncClient、API handler 均可直接调用。

---

### 决策 2：同步白名单对齐 Agent 工具白名单

**前提依赖**：前提 2（Agent 文件工具白名单不可绕过）、前提 3（云端无前端 API）、前提 4（云端无 dreaming）

**选择逻辑**：同步白名单应该只包含会被 Agent 修改的目录。既然 Agent 只能修改 `ALLOWED_DIRS` 内的文件，同步白名单就应该以此为基准。额外加上 `session/`（Agent 会话层自然写入，不走文件工具但确实被 Agent 修改）。

**最终白名单**：

```python
SYNC_DIRECTORIES = [
    "session/",   # 聊天会话 JSONL（Agent 会话层写入）
    "diary/",     # 日记 MD（Agent write_file/edit_file）
    "agent/",     # Agent 身份/记忆/chat 配置（Agent write_file/edit_file）
    "user/",      # 用户级数据（Agent write_file/edit_file）
]
```

**排除项及理由**（按"前提失效时需重新评估"记录）：

| 目录 | 排除理由 | Agent 变更前提 |
|------|---------|---------------|
| `docs/` | 系统说明文档，由 `resource_initializer.py` 从 template 复制，Agent 不可操作 | Agent 写入权限扩展到此目录时需重新评估 |
| `assets/` | VLM 能力测试图（猫咪图），由 template 复制，Agent 不可操作 | Agent 写入权限扩展到此目录时需重新评估 |
| `prompts/` | 系统提示词，由 template 复制，Agent 不可操作 | Agent 写入权限扩展到此目录时需重新评估 |
| `plan/` | 前端 API 管理 + 数据库绑定 md，Agent 不可操作（不在 ALLOWED_DIRS）。云端无前端 API，不会变化 | Agent 需读写 plan 文件时，先加入 ALLOWED_DIRS 再纳入同步白名单 |
| `external_files/` | 未投入使用 | 投入使用后按文件类型评估 |
| `workflow/` | 已弃用 | 重新启用后评估 |
| `channel/wechat/account.json` | 改数据库存储（决策 4），从文件白名单移除 | - |

**白名单内文件的变更来源**：

| 目录 | 谁写 | 云端会变吗 | 场景 |
|------|------|-----------|------|
| `session/` | Agent 会话层 | 会（云端 Agent 处理微信消息时写入） | 主备切换 |
| `diary/` | Agent write_file | 会（云端 Agent 处理消息时可以读写） | 主备切换 |
| `agent/` | Agent write_file | 会（云端 Agent 处理消息时可以读写） | 主备切换 |
| `user/` | Agent write_file | 会（除 chat_history.json，它已被排除） | 主备切换 |

**`agent/` 特殊说明**：`resource_initializer.py` 初始化时若 `agent/chat` 目录已存在会跳过 `bootstrap.md` 复制，因此首次部署不会创建空 bootstrap.md 覆盖已有内容。

**`user/` 中的 `chat_history.json`**：由 dreaming task 写入（前提 8），云端无 dreaming task 不会变更。**明确从同步白名单排除**，在文件扫描时按文件名过滤跳过。

---

### 决策 3：MD 冲突由 AI 驱动解决（新增 CONFLICT_RESOLVE 消息类型）

**前提依赖**：前提 1（主备模式）、前提 7（user/ MD 由 AI 生成）、前提 6（冲突只能在本地解决）

**选择逻辑**：user/ 下的 MD 文件全部由 AI 生成——`user.md`、`behavior.md`、`recent_state.md`、`psychological_model/**/*.md`、`narrative/*.md`——用户不直接编辑。当这些文件发生冲突时，两份冲突内容本质上都是"AI 写的"，AI 最理解内容语义，能做出比用户更好的合并决策。因此不需要用户手动介入，直接将两份文档交给 AI 合并即可。

**按文件类型的分流策略**：

| 文件类型 | 策略 | 理由 |
|---------|------|------|
| `session/*.jsonl` | 文件级 LWW（整体覆盖，按最终 hash 或 mtime 取最新） | 追加式写入，每行有 timestamp，冲突场景下"各加一行"合并容易。文件级 LWW 取最新版本不丢独立记录 |
| `agent/`/`diary/`/`user/` 下 `.md` | **AI 冲突解决**（CONFLICT_RESOLVE 消息类型） | 全部由 AI 生成（前提 7），AI 最理解内容语义。可通过 read_file 阅读相关上下文做智能合并 |
| `account.json`（过渡期） | 保留本地版 + 备份云端版 | 改为数据库后不再走文件同步 |

**新增消息类型 CONFLICT_RESOLVE**：

在 `lifeprism/llm/bus/events.py` 的 `MessageType` 中新增：

```python
class MessageType:
    # 已有类型...
    CONFLICT_RESOLVE = "conflict_resolve"  # 同步冲突解决
```

**工具权限**（在 `AgentLoop._process_msg` 中新增分支）：

```python
elif msg.type == MessageType.CONFLICT_RESOLVE:
    tool_registry.register(ReadFileTool())        # 读相关上下文
    tool_registry.register(WriteFileTool())        # 写合并结果
    tool_registry.register(EditFileTool())         # 编辑合并
    tool_registry.register(FileTreeTool())         # 查看目录
    tool_registry.register(SearchFileTool())       # 搜索文件
    tool_registry.register(SearchStringTool())     # 搜索内容
    tools = tool_registry.get_definitions()
```

工具注册仅包含文件读写类工具，**不包含**数据库工具（UserActivitySummary、UserMoodCreate 等）和 Session 工具（QuerySessionHistory 等）——冲突解决只处理文件合并，不需要访问数据库。

**消息构建与处理**：

SyncClient 检测到 CONFLICT 时构建 InboundMessage：

```python
msg = InboundMessage(
    type=MessageType.CONFLICT_RESOLVE,
    content=f"""## 文件冲突需要解决

文件路径：{file_path}

### 本地版本（当前保留的版本）
{local_content}

### 云端版本（备份的版本）
{remote_content}

### 任务
请阅读以上两份文档，结合相关上下文（可以使用 read_file 读取相关文件），
决定如何合并。合并完成后使用 write_file 写入最终版本到：{file_path}
""",
    extra={
        "conflict_file_path": file_path,
        "local_hash": local_hash,
        "remote_hash": remote_hash,
    },
)
```

两份文档内容直接内联在 content 中，AI 不需要用 read_file 去读冲突文件本身。read_file 是用来读**相关上下文**的——比如 `user/user.md` 冲突时，AI 可以读 `daily_data/recent_state.md`、`daily_data/behavior.md` 来理解当前用户状态，做出更好的合并决策。

**冲突备份路径**：

```python
lifeprism_data_path/
└── sync_conflict/
    └── 20260714_153000/           # 同一批次同步的时间戳
        └── user/user.md            # 保持相对路径结构
```

**设计理由**：
- 不在 SYNC_DIRECTORIES（session/diary/agent/user）中，不会被再次同步，避免递归冲突
- 不在 ALLOWED_DIRS（user/diary/agent）中，AI 的 read_file 无法访问——AI 通过 message 内联内容拿到冲突文件，备份目录只做安全兜底
- 命名清晰，可追溯是哪次同步产生的冲突

**完整冲突解决流程**：

```
SyncClient 检测到 CONFLICT (MD 文件)
    ↓
1. 云端版本备份到 sync_conflict/{timestamp}/{relative_path}
    ↓
2. 构建 InboundMessage(type=CONFLICT_RESOLVE)
    - content: 两份文档内联 + 合并任务说明
    - extra: file_path, local_hash, remote_hash
    ↓
3. 发送到 bus → AgentLoop._process_msg 处理
    - SyncClient 在同步线程中通过 `asyncio.run_coroutine_threadsafe(bus.send(msg), loop)` 
      将 async 的 bus.send() 提交到主线程事件循环，同步等待结果（future.result(timeout=600)）
    - 事件循环引用在 main.py 创建 SyncClient 时传入（`asyncio.get_event_loop()`）
    - bus 和 AgentLoop 零改动，继续在事件循环中运行
    - CONFLICT_RESOLVE 不走 session（不保存到 session/*.jsonl）
      这是系统内部任务，类似 DREAM_TASK，不是用户对话
    - AI 用 read_file 读相关上下文（可选）
    - AI 用 write_file 写合并结果到原路径
    ↓
4. AI 完成后，SyncClient 校验文件已更新
    - new_hash = compute_file_hash(合并后内容)
    - 更新 file_sync_state: parent_hash = new_hash
    ↓
5. 下次同步双方 parent_hash 一致 → SKIP
```

**跨线程桥接方式**：`asyncio.run_coroutine_threadsafe()`

SyncClient 的 `sync_once()` 是同步方法，通过 `asyncio.to_thread()` 在独立线程中运行。bus.send() 是 async 方法，在主线程事件循环中运行。使用 Python 标准库的 `asyncio.run_coroutine_threadsafe()` 将 async 调用提交到主线程事件循环，是官方设计的跨线程调用方式，非 hack。

```python
# SyncClient 中
def _resolve_conflict_via_ai(self, file_path, local_content, remote_content):
    msg = InboundMessage(type=MessageType.CONFLICT_RESOLVE, content=..., extra=...)
    future = asyncio.run_coroutine_threadsafe(bus.send(msg), self._main_event_loop)
    result = future.result(timeout=600)  # 阻塞等待 AI 完成，在同步线程中不影响主线程
    return result
```

**不选方案 B（SyncClient 改 async）的原因**：改动面大——pull/push 全部方法 + httpx 同步客户端都要改异步，违反"务实优先"和"改造范围可控"。

**AI 合并失败时的处理**：
- 保留本地版本（不做任何修改）
- 云端备份已在 sync_conflict/ 中
- 下次同步 parent_hash 不一致 → 再次触发 CONFLICT_RESOLVE

**多文件同时冲突**：串行处理，一个一个发 InboundMessage。避免 token 爆炸、且让 AI 专注处理每个文件。

---

### 决策 4：account.json 改为数据库存储

**前提依赖**：前提 1（主备模式）

**选择逻辑**：`account.json` 存储微信对话状态（context_token、last_session_id），是保证本地断开后云端继续对话的核心数据。当前以文件同步，需要额外冲突处理。改为数据库存储后，直接走已有的 `SYNC_TABLES` + 记录级 LWW 机制，零额外代码。

**数据库表设计**：

```sql
CREATE TABLE wechat_account_state (
    wechat_user_id  TEXT PRIMARY KEY,
    context_token   TEXT,
    last_session_id TEXT,
    updated_at      TEXT NOT NULL
);
```

- 以 `wechat_user_id` 为主键（当前实际只有单用户，但设计上支持多微信用户）
- **加入 `SYNC_TABLES`**，自动走数据库同步的记录级 LWW。由于该表在 SYNC_TABLES 中，本地和云端数据通过 pull/push 自动同步，无需走文件同步链路
- 现有 `WechatChannel._user_data` 改为从数据库读写（通过 `WechatAccountStateProvider` 访问）
- 从 `SYNC_DIRECTORIES` 移除 `channel/wechat/account.json`

**Provider 实现**：在 `lifeprism/repository/providers/` 下新建 `wechat_account_state_provider.py`，遵循现有模式（继承 `LWBaseDataProvider`），提供 `get_state()`、`save_state()` 等方法。

**迁移策略**：首次启动时检测 `account.json` 是否存在。若存在且数据库中无对应记录 → 读取 account.json → 写入 `wechat_account_state` 表 → 删除（或重命名）`account.json`。若表中已有记录 → 跳过迁移（以数据库为准）。

---

### 决策 5：API 协议设计——三阶段 check → fetch/push → verify

**前提依赖**：前提 1（主备模式）、决策 1（per-file version tracking）

**选择逻辑**：文件同步的 API 协议需要同时满足两个需求：(1) mtime 作为第一重过滤，快速排除未变更文件，避免 700+ 文件全量传输；(2) hash 作为精确判断，执行 11 状态决策矩阵。三阶段设计将"快照交换"（轻量）、"内容传输"（重量）、"一致性校验"（轻量）分离，每个端点职责单一。

**核心原则：hash 时效性**

> **发送 hash 或对比 hash 时，必须确保 hash 是最新的。**

hash 代表的是"文件此刻的内容状态"。任何时间点发送或比对 hash，都必须是此刻实时计算的——不能用缓存值、不能用历史值。具体来说：
- Phase 1（check）：两端在同步开始时计算 current_hash
- Phase 2b/2c（fetch/push）：写入文件后立即计算 current_hash 并更新 DB
- Phase 3（verify）：云端实时计算 current_hash 返回，本地也用刚计算的 current_hash 比对

**hash 规范化策略**

hash 计算前对文件内容做规范化处理，去除所有空白字符（空格、换行 `\n`、回车 `\r`、制表符 `\t` 等），避免格式差异导致 hash 不一致。

```python
import hashlib

def compute_file_hash(content: bytes) -> str:
    """计算文件内容的规范化 hash

    规则：去除所有空白字符后计算 SHA-256。
    源文件不受影响，仅 hash 计算时做规范化。
    """
    text = content.decode("utf-8", errors="replace")
    # 去除所有空白字符（空格、换行、回车、制表符等）
    normalized = "".join(text.split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
```

**设计理由**：
- 两端可能因操作系统差异（Windows `\r\n` vs Linux `\n`）导致内容字节不同但语义相同
- AI 编辑文件时可能调整格式（加空行、改缩进），只要文字内容不变，hash 应保持一致
- 源文件保持原始格式不变，仅 hash 计算时做规范化
- `.jsonl` 文件（session/）同理，去除空白后比较内容

**四个端点设计**

| 端点 | 方法 | 性质 | 职责 |
|------|------|------|------|
| `/api/sync/pull-files/check` | POST | 新增 | 云端按 mtime 过滤，返回变更文件的 {path, parent_hash, current_hash} |
| `/api/sync/pull-files/fetch` | POST | 新增 | 云端按路径返回文件内容（仅 PULL + CONFLICT 文件） |
| `/api/sync/pull-files/verify` | POST | 新增 | 云端实时计算 hash，用于 Phase 3 一致性校验 |
| `/api/sync/push-files` | POST | 改造 | 推送文件内容 + hash，云端写入并更新 file_sync_state |

所有端点保持 POST 方法，与现有 sync API 惯例一致（路径列表可能很长，放 body 比 URL 参数更合适）。

**Phase 1：快照交换 `POST /pull-files/check`**

同步开始时，两端都计算"此刻"的 current_hash。

```python
# Request
{
    "last_sync_time": "2026-07-14T08:00:00+00:00",
    "directories": ["session/", "diary/", "agent/", "user/"]
}

# Response
{
    "files": [
        {"path": "user/user.md",        "parent_hash": "abc123", "current_hash": "def456"},
        {"path": "diary/2026-07-13.md", "parent_hash": null,     "current_hash": "xyz789"}
    ],
    "sync_time": "2026-07-14T08:10:00+00:00"
}
```

云端逻辑：遍历 directories（排除 `chat_history.json`），找到 mtime > last_sync_time 的文件 → 实时计算 current_hash → 从 `file_sync_state` 表读 parent_hash → 返回。

**Phase 2a：本地执行 11 状态矩阵**

本地拿到云端 hash 后，结合自己的 `file_sync_state` 做比较（决策 1 的 11 状态矩阵），分出：

| 判定 | 处理 |
|------|------|
| PULL（仅云端改） | Phase 2b 拉取内容 → 写入本地 → 立即更新 current_hash |
| PUSH（仅本地改） | Phase 2c 推送内容 + hash |
| CONFLICT（双方改 / parent 不一致） | Phase 2b 拉取云端内容 → AI 合并 → Phase 2c 推送合并结果 |
| SKIP（都没改） | 不操作 |

**Phase 2b：拉取内容 `POST /pull-files/fetch`**

仅拉取 PULL 和 CONFLICT 文件的实际内容。

```python
# Request
{
    "paths": ["user/user.md", "diary/2026-07-13.md"]
}

# Response
{
    "files": [
        {"path": "user/user.md",        "content": "base64...", "parent_hash": "abc123", "current_hash": "def456"},
        {"path": "diary/2026-07-13.md", "content": "base64...", "parent_hash": null,     "current_hash": "xyz789"}
    ]
}
```

本地写入文件后**立即**计算新 current_hash 并更新 DB。

**Phase 2c：推送 `POST /push-files`**

推送 PUSH 文件 + AI 合并后的 CONFLICT 结果。

```python
# Request
{
    "files": [
        {"path": "agent/identity.md", "content": "base64...", "parent_hash": "old111", "current_hash": "new222"},
        {"path": "user/user.md",      "content": "base64...", "parent_hash": "abc123", "current_hash": "merged333"}
    ]
}

# Response
{
    "results": [
        {"path": "agent/identity.md", "action": "accepted"},
        {"path": "user/user.md",      "action": "accepted"}
    ],
    "sync_time": "..."
}
```

云端写入文件后**立即**计算新 current_hash 并更新 DB。

**Phase 3：一致性校验 `POST /pull-files/verify`**

Phase 2b/2c 完成后，验证两端文件内容一致。

```python
# Request
{
    "paths": [
        "user/user.md",        # PULL 过来的
        "agent/identity.md",   # PUSH 上去的
        "diary/2026-07-13.md"  # CONFLICT 合并的
    ]
}

# Response
{
    "files": [
        {"path": "user/user.md",        "current_hash": "xxx"},
        {"path": "agent/identity.md",   "current_hash": "yyy"},
        {"path": "diary/2026-07-13.md", "current_hash": "zzz"}
    ]
}
```

云端对 `paths` 中的文件**实时计算** current_hash（再次读取文件内容 → 规范化 → SHA-256）。

本地比较：
- 本地 current_hash（Phase 2b/2c 写入后刚更新的）== 云端 current_hash（Phase 3 刚返回的）
  - 一致 ✅ → `parent_hash = current_hash`（两端各自推进）
  - 不一致 ❌ → 不推进 parent，下次同步重试

**完整时间线**

```
Phase 1          Phase 2a     Phase 2b/2c              Phase 3
─────●──────────────●──────────────●──────────────────────●─────→
     │              │              │                      │
  两端快照      本地矩阵判定    pull写入→本地算hash      verify
  hash（此刻）                 push写入→云端算hash      比对→推进parent
```

**原 pull-files / push-files 端点的处理**

| 原端点 | 处理 |
|--------|------|
| `POST /pull-files` | 替换为 `/pull-files/check` + `/pull-files/fetch` |
| `POST /push-files` | 改造，新增 parent_hash + current_hash 字段 |
| 新增 `/pull-files/verify` | 新建 |

**涉及改动**

| 文件 | 改动 |
|------|------|
| `sync_cloud_api.py` | 替换 `/pull-files` 为 `/pull-files/check` + `/pull-files/fetch` + `/pull-files/verify`；改造 `/push-files` 增加 hash 字段 |
| `sync_client.py:pull_files_from_remote()` | 拆为三步：check → 本地矩阵判定 → fetch |
| `sync_client.py:push_files_to_remote()` | 改造：附带 parent_hash + current_hash |
| `sync_client.py` | 新增 Phase 3 verify 逻辑 + parent_hash 推进逻辑 |
| 新增 `compute_file_hash()` 工具函数 | 规范化 hash 计算（去除空白 + SHA-256） |

---

## 方案优点汇总

1. ✅ 彻底解决 Bug 2（空文档覆盖）—— 通过 parent_hash 判定为 CONFLICT 或 PUSH
2. ✅ 换电脑场景正确拉取 —— 本地 NULL + 云端有 parent 时判 PULL
3. ✅ parent 不一致兜底 —— 一律 CONFLICT
4. ✅ 同步后一致性校验 —— 不一致时不推进 parent
5. ✅ 白名单收紧减少传输量 —— 从 11 项减到 4 项，chat_history.json 明确排除
6. ✅ account.json 改数据库节省同步链路 —— 复用已有 LWW 机制
7. ✅ AI 自动合并替代用户手动 —— user/ 下 MD 全由 AI 生成，AI 最理解内容语义，无需用户介入
8. ✅ 改造范围可控 —— 新增 2 张表（`file_sync_state`、`wechat_account_state`，均在 `lifewatch_ai.db` 中）+ 2 个 Provider（`FileSyncStateProvider`、`WechatAccountStateProvider`）+ 云端 API 扩展 hash 字段 + 新增 CONFLICT_RESOLVE 消息类型
9. ✅ 三阶段 API 协议 —— mtime 第一重过滤（快速排除未变更文件）+ hash 精确判断（11 状态矩阵）+ verify 校验（推进 parent 前确认两端一致）
10. ✅ hash 规范化 —— 去除空白字符后计算 SHA-256，避免 OS 差异（`\r\n` vs `\n`）和格式调整导致 false positive

## 备选触发

以下前提失效时需重新评估对应决策：

| 前提失效 | 影响的决策 | 需重新评估 |
|---------|-----------|-----------|
| Agent 写入权限扩展（新增 ALLOWED_DIRS） | 决策 2（白名单） | 新目录是否纳入同步 |
| Agent 需要读写 plan 文件 | 决策 2（白名单） | plan/ 是否纳入同步 |
| 云端启用 dreaming task | 决策 2（白名单） | chat_history.json 是否需要重新纳入同步范围 |
| 多客户端场景（非主备） | 决策 1（per-file）+ 决策 3（冲突分流） | 是否需要完整 snapshot 树 + 行级 diff 自动合并 |
| `external_files/` 投入使用 | 决策 2（白名单） | 按文件类型评估是否纳入 |
| 用户开始直接编辑 user/ 下的 MD 文件 | 决策 3（AI 冲突解决） | AI 合并是否符合用户期望，是否需要恢复手动介入 |

## 相关文档

- Bug 记录（含思源调研）：[2026-07-14 数据同步链路未打通 + 文件 LWW 空文档反向覆盖](../history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md)
- 数据库 LWW 决策：`docs/adr/2026-07-09-lww-conflict-resolution.md`
- 安全限制：[cloud-security-limitations.md](../known-limitations/cloud-security-limitations.md)
- 思源源代码：`D:\desktop\软件开发\siyuan\kernel\model\repository.go`

## 相关代码文件

- `lifeprism/sync/sync_client.py` — SyncClient + SYNC_DIRECTORIES + 文件冲突逻辑
- `lifeprism/server/api/sync_cloud_api.py` — 云端文件同步 API（需扩展 hash 字段）
- `lifeprism/config/settings_manager.py` — ALLOWED_DIRS 定义
- `lifeprism/llm/agent/tools/filesystem.py` — Agent 文件工具权限检查
- `lifeprism/llm/channel/wechat/channel.py` — WechatChannel._user_data（改为数据库读写）
