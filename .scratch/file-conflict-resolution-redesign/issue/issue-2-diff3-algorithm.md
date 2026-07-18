# Issue 2: 基于 difflib 自研 diff3 算法正式实现

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md` 决策 1）

## What to build

将已有探索性原型 `test/explore/diff3_self_difflib/difflib_merge.py`（176 行）迁移并整理为正式模块 `lifeprism/sync/diff3.py`，同时迁移测试套件到正式测试目录。

**实现基础**（`test/explore/diff3_self_difflib/` 已包含）：
- `difflib_merge.py`：原型实现（176 行），需迁移到 `lifeprism/sync/diff3.py`
- `test_scenarios.py`：7 经典 3-way merge 场景测试
- `test_edge_cases.py`：17 边界场景测试（中英文、emoji、Markdown、CRLF、无尾换行等）
- `test_git_oracle.py`：67 个 oracle 用例，对比 git merge 输出
- `REPORT.md`：稳定性测试报告（7 场景 8/8 通过、边界 17/17 通过、状态判定 100% 一致、文本一致率 89.6%）

**diff3 输入**：
- `base`：`parent_hash` 对应的文件内容（common ancestor）
- `ours`：本地当前文件内容
- `theirs`：云端当前文件内容

**diff3 输出**：
- 自动合并成功 → 合并后的文件内容
- 自动合并失败 → 含 conflict marker 的文件内容（标记格式在 Issue 4 中定义）

**关键约束**：
- 零外部依赖，纯 Python 标准库 `difflib`
- 失败模式可控：最差情况产生 conflict marker，**数据永不丢失**
- 不包含冲突标记格式定义（在 Issue 4 中实现）
- 不包含 LLM 调用逻辑（在 Issue 4 中实现）

## Acceptance criteria

- [ ] 新建 `lifeprism/sync/diff3.py`，基于 `test/explore/diff3_self_difflib/difflib_merge.py` 迁移整理
- [ ] 新建 `test/core/unit/sync/test_diff3_merge.py`，迁移 `test_scenarios.py` 的 7 场景测试
- [ ] 迁移 `test_edge_cases.py` 的 17 边界场景测试到正式测试目录
- [ ] 迁移 `test_git_oracle.py` 的 67 oracle 用例到正式测试目录
- [ ] 7 经典场景全部通过（双方改不同区域、双方改同一行、一方删除一方修改等）
- [ ] 17 边界场景全部通过（中英文、emoji、Markdown、CRLF、无尾换行等）
- [ ] git merge oracle 对比：状态判定 100% 一致（67/67 正确判定"能否自动合并"）
- [ ] 所有冲突场景 ours/theirs 内容均完整保留（在合并结果或冲突块中），数据永不丢失
- [ ] 性能验证：1500 行文件合并耗时 < 200ms

## Blocked by

None - can start immediately

## User stories covered

PRD 用户故事：1, 2, 3, 4, 5（diff3 自动合并）

## Related ADRs

- [docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md) - 决策 1（diff3 算法自研），本 issue 的核心 ADR
- [docs/adr/2026-07-14-file-sync-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-14-file-sync-conflict-resolution.md) - 原文件同步冲突解决决策（被 ADR-2026-07-17 修订决策 3 替代）
