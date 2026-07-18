---
version: 2.0
created_at: 2026-07-18
updated_at: 2026-07-19
last_updated: 修复 bug 后重测全部通过 - T1/T2/T3/T4/T5/T6 端到端测试完成
abstract: LifePrism 云端同步端到端测试报告 v2.0，修复 bug 后所有测试项通过。覆盖 T1（首次同步全覆盖）、T2（二次启动增量同步）、T3（空文件+template 过滤）、T4（diff3 自动合并）、T5（LLM 串行合并）、T6（双备份）。
---

# LifePrism 云端同步端到端测试报告

## 版本

| 版本 | 更新内容 |
| ---- | -------- |
| 1.0 | 创建测试报告初稿，T1/T3 通过，T4/T5/T6 因 bug 未能触发 |
| 2.0 | 修复 bug 后重测：T1/T2/T3/T4/T5/T6 全部通过 |

## 1. 测试背景

本次测试针对最近两天提交的两个核心功能：

1. **首次同步全覆盖方案**（基于 `docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md`）
   - 云端跳过种子数据初始化
   - 首次同步由本地全量覆盖云端（清空 + 推送 + mark-initialized）

2. **新文件冲突处理方案**（基于 `.scratch/file-conflict-resolution-redesign/`）
   - 自研 diff3 三方合并算法
   - LLM 串行辅助冲突解决（CONFLICT_RESOLVE 分支 tools=[]，输出 JSON 替换指令）
   - 冲突标记格式：`<<<<<<< LP-LOCAL-{file_hash_8} #{n}` / `=======` / `>>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}`
   - sync_conflict/ 双备份（local.md + remote.md）

**测试环境**：
- 本地仓库：`D:\desktop\软件开发\LifeWatch-AI`（端口 8101）
- 模拟云端：`D:\desktop\软件开发\LifeWatch-AI\explore\LifePrism`（端口 8102，agent_only 模式）
- 云端配置：`explore\LifePrism\localData\cloud_init.yaml`（已配置）
- 测试时间：2026-07-18 ~ 2026-07-19

**测试方法**：依靠本地仓库启动/结束 main 时自动同步的特性进行端到端测试，分析 `localData/debug_logs/sync.log` 和 `lifeprism.log` 验证同步行为。

## 2. 测试项与结果

| 测试项 | 内容 | v1.0 结果 | v2.0 结果 | 说明 |
| ------ | ---- | ---------- | ---------- | ---- |
| T1 | 首次同步全覆盖 | ✅ 通过 | ✅ 通过 | 云端 6 个无效数据全部被清空，117 个文件覆盖完成，云端 parent_hash 同步推进 |
| T2 | 二次启动走增量同步 | ⏸ 未执行 | ✅ 通过 | cloud_initialized 标志正确生成，二次启动未进入首次同步分支，走增量同步流程 |
| T3 | 空文件+template 过滤 | ✅ 通过 | ✅ 通过 | 空文件过滤 51 个、template 过滤 10 个生效 |
| T4 | diff3 自动合并 | ❌ 未触发 | ✅ 通过 | 双方在不同位置添加内容，diff3 自动合并成功，无冲突标记 |
| T5 | LLM 串行合并 | ❌ 未触发 | ✅ 通过 | diff3 产生冲突块，LLM 介入合并成功（1 个冲突块，成功 1/1） |
| T6 | 双备份（sync_conflict/） | ❌ 未触发 | ✅ 通过 | 每次冲突都生成 local.md + remote.md 双备份，内容正确 |

## 3. T1 首次同步全覆盖测试（v2.0 修复后重测）

### 3.1 测试目标

验证 ADR `2026-07-17-cloud-init-first-sync-full-clear.md` 实施的首次同步全清覆盖方案，并验证 bug 修复后云端 parent_hash 正确推进。

### 3.2 测试执行

1. 删除云端 `cloud_initialized` 标志文件
2. 启动云端 main_agent_only（端口 8102）
3. 启动本地 main 触发首次同步

### 3.3 测试结果

✅ **通过**（含 bug 修复验证）

#### 关键日志证据（来自 `localData/debug_logs/sync.log`）：

```
2026-07-19 00:13:11,742 INFO sync_client.py func:sync_once line 243 : 云端未初始化，执行首次同步（全清覆盖）...
2026-07-19 00:13:11,743 INFO sync_client.py func:_full_sync_to_cloud line 335 : 步骤 1/4: 清空云端数据...
2026-07-19 00:13:21,086 INFO sync_client.py func:_full_sync_to_cloud line 342 : 云端清空完成: {'status': 'ok', 'cleared_tables': [...31张...], 'cleared_files': 117, ...}
2026-07-19 00:13:21,086 INFO sync_client.py func:_full_sync_to_cloud line 345 : 步骤 2/4: 全量推送数据库...
2026-07-19 00:14:47,226 INFO sync_client.py func:_full_sync_to_cloud line 349 : 步骤 3/4: 全量推送文件...
2026-07-19 00:14:59,154 INFO sync_client.py func:_initial_push_files line 494 : 文件全量推送完成: 117 个文件
2026-07-19 00:14:59,190 INFO sync_client.py func:_advance_local_parent_after_initial_sync line 548 : 首次同步后推进 parent_hash: 117/117 个文件
2026-07-19 00:15:04,118 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 621 : 推进云端 parent_hash 进度: 50/117
2026-07-19 00:15:08,387 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 621 : 推进云端 parent_hash 进度: 100/117
2026-07-19 00:15:11,520 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 621 : 推进云端 parent_hash 进度: 117/117
2026-07-19 00:15:11,520 INFO sync_client.py func:_advance_remote_parent_after_initial_sync line 627 : 首次同步后推进云端 parent_hash: 117/117 个文件
2026-07-19 00:15:14,111 INFO sync_client.py func:_full_sync_to_cloud line 373 : 云端已标记为已初始化
```

#### 验证项：

| 验证项 | 期望 | 实际 | 结果 |
| ------ | ---- | ---- | ---- |
| 云端旧数据被清空 | cleared_files=117 | cleared_files=117 | ✅ |
| 31 张表全部被清空 | cleared_tables 包含 SYNC_TABLES | cleared_tables 列表完整 | ✅ |
| 本地全量推送文件数 | = 117 | 117 个文件 | ✅ |
| 本地 parent_hash 推进 | 117/117 | 117/117 | ✅ |
| **云端 parent_hash 推进（修复点）** | **117/117** | **117/117** | ✅ |
| cloud_initialized 标志文件生成 | 存在 | 存在 | ✅ |

#### Bug 修复验证

修复前：首次同步后两端状态不对称（本地 parent_hash=H0, 云端 parent_hash=None）

修复后通过 `debug_cloud_sync_state.py` 查询两端 DB：

```
=== e2e_normal.md 在 云端 file_sync_state ===
parent_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec
current_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec

=== e2e_normal.md 在 本地 file_sync_state ===
parent_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec
current_hash=86426146caf214671538861cbe27fe38746738f5f08985deaedc339206c01aec
```

✅ 两端 parent_hash 完全一致，状态对称。

## 4. T2 二次启动走增量同步测试

### 4.1 测试目标

验证 cloud_initialized 标志正确生成后，二次启动 main 走增量同步流程而非首次同步。

### 4.2 测试结果

✅ **通过**

#### 关键日志证据：

```
2026-07-19 00:17:00,153 INFO sync_client.py func:sync_once line 253 : 同步表列表: 静态表=31张, 动态表=0张, 总计=31张
2026-07-19 00:18:18,877 INFO sync_client.py func:pull_from_remote line 936 : pull_from_remote: 无需要拉取的内容
2026-07-19 00:18:18,883 INFO sync_client.py func:push_to_remote line 1019 : push_to_remote: 无需要推送的内容
```

**关键观察**：sync_once 未出现"云端未初始化，执行首次同步（全清覆盖）..."日志，直接走增量同步流程（pull_from_remote → push_to_remote → _sync_files_full_flow），证实 T2 通过。

## 5. T3 空文件+template 过滤测试

### 5.1 测试结果

✅ **通过**（与 v1.0 一致）

```
2026-07-19 00:14:47,415 INFO sync_client.py func:_refresh_current_hashes line 1148 : _refresh_current_hashes: 跳过 51 个空文件（PRD 决策 7）
2026-07-19 00:14:47,416 INFO sync_client.py func:_refresh_current_hashes line 1154 : _refresh_current_hashes: 跳过 10 个 template 文件（PRD 决策 8）
```

## 6. T4/T5/T6 diff3+LLM+双备份冲突解决测试（v2.0 修复后重测）

### 6.1 测试目标

验证 `.scratch/file-conflict-resolution-redesign/` 实施的：
- T4：diff3 三方合并自动解决冲突（双方在不同位置修改）
- T5：LLM 串行辅助合并（双方在同一位置修改，diff3 产生冲突块）
- T6：sync_conflict/ 双备份（local.md + remote.md）

### 6.2 测试执行

#### 步骤 1：准备 base content

`_fetch_remote_base_content` 从 `backups/docs/{timestamp}/` 查找匹配 parent_hash 的历史版本。由于 e2e 测试文件是测试期间创建的，不在每日备份范围内，需要手动创建备份目录：

```
localData/backups/docs/2026-07-18T16-30-00/diary/e2e_normal.md   # base content（hash 839bfb17...）
localData/backups/docs/2026-07-18T16-30-00/diary/e2e_template_copy.md  # base content（hash 455e083f...）
```

#### 步骤 2：制造冲突场景

**T4 测试 - `e2e_normal.md`**（diff3 自动合并）：
- base（备份版本）：第5行"本地新增：T4 diff3 自动合并测试（位置1，第3行后）"
- 本地 ours：第7行新增"这是本地修改（第二轮）：用于触发 diff3 自动合并。位置1在第3行后。"
- 云端 theirs：第12行新增"云端修改（第二轮）：用于触发 diff3 自动合并。位置2在第8行后。"
- 预期：双方在不同位置添加，diff3 能自动合并，无冲突块

**T5 测试 - `e2e_template_copy.md`**（LLM 串行合并）：
- base（备份版本）：第11行"本地修改：T5 LLM 串行合并测试（同一位置修改，应触发 LLM 介入）"
- 本地 ours：第11行改为"本地修改（第二轮）：T5 LLM 串行合并测试 - 本地版本"
- 云端 theirs：第11行改为"云端修改（第二轮）：T5 LLM 串行合并测试 - 云端版本"
- 预期：同一行不同内容，diff3 产生冲突块，LLM 介入合并

#### 步骤 3：启动本地 main 触发同步

### 6.3 测试结果

✅ **全部通过**

#### 关键日志证据：

```
2026-07-19 00:22:51,202 INFO sync_client.py func:_sync_files_full_flow line 2112 : _sync_files_full_flow: 矩阵判定完成 PULL=0, PUSH=0, CONFLICT=2, SKIP=115
2026-07-19 00:22:51,203 INFO sync_client.py func:_sync_files_full_flow line 2145 : _sync_files_full_flow: 非 JSONL 冲突走 AI 合并: 2 个: ['diary/e2e_normal.md', 'diary/e2e_template_copy.md']

# T4: e2e_normal.md - diff3 自动合并（无 LLM 串行处理日志 → 无冲突块）
2026-07-19 00:22:53,755 INFO conflict_backup.py func:backup_conflict_versions line 216 : backup_conflict_versions: 已备份冲突文件 local+remote 版本 file_path=diary/e2e_normal.md, backup_dir=...sync_conflict\20260718_162253

# T5: e2e_template_copy.md - LLM 串行合并成功
2026-07-19 00:23:09,749 INFO conflict_resolution.py func:resolve_conflict_blocks line 681 : resolve_conflict_blocks: 串行处理完成，成功=1, 失败=0, 总计=1
2026-07-19 00:23:09,750 INFO sync_client.py func:_resolve_conflicts line 1945 : _resolve_conflicts: LLM 串行处理完成 diary/e2e_template_copy.md，成功=1, 失败=0, 总计=1
2026-07-19 00:23:09,752 INFO conflict_backup.py func:backup_conflict_versions line 216 : backup_conflict_versions: 已备份冲突文件 local+remote 版本 file_path=diary/e2e_template_copy.md, backup_dir=...sync_conflict\20260718_162309

2026-07-19 00:23:09,871 INFO sync_client.py func:_resolve_conflicts line 2000 : _resolve_conflicts: 冲突解决完成，成功 2/2
2026-07-19 00:23:12,507 INFO sync_client.py func:_push_files line 1538 : _push_files: 推送 2 个文件, 批次数=1
2026-07-19 00:23:17,748 INFO sync_client.py func:_verify_and_advance_parent line 1651 : _verify_and_advance_parent: 校验 2 个文件, 一致 2, 推进 parent_hash
```

### 6.4 T4 diff3 自动合并验证

✅ **通过**

**最终文件内容（两端一致）**：

```markdown
# E2E 测试 - 正常文件

这是用于首次同步端到端测试的正常文件。

本地新增：T4 diff3 自动合并测试（位置1，第3行后）

这是本地修改（第二轮）：用于触发 diff3 自动合并。位置1在第3行后。

预期行为：
- 应被加入 file_sync_state
- 应被推送到云端
- 首次同步后云端应存在此文件

云端修改（第二轮）：用于触发 diff3 自动合并。位置2在第8行后。

测试时间：2026-07-18
对应测试：T1（首次同步全覆盖）+ T3（template/空文件过滤的反例）+ T4（diff3 自动合并）
```

**验证项**：
- ✅ 第7行包含本地新增内容
- ✅ 第14行包含云端新增内容
- ✅ 双方修改都被保留，无冲突标记
- ✅ 两端文件内容完全一致

### 6.5 T5 LLM 串行合并验证

✅ **通过**

**最终文件内容（两端一致）**：

```markdown
## Morning Page

## Evening Page

### 今天最有价值的一件事情

在这里用几句话说明你遇到的最有价值的事情，不必是世俗上重要的事情，可以上发现了一朵美丽的花，一个美丽的夕阳等。

### 今天发生的好事情

本地修改（第二轮）：T5 LLM 串行合并测试 - 本地版本 / 云端修改（第二轮）：T5 LLM 串行合并测试 - 云端版本
```

**验证项**：
- ✅ LLM 串行处理成功（成功=1, 失败=0, 总计=1）
- ✅ 第11行将两个冲突版本合并为一行（用 " / " 分隔）
- ✅ 两端文件内容完全一致

### 6.6 T6 双备份验证

✅ **通过**

**sync_conflict/ 目录结构**：

```
localData/sync_conflict/
├── 20260718_161824/  (第一轮 - LWW 降级)
│   ├── diary__e2e_normal.md.local.md      (427 bytes)
│   └── diary__e2e_normal.md.remote.md     (500 bytes)
├── 20260718_161826/  (第一轮 - LWW 降级)
│   ├── diary__e2e_template_copy.md.local.md  (369 bytes)
│   └── diary__e2e_template_copy.md.remote.md  (369 bytes)
├── 20260718_162253/  (第二轮 - diff3 自动合并)
│   ├── diary__e2e_normal.md.local.md      (524 bytes)
│   └── diary__e2e_normal.md.remote.md     (518 bytes)
└── 20260718_162309/  (第二轮 - LLM 串行合并)
    ├── diary__e2e_template_copy.md.local.md  (352 bytes)
    └── diary__e2e_template_copy.md.remote.md  (352 bytes)
```

**验证项**：
- ✅ 每次冲突都生成 local.md + remote.md 双备份
- ✅ local.md 内容 = 本地版本（含"本地修改"字样）
- ✅ remote.md 内容 = 云端版本（含"云端修改"字样）
- ✅ 两轮冲突共生成 8 个备份文件

## 7. Bug 修复验证

### 7.1 Bug 概述

**Bug**：首次同步后云端 `file_sync_state.parent_hash` 未推进（详见 `docs/history-bugs/2026-07-18-cloud-parent-hash-not-advanced-after-first-sync.md`）

**修复**：新增 [`_advance_remote_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L556-L638) 方法，在首次同步步骤 3 后调用 `/pull-files/commit` 推进云端 parent_hash，与 [`_advance_local_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L503-L554) 对称执行。

### 7.2 修复验证

| 验证项 | 修复前 | 修复后 | 结果 |
| ------ | ------ | ------ | ---- |
| 首次同步后云端 parent_hash | None（未推进） | H0（已推进） | ✅ |
| 两端 parent_hash 对称 | 不对称 | 对称 | ✅ |
| 第二次同步矩阵判定 | PUSH=2, CONFLICT=0 | CONFLICT=2 | ✅ |
| 冲突解决流程触发 | 未触发 | 触发 | ✅ |
| diff3 自动合并 | 未执行 | 成功 | ✅ |
| LLM 串行合并 | 未执行 | 成功 | ✅ |
| sync_conflict/ 双备份 | 未生成 | 生成 | ✅ |

## 8. 测试覆盖总结

### 8.1 通过的测试项

- ✅ T1 首次同步全覆盖（含云端 parent_hash 推进）
- ✅ T2 二次启动走增量同步
- ✅ T3 空文件+template 过滤
- ✅ T4 diff3 自动合并
- ✅ T5 LLM 串行合并
- ✅ T6 sync_conflict/ 双备份

### 8.2 Bug 修复

- ✅ **bug 2026-07-18-cloud-parent-hash-not-advanced-after-first-sync**：修复完成并验证通过

### 8.3 已知限制

1. **base content 获取依赖备份目录**：`_fetch_remote_base_content` 从 `backups/docs/{timestamp}/` 查找匹配 parent_hash 的历史版本。
   - 备份每天 03:00 执行，保留最近 3 份
   - 若文件创建后未经过备份周期（如本次测试的 e2e 文件），需要手动创建备份
   - 已记录在 `_fetch_remote_base_content` 的"已知限制"注释中

2. **LLM 合并结果质量**：本次测试中 LLM 将两个冲突版本用 " / " 简单连接，合并质量一般。实际生产中应根据 LLM prompt 优化合并结果。

## 9. 临时文件清理

测试期间创建的调试脚本（待清理）：
- `docs/temp/debug_cloud_sync_state.py`
- `docs/temp/debug_cloud_file_hash.py`
- `docs/temp/debug_template_hash.py`（v1.0 创建）

测试期间手动创建的备份目录（待清理）：
- `localData/backups/docs/2026-07-18T16-30-00/`（测试用 base content）

## 10. 参考

- ADR: [`docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-cloud-init-first-sync-full-clear.md)
- PRD: [`.scratch/file-conflict-resolution-redesign/prd.md`](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/file-conflict-resolution-redesign/prd.md)
- Issue 4: [`.scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md`](file:///d:/desktop/软件开发/LifeWatch-AI/.scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md)
- Bug 记录: [`docs/history-bugs/2026-07-18-cloud-parent-hash-not-advanced-after-first-sync.md`](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/2026-07-18-cloud-parent-hash-not-advanced-after-first-sync.md)
- 测试方法论文档: [`scripts/prompts/sync-e2e-testing.md`](file:///d:/desktop/软件开发/LifeWatch-AI/scripts/prompts/sync-e2e-testing.md)
- 修复代码: [`lifeprism/sync/sync_client.py` L556-L638 `_advance_remote_parent_after_initial_sync`](file:///d:/desktop/软件开发/LifeWatch-AI/lifeprism/sync/sync_client.py#L556-L638)
