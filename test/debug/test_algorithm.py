import sys

sys.path.insert(0, ".")
import re
from pathlib import Path

# 读取文件
file_path = Path("templates/prompts/schedule_prompts.md")
content = file_path.read_text(encoding="utf-8")

# 找到 update_memory 的 v1 部分
blocks = re.split(r"\n---\s*\n", content)

for block in blocks:
    if "# update_memory" in block:
        # 找到 v1 版本
        version_pattern = re.compile(r"^##\s+(v\d+)\s*\n", re.MULTILINE)
        for match in version_pattern.finditer(block):
            if match.group(1) == "v1":
                version_start = match.end()
                # 找到下一个二级标题
                next_match = re.search(r"^##\s+", block[version_start:], re.MULTILINE)
                if next_match:
                    version_end = version_start + next_match.start()
                else:
                    version_end = len(block)

                version_content = block[version_start:version_end].strip()

                # 测试我的算法
                if version_content.startswith("```md"):
                    first_newline = version_content.find("\n")

                    if first_newline != -1:
                        content_start = first_newline + 1
                        pos = content_start
                        in_nested_block = False
                        closing_pos = -1

                        print("开始搜索...")
                        iteration = 0
                        while pos <= len(version_content) - 3:
                            iteration += 1
                            if (
                                iteration <= 20 or version_content[pos : pos + 3] == "```"
                            ):  # 只打印前20次或遇到 ```
                                if version_content[pos : pos + 3] == "```":
                                    print(
                                        f"位置 {pos}: 找到 ```, in_nested_block={in_nested_block}"
                                    )

                            if version_content[pos : pos + 3] == "```":
                                if not in_nested_block:
                                    next_char_pos = pos + 3
                                    while (
                                        next_char_pos < len(version_content)
                                        and version_content[next_char_pos] in " \t"
                                    ):
                                        next_char_pos += 1

                                    if (
                                        next_char_pos >= len(version_content)
                                        or version_content[next_char_pos] == "\n"
                                    ):
                                        print(f"  -> 这是结束标记！closing_pos={pos}")
                                        closing_pos = pos
                                        break
                                    else:
                                        print(
                                            f"  -> 这是内部代码块开始，next_char={repr(version_content[next_char_pos])}"
                                        )
                                        in_nested_block = True
                                        pos += 3
                                else:
                                    print(f"  -> 这是内部代码块结束")
                                    in_nested_block = False
                                    pos += 3
                            else:
                                pos += 1

                        print(f"\n最终 closing_pos: {closing_pos}")
                        if closing_pos != -1:
                            extracted = version_content[content_start:closing_pos].strip()
                            print(f"提取的内容长度: {len(extracted)}")
                            print(f'包含 "## YYYY-MM-DD": {"## YYYY-MM-DD" in extracted}')
                            print(
                                f'包含 "更新recent_state.md规则": {"更新recent_state.md规则" in extracted}'
                            )
                break
        break
