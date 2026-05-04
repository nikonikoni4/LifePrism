"""ReadFileTool 单元测试"""
import pytest
import tempfile
import os
from pathlib import Path
from lifeprism.llm.agent.tools.filesystem import ReadFileTool, _read_file


@pytest.mark.core
class TestFileToolPermissions:
    """FileTool 权限功能测试（通过 ReadFileTool 测试）"""

    def test_init_with_workspace(self):
        """测试使用 workspace 初始化"""
        workspace = Path(tempfile.gettempdir())
        tool = ReadFileTool(workspace=workspace)

        assert len(tool.allowed_dir_path) >= 1
        assert workspace.resolve() in tool.allowed_dir_path

    def test_init_with_allowed_dirs(self):
        """测试使用 allowed_dirs 初始化"""
        allowed_dirs = [tempfile.gettempdir()]
        tool = ReadFileTool(workspace=None, allowed_dirs=allowed_dirs)

        assert len(tool.allowed_dir_path) >= 1

    def test_check_workspace_permission_allowed(self):
        """测试允许的路径"""
        workspace = Path(tempfile.gettempdir())
        tool = ReadFileTool(workspace=workspace)

        # 在允许的目录下创建临时文件
        with tempfile.NamedTemporaryFile(delete=False) as f:
            temp_path = f.name

        try:
            is_allowed, error_msg = tool._check_workspace_permission(temp_path)
            assert is_allowed is True
            assert error_msg == ""
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_check_workspace_permission_denied(self):
        """测试不允许的路径"""
        # 创建一个不在允许列表中的路径
        workspace = Path(tempfile.gettempdir()) / "allowed_dir"
        tool = ReadFileTool(workspace=workspace)

        # 使用一个明确不在 workspace 下的路径
        forbidden_path = "C:/Windows/System32/test.txt" if os.name == 'nt' else "/etc/passwd"

        is_allowed, error_msg = tool._check_workspace_permission(forbidden_path)
        assert is_allowed is False
        assert "没有权限访问该文件" in error_msg

    def test_check_workspace_permission_no_restriction(self):
        """测试无权限限制"""
        tool = ReadFileTool(workspace=None, allowed_dirs=None)

        is_allowed, error_msg = tool._check_workspace_permission("/any/path/file.txt")
        assert is_allowed is True
        assert error_msg == ""


@pytest.mark.core
class TestReadFileTool:
    """ReadFileTool 测试类"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # 清理
        import shutil
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_file_with_frontmatter(self, temp_dir):
        """创建带 frontmatter 的临时文件"""
        content = """---
title: 测试文档
author: Test User
version: 1.0
---
这是第一行正文
这是第二行正文
这是第三行正文
这是第四行正文
这是第五行正文
"""
        temp_path = os.path.join(temp_dir, "test_frontmatter.md")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)

        yield temp_path

    @pytest.fixture
    def temp_file_without_frontmatter(self, temp_dir):
        """创建不带 frontmatter 的临时文件"""
        content = """这是第一行
这是第二行
这是第三行
这是第四行
这是第五行
"""
        temp_path = os.path.join(temp_dir, "test_plain.txt")
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)

        yield temp_path

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = ReadFileTool()

        assert tool.name == "read_file"
        assert "读取文件内容" in tool.description
        assert tool.parameters["type"] == "object"
        assert "file_path" in tool.parameters["properties"]
        assert "file_path" in tool.parameters["required"]

    def test_tool_parameters_defaults(self):
        """测试参数默认值"""
        tool = ReadFileTool()
        params = tool.parameters["properties"]

        assert params["start_line"]["default"] == 0
        assert params["end_line"]["default"] is None
        assert params["only_frontmatter"]["default"] is False
        assert params["max_chars"]["default"] == 1024

    def test_tool_init_with_workspace(self, temp_dir):
        """测试使用 workspace 初始化"""
        tool = ReadFileTool(workspace=Path(temp_dir))

        assert len(tool.allowed_dir_path) >= 1
        assert Path(temp_dir).resolve() in tool.allowed_dir_path

    def test_tool_init_with_allowed_dirs(self, temp_dir):
        """测试使用 allowed_dirs 初始化"""
        tool = ReadFileTool(workspace=None, allowed_dirs=[temp_dir])

        assert len(tool.allowed_dir_path) >= 1

    @pytest.mark.asyncio
    async def test_execute_success(self, temp_dir, temp_file_without_frontmatter):
        """测试成功执行"""
        tool = ReadFileTool(workspace=Path(temp_dir))
        result = await tool.execute(file_path=temp_file_without_frontmatter)

        assert result.startswith("Success:")
        assert "content" in result
        assert "read_ratio" in result
        assert "last_line" in result

    @pytest.mark.asyncio
    async def test_execute_file_not_found(self, temp_dir):
        """测试文件不存在"""
        tool = ReadFileTool(workspace=Path(temp_dir))
        nonexistent_path = os.path.join(temp_dir, "nonexistent.txt")
        result = await tool.execute(file_path=nonexistent_path)

        assert result.startswith("Error:")
        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_execute_empty_path(self):
        """测试空路径"""
        tool = ReadFileTool()
        result = await tool.execute(file_path="")

        assert result.startswith("Error:")
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_execute_permission_denied(self, temp_dir, temp_file_without_frontmatter):
        """测试权限拒绝"""
        # 创建一个只允许访问其他目录的工具
        other_dir = tempfile.mkdtemp()
        try:
            tool = ReadFileTool(workspace=Path(other_dir))
            result = await tool.execute(file_path=temp_file_without_frontmatter)

            assert result.startswith("Error:")
            assert "没有权限访问该文件" in result
        finally:
            import shutil
            if os.path.exists(other_dir):
                shutil.rmtree(other_dir)

    @pytest.mark.asyncio
    async def test_execute_no_permission_restriction(self, temp_file_without_frontmatter):
        """测试无权限限制"""
        tool = ReadFileTool(workspace=None, allowed_dirs=None)
        result = await tool.execute(file_path=temp_file_without_frontmatter)

        assert result.startswith("Success:")

    def test_read_file_basic(self, temp_file_without_frontmatter):
        """测试基本文件读取"""
        result = _read_file(temp_file_without_frontmatter)

        assert "content" in result
        assert "read_ratio" in result
        assert "last_line" in result
        assert result["read_ratio"] == 1.0  # 读取全部内容
        assert result["last_line"] == 4  # 5行，最后一行索引为4
        assert "这是第一行" in result["content"]

    def test_read_file_with_line_range(self, temp_file_without_frontmatter):
        """测试按行号范围读取"""
        # 读取第1-2行（索引0-1）
        result = _read_file(temp_file_without_frontmatter, start_line=0, end_line=1)

        assert "这是第一行" in result["content"]
        assert "这是第二行" in result["content"]
        assert "这是第三行" not in result["content"]
        assert result["last_line"] == 1

    def test_read_file_with_start_line_only(self, temp_file_without_frontmatter):
        """测试只指定开始行号"""
        # 从第3行开始读取到末尾
        result = _read_file(temp_file_without_frontmatter, start_line=2)

        assert "这是第一行" not in result["content"]
        assert "这是第三行" in result["content"]
        assert "这是第五行" in result["content"]
        assert result["last_line"] == 4

    def test_read_file_with_max_chars(self, temp_file_without_frontmatter):
        """测试字符数限制"""
        result = _read_file(temp_file_without_frontmatter, max_chars=20)

        assert len(result["content"]) <= 20
        assert result["read_ratio"] < 1.0

    def test_read_frontmatter_only(self, temp_file_with_frontmatter):
        """测试只读取 frontmatter"""
        result = _read_file(temp_file_with_frontmatter, only_frontmatter=True)

        assert "title: 测试文档" in result["content"]
        assert "author: Test User" in result["content"]
        assert "这是第一行正文" not in result["content"]

    def test_read_body_without_frontmatter(self, temp_file_with_frontmatter):
        """测试读取正文（不包含 frontmatter）"""
        result = _read_file(temp_file_with_frontmatter, only_frontmatter=False)

        assert "title: 测试文档" not in result["content"]
        assert "这是第一行正文" in result["content"]
        assert result["last_line"] == 4  # 5行正文，最后一行索引为4

    def test_read_body_line_range_with_frontmatter(self, temp_file_with_frontmatter):
        """测试带 frontmatter 文件的正文行号范围读取"""
        # 读取正文的第2-3行（索引1-2）
        result = _read_file(temp_file_with_frontmatter, start_line=1, end_line=2)

        assert "这是第一行正文" not in result["content"]
        assert "这是第二行正文" in result["content"]
        assert "这是第三行正文" in result["content"]
        assert "这是第四行正文" not in result["content"]
        assert result["last_line"] == 2

    def test_read_file_not_exists(self):
        """测试文件不存在"""
        result = _read_file("/nonexistent/file.txt")

        assert "error" in result
        assert "不存在" in result["error"]
        assert result["content"] == ""
        assert result["read_ratio"] == 0.0
        assert result["last_line"] == -1

    def test_read_file_start_line_out_of_range(self, temp_file_without_frontmatter):
        """测试开始行号超出范围"""
        result = _read_file(temp_file_without_frontmatter, start_line=100)

        assert result["content"] == ""
        assert result["read_ratio"] == 0.0
        assert result["last_line"] == -1

    def test_read_file_invalid_line_range(self, temp_file_without_frontmatter):
        """测试无效的行号范围（start > end）"""
        result = _read_file(temp_file_without_frontmatter, start_line=3, end_line=1)

        assert result["content"] == ""
        assert result["read_ratio"] == 0.0
        assert result["last_line"] == -1

    def test_read_frontmatter_when_not_exists(self, temp_file_without_frontmatter):
        """测试读取不存在的 frontmatter"""
        result = _read_file(temp_file_without_frontmatter, only_frontmatter=True)

        assert result["content"] == ""
        assert result["read_ratio"] == 0.0
        assert result["last_line"] == -1

    def test_read_ratio_calculation(self, temp_file_without_frontmatter):
        """测试读取比例计算"""
        # 读取全部
        result_full = _read_file(temp_file_without_frontmatter)
        assert result_full["read_ratio"] == 1.0

        # 读取一半
        result_half = _read_file(temp_file_without_frontmatter, start_line=0, end_line=2)
        assert 0 < result_half["read_ratio"] < 1.0

    def test_max_chars_truncation(self, temp_file_with_frontmatter):
        """测试字符数限制截断"""
        result = _read_file(temp_file_with_frontmatter, max_chars=30)

        assert len(result["content"]) == 30
        assert result["read_ratio"] < 1.0
        # 验证 last_line 被正确更新
        assert result["last_line"] >= 0

    @pytest.mark.asyncio
    async def test_tool_schema_generation(self):
        """测试工具 schema 生成"""
        tool = ReadFileTool()
        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "read_file"
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"]["type"] == "object"

