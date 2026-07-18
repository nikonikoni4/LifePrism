# CONFLICT_RESOLVE LLM 工具化导致 behavior.md 被破坏

## 元信息

- **发生时间**: 2026-07-16 上午 07:45 左右
- **修复状态**: ❌ 待修复（严重生产级 bug，已紧急手动恢复 behavior.md，根因未消除）
- **影响范围**: 文件同步冲突解决全链路（所有非 JSONL 文件的 AI 合并）
- **bug 类型**: 架构设计缺陷（LLM 工具化失控）+ 缺乏数据备份兜底
- **严重程度**: 严重（P0）
  - **数据破坏**：LLM 在合并 behavior.md 时由于内容过长，输出被截断或被 LLM 自行"精简"，导致历史行为记录被永久丢失
  - **不可恢复**：冲突备份 `sync_conflict/{timestamp}/` 虽然保留了一份本地版本，但用户若未及时察觉，合并后的截断内容会被推送到云端，造成两端都被破坏
  - **设计通病**：CONFLICT_RESOLVE 分支给 LLM 注册了 6 个工具（包括 WriteFileTool/EditFileTool），LLM 可绕过 sync_client 直接修改文件，行为不可控

## 触发规则

在以下场景时阅读此文档：
- 排查"AI 合并文件后内容丢失/被截断/被精简"
- 修改 `lifeprism/llm/agent/loop.py` 中 `CONFLICT_RESOLVE` 分支的工具注册逻辑
- 修改 `lifeprism/sync/sync_client.py` 中 `_resolve_conflicts` 的 AI 合并调用
- 讨论"LLM 是否应该被赋予工具"或"LLM 工具调用边界"
- 设计文档冲突解决机制（diff / patch / 3-way merge / LLM 合并）
- 排查 `sync_conflict/` 备份目录未清理无限增长
- 评估"是否需要定时全量数据备份"作为最后兜底

## 问题描述

**用户现象**：
- 2026-07-16 上午 07:45 左右执行一次数据同步
- 同步过程中触发 `behavior.md`（位于 `D:\数据文档\lifeprismData\user\`）的 CONFLICT_RESOLVE 流程
- AI 合并完成后，本地 `behavior.md` 的历史行为记录被永久丢失
- 用户已手动紧急修复，但根因未消除，下次同步仍可能复现

**根因（最关键）**：
CONFLICT_RESOLVE 消息被送入 AgentLoop 时，注册了 6 个工具：

| 工具 | 风险 |
|------|------|
| `ReadFileTool` | LLM 可能重新读取本地文件而非使用消息中的内容 |
| **`WriteFileTool`** | **LLM 可绕过 sync_client 直接覆盖本地文件** |
| **`EditFileTool`** | **LLM 可直接编辑本地文件内容** |
| `FileTreeTool` | LLM 可能探索目录后做无关操作 |
| `SearchFileTool` | 同上 |
| `SearchStringTool` | 同上 |

**与 sync_client 逻辑冲突**：
- `sync_client._resolve_conflicts` 的设计假设：LLM 返回合并内容字符串，sync_client 调用 `_safe_write_file(local_file, merged_content.encode("utf-8"))` 原子写入
- 实际可能发生：LLM 调用 `WriteFileTool` 直接写入"精简版"内容，然后返回"已合并"消息；sync_client 接收到空内容或不完整内容继续写入
- 即使 sync_client 检查 `if not merged_content or not merged_content.strip(): continue`，LLM 返回的部分内容（非空但不完整）也会被写入

**触发 bug 的具体路径**（推测）：
1. behavior.md 是用户长期累积的行为记录，内容很长
2. CONFLICT_RESOLVE 消息体将完整 local_content 和 remote_content 嵌入 prompt（context 过长）
3. LLM 因 context 超限或自身倾向，输出"摘要版"或"截断版"合并内容
4. sync_client 用 `_safe_write_file` 覆盖本地文件，旧内容已被破坏
5. sync_client 在覆盖前虽有 `sync_conflict/{timestamp}/` 备份，但用户未必察觉

## 代码位置

### 1. LLM 工具注册（根因所在）

**位置**：[lifeprism/llm/agent/loop.py:492-499](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/loop.py#L492-L499)

```python
elif msg.type == MessageType.CONFLICT_RESOLVE:
    tool_registry.register(ReadFileTool())
    tool_registry.register(WriteFileTool())     # ← 根因 1：不应给写文件工具
    tool_registry.register(EditFileTool())      # ← 根因 1：不应给编辑文件工具
    tool_registry.register(FileTreeTool())       # ← 不必要的工具，可能让 LLM 跑偏
    tool_registry.register(SearchFileTool())     # ← 同上
    tool_registry.register(SearchStringTool())   # ← 同上
    tools: list[dict[str, Any]] = tool_registry.get_definitions()
```

**问题**：CONFLICT_RESOLVE 的职责是"接收两份内容 → 返回合并内容"，根本不需要任何文件工具。所有内容都已经在 InboundMessage 的 content 字段里。

### 2. sync_client 调用 LLM 合并

**位置**：[lifeprism/sync/sync_client.py:1156-1300](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1156-L1300)（`_resolve_conflicts` 方法）

关键流程：
1. 读取本地文件内容 `local_content`（[sync_client.py:1202](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1202)）
2. 获取远端文件内容 `remote_content`（[sync_client.py:1205](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1205)）
3. 构建 InboundMessage，把两份内容嵌入 prompt（[sync_client.py:1214-1232](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1214-L1232)）
4. 通过 bus.send 送入 AgentLoop（[sync_client.py:1235-1238](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1235-L1238)）
5. 等待结果 `merged_content`（[sync_client.py:1241](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1241)）
6. **备份本地版本到 sync_conflict/{timestamp}/（[sync_client.py:1255-1259](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1255-L1259)）**
7. 用 `_safe_write_file` 覆盖本地文件（[sync_client.py:1262](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1262)）

**问题 1**：第 6 步的备份在覆盖之前完成，理论上应该能保住本地版本。但用户在发现问题时未必意识到有这个备份目录，可能直接手动恢复或被新同步覆盖。

**问题 2**：第 3 步把两份完整文档嵌入 prompt，behavior.md 这类长文档会让 context 超限，LLM 可能：
- 截断输出
- 返回摘要而非合并内容
- 调用 WriteFileTool "清理"后再返回

### 3. 工具路径白名单（未阻止破坏）

**位置**：[lifeprism/llm/agent/tools/filesystem.py:22-48](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/llm/agent/tools/filesystem.py#L22-L48)（`_check_workspace_permission`）

```python
def _check_workspace_permission(self, file_path: str) -> tuple[bool, str]:
    if not self.allowed_dir_path:
        return True, ""
    file_path_obj = Path(file_path).resolve()
    for allowed_dir in self.allowed_dir_path:
        try:
            file_path_obj.relative_to(allowed_dir)
            return True, ""
        except ValueError:
            continue
    return (False, "没有权限访问该文件...")
```

**问题**：`settings.allowed_dir_path` 包含 `user/` 等同步白名单目录，`behavior.md` 落在 `user/` 下，因此 LLM 通过 WriteFileTool 可以直接覆盖它。白名单只防外部目录，不防"LLM 不该写的本目录文件"。

## 发生原因（根因分析）

### 根因 1：CONFLICT_RESOLVE 不应该给 LLM 任何工具

**设计原则违反**：CONFLICT_RESOLVE 是一个**纯文本合并任务**，输入是两份文本，输出是一份合并文本。这种任务应该是一次简单的 LLM 调用（参考 `MessageType.CLASSIFY` 分支的 `tools = []`），而不是 Agent Loop。

**对比 CLASSIFY 分支**：
```python
elif msg.type == MessageType.CLASSIFY:
    tools = []  # ← 正确做法：纯 LLM 调用，无工具
```

**为什么 CONFLICT_RESOLVE 没有这样做？**
推测原因：早期实现时直接复用了 CHAT 分支的工具集，没有思考"合并任务是否真的需要文件工具"。

### 根因 2：长文档 LLM 合并本身不可靠

behavior.md 这种用户长期累积的文档：
- 内容可能超过 LLM 上下文窗口
- LLM 倾向于"总结"而非"原样合并"
- LLM 无法保证字面级别的完整性

**LLM 合并适合的场景**：
- 短文档（< 4K tokens）
- 结构化文档（frontmatter + 短正文）
- 双方差异较小（少量行变更）

**LLM 合并不适合的场景**：
- 长文档（behavior.md、长期累积的日记）
- 半结构化文档（自由格式）
- 双方差异较大（大量行变更）

### 根因 3：缺乏数据备份兜底

**当前已有备份机制**：
- 数据库迁移前备份（`migration_runner.py:71-105`）：仅触发于 schema 升级，保留 3 个
- 配置文件迁移前备份（`config_migrator.py:117-141`）：仅触发于配置迁移
- 冲突解决前备份（`sync_client.py:1255-1259`）：备份到 `sync_conflict/{timestamp}/`，**无清理机制，永久保留**
- 文件损坏时备份（`wechat/auth.py:212-216`）：单点修复

**当前缺失的备份机制**：
- ❌ 定时全量备份（每天/每周备份整个 `lifeprism_data_path`）
- ❌ 文档目录备份（user/、agent/、diary/、session/）
- ❌ 异地备份（云端副本）
- ❌ 备份完整性校验（备份文件是否能成功恢复）
- ❌ 备份清理机制（除冲突备份外都缺少）

如果有一个"每天凌晨全量备份 user/"的机制，即使 AI 合并破坏了文件，也能从备份恢复。

## 修复方案

### 方案 A（最小修复，强烈推荐立即实施）：CONFLICT_RESOLVE 改为无工具纯 LLM 调用

**修改 `lifeprism/llm/agent/loop.py`**：

```python
elif msg.type == MessageType.CONFLICT_RESOLVE:
    # 纯文本合并任务，不赋予任何工具
    # 所有内容已在 InboundMessage.content 中提供，LLM 只需返回合并内容
    tools = []
```

**收益**：
- 消除 LLM 直接写文件的能力，行为可控
- LLM 只能通过 OutboundMessage 返回合并内容，由 sync_client 统一写入
- 复用 CLASSIFY 分支已验证的"无工具调用"模式

**风险**：
- 如果原代码中 LLM 通过 ReadFileTool 读取了本地文件并依赖该内容做合并，移除后 LLM 只能依赖 InboundMessage 中的内容。但实际上 InboundMessage 已经包含了完整 local_content 和 remote_content，无需额外读取。

### 方案 B（中期改造）：按文档大小分流冲突解决策略

在 `_resolve_conflicts` 入口加判断：

```python
def _resolve_conflicts(self, conflict_paths, remote_url, api_key):
    # ...
    for file_path in conflict_paths:
        local_content = local_file.read_text(encoding="utf-8")
        remote_content = self._fetch_remote_file_content(remote_url, api_key, file_path)
        
        # 新增：按内容大小分流
        total_chars = len(local_content) + len(remote_content)
        if total_chars > 8000:  # 阈值待讨论
            # 长文档：走 3-way merge 或保留双方版本
            # 不送 LLM，避免截断风险
            resolved_content = self._long_doc_conflict_resolve(file_path, local_content, remote_content)
        else:
            # 短文档：走 LLM 合并（无工具）
            resolved_content = self._llm_conflict_resolve(file_path, local_content, remote_content)
```

**长文档策略候选**：
- 保留本地版本（最保守，但可能丢失云端修改）
- 保留云端版本（同上）
- 双方拼接（local + "\n\n---\n\n" + remote，加冲突标记）
- 3-way merge（需要 base 版本，从 parent_hash 反查 git-like 历史）

### 方案 C（兜底）：实现数据备份机制（独立 spec）

参见 `docs/specs/2026-07-17-data-backup-spec.md`，包括：
- 每日定时全量备份 user/、agent/、diary/、session/
- 数据库每日定时备份（不仅迁移时）
- 备份保留策略（如每日保留 7 天、每周保留 4 周）
- 备份完整性校验

### 推荐实施顺序

1. **立即**（方案 A）：消除根因，1 行代码改动
2. **本周**（方案 C 第一阶段）：实现每日定时备份，作为兜底
3. **中期**（方案 B）：长文档分流，避免 LLM 合并长文档

## 验证方法

1. **方案 A 验证**：
   - 构造一个 behavior.md 冲突场景（本地 + 云端都修改）
   - 触发同步，观察 AgentLoop 日志是否仍调用工具
   - 验证合并后的文件内容完整、无截断

2. **方案 C 验证**：
   - 配置每日定时备份
   - 模拟 behavior.md 被破坏
   - 从备份恢复，验证内容完整

## 预防措施

1. **代码评审**：所有 `MessageType.XXX` 分支的工具注册，必须论证"为什么需要这个工具"，而非默认给全套工具
2. **LLM 工具白名单原则**：默认 `tools = []`，按需添加，而非默认全套
3. **长文档保护**：超过阈值的文件不送 LLM 合并，走兜底策略
4. **数据备份**：实现定时全量备份，作为最后兜底
5. **冲突备份清理**：sync_conflict/ 目录添加 30 天清理机制，避免无限增长

## 关联文档

- **数据备份 spec**：[docs/specs/2026-07-17-data-backup-spec.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-17-data-backup-spec.md)
- **文件同步 spec**：[docs/specs/2026-07-16-data-sync-files-spec.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/specs/2026-07-16-data-sync-files-spec.md)
- **冲突解决 ADR**：[docs/adr/2026-07-14-file-sync-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-14-file-sync-conflict-resolution.md)
- **类似 bug（空文档覆盖）**：[docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md)
