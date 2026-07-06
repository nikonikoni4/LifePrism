"""
临时脚本：将 diary 表中的 ai_summary 迁移到 behavior.md 的对应日期 "" 日记总结 "" 子标题下

用法：
    python -m lifeprism.llm.function.migrate_ai_summary
    python -m lifeprism.llm.function.migrate_ai_summary --dry-run
"""

import sys

from lifeprism.config.settings_manager import settings
from lifeprism.llm.utils.md_os import write_date_md
from lifeprism.repository import diary_repository

BEHAVIOR_PATH = settings.lifeprism_data_path / "user" / "daily_data" / "behavior.md"


def migrate(dry_run: bool = False) -> int:
    items, total = diary_repository.query_diaries()
    count = 0

    for item in items:
        date = item.get("date")
        ai_summary = item.get("ai_summary")

        if not date or not ai_summary:
            continue

        # 清理可能的前后缀空白
        summary = ai_summary.strip()
        if not summary:
            continue

        if dry_run:
            print(f"  {date}: {summary[:80]}...")
        else:
            write_date_md(BEHAVIOR_PATH, date, summary, subheading="日记总结", mode="overwrite")

        count += 1

    return count


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    print(f"目标文件: {BEHAVIOR_PATH}")
    print(f"模式: {'dry-run (预览)' if dry_run else '实际写入'}")
    print("-" * 50)

    n = migrate(dry_run=dry_run)

    if dry_run:
        print(f"\n共发现 {n} 条待迁移的 AI 总结")
    else:
        print(f"\n已迁移 {n} 条 AI 总结到 behavior.md")
