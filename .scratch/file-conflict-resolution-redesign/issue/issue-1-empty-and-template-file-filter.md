# Issue 1: 空文件与 Template 文件不入 file_sync_state

## Parent

无（来源：`.scratch/file-conflict-resolution-redesign/prd.md`）

## What to build

在文件同步扫描阶段预防性地过滤掉两类不应进入同步流程的文件：

1. **空文件**：内容 `strip()` 后为空的文件，从根本解决"云端空文档覆盖本地"bug 根因（详见 `docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md`）
2. **Template 初始化文件**：从 `templates/` 目录复制过来的初始化文档，不携带用户数据，不应触发同步冲突

具体行为：

- 启动时计算 `templates/` 目录下所有文件的 hash，写入 `template_hashes` 集合（内存）
- `file_sync_state` 写入前检查：
  - 文件内容为空 → 跳过
  - 文件 hash 在 `template_hashes` 集合中 → 跳过
- 数据源单一：从 `templates/` 目录派生，不硬编码

## Acceptance criteria

- [ ] 启动时计算 `templates/` 目录所有文件 hash，加载到 `template_hashes` 集合
- [ ] 空文件（`content.strip() == ""`）不写入 `file_sync_state`
- [ ] template hash 命中的文件不写入 `file_sync_state`
- [ ] 单元测试覆盖空文件跳过场景（位置：`test/core/unit/sync/test_file_filter.py`，参考 `test/core/unit/sync/test_compute_file_hash.py` 模式）
- [ ] 单元测试覆盖 template hash 过滤场景
- [ ] 单元测试覆盖"启动时 template_hashes 集合正确生成"场景
- [ ] 验证：触发同步后 `file_sync_state` 表中无空文件和 template 文件记录

## Blocked by

None - can start immediately

## User stories covered

PRD 用户故事：22, 23, 24, 25（空文件 + Template 文件过滤）

## Related ADRs

- [docs/adr/2026-07-14-file-sync-conflict-resolution.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/adr/2026-07-14-file-sync-conflict-resolution.md) - 原文件同步冲突解决决策（决策 2 同步白名单 + 11 态矩阵），本 issue 在此基础上增加空文件和 template 文件的预防性过滤
- [docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md](file:///d:/desktop/软件开发/LifeWatch-AI/docs/history-bugs/) - 空文档覆盖 bug 根因（本 issue 的触发问题）
- 无对应独立 ADR（本 issue 来源是 PRD 决策 7、8，无单独 ADR）
