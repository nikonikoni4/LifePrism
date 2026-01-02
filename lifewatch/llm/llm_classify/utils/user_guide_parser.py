"""用户指南 Markdown 文档解析器"""

import json
import re
from pathlib import Path

from lifewatch.llm.llm_classify.schemas.user_guide_schemas import (
    GuideSection,
    UserGuide,
)


def parse_user_guide(file_path: str | Path) -> UserGuide:
    """
    解析用户指南 Markdown 文件，提取所有 JSON 代码块并转换为 UserGuide 结构。

    Args:
        file_path: 用户指南 Markdown 文件路径

    Returns:
        UserGuide: 解析后的用户指南数据结构

    Raises:
        FileNotFoundError: 文件不存在
        json.JSONDecodeError: JSON 解析失败
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"用户指南文件不存在: {file_path}")

    content = file_path.read_text(encoding="utf-8")
    sections = _extract_json_sections(content)

    return UserGuide(sections=sections)


def _extract_json_sections(markdown_content: str) -> list[GuideSection]:
    """
    从 Markdown 内容中提取所有 JSON 代码块并解析为 GuideSection 列表。

    Args:
        markdown_content: Markdown 文档内容

    Returns:
        list[GuideSection]: 解析后的章节列表
    """
    # 匹配 ```json ... ``` 代码块
    json_pattern = r"```json\s*\n(.*?)\n```"
    matches = re.findall(json_pattern, markdown_content, re.DOTALL)

    sections = []
    for json_str in matches:
        try:
            # 清理可能的注释（JSON 标准不支持注释）
            cleaned_json = _clean_json_string(json_str)
            data = json.loads(cleaned_json)
            section = GuideSection(**data)
            sections.append(section)
        except json.JSONDecodeError as e:
            # 记录错误但继续解析其他章节
            print(f"JSON 解析警告: {e}")
            continue

    return sections


def _clean_json_string(json_str: str) -> str:
    """
    清理 JSON 字符串中的潜在问题。

    - 移除单行注释
    - 移除尾随逗号
    - 处理可能的格式问题

    Args:
        json_str: 原始 JSON 字符串

    Returns:
        str: 清理后的 JSON 字符串
    """
    # 移除 // 单行注释
    lines = json_str.split("\n")
    cleaned_lines = []
    for line in lines:
        # 简单移除 // 注释（注意：这不处理字符串内的 //）
        comment_idx = line.find("//")
        if comment_idx != -1:
            # 检查是否在引号内（简单检查）
            quote_count = line[:comment_idx].count('"') - line[:comment_idx].count(
                '\\"'
            )
            if quote_count % 2 == 0:
                line = line[:comment_idx]
        cleaned_lines.append(line)

    result = "\n".join(cleaned_lines)

    # 移除数组或对象末尾的尾随逗号
    result = re.sub(r",(\s*[}\]])", r"\1", result)

    return result


def get_default_user_guide_path() -> Path:
    """获取默认的用户指南文件路径（位于 utils 目录下）"""
    return Path(__file__).parent / "user_guide.md"


def load_user_guide() -> UserGuide:
    """
    加载默认路径的用户指南。

    Returns:
        UserGuide: 解析后的用户指南数据结构
    """
    return parse_user_guide(get_default_user_guide_path())


# ============ 便捷查询函数 ============


def search_sections_by_keyword(
    guide: UserGuide, keyword: str
) -> list[GuideSection]:
    """
    根据关键词搜索相关章节。

    Args:
        guide: 用户指南实例
        keyword: 搜索关键词

    Returns:
        list[GuideSection]: 匹配的章节列表
    """
    keyword_lower = keyword.lower()
    results = []

    def search_recursive(sections: list[GuideSection]):
        for section in sections:
            # 检查关键词列表
            if any(keyword_lower in kw.lower() for kw in section.keywords):
                results.append(section)
            # 检查标题
            elif keyword_lower in section.title.lower():
                results.append(section)
            # 检查摘要
            elif keyword_lower in section.abstract.lower():
                results.append(section)
            # 递归搜索子章节
            if section.content:
                search_recursive(section.content)

    search_recursive(guide.sections)
    return results


def get_section_hierarchy(
    guide: UserGuide, section_id: str
) -> list[GuideSection]:
    """
    获取指定章节的完整层级路径（从根到该章节）。

    Args:
        guide: 用户指南实例
        section_id: 目标章节 ID

    Returns:
        list[GuideSection]: 从根章节到目标章节的路径列表
    """

    def find_path(
        sections: list[GuideSection], target_id: str, current_path: list[GuideSection]
    ) -> list[GuideSection] | None:
        for section in sections:
            new_path = current_path + [section]
            if section.id == target_id:
                return new_path
            if section.content:
                result = find_path(section.content, target_id, new_path)
                if result:
                    return result
        return None

    return find_path(guide.sections, section_id, []) or []


def flatten_sections(guide: UserGuide) -> list[GuideSection]:
    """
    将所有章节扁平化为一个列表（深度优先遍历）。

    Args:
        guide: 用户指南实例

    Returns:
        list[GuideSection]: 所有章节的扁平列表
    """
    result = []

    def flatten_recursive(sections: list[GuideSection]):
        for section in sections:
            result.append(section)
            if section.content:
                flatten_recursive(section.content)

    flatten_recursive(guide.sections)
    return result


if __name__ == "__main__":
    guide = load_user_guide()
    print(guide.get_children_summary("faq"))
    