# 首次同步后云端 parent_hash 未推进 — 导致冲突解决永远不触发

## 元信息

- **发生时间**: 2026-07-18（T4/T5/T6 端到端测试时发现）
- **发现时间**: 2026-07-18 23:47
- **修复状态**: ✅ 已修复并验证通过（2026-07-19）
- **影响范围**: 文件冲突解决全流程 — 首次同步后所有"双方修改同一文件"的 CONFLICT 场景永远无法触发，本地 PUSH 直接覆盖云端修改
- **bug 类型**: 设计缺陷 — 首次同步流程遗漏云端 parent_hash 推进步骤
- **严重程度**: 严重（P0）— 冲突解决功能完全失效，云端用户修改会被本地 PUSH 静默覆盖

## 触发规则

在以下场景时阅读此文档：
- 排查"文件冲突解决（diff3 + LLM 串行合并）永远不触发"
- 排查"矩阵判定 `PUSH=N, CONFLICT=0` 而非预期的 `CONFLICT=N`"
- 修改 `sync_client.py` 中 `_full_sync_to_cloud` 首次同步流程
- 修改 `_advance_local_parent_after_initial_sync` 方法
- 修改首次同步后的 parent_hash 推进逻辑
- 排查"本地 PUSH 覆盖了云端的修改"
- 修改 `/pull-files/commit` 端点调用时机

## Bug 简述

首次同步全清覆盖方案（ADR `2026-07-17-cloud-init-first-sync-full-clear.md`）的实施代码 [`_full_sync_to_cloud`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L325-L366) 在步骤 3 推送文件后，只调用了 [`_advance_local_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L491-L542) 推进**本地** parent_hash = current_hash，**未调用任何云端端点推进云端 parent_hash**。

结果：首次同步后两端 `file_sync_state` 状态不对称：
- 本地：parent_hash = H0, current_hash = H0
- 云端：parent_hash = **None**, current_hash = H0（[`/push-files`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L856-L931) 对新文件设 parent_hash=None）

当本地和云端都修改同一文件后，矩阵判定走 [Row 5 (PUSH)](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1230-L1231)（local_has_parent=True, remote_has_parent=False）而非 Row 9 (CONFLICT)，本地 PUSH 静默覆盖云端修改，冲突解决流程完全失效。

## 复用场景

此 bug 的根因（"首次同步后只推进本地状态而忘记推进云端状态"）可作为以下场景的设计参考：
- 任何"本地+云端"双端状态对称设计的首次初始化流程
- 涉及 [`_advance_local_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L491-L542) 的对称方法设计
- 评估首次同步的完整性（4 个步骤是否对称执行于两端）

## 代码位置

### Bug 发生位置

- **缺陷代码**：[`lifeprism/sync/sync_client.py` L325-L366 `_full_sync_to_cloud`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L325-L366)
  - 步骤 3 推送文件后，未调用云端 commit 端点
  - 步骤 4 直接 mark-initialized，跳过云端 parent_hash 推进

### 关联代码

- **本地推进方法**：[`_advance_local_parent_after_initial_sync` L491-L542](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L491-L542) — 只对本地 DB 做 batch_upsert_states
- **云端 push-files 行为**：[`sync_cloud_api.py` L856-L931](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L856-L931) — 新文件 `preserved_parent_hash = None`，仅写入 current_hash
- **云端 commit 端点**：[`sync_cloud_api.py` L792-L850](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L792-L850) — 推进 parent_hash = current_hash，但首次同步流程未调用
- **矩阵判定**：[`_decide_sync_action` L1169-L1255](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1169-L1255) — Row 5 分支为 bug 触发路径

## 发生原因

### 1. 设计遗漏

[`_full_sync_to_cloud`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L325-L366) 的 4 步流程：

```
步骤 1/4: 清空云端数据（/full-clear）
步骤 2/4: 全量推送数据库（/push）
步骤 3/4: 全量推送文件（/push-files）+ _advance_local_parent_after_initial_sync
步骤 4/4: 更新 last_sync_time + mark-initialized
```

步骤 3 只推进本地 parent_hash，忘记推进云端 parent_hash。

### 2. `/push-files` 端点的隐含假设

[`/push-files`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/server/api/sync_cloud_api.py#L856-L931) 注释明确写道：

```python
# push-files 不推进 parent_hash（由 commit 端点负责）
# 新文件：parent_hash = NULL；已有记录：保持原 parent_hash 不变
preserved_parent_hash = existing_state["parent_hash"] if existing_state else None
```

设计意图是 parent_hash 推进由 `/pull-files/commit` 端点负责（在 [`_verify_and_advance_parent` L1448-L1559](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1448-L1559) 中调用）。但首次同步流程**未调用** `_verify_and_advance_parent`，导致云端 parent_hash 永远停留在 None。

### 3. `_advance_local_parent_after_initial_sync` 注释的误导

方法注释写道：

```python
# 推进后：
# - 本地 parent_hash = current_hash（标记"已同步到此版本"）
# - 下次 sync_once 时本地文件未修改 → current_hash 不变 → SKIP（正确）
# - 本地文件被修改 → current_hash 变化 → local_has_parent=True, remote_has_parent=False → Row 5 → PUSH（正确）
```

注释假设"remote_has_parent=False → Row 5 → PUSH（正确）"是基于"云端是新文件"的前提。但首次同步推送后，云端**应当**进入"已同步"状态（parent_hash=current_hash），而非停留在"新文件"状态。注释未能发现此状态不对称。

### 4. ADR 未明确要求推进云端 parent_hash

ADR `2026-07-17-cloud-init-first-sync-full-clear.md` 的"需要实施的变更"章节只描述：

> **Phase C**：修改 sync_once，新增首次同步分支：检测未初始化 → full-clear → 全量推送数据库 → 全量推送文件 → mark-initialized → 设置 last_sync_time。

未明确要求"推进云端 parent_hash"。实施时依据 [`_advance_local_parent_after_initial_sync` 的现有设计](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L491-L542)，只推进本地，遗漏云端。

## 关键证据

### 证据 1：日志无 /pull-files/commit 调用

T1 同步期间（23:35-23:36）云端 lifeprism.log：

```
2026-07-18 23:35:12,696 INFO sync_cloud_api.py func:sync_full_clear line 1024 : full-clear 完成: 表=31, 文件=6
2026-07-18 23:35:15,227 INFO sync_cloud_api.py func:sync_get_dynamic_tables_definitions line 308 : 查询云端动态表定义: types=0
...（数据库推送）
2026-07-18 23:36:44,712 INFO sync_cloud_api.py func:sync_push_files line 882 : 同步 Push-Files 请求开始: 文件数=50
2026-07-18 23:36:55,759 INFO sync_cloud_api.py func:sync_push_files line 922 : 同步 Push-Files 完成: 写入文件数=17, 耗时=828.56ms
2026-07-18 23:36:58,452 INFO sync_cloud_api.py func:sync_mark_initialized line 1057 : 云端已标记为已初始化
```

**无 `/pull-files/commit` 调用记录**，证实云端 parent_hash 未被推进。

### 证据 2：DB 查询确认状态不对称

通过 `docs/temp/debug_cloud_sync_state.py` 查询 T1 完成后两端 DB：

```
=== 云端 file_sync_state ===
file_path=diary/e2e_normal.md
parent_hash=None  ← 未推进
current_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec

=== 本地 file_sync_state ===
file_path=diary/e2e_normal.md
parent_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec  ← 已推进
current_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec
```

### 证据 3：T4 测试时矩阵判定结果

```
2026-07-18 23:47:42,699 INFO sync_client.py func:_sync_files_full_flow line 2016 :
    _sync_files_full_flow: 矩阵判定完成 PULL=0, PUSH=2, CONFLICT=0, SKIP=115
```

预期 `CONFLICT=2`，实际 `PUSH=2, CONFLICT=0`，bug 触发。

## 最佳方案

### 方案 A（推荐）：新增 `_advance_remote_parent_after_initial_sync` 方法

**修改位置**：[`lifeprism/sync/sync_client.py` L350-351](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L350-L351)

**修改内容**：

```python
# 3. 全量推送文件
logger.info("步骤 3/4: 全量推送文件...")
self._initial_push_files(remote_url, api_key, directories or SYNC_DIRECTORIES)

# 3.5 推进云端 parent_hash = current_hash
# 修复：首次同步后云端 file_sync_state.parent_hash 仍为 None（/push-files 对新文件设为 None），
# 不推进会导致下次矩阵判定走 Row 5 (PUSH) 而非 Row 9 (CONFLICT)
# 参考 _advance_local_parent_after_initial_sync 的对称设计
self._advance_remote_parent_after_initial_sync(remote_url, api_key, file_list)
```

**新增方法**：

```python
def _advance_remote_parent_after_initial_sync(
    self, remote_url: str, api_key: str, paths: list[str]
) -> None:
    """首次同步后推进云端 parent_hash = current_hash

    修复 _advance_local_parent_after_initial_sync 的对称缺陷：
    该方法只推进本地 parent_hash，未推进云端，导致首次同步后两端状态不对称
    （本地 parent_hash=H0, 云端 parent_hash=None），下次同步时矩阵判定走 Row 5 (PUSH)
    而非 Row 9 (CONFLICT)，本地 PUSH 静默覆盖云端修改。

    实现：调用 /pull-files/commit 端点推进云端 parent_hash = current_hash。

    Args:
        remote_url: 远程服务器 URL
        api_key: API Key
        paths: 首次同步推送的文件相对路径列表
    """
    if not paths:
        return

    try:
        response = httpx.post(
            url=f"{remote_url}/api/sync/pull-files/commit",
            json={"paths": paths},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=60.0,
        )
        response.raise_for_status()
    except (httpx.HTTPStatusError, httpx.RequestError) as e:
        logger.error(
            "_advance_remote_parent_after_initial_sync: 调用 commit 失败, "
            "remote_url=%s, error=%s",
            remote_url,
            e,
        )
        raise

    committed = response.json().get("committed", [])
    logger.info(
        "首次同步后推进云端 parent_hash: %d/%d 个文件",
        len(committed),
        len(paths),
    )
```

### 方案 B（备选）：复用 `_verify_and_advance_parent`

直接在 `_full_sync_to_cloud` 步骤 3 后调用现有的 [`_verify_and_advance_parent`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L1448-L1559)：

```python
# 3. 全量推送文件
self._initial_push_files(remote_url, api_key, directories or SYNC_DIRECTORIES)

# 3.5 推进云端 parent_hash（复用现有 verify + commit 流程）
self._verify_and_advance_parent(remote_url, api_key, file_list)
```

**优势**：复用现有 verify + commit 流程，多一层 hash 一致性校验。
**劣势**：verify 端点逐个文件计算 hash（117 个文件），首次同步较慢。

### 推荐：方案 A

方案 A 更直接（只调用 commit 端点），与 `_advance_local_parent_after_initial_sync` 对称，命名清晰。verify 校验在首次同步场景下冗余（推送后立即 commit，hash 必然一致）。

## 验证方法

### 修复后重测 T4/T5/T6

1. 删除云端 `cloud_initialized` 标志文件重置状态：
   ```
   explore/LifePrism/localData/config/cloud_initialized
   ```

2. 启动本地 main 触发 T1 全清覆盖（重新执行）

3. 验证 T1 后两端状态对称：
   ```python
   # docs/temp/debug_cloud_sync_state.py 输出应显示两端 parent_hash 一致
   ```

4. 修改本地+云端各 2 个文件：
   - `diary/e2e_normal.md`
   - `diary/e2e_template_copy.md`

5. 重启本地 main 触发第二次同步

6. **期望日志**：
   ```
   _sync_files_full_flow: 矩阵判定完成 PULL=0, PUSH=0, CONFLICT=2, SKIP=115
   _sync_files_full_flow: 非 JSONL 冲突走 AI 合并: 2 个: ['diary/e2e_normal.md', 'diary/e2e_template_copy.md']
   ```

7. **验证 sync_conflict/ 双备份**：
   ```
   explore/LifePrism/localData/sync_conflict/diary/e2e_normal.local.md
   explore/LifePrism/localData/sync_conflict/diary/e2e_normal.remote.md
   ```

## 修复验证结果（2026-07-19）

✅ **修复完全有效**

### 验证项

| 验证项 | 修复前 | 修复后 | 结果 |
| ------ | ------ | ------ | ---- |
| 首次同步后云端 parent_hash | None（未推进） | H0（已推进） | ✅ |
| 两端 parent_hash 对称 | 不对称 | 对称 | ✅ |
| 第二次同步矩阵判定 | PUSH=2, CONFLICT=0 | CONFLICT=2 | ✅ |
| 冲突解决流程触发 | 未触发 | 触发 | ✅ |
| diff3 自动合并（T4） | 未执行 | 成功 | ✅ |
| LLM 串行合并（T5） | 未执行 | 成功 | ✅ |
| sync_conflict/ 双备份（T6） | 未生成 | 生成 | ✅ |

### 修复代码

新增方法 [`_advance_remote_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L556-L638)（lifeprism/sync/sync_client.py L556-L638）：
- 分批调用 `/pull-files/commit` 端点推进云端 parent_hash = current_hash
- 使用 `FILE_BATCH_SIZE` 分批（每批 50 个文件）
- 使用 `MARK_INITIALIZED_TIMEOUT`（60s）作为单批 timeout
- 与 `_advance_local_parent_after_initial_sync` 对称执行

修改 [`_full_sync_to_cloud`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L325-L380)：
- 步骤 3 后新增步骤 3.5：调用 `_advance_remote_parent_after_initial_sync`
- `_initial_push_files` 返回类型从 `None` 改为 `list[str]`，返回推送的文件路径列表

### 测试日志证据

```
2026-07-19 00:14:59,190 INFO sync_client.py func:_advance_local_parent_after_initial_sync line 548 : 首次同步后推进 parent_hash: 117/117 个文件
2026-07-19 00:15:04,118 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 621 : 推进云端 parent_hash 进度: 50/117
2026-07-19 00:15:08,387 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 621 : 推进云端 parent_hash 进度: 100/117
2026-07-19 00:15:11,520 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 621 : 推进云端 parent_hash 进度: 117/117
2026-07-19 00:15:11,520 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 627 : 首次同步后推进云端 parent_hash: 117/117 个文件

2026-07-19 00:22:51,202 INFO sync_client.py func:_sync_files_full_flow line 2112 : _sync_files_full_flow: 矩阵判定完成 PULL=0, PUSH=0, CONFLICT=2, SKIP=115
2026-07-19 00:23:09,749 INFO conflict_resolution.py func:resolve_conflict_blocks line 681 : resolve_conflict_blocks: 串行处理完成，成功=1, 失败=0, 总计=1
2026-07-19 00:23:09,871 INFO sync_client.py func:_resolve_conflicts line 2000 : _resolve_conflicts: 冲突解决完成，成功 2/2
```

## 预防措施

1. **首次同步流程的对称性原则**：任何对本地 file_sync_state 的修改，必须考虑云端是否需要对称修改。
2. **端到端测试覆盖**：补充 T4/T5/T6 的端到端测试用例，确保冲突解决流程可被触发。
3. **ADR 实施检查清单**：ADR 的"需要实施的变更"应包含"对称性检查"项，避免遗漏。

## 关联文档

- ADR: [`docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md)
- 测试报告: [`docs/generated/018/2026-07-18-sync-e2e-test-report.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/generated/018/2026-07-18-sync-e2e-test-report.md)
- Issue 4: [`.scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md`](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md)
- 关联 bug: [`docs/history-bugs/2026-07-16-cloud-missing-files-skipped-by-false-assumption.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-16-cloud-missing-files-skipped-by-false-assumption.md)（同样涉及 file_sync_state 状态推断错误）
