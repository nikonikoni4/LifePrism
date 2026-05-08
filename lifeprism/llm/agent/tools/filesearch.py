"""文件搜索工具 - 纯 Python 实现版本

本模块提供三个文件搜索相关工具的纯 Python 实现，不依赖外部命令行工具。
相比 filesystem.py 中的 PowerShell 实现，本实现：
- 更安全：无命令注入风险
- 跨平台：Windows/Linux/Mac 统一实现
- 更快：无进程启动开销
- 更可控：可以精确控制搜索行为

包含工具：
1. FileTreeToolPy - 查看目录结构
2. SearchFileToolPy - 按文件名搜索文件
3. SearchStringToolPy - 在文件内容中搜索字符串
"""

from typing import Dict, Any, List, Tuple
from pathlib import Path
import re
from datetime import datetime
from lifeprism.llm.agent.tools.base import Tool, ERROR, SUCCESS
from lifeprism.utils import get_logger
from lifeprism.config import settings

logger = get_logger(__name__)


class _FileToolPy(Tool):
    """文件工具基类（纯 Python 版本）"""

    def __init__(self):
        self.allowed_dir_path: list[Path] = settings.allowed_dir_path
        logger.debug(f"允许的工作目录: {self.allowed_dir_path}")

    def _check_workspace_permission(self, file_path: str) -> Tuple[bool, str]:
        """检查文件路径是否在允许的工作目录内

        Args:
            file_path: 要检查的文件路径

        Returns:
            Tuple[bool, str]: (是否允许, 错误信息)
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

        return False, f"没有权限访问该路径: {file_path}，允许的工作目录为: {[str(p) for p in self.allowed_dir_path]}"


# ==========================================
# 文件树工具（纯 Python 实现）
# ==========================================

class FileTreeToolPy(_FileToolPy):
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
        return ("获取文件树结构（纯 Python 实现）。"
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
                    "maximum": 10,
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
            logger.error(f"没有权限访问目录 {dir_path}: {e}")
            return f"{ERROR}没有权限访问目录: {dir_path}"
        except Exception as e:
            logger.error(f"获取文件树 {dir_path} 时出错: {e}")
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
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

                if item.is_dir():
                    # 目录
                    lines.append(f"{prefix}{connector}📁 {item.name}/ ({mtime})")

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
                    # 文件
                    size_str = _format_size(size)
                    lines.append(f"{prefix}{connector}📄 {item.name} ({size_str}, {mtime})")

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

class SearchFileToolPy(_FileToolPy):
    """搜索文件工具 - 纯 Python 实现

    使用 pathlib.rglob() 搜索文件，无命令注入风险
    """

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "search_file_py"

    @property
    def description(self) -> str:
        return ("依据文件名称，搜索文件位置，支持模糊匹配（纯 Python 实现）。"
                "注意：大型目录搜索可能需要较长时间")

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
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
            },
            "required": ["file_name"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行文件搜索操作

        Args:
            **kwargs: 工具参数

        Returns:
            str: 执行结果
        """
        import json

        file_name = kwargs.get("file_name")
        max_results = kwargs.get("max_results", 20)

        if not file_name:
            return f"{ERROR}文件名不能为空"

        # 在所有允许的目录中搜索
        result = _search_files_py(
            file_name=file_name,
            allowed_dirs=self.allowed_dir_path,
            max_results=max_results
        )

        if "error" in result:
            return f"{ERROR}{result['error']}"

        return f"{SUCCESS}{json.dumps(result, ensure_ascii=False)}"


def _search_files_py(
    file_name: str,
    allowed_dirs: list[Path],
    max_results: int = 20
) -> Dict[str, Any]:
    """搜索文件（纯 Python 实现）

    Args:
        file_name: 要搜索的文件名
        allowed_dirs: 允许搜索的目录列表
        max_results: 最大返回结果数

    Returns:
        dict: 包含 files (文件路径列表) 和 count (数量)
    """
    try:
        matched_files = []

        if not allowed_dirs:
            return {"files": [], "count": 0}

        # 将文件名转换为小写用于不区分大小写的匹配
        file_name_lower = file_name.lower()

        for allowed_dir in allowed_dirs:
            if not allowed_dir.exists():
                continue

            try:
                # 使用 rglob 递归搜索所有文件
                for file_path in allowed_dir.rglob("*"):
                    # 只处理文件，跳过目录
                    if not file_path.is_file():
                        continue

                    # 模糊匹配：文件名包含搜索关键词（不区分大小写）
                    if file_name_lower in file_path.name.lower():
                        matched_files.append(str(file_path))

                        # 达到最大结果数时停止
                        if len(matched_files) >= max_results:
                            break

            except PermissionError:
                logger.warning(f"没有权限访问目录: {allowed_dir}")
                continue
            except Exception as e:
                logger.warning(f"搜索目录 {allowed_dir} 时出错: {e}")
                continue

            if len(matched_files) >= max_results:
                break

        logger.debug(f"搜索文件 '{file_name}': 找到 {len(matched_files)} 个匹配项")

        return {
            "files": matched_files,
            "count": len(matched_files)
        }

    except Exception as e:
        logger.error(f"搜索文件 '{file_name}' 时出错: {e}")
        return {"error": f"搜索文件时出错: {str(e)}"}


# ==========================================
# 文件内容搜索工具（纯 Python 实现）
# ==========================================

class SearchStringToolPy(_FileToolPy):
    """搜索字符串工具 - 纯 Python 实现

    使用 Python 的 re 模块搜索文件内容，无命令注入风险
    """

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "search_string_py"

    @property
    def description(self) -> str:
        return "在文件或文件夹中搜索匹配指定模式的字符串，支持正则表达式（纯 Python 实现）"

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

        if not path:
            return f"{ERROR}路径不能为空"
        if not pattern:
            return f"{ERROR}搜索模式不能为空"

        # 权限检查
        is_allowed, error_msg = self._check_workspace_permission(path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        # 调用底层实现
        result = _search_string_py(
            path=path,
            pattern=pattern,
            context_lines=context_lines,
            case_sensitive=case_sensitive,
            max_results=max_results
        )

        if "error" in result:
            return f"{ERROR}{result['error']}"

        return f"{SUCCESS}{result['result']}"


def _search_string_py(
    path: str,
    pattern: str,
    context_lines: int = 0,
    case_sensitive: bool = False,
    max_results: int = 100
) -> Dict[str, Any]:
    """使用 Python re 模块搜索文件内容

    Args:
        path: 文件或文件夹路径
        pattern: 搜索模式（正则表达式）
        context_lines: 上下文行数
        case_sensitive: 是否区分大小写
        max_results: 最大结果数

    Returns:
        dict: 包含 result (搜索结果) 或 error (错误信息)
    """
    try:
        path_obj = Path(path)
        if not path_obj.exists():
            return {"error": f"路径 {path} 不存在"}

        # 编译正则表达式
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return {"error": f"无效的正则表达式: {str(e)}"}

        results = []
        total_matches = 0

        # 判断是文件还是目录
        if path_obj.is_file():
            files_to_search = [path_obj]
        else:
            # 递归获取所有文件
            files_to_search = [f for f in path_obj.rglob("*") if f.is_file()]

        for file_path in files_to_search:
            if total_matches >= max_results:
                break

            try:
                # 尝试以文本模式读取文件
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                # 搜索匹配行
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
                logger.warning(f"搜索文件 {file_path} 时出错: {e}")
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

        logger.debug(f"搜索完成: pattern={pattern}, path={path}, matches={total_matches}")
        return {"result": result_text}

    except Exception as e:
        logger.error(f"搜索字符串时出错: {e}")
        return {"error": f"搜索时出错: {str(e)}"}
