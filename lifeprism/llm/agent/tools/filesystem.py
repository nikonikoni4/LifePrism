"""文件系统工具"""
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from lifeprism.llm.agent.tools.base import Tool,ERROR,SUCCESS
from lifeprism.utils import get_logger,DEBUG
from lifeprism.config import settings,ALLOWED_DIRS

logger = get_logger(__name__)
logger.debug(DEBUG)
# 问题1：需要限制阅读工具的返回字符长度吗？
# 需要：
# 问题2：阅读工具需要什么参数
# 1. 路径 2. 阅读的行号 3. 读取的最大字符限制  4. 正文内容还是md文档的frontmatter内容
# 问题3： 要不要剥离 frontmatter内容 作为一个独立的工具？
# 不，
# 增加：only_frontmatter参数,表示是否只返回frontmatter内容






class _FileTool(Tool):
    """文件系统工具基类，提供路径权限验证功能"""
    
    def __init__(
        self, 
        workspace: Path | None = None, 
        allowed_dirs: list[str] | None = None
    ):
        self.workspace = workspace if workspace else settings.lifeprism_data_path
        self.allowed_dirs = allowed_dirs if allowed_dirs else ALLOWED_DIRS
        self.allowed_dir_path: list[Path] = []
        for dir in self.allowed_dirs:
            self.allowed_dir_path.append(Path(self.workspace / dir).resolve())
        logger.debug(f"允许的工作目录: {[self.allowed_dir_path]}")
        
    
    
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

class ReadFileTool(_FileTool):

    def __init__(self, workspace: Path | None = None, allowed_dirs: list[str] | None = None):
        super().__init__(workspace, allowed_dirs)
            

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return ("读取文件内容，支持按行号范围读取正文或读取 frontmatter。"
                "返回：content(内容), read_ratio(已读内容占全文比例), last_line(最后行号)")

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
        end_line = kwargs.get("end_line", None)
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
    end_line: Optional[int] = None,
    only_frontmatter: bool = False,
    max_chars: int = 1024
) -> Dict[str, Any]:
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
            logger.warning(f"文件不存在: {file_path}")
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

            # 应用字符数限制
            if len(content) > max_chars:
                content = content[:max_chars]

            # 计算读取比例和最后一行
            read_ratio = len(content) / total_chars if total_chars > 0 else 0.0
            last_line = len(frontmatter_lines) - 1 if frontmatter_lines else -1

            logger.debug(
                f"读取文件 {file_path} frontmatter: "
                f"字符数 {len(content)}/{total_chars}, "
                f"比例 {read_ratio:.2%}"
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
            logger.debug(f"start_line ({start_line}) 超出文件行数 ({total_body_lines})")
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
            logger.debug(f"start_line ({start_line}) > end_line ({actual_end_line})")
            return {
                "content": "",
                "read_ratio": 0.0,
                "last_line": -1
            }

        # 截取行范围
        selected_lines = body_lines[start_line:actual_end_line + 1]
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
            f"读取文件 {file_path}: "
            f"行范围 [{start_line}, {actual_last_line}], "
            f"字符数 {len(content)}/{total_body_chars}, "
            f"比例 {read_ratio:.2%}"
        )

        return {
            "content": content,
            "read_ratio": read_ratio,
            "last_line": actual_last_line
        }

    except UnicodeDecodeError as e:
        logger.error(f"文件编码错误 {file_path}: {e}")
        return {
            "content": "",
            "read_ratio": 0.0,
            "last_line": -1,
            "error": f"文件编码错误: {str(e)}"
        }
    except Exception as e:
        logger.error(f"读取文件 {file_path} 时出错: {e}")
        return {
            "content": "",
            "read_ratio": 0.0,
            "last_line": -1,
            "error": f"读取文件时出错: {str(e)}"
        }


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
            logger.warning(f"文件不存在: {file_path}")
            return {"error": f"文件 {file_path} 不存在"}

        # 读取文件全部内容
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        # 检查 old_content 是否存在
        if old_content not in original_content:
            logger.warning(f"未找到要替换的内容: {file_path}")
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
        logger.error(f"文件编码错误 {file_path}: {e}")
        return {"error": f"文件编码错误: {str(e)}"}
    except PermissionError as e:
        logger.error(f"没有权限写入文件 {file_path}: {e}")
        return {"error": f"没有权限写入文件: {str(e)}"}
    except Exception as e:
        logger.error(f"更新文件 {file_path} 时出错: {e}")
        return {"error": f"更新文件时出错: {str(e)}"}



class WriteFileTool(_FileTool):
    def __init__(self, workspace: Path | None = None, allowed_dirs: list[str] | None = None):
        super().__init__(workspace, allowed_dirs)

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
        



class EditFileTool(_FileTool):
    """编辑文件工具，通过内容替换的方式修改文件"""

    def __init__(self, workspace: Path | None = None, allowed_dirs: list[str] | None = None):
        super().__init__(workspace, allowed_dirs)

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
