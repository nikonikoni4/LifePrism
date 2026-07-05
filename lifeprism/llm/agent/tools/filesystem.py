"""文件系统工具"""
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import re
from lifeprism.llm.agent.tools.base import Tool,ERROR,SUCCESS
from lifeprism.utils import get_logger,DEBUG
from lifeprism.config import settings
import asyncio
logger = get_logger(__name__)
logger.debug(DEBUG)

class _FileTool(Tool):
    """文件系统工具基类，提供路径权限验证功能"""

    def __init__(self):
        self.allowed_dir_path: list[Path] = settings.allowed_dir_path
        logger.debug("允许的工作目录: %s", self.allowed_dir_path)
        
    
    
    def _check_workspace_permission(self, file_path: str) -> Tuple[bool, str]:
        """检查文件路径是否在允许的工作目录内
        
        Args:
            file_path: 要检查的文件路径
            
        Returns:
            Tuple[bool, str]: (是否允许, 错误信息)
                              如果允许，返回 (True, "")
                              如果不允许，返回 (False, 错误信息)
        """
        if not self.allowed_dir_path:
            return True, ""
        
        file_path_obj = Path(file_path).resolve()
        
        for allowed_dir in self.allowed_dir_path:
            try:
                file_path_obj.relative_to(allowed_dir)
                return True, ""
            except ValueError:
                continue
        
        return False, f"没有权限访问该文件: {file_path}，允许的工作目录为: {[str(p) for p in self.allowed_dir_path]}"

# ==========================================
# 读取文件工具
# ==========================================

class ReadFileTool(_FileTool):

    def __init__(self):
        super().__init__()
            

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return ("读取文件内容，支持按行号范围读取正文或读取 frontmatter。"
                "使用 limit 控制读取行数。返回：content(内容), read_ratio(已读内容占全文字符数比例，1.0=已读完), last_line(最后行号)")

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（绝对路径或相对路径）",
                    "minLength": 1,
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号（从1开始，相对于正文，only_frontmatter=True时忽略）",
                    "minimum": 1,
                    "default": 1,
                },
                "limit": {
                    "type": ["integer", "null"],
                    "description": "读取行数（None表示读取到文件末尾）",
                    "minimum": 1,
                    "default": None,
                },
                "only_frontmatter": {
                    "type": "boolean",
                    "description": "是否只返回 frontmatter 内容（忽略 offset 和 limit）",
                    "default": False,
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行文件读取操作

        Args:
            **kwargs: 工具参数（file_path, offset, limit, only_frontmatter）

        Returns:
            str: 执行结果（成功返回 JSON 格式的结果，失败返回错误信息）
        """
        import json

        # 提取参数（使用默认值）
        file_path = kwargs.get("file_path")
        offset = kwargs.get("offset", 1)
        limit = kwargs.get("limit", None)
        only_frontmatter = kwargs.get("only_frontmatter", False)

        if not file_path:
            return f"{ERROR}文件路径不能为空"

        # 权限检查
        is_allowed, error_msg = self._check_workspace_permission(file_path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        # 将 offset/limit 转换为 start_line/end_line（内部使用从0开始的索引）
        start_line = offset - 1  # offset 从1开始，start_line 从0开始
        if limit is not None:
            end_line = start_line + limit - 1  # 转换为闭区间的结束行号
        else:
            end_line = None  # None 表示读到文件末尾

        # 调用底层实现
        result = _read_file(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            only_frontmatter=only_frontmatter,
        )

        # 检查是否有错误
        if "error" in result:

            return f"{ERROR}{result['error']}"

        # 返回成功结果
        return f"{SUCCESS}{json.dumps(result, ensure_ascii=False)}"


def _read_file(
    file_path: str,
    start_line: int = 0,
    end_line: Optional[int] = None,
    only_frontmatter: bool = False,
) -> Dict[str, Any]:
    """读取文件内容

    Args:
        file_path: 文件路径
        start_line: 开始行号（从0开始，相对于正文，only_frontmatter=True时忽略）
        end_line: 结束行号（None表示读取到文件末尾，相对于正文，only_frontmatter=True时忽略）
        only_frontmatter: 是否只返回frontmatter内容

    Returns:
        dict: 包含以下字段
            - content (str): 文件内容（only_frontmatter=True时返回frontmatter，否则返回正文）
            - read_ratio (float): 已读取内容占全文字符数的比例（1.0=已读完正文）
            - last_line (int): 当前返回内容的最后一行行号（从0开始）
    """
    try:
        # 读取文件所有行
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.warning("文件不存在: %s", file_path)
            return {
                "content": "",
                "read_ratio": 0.0,
                "last_line": -1,
                "error": f"文件 {file_path} 不存在"
            }

        with open(file_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()

        # 分离 frontmatter 和正文
        frontmatter_lines = []
        body_lines = all_lines
        frontmatter_end_idx = 0

        # 检测 frontmatter（以 --- 开头和结尾）
        if len(all_lines) > 0 and all_lines[0].strip() == "---":
            # 查找第二个 ---
            for i in range(1, len(all_lines)):
                if all_lines[i].strip() == "---":
                    frontmatter_end_idx = i + 1
                    # 提取 frontmatter 内容（不包括 --- 分隔符）
                    frontmatter_lines = all_lines[1:i]
                    # 正文从 frontmatter 之后开始
                    body_lines = all_lines[frontmatter_end_idx:]
                    break

        # 如果只读取 frontmatter
        if only_frontmatter:
            content = "".join(frontmatter_lines)
            total_chars = sum(len(line) for line in frontmatter_lines)

            # 计算读取比例和最后一行
            read_ratio = 1.0 if total_chars > 0 else 0.0
            last_line = len(frontmatter_lines) - 1 if frontmatter_lines else -1

            logger.debug(
                "读取文件 %s frontmatter: 字符数 %s/%s, 比例 %.2f%%",
                file_path, len(content), total_chars, read_ratio * 100
            )

            return {
                "content": content,
                "read_ratio": read_ratio,
                "last_line": last_line
            }

        # 读取正文内容
        total_body_chars = sum(len(line) for line in body_lines)
        total_body_lines = len(body_lines)

        # 处理行号范围
        if start_line >= total_body_lines:
            logger.debug("start_line (%s) 超出文件行数 (%s)", start_line, total_body_lines)
            return {
                "content": "",
                "read_ratio": 0.0,
                "last_line": -1
            }

        # 确定实际的结束行号
        actual_end_line = end_line if end_line is not None else total_body_lines - 1
        actual_end_line = min(actual_end_line, total_body_lines - 1)

        # 检查行号范围有效性
        if start_line > actual_end_line:
            logger.debug("start_line (%s) > end_line (%s)", start_line, actual_end_line)
            return {
                "content": "",
                "read_ratio": 0.0,
                "last_line": -1
            }

        # 截取行范围
        selected_lines = body_lines[start_line:actual_end_line + 1]
        content = "".join(selected_lines)

        # 计算读取比例
        read_ratio = len(content) / total_body_chars if total_body_chars > 0 else 0.0

        logger.debug(
            "读取文件 %s: 行范围 [%s, %s], 字符数 %s/%s, 比例 %.2f%%",
            file_path, start_line, actual_end_line, len(content), total_body_chars, read_ratio * 100
        )

        return {
            "content": content,
            "read_ratio": read_ratio,
            "last_line": actual_end_line
        }

    except UnicodeDecodeError as e:
        logger.error("文件编码错误 %s: %s", file_path, e)
        return {
            "content": "",
            "read_ratio": 0.0,
            "last_line": -1,
            "error": f"文件编码错误: {str(e)}"
        }
    except Exception as e:
        logger.error("读取文件 %s 时出错: %s", file_path, e)
        return {
            "content": "",
            "read_ratio": 0.0,
            "last_line": -1,
            "error": f"读取文件时出错: {str(e)}"
        }



# ==========================================
# 写入文件工具
# ==========================================



class WriteFileTool(_FileTool):
    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "write_file"
    @property
    def description(self) -> str:
        return "编写一个全新的文件"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            'type':'object',
            'properties':{
                'file_path':{
                    'type':'string',
                    'description':'文件路径'
                },
                'content':{
                    'type':'string',
                    'description':'文件内容'
                }
            },
            'required':['file_path','content']
        }

    async def execute(self, **kwargs: Any) -> Any:
        file_path = kwargs.get("file_path")
        content = kwargs.get("content")
        if not file_path or not content:
            return f"{ERROR}: 缺少参数 file_path 或 content"
        try:
            # 确保文件路径在允许的目录中
            permission,error_msg = self._check_workspace_permission(file_path)
            if not permission:
                return f"{ERROR}: {error_msg}"
            # 写入文件内容
            file_path = Path(file_path)
            # 确保路径和文件存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"{SUCCESS}: 文件 {file_path} 已成功写入"
        except Exception as e:
            return f"{ERROR}: 写入文件 {file_path} 时出错: {str(e)}"
        

# ==========================================
# 编辑文件内容工具
# ==========================================

def _replace_content(
    file_path: str,
    old_content: str,
    new_content: str,
    replace_all: bool = False
) -> Dict[str, Any]:
    """替换文件内容的辅助函数

    Args:
        file_path: 文件路径
        old_content: 要替换的原内容
        new_content: 新内容
        replace_all: 是否替换所有匹配项（默认只替换第一个）

    Returns:
        dict: 包含以下字段
            - message (str): 成功消息
            - replaced_count (int): 替换次数
            或
            - error (str): 错误信息
    """
    try:
        # 检查文件是否存在
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.warning("文件不存在: %s", file_path)
            return {"error": f"文件 {file_path} 不存在"}

        # 读取文件全部内容
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # 检查 old_content 是否存在
        if old_content not in original_content:
            logger.warning("未找到要替换的内容: %s", file_path)
            return {"error": "未找到要替换的内容"}

        # 计算匹配次数
        match_count = original_content.count(old_content)

        # 执行替换
        if replace_all:
            updated_content = original_content.replace(old_content, new_content)
            replaced_count = match_count
        else:
            # 只替换第一个
            updated_content = original_content.replace(old_content, new_content, 1)
            replaced_count = 1

        # 写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(updated_content)

        # 构建成功消息
        if match_count > 1 and not replace_all:
            message = f"文件 {file_path} 更新成功，替换了第 1 个匹配项（共找到 {match_count} 个匹配项）"
            logger.info(message)
        else:
            message = f"文件 {file_path} 更新成功，替换了 {replaced_count} 个匹配项"
            logger.info(message)

        return {
            "message": message,
            "replaced_count": replaced_count
        }

    except UnicodeDecodeError as e:
        logger.error("文件编码错误 %s: %s", file_path, e)
        return {"error": f"文件编码错误: {str(e)}"}
    except PermissionError as e:
        logger.error("没有权限写入文件 %s: %s", file_path, e)
        return {"error": f"没有权限写入文件: {str(e)}"}
    except Exception as e:
        logger.error("更新文件 %s 时出错: %s", file_path, e)
        return {"error": f"更新文件时出错: {str(e)}"}

class EditFileTool(_FileTool):
    """编辑文件工具，通过内容替换的方式修改文件"""

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return ("通过替换内容的方式编辑文件。"
                "使用场景：1. 直接替换旧内容为新内容 2. 在某处插入新内容（将原文替换为原文+新增内容）")

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（绝对路径或相对路径）",
                    "minLength": 1,
                },
                "old_content": {
                    "type": "string",
                    "description": "要替换的原内容（必须完全匹配）",
                    "minLength": 1,
                },
                "new_content": {
                    "type": "string",
                    "description": "新内容（替换后的内容）",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "是否替换所有匹配项（默认只替换第一个）",
                    "default": False,
                },
            },
            "required": ["file_path", "old_content", "new_content"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行文件更新操作

        Args:
            **kwargs: 工具参数（file_path, old_content, new_content, replace_all）

        Returns:
            str: 执行结果（成功返回成功信息，失败返回错误信息）
        """
        # 提取参数
        file_path = kwargs.get("file_path")
        old_content = kwargs.get("old_content")
        new_content = kwargs.get("new_content")
        replace_all = kwargs.get("replace_all", False)

        # 参数验证
        if not file_path:
            return f"{ERROR}文件路径不能为空"
        if not old_content:
            return f"{ERROR}old_content 不能为空"
        if new_content is None:
            return f"{ERROR}new_content 不能为 None"

        # 权限检查
        is_allowed, error_msg = self._check_workspace_permission(file_path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        # 调用底层实现
        result = _replace_content(
            file_path=file_path,
            old_content=old_content,
            new_content=new_content,
            replace_all=replace_all,
        )

        # 检查是否有错误
        if "error" in result:
            return f"{ERROR}{result['error']}"

        # 返回成功结果
        return f"{SUCCESS}{result['message']}"



# ==========================================
# 文件树工具（纯 Python 实现）
# ==========================================

class FileTreeTool(_FileTool):
    """文件树工具 - 纯 Python 实现

    使用 pathlib 遍历目录，无命令注入风险
    """

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "file_tree_py"

    @property
    def description(self) -> str:
        return ("获取文件树结构。"
                "使用场景：1. 查看目录结构 2. 分析文件组织")

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dir_path": {
                    "type": "string",
                    "description": "目录路径（绝对路径或相对路径）",
                    "minLength": 1,
                },
                "recursive": {
                    "type": "boolean",
                    "description": "是否递归获取子目录（False=只看当前层，True=递归子目录）",
                    "default": False,
                },
                "max_depth": {
                    "type": "integer",
                    "description": "递归最大深度（仅在 recursive=True 时生效）",
                    "minimum": 1,
                    "maximum": 5,
                    "default": 3,
                },
                "show_hidden": {
                    "type": "boolean",
                    "description": "是否显示隐藏文件（以 . 开头的文件/文件夹）",
                    "default": False,
                },
            },
            "required": ["dir_path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行文件树查看操作

        Args:
            **kwargs: 工具参数

        Returns:
            str: 执行结果
        """
        dir_path = kwargs.get("dir_path")
        recursive = kwargs.get("recursive", False)
        max_depth = kwargs.get("max_depth", 3)
        show_hidden = kwargs.get("show_hidden", False)

        if not dir_path:
            return f"{ERROR}目录路径不能为空"

        # 权限检查
        is_allowed, error_msg = self._check_workspace_permission(dir_path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        # 检查路径是否存在
        dir_path_obj = Path(dir_path).resolve()
        if not dir_path_obj.exists():
            return f"{ERROR}目录 {dir_path} 不存在"

        if not dir_path_obj.is_dir():
            return f"{ERROR}路径 {dir_path} 不是目录"

        try:
            result = _build_file_tree(
                dir_path_obj,
                recursive=recursive,
                max_depth=max_depth,
                show_hidden=show_hidden,
                current_depth=0
            )

            if not result:
                return f"{SUCCESS}目录: {dir_path_obj}\n(空目录)"

            output = f"目录: {dir_path_obj}\n{result}"
            return f"{SUCCESS}{output}"

        except PermissionError as e:
            logger.error("没有权限访问目录 %s: %s", dir_path, e)
            return f"{ERROR}没有权限访问目录: {dir_path}"
        except Exception as e:
            logger.error("获取文件树 %s 时出错: %s", dir_path, e)
            return f"{ERROR}获取文件树时出错: {str(e)}"


def _build_file_tree(
    path: Path,
    recursive: bool,
    max_depth: int,
    show_hidden: bool,
    current_depth: int,
    prefix: str = ""
) -> str:
    """构建文件树字符串

    Args:
        path: 目录路径
        recursive: 是否递归
        max_depth: 最大深度
        show_hidden: 是否显示隐藏文件
        current_depth: 当前深度
        prefix: 当前行的前缀（用于缩进）

    Returns:
        str: 文件树字符串
    """
    if not recursive and current_depth > 0:
        return ""

    if recursive and current_depth >= max_depth:
        return ""

    lines = []

    try:
        # 获取目录下的所有项
        items = list(path.iterdir())

        # 过滤隐藏文件
        if not show_hidden:
            items = [item for item in items if not item.name.startswith('.')]

        # 排序：目录在前，文件在后，同类按名称排序
        items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

        for i, item in enumerate(items):
            is_last = (i == len(items) - 1)
            connector = "└── " if is_last else "├── "
            extension = "    " if is_last else "│   "

            # 获取文件信息
            try:
                stat = item.stat()
                size = stat.st_size

                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")

                    # 递归处理子目录
                    if recursive and current_depth < max_depth - 1:
                        subtree = _build_file_tree(
                            item,
                            recursive=recursive,
                            max_depth=max_depth,
                            show_hidden=show_hidden,
                            current_depth=current_depth + 1,
                            prefix=prefix + extension
                        )
                        if subtree:
                            lines.append(subtree)
                else:
                    size_str = _format_size(size)
                    # lines.append(f"{prefix}{connector}{item.name} ({size_str})")
                    lines.append(f"{prefix}{connector}{item.name} ")

            except (PermissionError, OSError) as e:
                # 无法访问的文件/目录
                lines.append(f"{prefix}{connector}❌ {item.name} (无法访问: {str(e)})")

    except PermissionError:
        return f"{prefix}(无权限访问)"
    except Exception as e:
        return f"{prefix}(错误: {str(e)})"

    return "\n".join(lines)


def _format_size(size: int) -> str:
    """格式化文件大小

    Args:
        size: 字节数

    Returns:
        str: 格式化后的大小字符串
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}PB"

# ==========================================
# 搜索文件工具（纯 Python 实现）
# ==========================================

class SearchFileTool(_FileTool):
    """搜索文件工具 - 纯 Python 实现

    使用 pathlib.rglob() 搜索文件，无命令注入风险
    """

    DEFAULT_TIMEOUT = 30.0

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "search_file_py"

    @property
    def description(self) -> str:
        return ("依据文件名称，搜索文件位置，支持模糊匹配。"
                "注意：大型目录搜索可能需要较长时间")

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search_dir": {
                    "type": "string",
                    "description": "要搜索的目录路径（绝对路径或相对路径），必须在允许的工作目录内",
                    "minLength": 1,
                },
                "file_name": {
                    "type": "string",
                    "description": "要搜索的文件名（支持模糊匹配，如 'test' 会匹配 'test.py', 'my_test.txt' 等）",
                    "minLength": 1,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
                "timeout": {
                    "type": "number",
                    "description": "超时时间（秒），默认30秒",
                    "minimum": 1,
                    "maximum": 300,
                },
                "max_depth": {
                    "type": ["integer", "null"],
                    "description": "最大搜索深度（相对于起始目录的层级），默认null 无限制",
                    "minimum": 1,
                    "maximum": 50,
                    "default": None,
                },
            },
            "required": ["file_name", "search_dir"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行文件搜索操作

        Args:
            **kwargs: 工具参数

        Returns:
            str: 执行结果
        """
        import json

        search_dir = kwargs.get("search_dir")
        file_name = kwargs.get("file_name")
        max_results = kwargs.get("max_results", 20)
        timeout = kwargs.get("timeout", self.DEFAULT_TIMEOUT)
        max_depth = kwargs.get("max_depth")

        if not search_dir:
            return f"{ERROR}搜索目录不能为空"
        if not file_name:
            return f"{ERROR}文件名不能为空"

        is_allowed, error_msg = self._check_workspace_permission(search_dir)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        try:
            async with asyncio.timeout(timeout):
                result = await asyncio.to_thread(
                    _search_files_py,
                    search_dir=search_dir,
                    file_name=file_name,
                    max_results=max_results,
                    max_depth=max_depth
                )
        except asyncio.TimeoutError:
            return f"{ERROR}搜索超时（{timeout}秒），请尝试缩小搜索范围或增加超时时间"

        if "error" in result:
            return f"{ERROR}{result['error']}"

        return f"{SUCCESS}{json.dumps(result, ensure_ascii=False)}"


def _search_files_py(
    search_dir: str,
    file_name: str,
    max_results: int = 20,
    max_depth: int | None = None
) -> Dict[str, Any]:
    """搜索文件（纯 Python 实现）

    Args:
        search_dir: 要搜索的目录
        file_name: 要搜索的文件名
        max_results: 最大返回结果数
        max_depth: 最大搜索深度（None 表示无限制）

    Returns:
        dict: 包含 files (文件路径列表) 和 count (数量)
    """
    try:
        matched_files = []

        search_path = Path(search_dir)
        if not search_path.exists():
            return {"error": f"搜索目录不存在: {search_dir}"}
        if not search_path.is_dir():
            return {"error": f"路径不是目录: {search_dir}"}

        file_name_lower = file_name.lower()

        try:
            for file_path in search_path.rglob("*"):
                if not file_path.is_file():
                    continue

                if max_depth is not None:
                    try:
                        depth = len(file_path.relative_to(search_path).parts) - 1
                        if depth > max_depth:
                            continue
                    except ValueError:
                        continue

                if file_name_lower in file_path.name.lower():
                    matched_files.append(str(file_path))

                    if len(matched_files) >= max_results:
                        break

        except PermissionError:
            return {"error": f"没有权限访问目录: {search_dir}"}
        except Exception as e:
            return {"error": f"搜索目录 {search_dir} 时出错: {e}"}

        logger.debug("搜索文件 '%s' in '%s': 找到 %s 个匹配项", file_name, search_dir, len(matched_files))

        return {
            "files": matched_files,
            "count": len(matched_files)
        }

    except Exception as e:
        logger.error("搜索文件 '%s' 时出错: %s", file_name, e)
        return {"error": f"搜索文件时出错: {str(e)}"}


# ==========================================
# 文件内容搜索工具（纯 Python 实现）
# ==========================================

class SearchStringTool(_FileTool):
    """搜索字符串工具 - 纯 Python 实现

    使用 Python 的 re 模块搜索文件内容，无命令注入风险
    """

    DEFAULT_TIMEOUT = 30.0

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "search_string_py"

    @property
    def description(self) -> str:
        return "在文件或文件夹中搜索匹配指定模式的字符串，支持正则表达式"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件或文件夹路径（绝对路径或相对路径）",
                    "minLength": 1,
                },
                "pattern": {
                    "type": "string",
                    "description": "搜索模式（支持正则表达式）",
                    "minLength": 1,
                },
                "context_lines": {
                    "type": "integer",
                    "description": "上下文行数（显示匹配行前后的行数）",
                    "minimum": 0,
                    "maximum": 10,
                    "default": 0,
                },
                "case_sensitive": {
                    "type": "boolean",
                    "description": "是否区分大小写",
                    "default": False,
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                },
                "timeout": {
                    "type": "number",
                    "description": "超时时间（秒），默认30秒",
                    "minimum": 1,
                    "maximum": 300,
                },
                "max_depth": {
                    "type": ["integer", "null"],
                    "description": "最大搜索深度（相对于起始目录的层级），默认null 无限制",
                    "minimum": 1,
                    "maximum": 50,
                    "default": None,
                },
            },
            "required": ["path", "pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行字符串搜索操作

        Args:
            **kwargs: 工具参数

        Returns:
            str: 执行结果
        """
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")
        context_lines = kwargs.get("context_lines", 0)
        case_sensitive = kwargs.get("case_sensitive", False)
        max_results = kwargs.get("max_results", 100)
        timeout = kwargs.get("timeout", self.DEFAULT_TIMEOUT)
        max_depth = kwargs.get("max_depth")

        if not path:
            return f"{ERROR}路径不能为空"
        if not pattern:
            return f"{ERROR}搜索模式不能为空"

        is_allowed, error_msg = self._check_workspace_permission(path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        try:
            async with asyncio.timeout(timeout):
                result = await asyncio.to_thread(
                    _search_string_py,
                    path=path,
                    pattern=pattern,
                    context_lines=context_lines,
                    case_sensitive=case_sensitive,
                    max_results=max_results,
                    max_depth=max_depth
                )
        except asyncio.TimeoutError:
            return f"{ERROR}搜索超时（{timeout}秒），请尝试缩小搜索范围或增加超时时间"

        if "error" in result:
            return f"{ERROR}{result['error']}"

        return f"{SUCCESS}{result['result']}"


# 允许搜索的文本文件后缀（硬约束）
ALLOWED_SEARCH_EXTENSIONS = {
    '.txt', '.md', '.json', '.log', '.csv'
}

def _search_string_py(
    path: str,
    pattern: str,
    context_lines: int = 0,
    case_sensitive: bool = False,
    max_results: int = 100,
    max_depth: int | None = None
) -> Dict[str, Any]:
    """使用 Python re 模块搜索文件内容

    Args:
        path: 文件或文件夹路径
        pattern: 搜索模式（正则表达式）
        context_lines: 上下文行数
        case_sensitive: 是否区分大小写
        max_results: 最大结果数
        max_depth: 最大搜索深度（None 表示无限制）

    Returns:
        dict: 包含 result (搜索结果) 或 error (错误信息)
    """
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return {"error": f"路径 {path} 不存在"}

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {"error": f"无效的正则表达式: {str(e)}"}

        results = []
        total_matches = 0

        if path_obj.is_file():
            # 硬约束：直接指定的文件也必须是允许的文本文件后缀
            if path_obj.suffix.lower() not in ALLOWED_SEARCH_EXTENSIONS:
                return {"error": f"文件 {path} 不是可搜索的文本文件类型，允许的后缀: {', '.join(sorted(ALLOWED_SEARCH_EXTENSIONS))}"}
            files_to_search = [path_obj]
        else:
            base_depth = len(path_obj.absolute().parts)
            files_to_search = []
            for f in path_obj.rglob("*"):
                if not f.is_file():
                    continue
                if max_depth is not None:
                    file_depth = len(f.absolute().parts) - base_depth
                    if file_depth > max_depth:
                        continue
                files_to_search.append(f)

        for file_path in files_to_search:
            if total_matches >= max_results:
                break

            # 硬约束：只搜索允许的文本文件后缀
            if file_path.suffix.lower() not in ALLOWED_SEARCH_EXTENSIONS:
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, start=1):
                    if total_matches >= max_results:
                        break

                    if regex.search(line):
                        # 构建结果
                        match_info = {
                            "file": str(file_path),
                            "line": line_num,
                            "content": line.rstrip('\n')
                        }

                        # 添加上下文
                        if context_lines > 0:
                            context_before = []
                            context_after = []

                            # 前面的行
                            for i in range(max(0, line_num - context_lines - 1), line_num - 1):
                                context_before.append(f"  {i + 1}: {lines[i].rstrip()}")

                            # 后面的行
                            for i in range(line_num, min(len(lines), line_num + context_lines)):
                                context_after.append(f"  {i + 1}: {lines[i].rstrip()}")

                            match_info["context_before"] = context_before
                            match_info["context_after"] = context_after

                        results.append(match_info)
                        total_matches += 1

            except (UnicodeDecodeError, PermissionError):
                # 跳过二进制文件或无权限的文件
                continue
            except Exception as e:
                logger.warning("搜索文件 %s 时出错: %s", file_path, e)
                continue

        # 格式化输出
        if not results:
            return {"result": "未找到匹配项"}

        output_lines = []
        for match in results:
            output_lines.append(f"\n{match['file']}:{match['line']}")

            if "context_before" in match and match["context_before"]:
                output_lines.extend(match["context_before"])

            output_lines.append(f"> {match['line']}: {match['content']}")

            if "context_after" in match and match["context_after"]:
                output_lines.extend(match["context_after"])

        result_text = "\n".join(output_lines)
        result_text += f"\n\n共找到 {total_matches} 个匹配项"

        if total_matches >= max_results:
            result_text += f"（已达到最大结果数 {max_results}，可能还有更多匹配项）"

        logger.debug("搜索完成: pattern=%s, path=%s, matches=%s", pattern, path, total_matches)
        return {"result": result_text}

    except Exception as e:
        logger.error("搜索字符串时出错: %s", e)
        return {"error": f"搜索时出错: {str(e)}"}


if __name__ == "__main__":
    def _check_workspace_permission(file_path: str) -> Tuple[bool, str]:
        """检查文件路径是否在允许的工作目录内
        
        Args:
            file_path: 要检查的文件路径
            
        Returns:
            Tuple[bool, str]: (是否允许, 错误信息)
                              如果允许，返回 (True, "")
                              如果不允许，返回 (False, 错误信息)
        """
        workspace = settings.lifeprism_data_path
        allowed_dirs =  ALLOWED_DIRS
        allowed_dir_path: list[Path] = []
        for dir in allowed_dirs:
            allowed_dir_path.append(Path(workspace / dir).resolve())
        print(f"允许的工作目录: {[allowed_dir_path]}")
        if not allowed_dir_path:
            return True, ""
        
        file_path_obj = Path(file_path).resolve()
        
        for allowed_dir in allowed_dir_path:
            try:
                file_path_obj.relative_to(allowed_dir)
                return True, ""
            except ValueError:
                continue
        
        return False, f"没有权限访问该文件: {file_path}，允许的工作目录为: {[str(p) for p in allowed_dir_path]}"

    
    print(_check_workspace_permission("user/user.md"))



    