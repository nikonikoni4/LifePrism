"""测试数据备份与恢复指导文档的存在性和内容完整性

测试 seam: templates/docs/lifewatch/06-数据备份与恢复.md（文档存在性 + 内容完整性）

设计原则:
- 文档面向 Agent 可读，未来 Agent 可通过 ReadFileTool 读取以指导用户手工恢复操作
- 文档必须基于 Issue 7 实际实现编写（不描述未实现的特性）
- 文档必须包含 10 个章节（按任务规格）
- 文档必须包含 6 个 FAQ
- 文档必须包含技术附录

测试覆盖:
- 文档存在性
- 章节完整性（10 章节）：
  1. 备份位置说明
  2. 文档备份结构说明
  3. 数据库备份结构说明
  4. 文档恢复操作步骤
  5. 数据库恢复操作步骤
  6. 恢复前手动备份建议
  7. 恢复后对 file_sync_state 的影响
  8. sync_conflict/ 目录说明
  9. 6 个 FAQ
  10. 技术附录
- 关键内容检查
- Agent 可读性设计
- 与 Issue 7 实现一致性

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-8-backup-recovery-documentation.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 18
- ADR: docs/adr/2026-07-17-data-backup-strategy.md
- ADR: docs/adr/2026-07-17-conflict-failure-policy.md（sync_conflict 目录说明）
- Issue 7 实现:
  - lifeprism/backup/constants.py
  - lifeprism/server/services/backup_service.py
"""

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.core

# 文档路径：项目根目录 / templates / docs / lifewatch / 06-数据备份与恢复.md
DOC_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent.parent
    / "templates"
    / "docs"
    / "lifewatch"
    / "06-数据备份与恢复.md"
)


def _read_doc() -> str:
    """读取文档内容（断言文档存在）"""
    assert DOC_PATH.exists(), f"文档应存在：{DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def _get_h2_headers(content: str) -> list[str]:
    """提取所有 ## 二级标题文本（去掉前导 #）"""
    return [
        line.lstrip("#").strip()
        for line in content.splitlines()
        if line.startswith("## ")
    ]


# ==================== Seam 1: 文档存在性 ====================


class TestBackupRecoveryDocExists:
    """测试文档存在性"""

    def test_doc_file_exists(self):
        """数据备份与恢复指导文档存在"""
        assert DOC_PATH.exists(), f"文档应存在：{DOC_PATH}"

    def test_doc_file_not_empty(self):
        """文档非空（至少 100 字符）"""
        content = _read_doc()
        assert len(content) > 100, f"文档不应为空，实际长度 {len(content)}"

    def test_doc_has_markdown_title(self):
        """文档以 Markdown 一级标题开头"""
        content = _read_doc()
        first_line = content.lstrip().splitlines()[0] if content.strip() else ""
        assert first_line.startswith("# "), (
            f"文档应以 Markdown 一级标题开头，实际首行：{first_line!r}"
        )


# ==================== Seam 2: 章节完整性（10 章节，严格匹配任务规格） ====================


class TestBackupRecoveryDocSections:
    """测试文档章节完整性（任务规格要求 10 章节结构）

    任务规格 10 章节（按顺序）：
    1. 备份位置说明（{lifeprism_data_path}/backups/）
    2. 文档备份结构说明（backups/docs/{timestamp}/）
    3. 数据库备份结构说明（backups/db/lifewatch_ai-{timestamp}.db）
    4. 文档恢复操作步骤（复制单个文件或整个时间戳目录）
    5. 数据库恢复操作步骤（关闭服务 → 替换 .db 文件 → 重启服务）
    6. 恢复前手动备份建议（复制到 backups/pre_restore-{ts}/）
    7. 恢复后对 file_sync_state 的影响（下次同步会触发 CONFLICT，预期行为）
    8. sync_conflict/ 目录说明（冲突备份，保留 30 天）
    9. 6 个 FAQ
    10. 技术附录
    """

    def test_has_at_least_10_h2_sections(self):
        """文档至少有 10 个二级标题（## 章节）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        assert len(h2_headers) >= 10, (
            f"应有至少 10 个 ## 章节标题，实际 {len(h2_headers)}: {h2_headers}"
        )

    def test_has_backup_location_section(self):
        """章节1：备份位置说明（{lifeprism_data_path}/backups/）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"备份位置"或"备份文件存在"或"备份位置说明"
        assert any(
            "备份位置" in h or "备份文件存在" in h or "备份存在" in h
            for h in h2_headers
        ), f"应有备份位置说明章节，实际章节：{h2_headers}"
        assert "{lifeprism_data_path}/backups" in content

    def test_has_docs_backup_structure_section(self):
        """章节2：文档备份结构说明（backups/docs/{timestamp}/）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"文档备份"或"备份结构"
        assert any(
            "文档备份" in h or "备份结构" in h or "文档备份结构" in h
            for h in h2_headers
        ), f"应有文档备份结构说明章节，实际章节：{h2_headers}"
        assert "backups/docs/" in content
        assert "{timestamp}" in content or "时间戳" in content

    def test_has_db_backup_structure_section(self):
        """章节3：数据库备份结构说明（backups/db/lifewatch_ai-{timestamp}.db）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"数据库备份"或"数据库备份结构"
        assert any(
            "数据库备份" in h or "数据库备份结构" in h for h in h2_headers
        ), f"应有数据库备份结构说明章节，实际章节：{h2_headers}"
        assert "backups/db/" in content
        assert "lifewatch_ai" in content
        assert "{timestamp}" in content or "时间戳" in content

    def test_has_docs_recovery_steps_section(self):
        """章节4：文档恢复操作步骤（复制单个文件或整个时间戳目录）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"文档恢复"或"恢复文档"
        assert any(
            "文档恢复" in h or "恢复文档" in h for h in h2_headers
        ), f"应有文档恢复操作步骤章节，实际章节：{h2_headers}"
        assert "复制" in content

    def test_has_db_recovery_steps_section(self):
        """章节5：数据库恢复操作步骤（关闭服务 → 替换 .db 文件 → 重启服务）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"数据库恢复"或"恢复数据库"
        assert any(
            "数据库恢复" in h or "恢复数据库" in h for h in h2_headers
        ), f"应有数据库恢复操作步骤章节，实际章节：{h2_headers}"
        # 必须明确说明停服要求
        assert any(
            kw in content for kw in ["关闭", "停止", "停服", "停机"]
        ), "数据库恢复必须明确说明停服要求"
        # 替换 .db 文件
        assert ".db" in content
        # 重启服务
        assert any(
            kw in content for kw in ["重启", "重新启动"]
        ), "数据库恢复必须说明重启服务"

    def test_has_pre_restore_backup_advice_section(self):
        """章节6：恢复前手动备份建议（backups/pre_restore-{ts}/）

        必须有独立章节或在恢复步骤章节中明确强调。
        """
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"恢复前"或"手动备份"或"pre_restore"
        assert any(
            "恢复前" in h or "手动备份" in h or "pre_restore" in h.lower()
            or "预恢复" in h
            for h in h2_headers
        ), f"应有恢复前手动备份建议章节，实际章节：{h2_headers}"
        assert "pre_restore" in content
        # 强烈建议恢复前手动备份
        assert "强烈建议" in content or "强烈推荐" in content, (
            "文档应强烈建议恢复前手动备份当前数据"
        )

    def test_has_file_sync_state_impact_section(self):
        """章节7：恢复后对 file_sync_state 的影响（下次同步触发 CONFLICT，预期行为）

        必须有独立章节说明对 file_sync_state 的影响。
        """
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"file_sync_state"或"同步影响"或"恢复后"或"对同步"
        assert any(
            "file_sync_state" in h.lower()
            or "同步影响" in h
            or "恢复后" in h
            or "对同步" in h
            or "影响" in h
            for h in h2_headers
        ), f"应有恢复后对 file_sync_state 影响的章节，实际章节：{h2_headers}"
        assert "file_sync_state" in content
        assert "CONFLICT" in content or "冲突" in content
        # 预期行为
        assert any(
            kw in content for kw in ["预期", "正常", "expected", "符合预期"]
        ), "文档应说明这是预期行为"

    def test_has_sync_conflict_dir_section(self):
        """章节8：sync_conflict/ 目录说明（保留 30 天）

        必须有独立章节说明 sync_conflict/ 目录用途和保留策略。
        """
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"sync_conflict"或"冲突备份"或"冲突目录"
        assert any(
            "sync_conflict" in h.lower()
            or "冲突备份" in h
            or "冲突目录" in h
            for h in h2_headers
        ), f"应有 sync_conflict/ 目录说明章节，实际章节：{h2_headers}"
        assert "sync_conflict" in content
        # 必须明确说明保留 30 天
        assert "30" in content, "文档应说明 sync_conflict/ 保留 30 天"
        assert "天" in content, "文档应使用'天'作为保留期单位"

    def test_has_faq_section(self):
        """章节9：6 个 FAQ"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"FAQ"或"常见问题"
        assert any(
            "FAQ" in h or "常见问题" in h for h in h2_headers
        ), f"应有 FAQ 章节，实际章节：{h2_headers}"
        # 至少 6 个 Q（Q1-Q6）
        q_numbers = set()
        for m in re.finditer(r"Q\s*0*(\d+)", content):
            q_numbers.add(int(m.group(1)))
        assert q_numbers >= {1, 2, 3, 4, 5, 6}, (
            f"文档应包含至少 6 个 FAQ（Q1-Q6），实际找到 Q{sorted(q_numbers)}"
        )

    def test_has_technical_appendix_section(self):
        """章节10：技术附录（SQLite Online Backup API、PRAGMA integrity_check、平铺存储设计理由）"""
        content = _read_doc()
        h2_headers = _get_h2_headers(content)
        # 必须有标题包含"附录"或"技术"
        assert any(
            "附录" in h or "技术" in h for h in h2_headers
        ), f"应有技术附录章节，实际章节：{h2_headers}"
        # SQLite Online Backup API
        assert "Online Backup" in content or "source.backup" in content
        # PRAGMA integrity_check
        assert "integrity_check" in content or "PRAGMA" in content
        # 平铺存储设计理由
        assert "平铺" in content


# ==================== Seam 3: 关键内容检查 ====================


class TestBackupRecoveryDocKeyContent:
    """测试文档关键内容（与 Issue 7 实际实现一致）"""

    def test_contains_backup_root_path(self):
        """包含备份位置 {lifeprism_data_path}/backups/"""
        content = _read_doc()
        assert "{lifeprism_data_path}/backups" in content

    def test_contains_docs_backup_path(self):
        """包含文档备份结构 backups/docs/{timestamp}/"""
        content = _read_doc()
        assert "backups/docs/" in content
        assert "{timestamp}" in content or "时间戳" in content

    def test_contains_db_backup_path(self):
        """包含数据库备份结构 backups/db/lifewatch_ai-{timestamp}.db"""
        content = _read_doc()
        assert (
            "lifewatch_ai-{timestamp}.db" in content
            or ("lifewatch_ai-" in content and ".db" in content)
        )

    def test_contains_docs_recovery_copy_single_file(self):
        """文档恢复操作步骤包含复制单个文件"""
        content = _read_doc()
        assert "复制" in content
        assert "单个文件" in content or "单文件" in content or "单个" in content

    def test_contains_docs_recovery_copy_directory(self):
        """文档恢复操作步骤包含复制整个时间戳目录"""
        content = _read_doc()
        assert "整个" in content or "整目录" in content or "目录" in content

    def test_contains_db_recovery_shutdown_replace_restart(self):
        """数据库恢复包含完整步骤：关闭服务 → 替换 .db 文件 → 重启服务"""
        content = _read_doc()
        # 关闭服务
        assert any(kw in content for kw in ["关闭", "停止", "停服", "停机"])
        # 替换 .db 文件
        assert ".db" in content
        assert any(kw in content for kw in ["替换", "覆盖", "复制"])
        # 重启服务
        assert any(kw in content for kw in ["重启", "重新启动"])

    def test_contains_pre_restore_path_template(self):
        """包含恢复前手动备份路径模板 backups/pre_restore-{ts}/"""
        content = _read_doc()
        assert "pre_restore" in content

    def test_contains_pre_restore_strong_advice(self):
        """文档强烈建议恢复前手动备份当前数据"""
        content = _read_doc()
        assert "强烈建议" in content or "强烈推荐" in content

    def test_contains_file_sync_state_impact(self):
        """包含恢复后对 file_sync_state 的影响说明"""
        content = _read_doc()
        assert "file_sync_state" in content
        assert "CONFLICT" in content or "冲突" in content

    def test_contains_sync_conflict_30_day_retention(self):
        """包含 sync_conflict/ 目录保留 30 天说明"""
        content = _read_doc()
        assert "sync_conflict" in content
        assert "30" in content
        assert "天" in content

    def test_contains_six_faqs(self):
        """包含 6 个 FAQ（Q1-Q6）"""
        content = _read_doc()
        q_numbers = set()
        for m in re.finditer(r"Q\s*0*(\d+)", content):
            q_numbers.add(int(m.group(1)))
        assert q_numbers >= {1, 2, 3, 4, 5, 6}

    def test_contains_sqlite_online_backup_api(self):
        """技术附录包含 SQLite Online Backup API 说明"""
        content = _read_doc()
        assert "Online Backup" in content or "source.backup" in content

    def test_contains_pragma_integrity_check(self):
        """技术附录包含 PRAGMA integrity_check 说明"""
        content = _read_doc()
        assert "integrity_check" in content or "PRAGMA" in content

    def test_contains_flat_storage_design_rationale(self):
        """技术附录包含平铺存储设计理由"""
        content = _read_doc()
        assert "平铺" in content

    def test_contains_doc_backup_subdirs(self):
        """包含文档备份子目录说明（session/diary/agent/user/plan）"""
        content = _read_doc()
        for subdir in ["session", "diary", "agent", "user", "plan"]:
            assert subdir in content, f"文档应提到 {subdir}/ 子目录"

    def test_contains_pause_sync_client_advice(self):
        """文档恢复必须明确说明暂停 sync_client"""
        content = _read_doc()
        assert "sync_client" in content
        assert any(kw in content for kw in ["暂停", "停止", "停用"])

    def test_contains_db_recovery_must_stop_service(self):
        """数据库恢复必须明确说明停服要求"""
        content = _read_doc()
        assert any(kw in content for kw in ["关闭", "停止", "停服", "停机"])


# ==================== Seam 4: Agent 可读性设计 ====================


class TestBackupRecoveryDocAgentReadability:
    """测试文档 Agent 可读性设计（关键设计点）"""

    def test_doc_mentions_agent_readability_explicitly(self):
        """文档明确说明面向 Agent 可读，未来可通过 ReadFileTool 读取

        关键设计点：文档必须面向 Agent 可读，未来 Agent 可通过 ReadFileTool 读取以指导用户。
        必须在文档中明确声明此设计意图（不能仅在测试中暗示）。
        """
        content = _read_doc()
        # 必须明确说明 ReadFileTool 或 "面向 Agent" 或 "Agent 可读"
        assert (
            "ReadFileTool" in content
            or "面向 Agent" in content
            or "Agent 可读" in content
            or "Agent 读取" in content
            or "Agent 通过" in content
        ), (
            "文档必须明确说明面向 Agent 可读，未来可通过 ReadFileTool 读取以指导用户手工恢复操作"
        )

    def test_doc_mentions_agent_in_context(self):
        """文档应在合适位置提到 Agent（说明本文档面向 Agent 可读）"""
        content = _read_doc()
        assert "Agent" in content

    def test_doc_has_clear_section_structure(self):
        """文档有清晰的章节结构（## 标题可被 ReadFileTool 解析）"""
        content = _read_doc()
        headers = re.findall(r"^#{1,2}\s+\S", content, re.MULTILINE)
        assert len(headers) >= 10, (
            f"应有至少 10 个章节标题（## 或 #），实际 {len(headers)}"
        )

    def test_doc_has_at_least_10_h2_sections(self):
        """文档应至少有 10 个二级标题（##）按章节组织"""
        content = _read_doc()
        h2_headers = re.findall(r"^##\s+\S", content, re.MULTILINE)
        assert len(h2_headers) >= 10, (
            f"应有至少 10 个 ## 章节标题，实际 {len(h2_headers)}"
        )

    def test_doc_has_power_shell_or_command_examples(self):
        """文档应包含 PowerShell 或命令行示例（Refactor 阶段要求）

        PowerShell 命令示例便于 Windows 用户直接复制执行。
        """
        content = _read_doc()
        # 必须有 PowerShell 命令示例（Copy-Item 或 powershell 标记的代码块）
        assert (
            "PowerShell" in content
            or "powershell" in content
            or "Copy-Item" in content
            or "```powershell" in content
            or "```PowerShell" in content
            or "```ps" in content
        ), "文档应包含 PowerShell 命令示例"


# ==================== Seam 5: 与 Issue 7 实现一致性 ====================


class TestBackupRecoveryDocIssue7Consistency:
    """测试文档与 Issue 7 实际实现的一致性"""

    def test_contains_backup_retention_count(self):
        """文档应说明保留 3 份（与 BACKUP_RETENTION_COUNT 一致）"""
        content = _read_doc()
        assert "3 份" in content or "保留 3" in content or "保留最新 3" in content

    def test_contains_doc_backup_frequency(self):
        """文档应说明文档备份频率：每天 03:00（与 cron 0 3 * * * 一致）"""
        content = _read_doc()
        assert "03:00" in content or "03" in content
        assert "每天" in content or "每日" in content or "每天 1 次" in content

    def test_contains_db_backup_frequency(self):
        """文档应说明数据库备份频率：每 8 小时（00/08/16 点）"""
        content = _read_doc()
        assert "8 小时" in content or "8小时" in content or "每 8 小时" in content
        assert "00" in content and ("08" in content or "8 点" in content) and "16" in content

    def test_contains_run_mode_guard(self):
        """文档应说明 run_mode 守卫（云端 agent_only 模式不备份）"""
        content = _read_doc()
        assert "agent_only" in content or "agent only" in content.lower()
        assert "full" in content or "本地" in content

    def test_contains_db_backup_excluded_files(self):
        """文档应说明数据库备份排除文件（chat_history.json, bootstrap.md）"""
        content = _read_doc()
        assert "chat_history.json" in content
        assert "bootstrap.md" in content

    def test_contains_sqlite_online_backup_api_description(self):
        """文档应说明 SQLite Online Backup API 是在线拷贝、不阻塞业务读写"""
        content = _read_doc()
        # 必须说明在线拷贝/不阻塞业务
        assert "在线" in content or "不阻塞" in content or "online" in content.lower()

    def test_contains_integrity_check_description(self):
        """文档应说明完整性校验机制（文档：hash 比对；数据库：PRAGMA integrity_check）"""
        content = _read_doc()
        # 文档完整性校验
        assert "hash" in content.lower() or "SHA-256" in content or "sha256" in content.lower()
        # 数据库完整性校验
        assert "integrity_check" in content or "PRAGMA" in content


# ==================== Seam 6: FAQ 内容覆盖（任务规格建议的 6 个场景） ====================


class TestBackupRecoveryDocFAQContent:
    """测试 FAQ 内容覆盖（任务规格建议的 6 个 FAQ 场景）

    任务规格建议（可根据实际调整）：
    1. 如何恢复某个特定日记文件？
    2. 如何恢复某天的数据库状态？
    3. 如何恢复被误删的 agent 配置？
    4. 恢复后下次同步会发生什么？
    5. 如何从 sync_conflict/ 恢复某个冲突版本？
    6. 备份文件损坏了怎么办？
    """

    def test_faq_covers_diary_recovery(self):
        """FAQ 涵盖日记文件恢复场景"""
        content = _read_doc()
        # FAQ 章节应包含日记恢复相关内容
        assert "日记" in content or "diary" in content.lower()

    def test_faq_covers_database_recovery(self):
        """FAQ 涵盖数据库恢复场景"""
        content = _read_doc()
        # FAQ 章节应包含数据库恢复相关内容
        assert "数据库" in content

    def test_faq_covers_agent_config_recovery(self):
        """FAQ 涵盖 agent 配置恢复场景"""
        content = _read_doc()
        # FAQ 章节应包含 agent 配置相关内容
        assert "agent" in content.lower() or "Agent" in content

    def test_faq_covers_sync_after_recovery(self):
        """FAQ 涵盖恢复后下次同步行为"""
        content = _read_doc()
        # FAQ 章节应包含恢复后同步相关内容
        assert "同步" in content

    def test_faq_covers_sync_conflict_recovery(self):
        """FAQ 涵盖从 sync_conflict/ 恢复冲突版本场景"""
        content = _read_doc()
        # FAQ 章节应包含 sync_conflict 恢复相关内容
        assert "sync_conflict" in content

    def test_faq_covers_backup_corruption(self):
        """FAQ 涵盖备份文件损坏场景"""
        content = _read_doc()
        # FAQ 章节应包含备份损坏相关内容
        assert "损坏" in content or "校验失败" in content or "备份失败" in content
