r"""
修复 behavior.md 中活动总结的错误格式

将 LLM 错误输出的 markdown 标题格式（### 今日概览 / ## 电脑使用总览 等）
替换为 prompt 要求的序号格式（1. 今日概览 / 2. 电脑使用总览 / 3. 高频使用时段）

用法：
    python -m lifeprism.llm.function.fix_behavior_md
    python -m lifeprism.llm.function.fix_behavior_md --dry-run
    python -m lifeprism.llm.function.fix_behavior_md --path "<自定义路径>"
"""

import re
import sys
from pathlib import Path

REPLACEMENTS = [
    # 纯 markdown 标题：### 今日概览 -> 1. 今日概览
    (r"^(#{1,3}\s+)今日概览\s*$", r"1. 今日概览"),
    (r"^(#{1,3}\s+)电脑使用总览\s*$", r"2. 电脑使用总览"),
    (r"^(#{1,3}\s+)高频使用时段\s*$", r"3. 高频使用时段"),
    # 混合格式：### 1. 今日概览（附注）-> 1. 今日概览
    (r"^#{1,3}\s+1\.\s*今日概览.*$", r"1. 今日概览"),
    (r"^#{1,3}\s+2\.\s*电脑使用总览.*$", r"2. 电脑使用总览"),
    (r"^#{1,3}\s+3\.\s*高频使用时段.*$", r"3. 高频使用时段"),
]


def fix_behavior_md(path: Path, dry_run: bool = False) -> int:
    if not path.exists():
        print(f"[ERROR] 文件不存在: {path}")
        return 0

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)
    fixed_count = 0

    new_lines = []
    for i, line in enumerate(lines):
        new_line = line
        for pattern, replacement in REPLACEMENTS:
            if re.match(pattern, line):
                new_line = re.sub(pattern, replacement, line)
                if new_line != line:
                    fixed_count += 1
                    if dry_run:
                        print(f"  L{i + 1}: {line.rstrip()} -> {new_line.rstrip()}")
                break
        new_lines.append(new_line)

    if fixed_count == 0:
        print("没有发现需要修复的内容")
        return 0

    if not dry_run:
        path.write_text("".join(new_lines), encoding="utf-8")
        print(f"已修复 {fixed_count} 处，文件已更新: {path}")
    else:
        print(f"\n[dry-run] 共发现 {fixed_count} 处需要修复（未实际写入）")

    return fixed_count


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv

    path_arg = None
    for i, arg in enumerate(sys.argv):
        if arg == "--path" and i + 1 < len(sys.argv):
            path_arg = sys.argv[i + 1]
            break

    if path_arg:
        target = Path(path_arg)
    else:
        from lifeprism.config.settings_manager import settings

        target = settings.lifeprism_data_path / "user" / "daily_data" / "behavior.md"

    print(f"目标文件: {target}")
    print(f"模式: {'dry-run (预览)' if dry_run else '实际修复'}")
    print("-" * 50)

    fix_behavior_md(target, dry_run=dry_run)
