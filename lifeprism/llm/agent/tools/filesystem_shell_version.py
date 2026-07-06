"""文件系统工具"""

import re
from pathlib import Path
from typing import Any

from lifeprism.config import ALLOWED_DIRS, settings
from lifeprism.llm.agent.tools.base import ERROR, SUCCESS, Tool
from lifeprism.utils import get_logger

logger = get_logger(__name__)

# 高危命令黑名单（不区分大小写）
#
# ⚠️ 已知安全问题（待修复）：
# 1. 黑名单机制容易被绕过（别名、字符串拼接、编码、变量等）
# 2. 正则表达式存在 ReDoS 风险（如 .* 的灾难性回溯）
# 3. 转义机制不完整（只转义了部分特殊字符）
# 4. 根本解决方案：使用 create_subprocess_exec 参数化执行，或用 Python 原生代码替代 PowerShell
#    参考：asyncio.create_subprocess_exec("powershell", "-Command", "Get-ChildItem", "-LiteralPath", path)
# 5. 当前黑名单仅作为辅助防护，不应作为唯一的安全措施
#
DANGEROUS_COMMANDS = [
    # 删除命令
    r"\brm\b",
    r"\brmdir\b",
    r"\bdel\b",
    r"\berase\b",
    r"\brd\b",
    r"Remove-Item",
    r"Remove-ItemProperty",
    r"Clear-RecycleBin",
    # 格式化磁盘命令（注意：不包括 Format-Table 等格式化输出命令）
    r"\bformat\s+[a-z]:",
    r"Format-Volume",
    # 系统关键操作
    r"\bshutdown\b",
    r"\breboot\b",
    r"Stop-Computer",
    r"Restart-Computer",
    # 权限提升（修复 ReDoS：.* 改为 [^;]* 限制回溯）
    r"\bsudo\b",
    r"\brunas\b",
    r"Start-Process[^;]*-Verb\s+RunAs",
    # 网络命令（可能外泄数据，修复 ReDoS）
    r"\bcurl\b[^;]*https?://",
    r"\bwget\b[^;]*https?://",
    r"Invoke-WebRequest[^;]*https?://",
    r"Invoke-RestMethod[^;]*https?://",
    # 进程操作
    r"\bkill\b",
    r"\btaskkill\b",
    r"Stop-Process",
    # 注册表操作
    r"\breg\b.*delete",
    r"\breg\b.*add",
    r"Remove-ItemProperty.*HKLM",
    r"Remove-ItemProperty.*HKCU",
    # 磁盘操作
    r"\bdiskpart\b",
    r"Clear-Disk",
    r"Initialize-Disk",
    # 危险的 PowerShell 命令
    r"Invoke-Expression",
    r"Invoke-Command",
    r"\biex\b",
    r"\bicm\b",
    # 文件覆盖
    r">\s*nul",
    r"2>&1",
    r"/dev/null",
]


def _check_command_safety(command: str) -> tuple[bool, str]:
    """检查命令是否包含高危操作

    ⚠️ 安全警告：
    此函数使用黑名单机制，存在以下已知问题：
    1. 可被绕过：PowerShell 别名、字符串拼接、编码、变量引用等方式可绕过检测
    2. 转义不完整：当前只转义了部分特殊字符（单引号、双引号），但 PowerShell 还有
       反引号(`)、美元符($)、分号(;)、管道(|)、与号(&)等特殊字符未处理
    3. 仅作辅助防护：不应作为唯一的安全措施，建议配合权限限制、沙箱等机制

    根本解决方案：
    - 使用 asyncio.create_subprocess_exec() 参数化执行，避免 shell 解析
    - 或使用 Python 原生代码（pathlib、os 等）替代 PowerShell 命令

    Args:
        command: 要检查的命令字符串

    Returns:
        Tuple[bool, str]: (是否安全, 错误信息)
                          如果安全，返回 (True, "")
                          如果不安全，返回 (False, 错误信息)
    """
    for pattern in DANGEROUS_COMMANDS:
        match = re.search(pattern, command, re.IGNORECASE)
        if match:
            matched = match.group()
            logger.warning("检测到高危命令: %s in command: %s", matched, command)
            return False, f"检测到高危命令模式: {matched}，已阻止执行"

    return True, ""


# 问题1：需要限制阅读工具的返回字符长度吗？
# 需要：
# 问题2：阅读工具需要什么参数
# 1. 路径 2. 阅读的行号 3. 读取的最大字符限制  4. 正文内容还是md文档的frontmatter内容
# 问题3： 要不要剥离 frontmatter内容 作为一个独立的工具？
# 不，
# 增加：only_frontmatter参数,表示是否只返回frontmatter内容


class _FileTool(Tool):
    """文件系统工具基类，提供路径权限验证功能"""

    def __init__(self):
        self.allowed_dir_path: list[Path] = settings.allowed_dir_path
        logger.debug("允许的工作目录: %s", self.allowed_dir_path)

    def _check_workspace_permission(self, file_path: str) -> tuple[bool, str]:
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

        return (
            False,
            f"没有权限访问该文件: {file_path}，允许的工作目录为: {[str(p) for p in self.allowed_dir_path]}",
        )


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
        return (
            "读取文件内容，支持按行号范围读取正文或读取 frontmatter。"
            "返回：content(内容), read_ratio(已读内容占全文比例), last_line(最后行号)"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "文件路径（绝对路径或相对路径）",
                    "minLength": 1,
                },
                "start_line": {
                    "type": "integer",
                    "description": "开始行号（从0开始，相对于正文，only_frontmatter=True时忽略）",
                    "minimum": 0,
                    "default": 0,
                },
                "end_line": {
                    "type": ["integer", "null"],
                    "description": "结束行号（None表示读取到文件末尾，相对于正文）",
                    "minimum": 0,
                    "default": None,
                },
                "only_frontmatter": {
                    "type": "boolean",
                    "description": "是否只返回 frontmatter 内容（忽略 start_line 和 end_line）",
                    "default": False,
                },
                "max_chars": {
                    "type": "integer",
                    "description": "最大字符数限制",
                    "minimum": 1,
                    "maximum": 100000,
                    "default": 1024,
                },
            },
            "required": ["file_path"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行文件读取操作

        Args:
            **kwargs: 工具参数（file_path, start_line, end_line, only_frontmatter, max_chars）

        Returns:
            str: 执行结果（成功返回 JSON 格式的结果，失败返回错误信息）
        """
        import json

        # 提取参数（使用默认值）
        file_path = kwargs.get("file_path")
        start_line = kwargs.get("start_line", 0)
        end_line = kwargs.get("end_line")
        only_frontmatter = kwargs.get("only_frontmatter", False)
        max_chars = kwargs.get("max_chars", 1024)
        if not file_path:
            return f"{ERROR}文件路径不能为空"

        # 权限检查
        is_allowed, error_msg = self._check_workspace_permission(file_path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        # 调用底层实现
        result = _read_file(
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            only_frontmatter=only_frontmatter,
            max_chars=max_chars,
        )

        # 检查是否有错误
        if "error" in result:
            return f"{ERROR}{result['error']}"

        # 返回成功结果
        return f"{SUCCESS}{json.dumps(result, ensure_ascii=False)}"


def _read_file(
    file_path: str,
    start_line: int = 0,
    end_line: int | None = None,
    only_frontmatter: bool = False,
    max_chars: int = 1024,
) -> dict[str, Any]:
    """读取文件内容

    Args:
        file_path: 文件路径
        start_line: 开始行号（从0开始，相对于正文，only_frontmatter=True时忽略）
        end_line: 结束行号（None表示读取到文件末尾，相对于正文，only_frontmatter=True时忽略）
        only_frontmatter: 是否只返回frontmatter内容
        max_chars: 最大字符数限制

    Returns:
        dict: 包含以下字段
            - content (str): 文件内容（only_frontmatter=True时返回frontmatter，否则返回正文）
            - read_ratio (float): 已读取内容占总内容的比例
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
                "error": f"文件 {file_path} 不存在",
            }

        with open(file_path, encoding="utf-8") as f:
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

            # 应用字符数限制
            if len(content) > max_chars:
                content = content[:max_chars]

            # 计算读取比例和最后一行
            read_ratio = len(content) / total_chars if total_chars > 0 else 0.0
            last_line = len(frontmatter_lines) - 1 if frontmatter_lines else -1

            logger.debug(
                "读取文件 %s frontmatter: 字符数 %s/%s, 比例 %.2f%%",
                file_path,
                len(content),
                total_chars,
                read_ratio * 100,
            )

            return {"content": content, "read_ratio": read_ratio, "last_line": last_line}

        # 读取正文内容
        total_body_chars = sum(len(line) for line in body_lines)
        total_body_lines = len(body_lines)

        # 处理行号范围
        if start_line >= total_body_lines:
            logger.debug("start_line (%s) 超出文件行数 (%s)", start_line, total_body_lines)
            return {"content": "", "read_ratio": 0.0, "last_line": -1}

        # 确定实际的结束行号
        actual_end_line = end_line if end_line is not None else total_body_lines - 1
        actual_end_line = min(actual_end_line, total_body_lines - 1)

        # 检查行号范围有效性
        if start_line > actual_end_line:
            logger.debug("start_line (%s) > end_line (%s)", start_line, actual_end_line)
            return {"content": "", "read_ratio": 0.0, "last_line": -1}

        # 截取行范围
        selected_lines = body_lines[start_line : actual_end_line + 1]
        content = "".join(selected_lines)

        # 应用字符数限制
        actual_last_line = actual_end_line
        if len(content) > max_chars:
            # 截断内容并重新计算最后一行
            content = content[:max_chars]
            # 计算截断后的实际行数
            char_count = 0
            for i, line in enumerate(selected_lines):
                char_count += len(line)
                if char_count >= max_chars:
                    actual_last_line = start_line + i
                    break

        # 计算读取比例
        read_ratio = len(content) / total_body_chars if total_body_chars > 0 else 0.0

        logger.debug(
            "读取文件 %s: 行范围 [%s, %s], 字符数 %s/%s, 比例 %.2f%%",
            file_path,
            start_line,
            actual_last_line,
            len(content),
            total_body_chars,
            read_ratio * 100,
        )

        return {"content": content, "read_ratio": read_ratio, "last_line": actual_last_line}

    except UnicodeDecodeError as e:
        logger.error("文件编码错误 %s: %s", file_path, e)
        return {
            "content": "",
            "read_ratio": 0.0,
            "last_line": -1,
            "error": f"文件编码错误: {str(e)}",
        }
    except Exception as e:
        logger.error("读取文件 %s 时出错: %s", file_path, e)
        return {
            "content": "",
            "read_ratio": 0.0,
            "last_line": -1,
            "error": f"读取文件时出错: {str(e)}",
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
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["file_path", "content"],
        }

    async def execute(self, **kwargs: Any) -> Any:
        file_path = kwargs.get("file_path")
        content = kwargs.get("content")
        if not file_path or not content:
            return f"{ERROR}: 缺少参数 file_path 或 content"
        try:
            # 确保文件路径在允许的目录中
            permission, error_msg = self._check_workspace_permission(file_path)
            if not permission:
                return f"{ERROR}: {error_msg}"
            # 写入文件内容
            file_path = Path(file_path)
            # 确保路径和文件存在
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info("文件写入成功: %s", file_path)
            return f"{SUCCESS}: 文件 {file_path} 已成功写入"
        except Exception as e:
            return f"{ERROR}: 写入文件 {file_path} 时出错: {str(e)}"


# ==========================================
# 编辑文件内容工具
# ==========================================


def _replace_content(
    file_path: str, old_content: str, new_content: str, replace_all: bool = False
) -> dict[str, Any]:
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
        with open(file_path, encoding="utf-8") as f:
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
            message = (
                f"文件 {file_path} 更新成功，替换了第 1 个匹配项（共找到 {match_count} 个匹配项）"
            )
            logger.debug(message)
        else:
            message = f"文件 {file_path} 更新成功，替换了 {replaced_count} 个匹配项"
            logger.debug(message)

        return {"message": message, "replaced_count": replaced_count}

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
        return (
            "通过替换内容的方式编辑文件。"
            "使用场景：1. 直接替换旧内容为新内容 2. 在某处插入新内容（将原文替换为原文+新增内容）"
        )

    @property
    def parameters(self) -> dict[str, Any]:
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
# 文件树工具
# ==========================================


class FileTreeTool(_FileTool):
    """文件树工具，用于查看目录结构"""

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "file_tree"

    @property
    def description(self) -> str:
        return "获取文件树结构。使用场景：1. 查看文件树结构 2. 分析文件组织结构"

    @property
    def parameters(self) -> dict[str, Any]:
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
            **kwargs: 工具参数（dir_path, recursive, max_depth, show_hidden）

        Returns:
            str: 执行结果（成功返回树形结构，失败返回错误信息）
        """
        import asyncio

        # 提取参数
        dir_path = kwargs.get("dir_path")
        recursive = kwargs.get("recursive", False)
        max_depth = kwargs.get("max_depth", 3)
        show_hidden = kwargs.get("show_hidden", False)

        # 参数验证
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

        # 构建 PowerShell 命令
        # Get-ChildItem -Path "路径" [-Recurse] [-Depth N] [-Force]
        #
        # ⚠️ 安全警告：当前使用字符串拼接构建命令，存在命令注入风险
        # 转义双引号只能防止语法错误，无法完全防止命令注入
        # 建议使用 create_subprocess_exec 或 Python 原生代码（pathlib）替代
        escaped_path = str(dir_path_obj).replace('"', '`"')
        cmd_parts = ["Get-ChildItem", "-Path", f'"{escaped_path}"']

        if recursive:
            cmd_parts.append("-Recurse")
            cmd_parts.append("-Depth")
            cmd_parts.append(str(max_depth))

        if show_hidden:
            cmd_parts.append("-Force")

        cmd = " ".join(cmd_parts)

        # 安全检查：防止命令注入
        is_safe, error_msg = _check_command_safety(cmd)
        if not is_safe:
            logger.error("FileTreeTool 命令安全检查失败: %s", error_msg)
            return f"{ERROR}{error_msg}"

        try:
            # 执行 PowerShell 命令
            process = await asyncio.create_subprocess_shell(
                f'powershell -Command "{cmd}"',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                encoding="utf-8",
                errors="ignore",
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.strip()
                logger.error("执行 PowerShell 命令失败: %s", error_msg)
                return f"{ERROR}执行命令失败: {error_msg}"

            output = stdout.strip()

            if not output:
                return f"{SUCCESS}目录: {dir_path_obj}\n(空目录)"

            result = f"目录: {dir_path_obj}\n{output}"
            logger.debug("获取文件树 %s 成功", dir_path)

            return f"{SUCCESS}{result}"

        except Exception as e:
            logger.error("获取文件树 %s 时出错: %s", dir_path, e)
            return f"{ERROR}获取文件树时出错: {str(e)}"


# ==========================================
# 搜索文件工具
# ==========================================


class SearchFileTool(_FileTool):
    """搜索文件工具，通过文件名匹配的方式搜索文件"""

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "search_file"

    @property
    def description(self) -> str:
        return (
            "依据文件名称，搜索文件位置，支持模糊匹配。"
            "注意：大型目录搜索可能需要较长时间，单个目录超时限制为30秒"
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_name": {
                    "type": "string",
                    "description": "要搜索的文件名（支持模糊匹配）",
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
            **kwargs: 工具参数（file_name, max_results）

        Returns:
            str: 执行结果（成功返回 JSON 格式的文件列表，失败返回错误信息）
        """
        import json

        file_name = kwargs.get("file_name")
        max_results = kwargs.get("max_results", 20)

        if not file_name:
            return f"{ERROR}文件名不能为空"

        # 调用异步底层实现
        result = await _search_files(
            file_name=file_name, allowed_dirs=self.allowed_dir_path, max_results=max_results
        )

        if "error" in result:
            return f"{ERROR}{result['error']}"

        return f"{SUCCESS}{json.dumps(result, ensure_ascii=False)}"


async def _search_files(
    file_name: str, allowed_dirs: list[Path], max_results: int = 20
) -> dict[str, Any]:
    """搜索文件（使用 asyncio 异步执行 PowerShell Get-ChildItem 命令）

    Args:
        file_name: 要搜索的文件名
        allowed_dirs: 允许搜索的目录列表
        max_results: 最大返回结果数

    Returns:
        dict: 包含以下字段
            - files (List[str]): 匹配的文件路径列表
            - count (int): 匹配的文件数量
    """
    import asyncio
    import platform

    try:
        matched_files = []

        # 如果没有指定允许目录，返回空结果
        if not allowed_dirs:
            return {"files": [], "count": 0}

        # 在每个允许的目录中搜索
        for allowed_dir in allowed_dirs:
            if not allowed_dir.exists():
                continue

            # 构建命令
            if platform.system() == "Windows":
                # Windows 使用 PowerShell
                # 转义单引号防止命令注入
                escaped_dir = str(allowed_dir).replace("'", "''")
                filter_pattern = f"*{file_name}*"
                escaped_pattern = filter_pattern.replace("'", "''")
                cmd = f"Get-ChildItem -Path '{escaped_dir}' -Recurse -File -Filter '{escaped_pattern}' -ErrorAction SilentlyContinue | Select-Object -First {max_results - len(matched_files)} | ForEach-Object {{ $_.FullName }}"
                shell_cmd = f'powershell -NoProfile -Command "{cmd}"'
            else:
                # Linux/Mac 使用 find 命令
                shell_cmd = f"find '{allowed_dir}' -type f -iname '*{file_name}*' -print | head -n {max_results - len(matched_files)}"

            # 安全检查：防止命令注入
            is_safe, error_msg = _check_command_safety(shell_cmd)
            if not is_safe:
                logger.error("SearchFileTool 命令安全检查失败: %s", error_msg)
                continue  # 跳过这个目录，继续搜索其他目录

            try:
                # 使用 asyncio.create_subprocess_shell 异步执行命令
                process = await asyncio.create_subprocess_shell(
                    shell_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    encoding="utf-8",
                    errors="ignore",
                )

                # 等待命令执行完成，设置30秒超时
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

                except asyncio.TimeoutError:
                    logger.warning("搜索目录 %s 超时", allowed_dir)
                    try:
                        process.kill()
                        await process.wait()
                    except ProcessLookupError:
                        pass  # 进程已结束
                    continue

                if process.returncode == 0 and stdout:
                    # 解析输出的文件路径
                    for line in stdout.strip().split("\n"):
                        line = line.strip()  # 去除行首尾的空白字符（包括 \r）
                        if line:
                            matched_files.append(line)

                            # 达到最大结果数时停止
                            if len(matched_files) >= max_results:
                                break

            except Exception as e:
                logger.warning("搜索目录 %s 时出错: %s", allowed_dir, e)
                continue

            if len(matched_files) >= max_results:
                break

        logger.debug("搜索文件 '%s': 找到 %s 个匹配项", file_name, len(matched_files))

        return {"files": matched_files, "count": len(matched_files)}

    except Exception as e:
        logger.error("搜索文件 '%s' 时出错: %s", file_name, e)
        return {"error": f"搜索文件时出错: {str(e)}"}


# ==========================================
# 文件内容搜索工具
# ==========================================


class SearchStringTool(_FileTool):
    """搜索字符串工具，使用 Select-String 命令搜索文件内容"""

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "search_string"

    @property
    def description(self) -> str:
        return "在文件或文件夹中搜索匹配指定模式的字符串，支持正则表达式"

    @property
    def parameters(self) -> dict[str, Any]:
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
            },
            "required": ["path", "pattern"],
        }

    async def execute(self, **kwargs: Any) -> str:
        """执行字符串搜索操作

        Args:
            **kwargs: 工具参数（path, pattern, context_lines）

        Returns:
            str: 执行结果（成功返回命令输出，失败返回错误信息）
        """
        # 提取参数
        path = kwargs.get("path")
        pattern = kwargs.get("pattern")
        context_lines = kwargs.get("context_lines", 0)

        # 参数验证
        if not path:
            return f"{ERROR}路径不能为空"
        if not pattern:
            return f"{ERROR}搜索模式不能为空"

        # 权限检查
        is_allowed, error_msg = self._check_workspace_permission(path)
        if not is_allowed:
            return f"{ERROR}{error_msg}"

        # 调用底层实现
        result = await _search_string(
            path=path,
            pattern=pattern,
            context_lines=context_lines,
        )

        # 检查是否有错误
        if "error" in result:
            return f"{ERROR}{result['error']}"

        # 返回成功结果
        return f"{SUCCESS}{result['result']}"


async def _search_string(path: str, pattern: str, context_lines: int = 0) -> dict[str, Any]:
    """使用 Select-String 搜索文件内容

    Args:
        path: 文件或文件夹路径
        pattern: 搜索模式（支持正则表达式）
        context_lines: 上下文行数

    Returns:
        dict: 包含以下字段
            - result (str): 搜索结果
            或
            - error (str): 错误信息
    """
    import asyncio

    try:
        # 检查路径是否存在
        path_obj = Path(path)
        if not path_obj.exists():
            logger.warning("路径不存在: %s", path)
            return {"error": f"路径 {path} 不存在"}

        # 构建 PowerShell 命令
        # 转义特殊字符
        escaped_pattern = pattern.replace("'", "''")
        escaped_path = str(path_obj.resolve()).replace("'", "''")

        # 判断是文件还是文件夹
        if path_obj.is_file():
            cmd = f"Select-String -Path '{escaped_path}' -Pattern '{escaped_pattern}'"
        else:
            cmd = f"Select-String -Path '{escaped_path}\\*' -Pattern '{escaped_pattern}' -Recurse"

        # 添加上下文参数
        if context_lines > 0:
            cmd += f" -Context {context_lines}"

        logger.debug("执行搜索命令: %s", cmd)

        # 安全检查：防止命令注入
        full_cmd = f'powershell.exe -NoProfile -Command "{cmd}"'
        is_safe, error_msg = _check_command_safety(full_cmd)
        if not is_safe:
            logger.error("SearchStringTool 命令安全检查失败: %s", error_msg)
            return {"error": error_msg}

        # 异步执行命令
        process = await asyncio.create_subprocess_shell(
            full_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            encoding="utf-8",
        )

        stdout, stderr = await process.communicate()

        # 检查错误
        if process.returncode != 0 and stderr:
            logger.error("搜索命令执行失败: %s", stderr)
            return {"error": f"搜索失败: {stderr}"}

        # 如果没有匹配结果
        if not stdout.strip():
            logger.debug("未找到匹配项: pattern=%s, path=%s", pattern, path)
            return {"result": "未找到匹配项"}

        logger.debug("搜索完成: pattern=%s, path=%s", pattern, path)
        return {"result": stdout}

    except Exception as e:
        logger.error("搜索字符串时出错: %s", e)
        return {"error": f"搜索时出错: {str(e)}"}


if __name__ == "__main__":

    def _check_workspace_permission(file_path: str) -> tuple[bool, str]:
        """检查文件路径是否在允许的工作目录内

        Args:
            file_path: 要检查的文件路径

        Returns:
            Tuple[bool, str]: (是否允许, 错误信息)
                              如果允许，返回 (True, "")
                              如果不允许，返回 (False, 错误信息)
        """
        workspace = settings.lifeprism_data_path
        allowed_dirs = ALLOWED_DIRS
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

        return (
            False,
            f"没有权限访问该文件: {file_path}，允许的工作目录为: {[str(p) for p in allowed_dir_path]}",
        )

    print(_check_workspace_permission("user/user.md"))
