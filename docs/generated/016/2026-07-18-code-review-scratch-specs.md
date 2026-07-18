# Code Review Report

**审查范围**: `.scratch/file-conflict-resolution-redesign/`（PRD + 8 个 Issue 规格文档 + 实现代码对齐）
**审查时间**: 2026-07-18
**变更文件**: 19 files changed, +2264/-76 lines（含 9 个 spec 文件 + 10 个实现代码文件）

## 架构上下文

### 相关 ADR
- `docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md`（decided）
- `docs/adr/2026-07-17-conflict-failure-policy.md`（decided）
- `docs/adr/2026-07-17-data-backup-strategy.md`（decided）
- `docs/adr/2026-07-17-backup-sync-decoupled-scope.md`（decided）

### 相关 Spec
- `.scratch/file-conflict-resolution-redesign/prd.md`：File Sync Conflict Resolution Redesign PRD
- `.scratch/file-conflict-resolution-redesign/issue/issue-1.md` ～ `issue-8.md`：8 个 Issue 规格

### 决策覆盖
- 9 个 spec 文件，4 个 ADR 覆盖
- 20 个 PRD 决策在代码中全部落地

## 审查结果

Found 5 issues（置信度 ≥ 80）：

### Issue 1: PRD decision 19 的代码示例与目录结构图自相矛盾
- **类型**: Documentation
- **置信度**: 90
- **位置**: `.scratch/file-conflict-resolution-redesign/prd.md:808-837`
- **详情**: PRD decision 19 包含三处对 sync_conflict/ 备份结构的描述，三者互相矛盾：
  1. **代码示例**（L808-819）：`data_path / "sync_conflict" / timestamp_str / file_path` → 产生 `sync_conflict/20260717_154500/user/behavior.md.local.md`（目录嵌套）
  2. **目录图 1**（L826-830）：文件路径作为目录名，内部放文件（`agent/behavior.md/` 目录）
  3. **目录图 2**（L832-837）：扁平化 `__` 分隔（`agent__behavior.md.local.md`）
  
  Issue 5 已纠正为扁平化方案（L28-35 使用 `flatten_file_path`），但 PRD 正文的代码示例和两个目录图均未同步更新。实现者依赖 PRD 而非 Issue 5 时会产生路径混淆。
- **依据**: PRD L808-837 三处描述互斥；Issue 5 L28-35 实现路径

### Issue 2: Issue 5 "Blocked by" 遗漏对 Issue 4 的依赖标注
- **类型**: Documentation
- **置信度**: 85
- **位置**: `.scratch/file-conflict-resolution-redesign/issue/issue-5-sync-conflict-dual-backup-and-cleanup.md:73`
- **详情**: Issue 5 声明 "None - can start immediately"，但 Issue 5 与 Issue 4 都修改 `sync_client.py` 的冲突处理区域。Issue 4 重写整个冲突解决流程（LLM 自主合并 → diff3 + LLM 辅助合并），改变备份触发位置和上下文。Issue 5 虽在 L55 说"不涉及冲突处理流程改造"，但缺少代码合并冲突标注和实施顺序建议（如"建议在 Issue 4 之后或与 Issue 4 协调并入"）。
- **依据**: Issue 5 L73（Blocked by: None）；PRD L472-501（实施顺序建议第三阶段）

### Issue 3: `file_path_str` 推导规则未在 spec 中显式定义
- **类型**: Documentation
- **置信度**: 80
- **位置**: `.scratch/file-conflict-resolution-redesign/issue/issue-5-sync-conflict-dual-backup-and-cleanup.md:32-35`
- **详情**: Issue 5 代码示例使用 `{file_path_str}` 作为变量占位符，AC 仅说"文件路径用 `__` 分隔避免嵌套"。但未定义从相对路径（如 `agent/behavior.md`）到 `file_path_str`（如 `agent__behavior.md`）的转换规则。文件名本身含 `__` 时（极低概率但可能）也无处理策略。实现代码中 `flatten_file_path` 函数已正确处理（替换 `/` 和 `\` 为 `__`），但 spec 遗漏了这一定义。
- **依据**: Issue 5 L32-35 使用 `f"{file_path_str}.local.md"` 但无推导公式

### Issue 4: Issue 7 未说明包结构决策（constants.py 与 backup_service.py 分属不同包）
- **类型**: Documentation
- **置信度**: 80
- **位置**: `.scratch/file-conflict-resolution-redesign/issue/issue-7-backup-service-and-scheduler.md:105-139`
- **详情**: Issue 7 将 `backup_service.py` 放在 `lifeprism/server/services/` 下（与 ScheduleService 同级），但 `constants.py` 放在新建的 `lifeprism/backup/` 包下。PRD 和 Issue 7 均未解释这一跨包结构决策的动机。ADR `2026-07-17-data-backup-strategy.md` L167-169 列出同样结构但未作说明。当前实现存在跨包 import（`from lifeprism.backup.constants import ...`），虽非循环依赖，但架构决策未记录。
- **依据**: PRD L554-556（constants.py 在 lifeprism/backup/）vs L664-665（backup_service.py 在 lifeprism/server/services/）

### Issue 5: Issue 1 中 `content.strip() == ""` 的 BOM 边界情况未讨论
- **类型**: Documentation
- **置信度**: 80
- **位置**: `.scratch/file-conflict-resolution-redesign/issue/issue-1-empty-and-template-file-filter.md:11`
- **详情**: Issue 1 用 `content.strip() == ""` 判断空文件。未讨论 UTF-8 BOM（`\xef\xbb\xbf`）+ 空白字符的文件——`content.strip()` 后 BOM 不会被移除（BOM 不是空白字符），返回 `"\ufeff"` 而非 `""`，不会被过滤。实现代码中 `is_empty_content` 函数实际检查 `content_bytes.strip() == b""`，对于 BOM 文件同样不会过滤。此场景概率极低（Editor 通常对 `.md` 文件不加 BOM），但 spec 未标注为已知限制。
- **依据**: Issue 1 L11, L25；PRD L270-275（决策 7）

## Spec-实现对齐检查

| PRD 决策 | 预期 | 代码实际 | 状态 |
|----------|------|---------|------|
| 1-2: diff3 优先 | 三方合并替代 LLM 自主合并 | `diff3.py` 实现完整 diff3 算法 + `sync_client.py` 优先调用 diff3 | ✅ |
| 3: 冲突标记格式 | `LP-LOCAL-{hash8} #{n}` | `diff3.py:_append_conflict` 实现完整格式 | ✅ |
| 4: LLM JSON 格式 | `{conflict_id, start_marker, end_marker, replacement}` | `conflict_resolution.py` parse + validate | ✅ |
| 5: 串行处理（理解 B） | 一次一个冲突块，基于更新后文件 | `conflict_resolution.py:resolve_conflict_blocks` 串行循环 | ✅ |
| 6: 重试 3 次 / 降级 keep_ours | max_retries=3, JSON/marker 失败重试 | L591-L646 重试循环 + L648-L678 降级 | ✅ |
| 7-8: tools=[] | CONFLICT_RESOLVE 无文件工具 | `loop.py` branch `tools=[]` | ✅ |
| 9: sync_conflict 双向备份 | 备份本地 + 云端原始版本 | `conflict_backup.py:backup_conflict_versions` 双文件写入 | ✅ |
| 10: 降级策略 | 单块 keep_ours, 整文件 LWW | L648 单块降级 + sync_client L1770 base=None LWW | ✅ |
| 11: 不校验行号 | 当前方案不验证行号 | `conflict_resolution.py` match_markers 仅字符串匹配 | ✅ |
| 12: 空文件 + template 过滤 | 空文件跳过, template hash 匹配跳过 | `file_filter.py:is_skip_file` 两层过滤 | ✅ |
| 13: 备份与同步解耦 | BACKUP_DIRS 独立于 SYNC_DIRECTORIES | `backup/constants.py` 独立常量（含 plan/ 非同步范围） | ✅ |
| 14: 平铺存储 | `backups/docs/{ts}/`, `backups/db/` | `backup_service.py` 目录结构一致 | ✅ |
| 15: 文档备份频率/保留 | 每日 03:00, 保留 3 份 | `schedule_service.py` cron `0 3 * * *`, `_cleanup_old_docs_backups` 3 份 | ✅ |
| 16: 数据库备份频率/保留 | 每 8 小时, 保留 3 份 | `schedule_service.py` cron `0 0,8,16 * * *`, `_cleanup_old_db_backups` 3 份 | ✅ |
| 17: SQLite Online Backup API | `source.backup(target)` | `backup_service.py:backup_database` sqlite3 Online Backup | ✅ |
| 18: 校验机制 | 文档: 数量+hash; 数据库: integrity_check | `_verify_docs_backup` + `_verify_db_backup` | ✅ |
| 19: 备份失败处理 | 删除损坏备份, 不影响其他 | L355-358/373-375 contextlib.suppress 清理 | ✅ |
| 20: sync.log 500KB 覆盖式 | RotatingFileHandler 500KB, backupCount=0 | `logger.py:setup_sync_logging` + `_OverwritingRotatingFileHandler` | ✅ |

**20/20 决策全部正确落地**，未发现任何实现与 spec 不一致的问题。

## 变更摘要

本次审查聚焦 `.scratch/file-conflict-resolution-redesign/` 中的规格文档（PRD + 8 个 Issue 规格），覆盖 9 个 spec 文件和 19 个实现文件。

**Spec 文档质量**：整体较高，PRD→Issue→ADR 双向追溯完整，20/20 决策与实现一致。主要改进点在 PRD decision 19 内部的代码示例与目录图矛盾（Issue 5 已纠正但 PRD 正文仍需更新），以及 Issue 5 的依赖关系标注和 `file_path_str` 推导说明。
