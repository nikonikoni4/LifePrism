"""用户指南文档结构的 Dataclass Schemas"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SummaryOption:
    """
    摘要输出选项，控制 get_children_summary 返回哪些字段。
    
    默认返回 id, title, abstract 三个字段。
    设置对应字段为 False 可以排除该字段。
    """
    id: bool = True
    title: bool = True
    abstract: bool = True
    keywords: bool = False  # 默认不包含关键词
    
    def get_enabled_fields(self) -> list[str]:
        """获取启用的字段名列表"""
        fields = []
        if self.id:
            fields.append("id")
        if self.title:
            fields.append("title")
        if self.abstract:
            fields.append("abstract")
        if self.keywords:
            fields.append("keywords")
        return fields


@dataclass
class GuideSection:
    """
    用户指南章节/组件/操作的通用数据结构。

    支持三种层级：
    - 章节级：使用 abstract + items + content（概述 + 索引 + 详情）
    - 组件级：使用 abstract + details + content（概述 + 静态属性 + 可操作元素）
    - 操作级：仅使用 abstract（单一功能描述）
    """

    title: str  # 标题（必填）
    abstract: str  # 摘要，用于快速检索匹配（必填）
    id: Optional[str] = None  # 唯一标识，便于引用和跳转（章节级必填）
    keywords: list[str] = field(default_factory=list)  # 关键词列表，提升匹配准确性
    items: list[str] = field(default_factory=list)  # 子章节标题列表（导航索引）
    details: dict[str, str] = field(default_factory=dict)  # 详细属性（位置、功能等静态信息）
    content: list["GuideSection"] = field(default_factory=list)  # 嵌套的子章节内容

    def __post_init__(self):
        """确保 content 中的元素都是 GuideSection 实例"""
        if self.content:
            self.content = [
                GuideSection(**item) if isinstance(item, dict) else item
                for item in self.content
            ]

    def to_dict(self) -> dict:
        """转换为字典格式"""
        result = {
            "title": self.title,
            "abstract": self.abstract,
        }
        if self.id:
            result["id"] = self.id
        if self.keywords:
            result["keywords"] = self.keywords
        if self.items:
            result["items"] = self.items
        if self.details:
            result["details"] = self.details
        if self.content:
            result["content"] = [section.to_dict() for section in self.content]
        return result


@dataclass
class UserGuide:
    """
    完整的用户指南文档结构。

    包含多个顶级章节（GuideSection）。
    """

    sections: list[GuideSection] = field(default_factory=list)
    _id_list_cache: list[str] = field(default_factory=list, init=False)  # ID 缓存，不参与初始化

    def __post_init__(self):
        """确保 sections 中的元素都是 GuideSection 实例，并缓存所有 ID"""
        if self.sections:
            self.sections = [
                GuideSection(**section) if isinstance(section, dict) else section
                for section in self.sections
            ]
        # 初始化时缓存所有 ID
        self._id_list_cache = self._collect_all_ids()

    def get_section_by_id(self, section_id: str) -> Optional[GuideSection]:
        """根据 ID 查找章节（支持嵌套查找）"""

        def search_in_sections(
            sections: list[GuideSection], target_id: str
        ) -> Optional[GuideSection]:
            for section in sections:
                if section.id == target_id:
                    return section
                if section.content:
                    found = search_in_sections(section.content, target_id)
                    if found:
                        return found
            return None

        return search_in_sections(self.sections, section_id)

    def _collect_all_ids(self) -> list[str]:
        """递归收集所有章节的 ID"""
        def collect_ids(sections: list[GuideSection]) -> list[str]:
            ids = []
            for section in sections:
                if section.id:
                    ids.append(section.id)
                if section.content:
                    ids.extend(collect_ids(section.content))
            return ids
        
        return collect_ids(self.sections)
    
    def get_all_ids(self) -> list[str]:
        """
        获取所有章节的 ID 列表（使用缓存）。
        
        Returns:
            list[str]: 所有章节 ID 的列表，按深度优先顺序排列
        """
        return self._id_list_cache
    
    def refresh_id_cache(self) -> list[str]:
        """
        刷新 ID 缓存。当 sections 被修改后调用此方法更新缓存。
        
        Returns:
            list[str]: 更新后的 ID 列表
        """
        self._id_list_cache = self._collect_all_ids()
        return self._id_list_cache
    
    def is_valid_id(self, section_id: str) -> bool:
        """
        检查给定的 ID 是否存在于缓存中。
        
        Args:
            section_id: 要检查的章节 ID
        
        Returns:
            bool: ID 是否有效
        """
        return section_id in self._id_list_cache

    def get_all_keywords(self) -> set[str]:
        """获取所有章节的关键词集合"""

        def collect_keywords(sections: list[GuideSection]) -> set[str]:
            keywords = set()
            for section in sections:
                keywords.update(section.keywords)
                if section.content:
                    keywords.update(collect_keywords(section.content))
            return keywords

        return collect_keywords(self.sections)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {"sections": [section.to_dict() for section in self.sections]}

    def get_children_summary(
        self, 
        section_id: Optional[str] = None,
        options: Optional[SummaryOption] = None
    ) -> list[dict[str, Optional[str | list[str]]]]:
        """
        获取下一个层级的摘要信息，支持自定义返回字段。

        Args:
            section_id: 目标章节 ID。如果为 None，返回顶级章节的摘要。
            options: 摘要选项，控制返回哪些字段。默认返回 id, title, abstract。

        Returns:
            list[dict]: 子章节摘要列表，包含选项中指定的字段
        
        Example:
            # 只返回 id 和 abstract
            guide.get_children_summary(options=SummaryOption(title=False))
            
            # 返回 id, title, abstract, keywords
            guide.get_children_summary(options=SummaryOption(keywords=True))
        """
        # 使用默认选项
        if options is None:
            options = SummaryOption()
        
        def build_summary(s: GuideSection) -> dict[str, Optional[str | list[str]]]:
            """根据选项构建单个章节的摘要"""
            result: dict[str, Optional[str | list[str]]] = {}
            if options.id:
                result["id"] = s.id
            if options.title:
                result["title"] = s.title
            if options.abstract:
                result["abstract"] = s.abstract
            if options.keywords:
                result["keywords"] = s.keywords
            return result
        
        if section_id is None:
            # 返回顶级章节的摘要
            return [build_summary(s) for s in self.sections]

        # 查找指定章节
        section = self.get_section_by_id(section_id)
        if section is None or not section.content:
            return []

        # 返回子章节摘要
        return [build_summary(s) for s in section.content]

    def get_max_depth(self, section_id: Optional[str] = None) -> int:
        """
        计算从指定章节开始还剩下多少层嵌套。

        Args:
            section_id: 起始章节 ID。如果为 None，从顶级开始计算整体深度。

        Returns:
            int: 剩余嵌套层数。
                 - 如果没有子内容，返回 0
                 - 如果有一层子内容，返回 1
                 - 以此类推
        """

        def calculate_depth(sections: list[GuideSection]) -> int:
            if not sections:
                return 0
            max_child_depth = 0
            for section in sections:
                if section.content:
                    child_depth = calculate_depth(section.content)
                    max_child_depth = max(max_child_depth, child_depth + 1)
            return max_child_depth

        if section_id is None:
            # 从顶级开始计算
            if not self.sections:
                return 0
            return calculate_depth(self.sections) + 1  # +1 包含顶级本身

        # 从指定章节开始计算
        section = self.get_section_by_id(section_id)
        if section is None:
            return 0
        if not section.content:
            return 0
        return calculate_depth(section.content) + 1
    def transform_to_table(self, json_data: dict | list[dict]) -> str:
        """
        将字典或字典列表转换为 Markdown 表格格式
        
        Args:
            json_data: 单个字典或字典列表
        
        Returns:
            str: Markdown 表格格式的字符串
        
        Example:
            输入:
            {
                "id": "id1",
                "title": "title1",
                "abstract": "abstract1"
            }
            
            输出:
            | id | title | abstract |
            | --- | --- | --- |
            | id1 | title1 | abstract1 |
            
            输入 (列表):
            [
                {"id": "id1", "title": "title1", "abstract": "abstract1"},
                {"id": "id2", "title": "title2", "abstract": "abstract2"}
            ]
            
            输出:
            | id | title | abstract |
            | --- | --- | --- |
            | id1 | title1 | abstract1 |
            | id2 | title2 | abstract2 |
        """
        # 统一处理为列表格式
        if isinstance(json_data, dict):
            data_list = [json_data]
        else:
            data_list = json_data
        
        if not data_list:
            return ""
        
        # 获取所有列名（使用第一个字典的键）
        headers = list(data_list[0].keys())
        
        # 构建表头行
        header_row = "| " + " | ".join(headers) + " |"
        
        # 构建分隔行
        separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
        
        # 构建数据行
        data_rows = []
        for item in data_list:
            row_values = [str(item.get(h, "")) for h in headers]
            data_rows.append("| " + " | ".join(row_values) + " |")
        
        # 组合所有行
        return "\n".join([header_row, separator_row] + data_rows)

    def get_section_as_markdown(
        self, 
        section_id: str, 
        include_self: bool = True,
        start_level: int = 2,
        max_heading_depth: int = 4
    ) -> str:
        """
        将指定章节及其所有子内容转换为 Markdown 格式。
        
        使用 `#` 标题格式展示层级结构，超过最大深度后使用 `-` 列表格式。
        
        Args:
            section_id: 目标章节的 ID
            include_self: 是否包含该章节本身，默认为 True
            start_level: 起始标题层级，默认为 2（即 ##）
            max_heading_depth: 最大标题深度，默认为 4（即最多到 ####）
                              超过此深度后使用列表格式
        
        Returns:
            str: Markdown 格式的字符串
        
        Example:
            # start_level=2, max_heading_depth=4 时的输出格式:
            ## Category Settings（分类设置）
            管理分类层级结构...
            
            ### 添加分类
            点击添加按钮...
            
            #### 子操作
            具体操作说明...
            
            - 更深层级: 使用列表格式...
        """
        section = self.get_section_by_id(section_id)
        if section is None:
            return ""
        
        def format_section(s: GuideSection, depth: int = 0) -> list[str]:
            """递归格式化章节为 Markdown"""
            lines = []
            current_level = start_level + depth
            
            # 判断使用标题还是列表格式
            if current_level <= max_heading_depth:
                # 使用 # 标题格式
                heading = "#" * current_level
                lines.append(f"{heading} {s.title}")
                if s.abstract:
                    lines.append(s.abstract)
                lines.append("")  # 空行
            else:
                # 超过最大深度，使用列表格式
                list_indent = current_level - max_heading_depth - 1
                prefix = "  " * list_indent + "- "
                title_line = f"{prefix}{s.title}"
                if s.abstract:
                    title_line += f": {s.abstract}"
                lines.append(title_line)
            
            # 格式化 details（如果有）
            if s.details:
                if current_level <= max_heading_depth:
                    for key, value in s.details.items():
                        lines.append(f"- {key}: {value}")
                    lines.append("")
                else:
                    list_indent = current_level - max_heading_depth
                    for key, value in s.details.items():
                        lines.append(f"{'  ' * list_indent}- {key}: {value}")
            
            # 格式化 items（如果有且没有 content）
            if s.items and not s.content:
                if current_level <= max_heading_depth:
                    for item in s.items:
                        lines.append(f"- {item}")
                    lines.append("")
                else:
                    list_indent = current_level - max_heading_depth
                    for item in s.items:
                        lines.append(f"{'  ' * list_indent}- {item}")
            
            # 递归处理子章节
            if s.content:
                for child in s.content:
                    lines.extend(format_section(child, depth + 1))
            
            return lines
        
        if include_self:
            result_lines = format_section(section, 0)
        else:
            # 不包含自身，只处理子章节
            result_lines = []
            if section.content:
                for child in section.content:
                    result_lines.extend(format_section(child, 0))
        
        # 清理多余空行
        result = "\n".join(result_lines)
        while "\n\n\n" in result:
            result = result.replace("\n\n\n", "\n\n")
        return result.strip()

