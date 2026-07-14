# CONFLICT_RESOLVE 消息类型 + AgentLoop 集成 + bus 桥接

**Status**: ready-for-agent
**Type**: AFK
**Created**: 2026-07-15

---

## Parent

`.scratch/linux-deployment-discussion/linux-deployment-prd.md` - P2 数据同步方案 - 文件同步冲突处理

## What to build

新增 CONFLICT_RESOLVE 消息类型，实现 SyncClient 检测到 MD 文件 CONFLICT 时通过 bus 发送给 AgentLoop，由 AI 合并两份文档。通过 `asyncio.run_coroutine_threadsafe()` 桥接 SyncClient 同步线程和 bus 异步事件循环。本 issue 补充 issue 33 中暂未实现的 CONFLICT 处理逻辑。

**ADR 参考**：`docs/adr/2026-07-14-file-sync-conflict-resolution.md` v2.1 决策 3

**需要实现的 5 个部分**：

### 1. 新增 MessageType

在 `lifeprism/llm/bus/events.py` 中新增（两处必须同步更新）：

```python
# events.py MessageType 是 plain class（不是 Enum），新增类属性即可
class MessageType:
    ...
    CONFLICT_RESOLVE = "conflict_resolve"

# events.py MESSAGE_TYPE 列表（InboundMessage.__post_init__ 校验依赖此列表）
MESSAGE_TYPE = [MessageType.CHAT, ..., MessageType.CONFLICT_RESOLVE]
```

**关键**：
1. MessageType 是 plain class（字符串常量），**不要改为 Enum**——改为 Enum 会破坏现有代码的 `is` 比较行为
2. 如果只加类属性不加 MESSAGE_TYPE 列表，InboundMessage 构建时 `__post_init__` 校验会抛 `ValueError`

### 2. InboundMessage 构建（Markdown 格式）

SyncClient 检测到 CONFLICT 时构建消息，content 使用 Markdown 格式（与 ADR 一致）：

```python
msg = InboundMessage(
    type=MessageType.CONFLICT_RESOLVE,
    content=f"## 文件冲突需要解决\n\n文件路径: {file_path}\n\n### 本地版本\n\n{local_content}\n\n### 云端版本\n\n{remote_content}\n\n### 合并指令\n\n请合并以上两份文档，保留双方的有效信息，生成一份完整的合并文档。",
    extra={
        "conflict_file_path": file_path,
        "system_prompt": "你是文档合并助手。请合并两份 Markdown 文档，保留双方的有效信息，移除重复内容，保持文档结构清晰。直接输出合并后的文档内容，不要解释。"
    }
)
```

**system_prompt**：通过 `extra["system_prompt"]` 传入。`context.py:build_system_prompt()` 对 CONFLICT_RESOLVE 走 else 分支返回 `extra.system_prompt`，无需新增分支。

**不走 session**：CONFLICT_RESOLVE 不保存到 `session/*.jsonl`。现有 `loop.py` 中 `if msg.type == MessageType.CHAT: session_manager.save_session(session)` 只对 CHAT 类型保存 session（loop.py:472-473, 492-493）。但 `auto_compact()` 内部也会调用 `save_session()`（loop.py:582），对所有消息类型生效。需在 `auto_compact()` 内部的 `save_session()` 调用前增加 `if msg.type == MessageType.CHAT:` 判断，确保 CONFLICT_RESOLVE 不触发 save_session。改动点集中在一个方法内，不影响 `_process_msg` 后续流程（session 对象照常创建和使用，只是不持久化）。

### 3. bus 桥接（run_coroutine_threadsafe）

SyncClient 在同步线程中通过 `asyncio.run_coroutine_threadsafe()` 将 `bus.send()` 提交到主线程的事件循环：

- main.py 创建 SyncClient 时传入 `asyncio.get_event_loop()` 引用
- SyncClient 保存为 `self._main_event_loop`
- 冲突解决时：`future = asyncio.run_coroutine_threadsafe(bus.send(msg), self._main_event_loop)` → `result = future.result(timeout=600)`
- SyncClient 拿到 OutboundMessage 后提取 AI 合并结果

**AI 合并结果处理**：
1. 提取 OutboundMessage.content 作为合并后的文档内容
2. 计算合并后内容的 new_hash = compute_file_hash(合并内容)
3. 冲突备份：将本地版本备份到 `sync_conflict/{timestamp}/{file_path}` 目录（不在 ALLOWED_DIRS 和 SYNC_DIRECTORIES 中，不会被同步）
4. 写入合并后的内容到本地文件
5. 更新 file_sync_state: current_hash = new_hash
6. 走 Phase 2c 推送合并结果到云端

**AI 合并失败处理**：
- `future.result(timeout=600)` 超时 → 保留本地版本（不做任何修改），记录 ERROR 日志，跳过该文件
- AI 返回空内容或异常内容 → 保留本地版本，记录 ERROR 日志，跳过该文件
- 下次同步时 parent_hash 不一致 → 再次触发 CONFLICT_RESOLVE

### 4. AgentLoop 工具注册

在 `lifeprism/llm/loop.py` 的 `_process_msg` 中新增 CONFLICT_RESOLVE 分支：
- 允许 AI 使用文件读写类工具（read_file、write_file 等）
- **不允许**使用数据库工具（防止 AI 修改同步状态）
- AI 合并完成后通过 OutboundMessage 返回合并结果

**串行处理**：多个文件同时 CONFLICT 时，串行处理（一次一个发送给 AI），防止单次 token 超限。

### 5. main.py 事件循环传入

- main.py 创建 SyncClient 时传入 `asyncio.get_running_loop()` 引用（`main.py:324-335` SyncClient 创建位置，在 lifespan async 函数内调用）：

```python
sync_client = SyncClient(
    ...,
    main_event_loop=asyncio.get_running_loop()
)
```

**与 issue 36 的协调**：issue 36 也修改 main.py 创建 SyncClient 的代码区域（启动 sync_once + start_scheduled_sync）。本 issue 先做 event_loop 传入，issue 36 在此基础上追加启动逻辑。两者修改同一代码区域但不冲突。

## Acceptance criteria

- [ ] MessageType.CONFLICT_RESOLVE 已定义
- [ ] MESSAGE_TYPE 列表同步更新（InboundMessage 构建不抛 ValueError）
- [ ] InboundMessage content 使用 Markdown 格式（## 文件冲突 + ### 本地版本 + ### 云端版本）
- [ ] system_prompt 通过 extra["system_prompt"] 传入
- [ ] CONFLICT_RESOLVE 不保存到 session（loop.py auto_compact 内部只对 CHAT 类型调用 save_session）
- [ ] main.py 创建 SyncClient 时传入事件循环引用（使用 `asyncio.get_running_loop()` 而非 `get_event_loop()`）
- [ ] SyncClient 通过 run_coroutine_threadsafe 调用 bus.send()
- [ ] future.result(timeout=600) 正确等待 AI 合并完成
- [ ] AI 合并结果：计算 new_hash → 备份本地版本 → 写入合并内容 → 更新 file_sync_state
- [ ] AI 合并失败/超时：保留本地版本，记录 ERROR 日志，跳过该文件
- [ ] AgentLoop 新增 CONFLICT_RESOLVE 分支处理
- [ ] AI 可使用文件读写工具，不可使用数据库工具
- [ ] 冲突备份：本地版本备份到 sync_conflict/{timestamp}/ 目录
- [ ] 多文件 CONFLICT 串行处理
- [ ] AI 合并结果写入本地后走 Phase 2c 推送（在 issue 33 跳过 CONFLICT 的基础上补充合并结果推送逻辑）
- [ ] 日志记录：冲突文件路径、AI 合并耗时、成功/失败
- [ ] 单元测试：InboundMessage 构建正确（Markdown 格式）
- [ ] 单元测试：MESSAGE_TYPE 列表包含 CONFLICT_RESOLVE
- [ ] 单元测试：run_coroutine_threadsafe 桥接正确
- [ ] 单元测试：AI 合并结果正确更新 file_sync_state
- [ ] 单元测试：AI 合并超时 → 保留本地版本
- [ ] 单元测试：AI 返回空内容 → 保留本地版本
- [ ] 集成测试：CONFLICT → AI 合并 → 推送 全流程

## Blocked by

- `.scratch/linux-deployment-discussion/issues-p2/33-sync-client-file-sync-full-flow.md` - SyncClient 文件同步全流程必须先就绪（CONFLICT 检测在 Phase 2a 矩阵判定中，本 issue 补充 33 暂未实现的 CONFLICT 处理）
