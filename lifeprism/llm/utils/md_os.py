from pathlib import Path


import os
import re
from datetime import datetime
from typing import Optional, Dict


def read_md(file_path: Path | str) -> str:
    """
    读取 md 文件内容。如果输入是 str 类型，会自动转化为 Path。
    如果该文档或者其所有的父目录不存在，会自动创建它们。
    最终返回文档内容的字符串。
    
    Args:
        file_path (Path | str): 文件路径
        
    Returns:
        str: 文件的文本内容
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)
        
    if not file_path.exists():
        # 如果目录不存在，创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # 创建空白文件
        file_path.touch()
        
    return file_path.read_text(encoding="utf-8")


def write_behavior_md(
    file_path: Path | str,
    date: str,
    content: str,
    subheading: str,
    mode: str = "append"
) -> None:
    """
    编写 behavior.md 文件的内容。包含两种模式：覆写（overwrite）和续写（append）。
    日志格式统一为 `## YYYY-MM-DD` 作为日期标题，`### subheading` 作为子标题。

    Args:
        file_path (Path | str): 文件路径。
        date (str): 目标日期的字符串，格式为 'YYYY-MM-DD'。
        content (str): 要写入的正文内容。
        subheading (str): 必须提供的子标题，用于组织日期下的内容分类。
        mode (str): 写入模式，可选值为 "overwrite"（仅覆盖指定一天的内容） 或 "append"（接着在指定一天的内容下追加）。

    Raises:
        ValueError: 当 subheading 为空或 None 时抛出。
    """
    if not subheading:
        raise ValueError("write_behavior_md requires a non-empty subheading")

    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"## {date}\n### {subheading}\n{content}\n", encoding="utf-8")
        return

    full_content = file_path.read_text(encoding="utf-8")

    # 匹配精确的日期标题
    date_pattern = re.compile(rf'^(##\s+{re.escape(date)}\s*)$', re.MULTILINE)
    date_match = date_pattern.search(full_content)

    if not date_match:
        # 日期标题不存在，按日期升序找到正确的插入位置
        all_dates_pattern = re.compile(r'^##\s+(\d{4}-\d{2}-\d{2})\s*$', re.MULTILINE)
        new_block = f"## {date}\n### {subheading}\n{content}\n\n"

        # 找第一个比 date 更大的日期节，将新内容插入其前面
        insert_pos = None
        for m in all_dates_pattern.finditer(full_content):
            if m.group(1) > date:
                insert_pos = m.start()
                break

        if insert_pos is None:
            # 新日期是最大的，追加到末尾
            if full_content and not full_content.endswith('\n'):
                full_content += '\n'
            if not full_content.endswith('\n\n'):
                full_content += '\n'
            full_content += new_block
        else:
            # 插入到 insert_pos 前面，确保前面有空行分隔
            before = full_content[:insert_pos]
            after = full_content[insert_pos:]
            if before and not before.endswith('\n\n'):
                if not before.endswith('\n'):
                    before += '\n'
                before += '\n'
            full_content = before + new_block + after

        file_path.write_text(full_content, encoding="utf-8")
        return

    # 日期标题存在，查找该日期下的指定子标题块
    # 子标题格式为 ### subheading
    subheading_pattern = re.compile(rf'^###\s+{re.escape(subheading)}\s*$', re.MULTILINE)
    subheading_match = subheading_pattern.search(full_content, date_match.end())

    if not subheading_match:
        # 子标题不存在，在当前日期块下添加新的子标题块
        # 找到下一个日期或文件结束的位置
        next_date_pattern = re.compile(r'^##\s+\d{4}-\d{2}-\d{2}\s*$', re.MULTILINE)
        next_date_match = next_date_pattern.search(full_content, date_match.end())

        if next_date_match:
            insert_pos = next_date_match.start()
        else:
            insert_pos = len(full_content)

        # 确保在插入点前有空行分隔
        before = full_content[:insert_pos]
        after = full_content[insert_pos:]
        if before and not before.endswith('\n\n'):
            if not before.endswith('\n'):
                before += '\n'
            before += '\n'

        new_block = f"### {subheading}\n{content}\n\n"
        full_content = before + new_block + after
        file_path.write_text(full_content, encoding="utf-8")
        return

    # 子标题存在，找到紧接着的下一个子标题或日期
    next_subheading_pattern = re.compile(r'^#{1,3}\s+\S+.*$', re.MULTILINE)
    next_match = next_subheading_pattern.search(full_content, subheading_match.end())

    next_pos = next_match.start() if next_match else len(full_content)

    # 提取当前子标题的已有内容块
    existing_block = full_content[subheading_match.end():next_pos]

    if mode == "append":
        # 追加模式，清理现有的末尾空白然后再拼接
        clean_existing = existing_block.rstrip()
        if clean_existing:
            new_block = "\n" + clean_existing + "\n\n" + content + "\n\n"
        else:
            new_block = "\n" + content + "\n\n"

    elif mode == "overwrite":
        new_block = "\n" + content + "\n\n"
    else:
        raise ValueError(f"Unknown mode: {mode}")

    # 替换其中的内容
    new_full_content = full_content[:subheading_match.end()] + new_block + full_content[next_pos:]

    # 写入文件
    file_path.write_text(new_full_content, encoding="utf-8")


def extract_behavior_md(
    markdown_content: str,
    start_date: str,
    end_date: Optional[str] = None,
    subheading: str = "all"
) -> Dict[str, str]:
    """
    提取 behavior.md 的纯文本内容中，符合给定日期范围的内容。
    假设日志采用了 `## YYYY-MM-DD` 格式的二级标题作为日期标识，
    `### subheading` 作为子标题组织日期下的内容。

    :param markdown_content: behavior.md 的完整纯文本内容。
    :param start_date: 开始日期，格式 'YYYY-MM-DD'。
    :param end_date: 结束日期，格式 'YYYY-MM-DD'。如果为 None，则只提取 start_date 这一天的内容。
    :param subheading: 要提取的子标题名称。默认为 "all"，表示提取该日期下所有子标题的内容。
                      如果指定了具体的子标题名称，则只提取该子标题下的内容。
    :return: 字典格式的结果，key 为日期，value 为当日标题下的正文内容。
    """
    if end_date is None:
        end_date = start_date

    # 将输入转化为 datetime 对象用于做范围比较
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    end_dt = datetime.strptime(end_date, '%Y-%m-%d')

    # 容错：如果用户传反了起止时间，自动进行对调
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    # 正则：匹配行首的 `## YYYY-MM-DD` 并将其日期捕获为单独的分组
    # re.MULTILINE 表示 ^ 匹配每一行的开头
    date_pattern = re.compile(r'^##\s+(\d{4}-\d{2}-\d{2})\s*$', re.MULTILINE)

    # re.split 返回列表：[匹配头部内容, 捕获的日期1, 日期1下方的内容, 捕获的日期2, 日期2下方的内容...]
    date_parts = date_pattern.split(markdown_content)

    results = {}

    # 因为第一个元素 (date_parts[0]) 是第一个二级标题前的所有内容（如文件大标题），我们不需要它
    # 后面的元素总是：索引为奇数的是"日期字符串"，紧随其后的偶数索引是"正文区块"
    for i in range(1, len(date_parts), 2):
        current_date_str = date_parts[i]
        date_block = date_parts[i+1]

        try:
            current_dt = datetime.strptime(current_date_str, '%Y-%m-%d')
        except ValueError:
            # 如果匹配到的格式仍然无法解析为真实日期（比如 2026-99-99）则跳过
            continue

        # 边界控制：比较包含起止日期。因为使用了 <=，所以开始、结束日期的内容都会被原封不动保留
        if start_dt <= current_dt <= end_dt:
            if subheading == "all":
                # 提取所有子标题的内容，合并到一个字符串中
                content = _extract_all_subheadings(date_block)
            else:
                # 只提取指定子标题的内容
                content = _extract_single_subheading(date_block, subheading)

            # 容错：如果一天内出现了两次同样的日期标题，将其内容合并追加
            if current_date_str in results:
                if content:
                    results[current_date_str] += "\n\n" + content
            else:
                results[current_date_str] = content if content else ""

    return results


def _extract_all_subheadings(date_block: str) -> str:
    """
    从日期块中提取所有子标题的内容。

    :param date_block: 日期块的内容（不包含日期标题本身）。
    :return: 所有子标题内容的合并字符串。
    """
    # 匹配 ### subheading 或 ## subheading 格式的子标题
    subheading_pattern = re.compile(r'^#{1,3}\s+\S+.*$', re.MULTILINE)

    parts = subheading_pattern.split(date_block)
    # parts[0] 是第一个子标题之前的内容（通常为空或只有空白）
    # parts[1:] 包含各子标题之间的内容

    contents = []
    for i in range(1, len(parts)):
        content = parts[i].strip()
        if content:
            contents.append(content)

    return "\n\n".join(contents)


def _extract_single_subheading(date_block: str, subheading: str) -> str:
    """
    从日期块中提取指定子标题的内容。

    :param date_block: 日期块的内容（不包含日期标题本身）。
    :param subheading: 要提取的子标题名称。
    :return: 指定子标题下的内容，如果不存在则返回空字符串。
    """
    # 匹配 ### subheading 格式（子标题）
    target_subheading_pattern = re.compile(
        rf'^###\s+{re.escape(subheading)}\s*$',
        re.MULTILINE
    )
    target_match = target_subheading_pattern.search(date_block)

    if not target_match:
        return ""

    # 找到下一个子标题（### 或 ## 开头）或者日期块结束
    next_subheading_pattern = re.compile(r'^#{1,3}\s+\S+.*$', re.MULTILINE)
    next_match = next_subheading_pattern.search(date_block, target_match.end())

    if next_match:
        content = date_block[target_match.end():next_match.start()]
    else:
        content = date_block[target_match.end():]

    return content.strip()


def extract_behavior_logs_from_file(
    file_path: Path | str,
    start_date: str,
    end_date: Optional[str] = None,
    subheading: str = "all"
) -> Dict[str, str]:
    """
    读取 behavior.md 文件，并提取符合日期范围的内容。

    :param file_path: 文件的绝对或相对路径
    :param start_date: 开始日期，格式 'YYYY-MM-DD'
    :param end_date: 结束日期，格式 'YYYY-MM-DD'。如果为空只读取一天。
    :param subheading: 要提取的子标题名称。默认为 "all"。
    """
    content = read_md(file_path)
    return extract_behavior_md(content, start_date, end_date, subheading)

# 如果直接运行当前脚本，可以作为一个轻量的命令行测试使用
if __name__ == "__main__":
    sample_md = '''
# 个人行为日志汇总

## 2026-04-10
这是4月10号的内容。
思考：今天很顺利。

## 2026-04-15
这是4月15号的内容。
跨天测试！

## 2026-04-16
这是4月16号。
也就是今天。

## 2026-04-20
这是未来的日子。
'''
    print("=== 测试只取单天 ===")
    print(extract_behavior_md(sample_md, "2026-04-16"))
    
    print("\n=== 测试取范围 (10号到16号) 包含边界 ===")
    res = extract_behavior_md(sample_md, "2026-04-10", "2026-04-16")
    for date, txt in res.items():
        print(f"[{date}日内的数据] -> {txt[:15]}...")
