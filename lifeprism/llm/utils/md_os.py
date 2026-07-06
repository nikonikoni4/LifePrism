import re
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


def read_md(file_path: Path | str) -> str:
    """
    读取 Markdown 文件内容，如果文件不存在则自动创建。

    该函数会自动处理文件和目录的创建：
    - 如果父目录不存在，会递归创建所有必需的父目录
    - 如果文件不存在，会创建一个空文件
    - 自动将 str 类型的路径转换为 Path 对象

    Args:
        file_path (Path | str): Markdown 文件的绝对路径或相对路径。
            支持 Path 对象或字符串路径。

    Returns:
        str: 文件的完整文本内容，使用 UTF-8 编码读取。
            如果文件是新创建的，返回空字符串。
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.exists():
        # 如果目录不存在，创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # 创建空白文件
        file_path.touch()

    return file_path.read_text(encoding="utf-8")


def _sanitize_behavior_content(content: str) -> str:
    """过滤 LLM 输出中的 markdown 标题语法，保持 behavior.md 层级干净。

    behavior.md 使用 ``## date`` 和 ``### subheading`` 管理文档结构，
    子标题下的内容中不能再出现 markdown 标题（#、##、### 等），
    否则会导致提取时和人工阅读时层级混乱。

    处理规则：去除每行行首的 ``#{1,6} `` 标记，保留标题文本本身。

    Args:
        content: LLM 生成的原始内容

    Returns:
        str: 过滤后的内容
    """
    return re.sub(r"^#{1,6}\s+", "", content, flags=re.MULTILINE)


def write_date_md(
    file_path: Path | str, date: str, content: str, subheading: str, mode: str = "append"
) -> None:
    """
    向按日期组织的 Markdown 文件中写入内容，支持追加和覆盖两种模式。

    该函数用于维护使用 `## YYYY-MM-DD` 格式作为日期标题、`### subheading` 格式
    作为子标题的结构化 Markdown 文件。具有以下特性：
    - 自动按日期升序组织内容（新日期会插入到正确的位置）
    - 如果文件或目录不存在，会自动创建
    - 支持在指定日期和子标题下追加或覆盖内容
    - 自动处理空行和格式，保持文档结构整洁

    Args:
        file_path (Path | str): Markdown 文件的绝对路径或相对路径。
            支持 Path 对象或字符串路径。
        date (str): 目标日期，格式必须为 'YYYY-MM-DD'（如 '2026-05-08'）。
            如果该日期在文件中不存在，会自动按升序插入。
        content (str): 要写入的正文内容，不需要包含日期标题和子标题。
        subheading (str): 子标题名称，用于在日期下组织不同类别的内容。
            不能为空或 None。
        mode (str, optional): 写入模式，默认为 "append"。
            - "append": 在指定日期和子标题的现有内容后追加新内容
            - "overwrite": 完全覆盖指定日期和子标题下的现有内容

    Returns:
        None

    Raises:
        ValueError: 当 subheading 为空、None 或 mode 不是 "append"/"overwrite" 时抛出。

    Example:
        >>> write_date_md("log.md", "2026-05-08", "完成了功能开发", "工作记录")
        >>> write_date_md("log.md", "2026-05-08", "修复了bug", "工作记录", mode="append")
    """
    if not subheading:
        raise ValueError("write_date_md requires a non-empty subheading")

    # 统一过滤：去除内容中的 markdown 标题语法，避免与 ## date / ### subheading 层级冲突
    content = _sanitize_behavior_content(content)

    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.exists():
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"## {date}\n### {subheading}\n{content}\n", encoding="utf-8")
        return

    full_content = file_path.read_text(encoding="utf-8")

    # 匹配精确的日期标题
    date_pattern = re.compile(rf"^(##\s+{re.escape(date)}\s*)$", re.MULTILINE)
    date_match = date_pattern.search(full_content)

    if not date_match:
        # 日期标题不存在，按日期升序找到正确的插入位置
        all_dates_pattern = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)
        new_block = f"## {date}\n### {subheading}\n{content}\n\n"

        # 找第一个比 date 更大的日期节，将新内容插入其前面
        insert_pos = None
        for m in all_dates_pattern.finditer(full_content):
            if m.group(1) > date:
                insert_pos = m.start()
                break

        if insert_pos is None:
            # 新日期是最大的，追加到末尾
            if full_content and not full_content.endswith("\n"):
                full_content += "\n"
            if not full_content.endswith("\n\n"):
                full_content += "\n"
            full_content += new_block
        else:
            # 插入到 insert_pos 前面，确保前面有空行分隔
            before = full_content[:insert_pos]
            after = full_content[insert_pos:]
            if before and not before.endswith("\n\n"):
                if not before.endswith("\n"):
                    before += "\n"
                before += "\n"
            full_content = before + new_block + after

        file_path.write_text(full_content, encoding="utf-8")
        return

    # 日期标题存在，查找该日期下的指定子标题块
    # 子标题格式为 ### subheading
    subheading_pattern = re.compile(rf"^###\s+{re.escape(subheading)}\s*$", re.MULTILINE)
    subheading_match = subheading_pattern.search(full_content, date_match.end())

    if not subheading_match:
        # 子标题不存在，在当前日期块下添加新的子标题块
        # 找到下一个日期或文件结束的位置
        next_date_pattern = re.compile(r"^##\s+\d{4}-\d{2}-\d{2}\s*$", re.MULTILINE)
        next_date_match = next_date_pattern.search(full_content, date_match.end())

        insert_pos = next_date_match.start() if next_date_match else len(full_content)

        # 确保在插入点前有空行分隔
        before = full_content[:insert_pos]
        after = full_content[insert_pos:]
        if before and not before.endswith("\n\n"):
            if not before.endswith("\n"):
                before += "\n"
            before += "\n"

        new_block = f"### {subheading}\n{content}\n\n"
        full_content = before + new_block + after
        file_path.write_text(full_content, encoding="utf-8")
        return

    # 子标题存在，找到紧接着的下一个子标题或日期
    next_subheading_pattern = re.compile(r"^#{1,3}\s+\S+.*$", re.MULTILINE)
    next_match = next_subheading_pattern.search(full_content, subheading_match.end())

    next_pos = next_match.start() if next_match else len(full_content)

    # 提取当前子标题的已有内容块
    existing_block = full_content[subheading_match.end() : next_pos]

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
    new_full_content = full_content[: subheading_match.end()] + new_block + full_content[next_pos:]

    # 写入文件
    file_path.write_text(new_full_content, encoding="utf-8")


def extract_date_md(
    markdown_content: str, start_date: str, end_date: str | None = None, subheading: str = "all"
) -> dict[str, str]:
    """
    从按日期组织的 Markdown 文本中提取指定日期范围的内容。

    该函数用于解析使用 `## YYYY-MM-DD` 格式作为日期标题、`### subheading` 格式
    作为子标题的结构化 Markdown 文本。具有以下特性：
    - 支持提取单日或日期范围的内容（包含起止日期）
    - 可以提取所有子标题或指定子标题的内容
    - 自动容错：如果起止日期顺序颠倒会自动调整
    - 自动跳过格式错误的日期（如 2026-99-99）
    - 如果同一日期出现多次，会自动合并内容

    Args:
        markdown_content (str): 完整的 Markdown 文本内容（不是文件路径）。
            应包含 `## YYYY-MM-DD` 格式的日期标题。
        start_date (str): 开始日期，格式必须为 'YYYY-MM-DD'（如 '2026-05-08'）。
        end_date (Optional[str], optional): 结束日期，格式为 'YYYY-MM-DD'。
            如果为 None，则只提取 start_date 当天的内容。默认为 None。
        subheading (str, optional): 要提取的子标题名称。默认为 "all"。
            - "all": 提取该日期下所有子标题的内容（合并为一个字符串）
            - 具体子标题名: 只提取该子标题下的内容

    Returns:
        Dict[str, str]: 字典，key 为日期字符串（'YYYY-MM-DD'），value 为该日期下的内容。
            - 如果指定日期不存在，不会出现在返回字典中
            - 如果指定日期存在但内容为空，value 为空字符串
            - 内容不包含日期标题（`## YYYY-MM-DD`），但保留子标题（`### subheading`）

    Example:
        >>> content = "## 2026-05-08\\n### 工作\\n完成开发\\n## 2026-05-09\\n### 工作\\n修复bug"
        >>> extract_date_md(content, "2026-05-08")
        {'2026-05-08': '### 工作\\n完成开发'}
        >>> extract_date_md(content, "2026-05-08", "2026-05-09")
        {'2026-05-08': '### 工作\\n完成开发', '2026-05-09': '### 工作\\n修复bug'}
    """
    if end_date is None:
        end_date = start_date

    # 将输入转化为 datetime 对象用于做范围比较
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    # 容错：如果用户传反了起止时间，自动进行对调
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt

    # 正则：匹配行首的 `## YYYY-MM-DD` 并将其日期捕获为单独的分组
    # re.MULTILINE 表示 ^ 匹配每一行的开头
    date_pattern = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)

    # re.split 返回列表：[匹配头部内容, 捕获的日期1, 日期1下方的内容, 捕获的日期2, 日期2下方的内容...]
    date_parts = date_pattern.split(markdown_content)

    results = {}

    # 因为第一个元素 (date_parts[0]) 是第一个二级标题前的所有内容（如文件大标题），我们不需要它
    # 后面的元素总是：索引为奇数的是"日期字符串"，紧随其后的偶数索引是"正文区块"
    for i in range(1, len(date_parts), 2):
        current_date_str = date_parts[i]
        date_block = date_parts[i + 1]

        try:
            current_dt = datetime.strptime(current_date_str, "%Y-%m-%d")
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
    从日期块中提取所有子标题的内容并合并。

    该函数是内部辅助函数，用于处理一个日期标题下的所有子标题内容。
    保留子标题行（### subheading），并在各子标题块之间使用 ``\\n\\n`` 分隔。

    Args:
        date_block (str): 日期块的内容，不包含日期标题本身（`## YYYY-MM-DD`）。
            应包含一个或多个 `### subheading` 格式的子标题及其内容。

    Returns:
        str: 所有子标题块合并后的字符串，保留子标题行。
            如果没有任何子标题，返回原始内容（去除首尾空白）。
    """
    # 匹配 ### subheading 或 ## subheading 格式的子标题
    subheading_pattern = re.compile(r"^(#{1,3}\s+\S+.*)$", re.MULTILINE)

    matches = list(subheading_pattern.finditer(date_block))

    if not matches:
        # 没有子标题，直接返回原始内容
        return date_block.strip()

    contents = []
    for i, match in enumerate(matches):
        heading = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(date_block)
        body = date_block[start:end].strip()

        if body:
            contents.append(f"{heading}\n{body}")
        else:
            contents.append(heading)

    return "\n\n".join(contents)


def _extract_single_subheading(date_block: str, subheading: str) -> str:
    """
    从日期块中提取指定子标题的内容。

    该函数是内部辅助函数，用于从一个日期标题下提取特定子标题的内容。
    会自动定位子标题的起止位置，只提取该子标题下的正文。

    Args:
        date_block (str): 日期块的内容，不包含日期标题本身（`## YYYY-MM-DD`）。
            应包含一个或多个 `### subheading` 格式的子标题及其内容。
        subheading (str): 要提取的子标题名称，必须精确匹配。

    Returns:
        str: 指定子标题下的正文内容，已去除首尾空白。
            如果指定的子标题不存在，返回空字符串。
            返回内容不包含子标题行本身。
    """
    # 匹配 ### subheading 格式（子标题）
    target_subheading_pattern = re.compile(rf"^###\s+{re.escape(subheading)}\s*$", re.MULTILINE)
    target_match = target_subheading_pattern.search(date_block)

    if not target_match:
        return ""

    # 找到下一个子标题（### 或 ## 开头）或者日期块结束
    next_subheading_pattern = re.compile(r"^#{1,3}\s+\S+.*$", re.MULTILINE)
    next_match = next_subheading_pattern.search(date_block, target_match.end())

    if next_match:
        content = date_block[target_match.end() : next_match.start()]
    else:
        content = date_block[target_match.end() :]

    return content.strip()


def extract_date_logs_from_file(
    file_path: Path | str, start_date: str, end_date: str | None = None, subheading: str = "all"
) -> dict[str, str]:
    """
    从按日期组织的 Markdown 文件中读取并提取指定日期范围的内容。

    该函数是 `read_md` 和 `extract_date_md` 的组合封装，提供了一步到位的
    文件读取和内容提取功能。适用于使用 `## YYYY-MM-DD` 格式作为日期标题、
    `### subheading` 格式作为子标题的结构化 Markdown 文件。

    Args:
        file_path (Path | str): Markdown 文件的绝对路径或相对路径。
            支持 Path 对象或字符串路径。如果文件不存在会自动创建空文件。
        start_date (str): 开始日期，格式必须为 'YYYY-MM-DD'（如 '2026-05-08'）。
        end_date (Optional[str], optional): 结束日期，格式为 'YYYY-MM-DD'。
            如果为 None，则只提取 start_date 当天的内容。默认为 None。
        subheading (str, optional): 要提取的子标题名称。默认为 "all"。
            - "all": 提取该日期下所有子标题的内容
            - 具体子标题名: 只提取该子标题下的内容

    Returns:
        Dict[str, str]: 字典，key 为日期字符串（'YYYY-MM-DD'），value 为该日期下的内容。
            返回格式与 `extract_date_md` 相同。

    Example:
        >>> extract_date_logs_from_file("log.md", "2026-05-08")
        {'2026-05-08': '### 工作\\n完成开发'}
        >>> extract_date_logs_from_file("log.md", "2026-05-08", "2026-05-09", "工作")
        {'2026-05-08': '完成开发', '2026-05-09': '修复bug'}
    """
    content = read_md(file_path)
    return extract_date_md(content, start_date, end_date, subheading)


def prompts_md_load(file_path: Path | str) -> dict[str, Any]:
    """
    从 prompt markdown 文件中加载所有 prompts 及其元数据。

    该函数用于解析按照 prompt 管理规范组织的 Markdown 文件，提取文件级元数据、
    各个 prompt 的名称、版本信息和内容。文件格式要求：
    - 文件级 frontmatter（YAML）包含 module、description、author
    - 一级标题 `#` 表示 prompt 名称
    - 二级标题 `## metadata` 包含 YAML 格式的元数据
    - 二级标题 `## v1`, `## v2` 等表示各个版本的 prompt 内容
    - 使用 `---` 分隔不同的 prompts

    Args:
        file_path (Path | str): Prompt markdown 文件的绝对路径或相对路径。
            支持 Path 对象或字符串路径。

    Returns:
        Dict[str, Any]: 包含文件级元数据和所有 prompts 的字典，结构如下：
            {
                "module": str,           # 模块名称
                "description": str,      # 模块描述
                "author": str,           # 作者
                "prompts": {
                    "prompt_name": {
                        "metadata": {
                            "active_version": str,
                            "version_history": dict
                        },
                        "versions": {
                            "v1": str,   # 版本内容
                            "v2": str
                        }
                    }
                }
            }

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件格式错误（缺少 frontmatter、metadata 等）

    Example:
        >>> data = prompts_md_load("templates/prompts/schedule_prompts.md")
        >>> data["module"]
        'schedule'
        >>> data["prompts"]["activity_summary"]["metadata"]["active_version"]
        'v2'
        >>> data["prompts"]["activity_summary"]["versions"]["v2"]
        '### task\\n你需要依据用户数据总结...'
    """
    if isinstance(file_path, str):
        file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt 文件不存在: {file_path}")

    content = file_path.read_text(encoding="utf-8")

    # 1. 解析文件级 frontmatter
    frontmatter_pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL | re.MULTILINE)
    frontmatter_match = frontmatter_pattern.match(content)

    if not frontmatter_match:
        raise ValueError(f"文件缺少 frontmatter: {file_path}")

    frontmatter_yaml = frontmatter_match.group(1)
    frontmatter = yaml.safe_load(frontmatter_yaml)

    # 提取 frontmatter 后的正文内容
    body_content = content[frontmatter_match.end() :]

    # 2. 按 --- 分割 prompt 块
    prompt_blocks = re.split(r"\n---\s*\n", body_content)

    prompts = {}

    for block in prompt_blocks:
        block = block.strip()
        if not block:
            continue

        # 3. 提取一级标题作为 prompt 名称
        title_pattern = re.compile(r"^#\s+(\S+)", re.MULTILINE)
        title_match = title_pattern.search(block)

        if not title_match:
            continue

        prompt_name = title_match.group(1)

        # 4. 提取 metadata 部分
        metadata_pattern = re.compile(
            r"^##\s+metadata\s*\n```yaml\s*\n(.*?)\n```", re.MULTILINE | re.DOTALL
        )
        metadata_match = metadata_pattern.search(block)

        if not metadata_match:
            raise ValueError(f"Prompt '{prompt_name}' 缺少 metadata 部分")

        metadata_yaml = metadata_match.group(1)
        metadata = yaml.safe_load(metadata_yaml)

        # 5. 提取所有版本内容
        versions = {}
        version_pattern = re.compile(r"^##\s+(v\d+)\s*\n", re.MULTILINE)

        for version_match in version_pattern.finditer(block):
            version_name = version_match.group(1)
            version_start = version_match.end()

            # 找到下一个二级标题或块结束，需要跳过代码块内部的二级标题
            version_end = len(block)

            # 使用深度计数来跟踪代码块嵌套
            code_block_depth = 0
            pos = version_start

            while pos < len(block):
                # 检查是否是代码块标记
                if block[pos : pos + 3] == "```":
                    # 检查后面的字符来判断是开始还是结束
                    next_char_pos = pos + 3
                    # 跳过空白字符（空格和制表符）
                    while next_char_pos < len(block) and block[next_char_pos] in " \t":
                        next_char_pos += 1

                    # 判断是开始还是结束
                    if next_char_pos < len(block) and block[next_char_pos] not in "\n\r":
                        # 后面有非换行字符（语言标识），这是代码块开始
                        code_block_depth += 1
                    else:
                        # 后面是换行或结束，这是代码块结束
                        if code_block_depth > 0:
                            code_block_depth -= 1

                    pos += 3
                    continue

                # 如果不在代码块内部，检查是否是行首的 ##
                if (
                    code_block_depth == 0
                    and (pos == 0 or block[pos - 1] == "\n")
                    and block[pos : pos + 2] == "##"
                    and (pos + 2 >= len(block) or block[pos + 2] in " \n")
                ):
                    version_end = pos
                    break

                pos += 1

            version_content = block[version_start:version_end].strip()

            # 解析 ```md ``` 代码块，只提取代码块内的内容
            # 由于前面的 version_end 查找已经正确处理了嵌套，这里只需要简单去掉最外层标记
            if version_content.startswith("```md"):
                # 找到第一个换行后的内容
                first_newline = version_content.find("\n")
                if first_newline != -1:
                    # 找到最后一个 ```（这应该是最外层的结束标记）
                    last_backticks = version_content.rfind("```")
                    if last_backticks > first_newline:
                        version_content = version_content[
                            first_newline + 1 : last_backticks
                        ].strip()

            versions[version_name] = version_content

        prompts[prompt_name] = {"metadata": metadata, "versions": versions}

    return {
        "module": frontmatter.get("module", ""),
        "description": frontmatter.get("description", ""),
        "author": frontmatter.get("author", ""),
        "prompts": prompts,
    }


# 如果直接运行当前脚本，可以作为一个轻量的命令行测试使用
if __name__ == "__main__":
    sample_md = """
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
"""
    print("=== 测试只取单天 ===")
    print(extract_date_md(sample_md, "2026-04-16"))

    print("\n=== 测试取范围 (10号到16号) 包含边界 ===")
    res = extract_date_md(sample_md, "2026-04-10", "2026-04-16")
    for date, txt in res.items():
        print(f"[{date}日内的数据] -> {txt[:15]}...")
