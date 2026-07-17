"""
调试 markdown 代码块解析
"""

from pathlib import Path

from lifeprism.llm.utils.md_os import prompts_md_load


def debug_parse():
    prompts_file = Path("templates/prompts/schedule_prompts.md")

    if not prompts_file.exists():
        print(f"文件不存在: {prompts_file}")
        return

    data = prompts_md_load(prompts_file)

    # 检查 update_memory
    if "update_memory" in data["prompts"]:
        update_memory = data["prompts"]["update_memory"]
        if "v1" in update_memory["versions"]:
            v1_content = update_memory["versions"]["v1"]

            print("=" * 80)
            print("update_memory v1 内容:")
            print("=" * 80)
            print(v1_content[:500])  # 打印前500个字符
            print("=" * 80)
            print(f"总长度: {len(v1_content)}")
            print(f"包含 '## YYYY-MM-DD': {'## YYYY-MM-DD' in v1_content}")
            print(f"包含 '```md': {'```md' in v1_content}")
            print(f"开头: {repr(v1_content[:50])}")

    # 检查 activity_summary
    if "activity_summary" in data["prompts"]:
        activity_summary = data["prompts"]["activity_summary"]
        if "v1" in activity_summary["versions"]:
            v1_content = activity_summary["versions"]["v1"]

            print("\n" + "=" * 80)
            print("activity_summary v1 内容:")
            print("=" * 80)
            print(v1_content)
            print("=" * 80)


if __name__ == "__main__":
    debug_parse()
