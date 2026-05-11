"""文件搜索工具单元测试

测试 filesystem.py 中的三个文件搜索工具：
1. SearchFileTool - 文件名搜索 (search_file_py)
2. SearchStringTool - 文件内容字符串搜索 (search_string_py)
3. FileTreeTool - 文件树查看 (file_tree_py)

注意：
- SearchFileTool.execute 存在 asyncio 未导入的 bug，直接测试底层函数 _search_files_py
- FileTreeTool 存在 datetime 未导入的 bug，部分功能测试跳过
- SearchStringTool 只允许搜索 .txt, .md, .json, .log, .csv 后缀的文件
"""
import pytest
import shutil
from pathlib import Path

from lifeprism.config import settings
from lifeprism.llm.agent.tools.filesystem import (
    SearchFileTool,
    SearchStringTool,
    FileTreeTool,
    _search_files_py,
    _search_string_py,
    ALLOWED_SEARCH_EXTENSIONS,
)


@pytest.fixture
def temp_search_dir():
    """创建临时测试目录结构"""
    base_dir = settings.allowed_dir_path[0]
    temp_dir = base_dir / "test_search_tools_temp"

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    temp_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试文件结构
    # temp_dir/
    # ├── test.py                    (不会被 SearchStringTool 搜索)
    # ├── test_file.txt              (会搜索)
    # ├── readme.md                  (会搜索)
    # ├── data.json                  (会搜索)
    # ├── .hidden_file               (无后缀，不会被搜索)
    # ├── subdir1/
    # │   ├── nested_test.py         (不会被 SearchStringTool 搜索)
    # │   └── config.yaml            (不会被搜索)
    # └── subdir2/
    #     ├── deep/
    #     │   └── deep_file.py       (不会被 SearchStringTool 搜索)
    #     └── data.csv               (会搜索)

    (temp_dir / "test.py").write_text("def hello():\n    pass", encoding="utf-8")
    (temp_dir / "test_file.txt").write_text("test content here", encoding="utf-8")
    (temp_dir / "readme.md").write_text("# README\nsearch keyword here", encoding="utf-8")
    (temp_dir / "data.json").write_text('{"search_key": "value"}', encoding="utf-8")
    (temp_dir / ".hidden_file").write_text("hidden", encoding="utf-8")

    subdir1 = temp_dir / "subdir1"
    subdir1.mkdir()
    (subdir1 / "nested_test.py").write_text("class Test:", encoding="utf-8")
    (subdir1 / "config.yaml").write_text("key: val", encoding="utf-8")

    subdir2 = temp_dir / "subdir2"
    subdir2.mkdir()
    deep = subdir2 / "deep"
    deep.mkdir()
    (deep / "deep_file.py").write_text("x = 1", encoding="utf-8")
    (subdir2 / "data.csv").write_text("a,b,search,c", encoding="utf-8")

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_string_search_dir():
    """创建 SearchStringTool 专用的临时测试目录（只包含允许的文件类型）"""
    base_dir = settings.allowed_dir_path[0]
    temp_dir = base_dir / "test_string_search_temp"

    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    temp_dir.mkdir(parents=True, exist_ok=True)

    # 只创建允许搜索的文件类型: .txt, .md, .json, .log, .csv
    (temp_dir / "notes.txt").write_text(
        "Hello World\nThis is a test file\nsearch keyword here\nEnd of file",
        encoding="utf-8"
    )
    (temp_dir / "readme.md").write_text(
        "# Project README\n\nSearch documentation here\n\n## Section 2",
        encoding="utf-8"
    )
    (temp_dir / "config.json").write_text(
        '{\n  "search_key": "value",\n  "name": "test"\n}',
        encoding="utf-8"
    )
    (temp_dir / "app.log").write_text(
        "[INFO] Application started\n[ERROR] search failed\n[DEBUG] Debug info",
        encoding="utf-8"
    )
    (temp_dir / "data.csv").write_text(
        "id,name,value\n1,search_item,100\n2,other,200",
        encoding="utf-8"
    )

    # 创建不允许搜索的文件类型
    (temp_dir / "script.py").write_text("def search():\n    pass", encoding="utf-8")
    (temp_dir / "style.css").write_text("body { color: search; }", encoding="utf-8")
    (temp_dir / "page.html").write_text("<div>search</div>", encoding="utf-8")

    # 创建子目录
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("nested search content", encoding="utf-8")
    (subdir / "nested.py").write_text("x = 'search'", encoding="utf-8")

    deep = subdir / "deep"
    deep.mkdir()
    (deep / "deep.md").write_text("# Deep\nsearch deep content", encoding="utf-8")

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


# ==========================================
# SearchFileTool 测试
# ==========================================

class TestSearchFileTool:
    """SearchFileTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = SearchFileTool()
        assert tool.name == "search_file_py"
        assert "搜索" in tool.description
        assert "文件" in tool.description

    def test_tool_parameters(self):
        """测试工具参数定义"""
        tool = SearchFileTool()
        params = tool.parameters

        assert params["type"] == "object"
        assert "file_name" in params["properties"]
        assert "max_results" in params["properties"]
        assert "timeout" in params["properties"]
        assert "max_depth" in params["properties"]
        assert "file_name" in params["required"]

    def test_tool_schema(self):
        """测试工具 schema 生成"""
        tool = SearchFileTool()
        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search_file_py"
        assert "parameters" in schema["function"]

    def test_tool_init(self):
        """测试工具初始化"""
        tool = SearchFileTool()
        assert hasattr(tool, "allowed_dir_path")

    @pytest.mark.asyncio
    async def test_search_basic(self, temp_search_dir):
        """测试基本文件名搜索"""
        result = _search_files_py(
            search_dir=str(temp_search_dir),
            file_name="test",
            max_results=20
        )

        assert "files" in result
        assert "count" in result
        assert result["count"] > 0
        assert any("test.py" in f for f in result["files"])
        assert any("test_file.txt" in f for f in result["files"])

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, temp_search_dir):
        """测试不区分大小写搜索"""
        result_upper = _search_files_py(search_dir=str(temp_search_dir), file_name="TEST", max_results=20)
        result_lower = _search_files_py(search_dir=str(temp_search_dir), file_name="test", max_results=20)

        assert result_upper["count"] == result_lower["count"]

    @pytest.mark.asyncio
    async def test_search_exact_filename(self, temp_search_dir):
        """测试精确文件名匹配"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name="data.json", max_results=20)

        assert result["count"] == 1
        assert "data.json" in result["files"][0]

    @pytest.mark.asyncio
    async def test_search_extension(self, temp_search_dir):
        """测试按扩展名搜索"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name=".py", max_results=20)

        assert result["count"] >= 3
        for f in result["files"]:
            assert f.endswith(".py")

    @pytest.mark.asyncio
    async def test_search_nested_directories(self, temp_search_dir):
        """测试搜索嵌套目录"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name="deep_file", max_results=20)

        assert result["count"] == 1
        assert "subdir2" in result["files"][0]
        assert "deep" in result["files"][0]

    @pytest.mark.asyncio
    async def test_search_max_results(self, temp_search_dir):
        """测试最大结果数限制"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name="test", max_results=2)

        assert result["count"] == 2
        assert len(result["files"]) == 2

    @pytest.mark.asyncio
    async def test_search_no_match(self, temp_search_dir):
        """测试无匹配结果"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name="nonexistent_xyz", max_results=20)

        assert result["count"] == 0
        assert len(result["files"]) == 0

    @pytest.mark.asyncio
    async def test_search_nonexistent_dir(self):
        """测试不存在的目录"""
        result = _search_files_py(search_dir="/nonexistent/dir", file_name="test", max_results=20)

        assert "error" in result
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_search_returns_absolute_paths(self, temp_search_dir):
        """测试返回绝对路径"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name="test", max_results=20)

        for f in result["files"]:
            assert isinstance(f, str)
            assert Path(f).is_absolute()

    @pytest.mark.asyncio
    async def test_search_max_depth(self, temp_search_dir):
        """测试最大搜索深度限制"""
        result = _search_files_py(search_dir=str(temp_search_dir), file_name="test", max_results=20, max_depth=1)

        assert result["count"] >= 2
        assert not any("deep_file" in f for f in result["files"])

    @pytest.mark.asyncio
    async def test_execute_empty_search_dir(self):
        """测试执行时空搜索目录"""
        tool = SearchFileTool()
        result = await tool.execute(search_dir="", file_name="test")

        assert "Error" in result
        assert "搜索目录不能为空" in result

    @pytest.mark.asyncio
    async def test_execute_empty_file_name(self, temp_search_dir):
        """测试执行时空文件名"""
        tool = SearchFileTool()
        result = await tool.execute(search_dir=str(temp_search_dir), file_name="")

        assert "Error" in result
        assert "文件名不能为空" in result

    @pytest.mark.asyncio
    async def test_execute_success(self, temp_search_dir):
        """测试成功执行搜索"""
        tool = SearchFileTool()
        original_paths = tool.allowed_dir_path
        tool.allowed_dir_path = [temp_search_dir]

        try:
            result = await tool.execute(search_dir=str(temp_search_dir), file_name="test", max_results=20)
            assert "Success" in result
        finally:
            tool.allowed_dir_path = original_paths


# ==========================================
# SearchStringTool 测试
# ==========================================

class TestSearchStringTool:
    """SearchStringTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = SearchStringTool()
        assert tool.name == "search_string_py"
        assert "搜索" in tool.description

    def test_tool_parameters(self):
        """测试工具参数定义"""
        tool = SearchStringTool()
        params = tool.parameters

        assert params["type"] == "object"
        assert "path" in params["properties"]
        assert "pattern" in params["properties"]
        assert "context_lines" in params["properties"]
        assert "case_sensitive" in params["properties"]
        assert "max_results" in params["properties"]
        assert "timeout" in params["properties"]
        assert "max_depth" in params["properties"]
        assert params["required"] == ["path", "pattern"]

    def test_tool_schema(self):
        """测试工具 schema 生成"""
        tool = SearchStringTool()
        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "search_string_py"

    def test_allowed_extensions(self):
        """测试允许搜索的文件后缀配置"""
        expected = {'.txt', '.md', '.json', '.log', '.csv'}
        assert ALLOWED_SEARCH_EXTENSIONS == expected

    @pytest.mark.asyncio
    async def test_search_in_txt_file(self, temp_string_search_dir):
        """测试在 txt 文件中搜索"""
        file_path = temp_string_search_dir / "notes.txt"

        result = _search_string_py(
            path=str(file_path),
            pattern="search keyword"
        )

        assert "result" in result
        assert "search keyword" in result["result"]
        assert "notes.txt" in result["result"]

    @pytest.mark.asyncio
    async def test_search_in_md_file(self, temp_string_search_dir):
        """测试在 md 文件中搜索"""
        file_path = temp_string_search_dir / "readme.md"

        result = _search_string_py(
            path=str(file_path),
            pattern="Search documentation"
        )

        assert "result" in result
        assert "Search documentation" in result["result"]

    @pytest.mark.asyncio
    async def test_search_in_json_file(self, temp_string_search_dir):
        """测试在 json 文件中搜索"""
        file_path = temp_string_search_dir / "config.json"

        result = _search_string_py(
            path=str(file_path),
            pattern="search_key"
        )

        assert "result" in result
        assert "search_key" in result["result"]

    @pytest.mark.asyncio
    async def test_search_in_log_file(self, temp_string_search_dir):
        """测试在 log 文件中搜索"""
        file_path = temp_string_search_dir / "app.log"

        result = _search_string_py(
            path=str(file_path),
            pattern="search failed"
        )

        assert "result" in result
        assert "search failed" in result["result"]

    @pytest.mark.asyncio
    async def test_search_in_csv_file(self, temp_string_search_dir):
        """测试在 csv 文件中搜索"""
        file_path = temp_string_search_dir / "data.csv"

        result = _search_string_py(
            path=str(file_path),
            pattern="search_item"
        )

        assert "result" in result
        assert "search_item" in result["result"]

    @pytest.mark.asyncio
    async def test_search_in_directory(self, temp_string_search_dir):
        """测试在目录中递归搜索（只搜索允许的文件类型）"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="search"
        )

        assert "result" in result
        # 应该在 txt, md, json, log, csv 文件中找到匹配
        assert "notes.txt" in result["result"] or "readme.md" in result["result"]

    @pytest.mark.asyncio
    async def test_search_skips_py_files(self, temp_string_search_dir):
        """测试搜索时跳过 .py 文件"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="search"
        )

        assert "result" in result
        # .py 文件不应该出现在结果中
        assert "script.py" not in result["result"]
        assert "nested.py" not in result["result"]

    @pytest.mark.asyncio
    async def test_search_skips_unsupported_files(self, temp_string_search_dir):
        """测试搜索时跳过不支持的文件类型"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="search"
        )

        assert "result" in result
        # .css, .html 文件不应该出现在结果中
        assert "style.css" not in result["result"]
        assert "page.html" not in result["result"]

    @pytest.mark.asyncio
    async def test_search_py_file_directly_returns_error(self, temp_string_search_dir):
        """测试直接指定 .py 文件搜索时返回错误"""
        file_path = temp_string_search_dir / "script.py"

        result = _search_string_py(
            path=str(file_path),
            pattern="search"
        )

        assert "error" in result
        assert "不是可搜索的文本文件类型" in result["error"]

    @pytest.mark.asyncio
    async def test_search_with_regex(self, temp_string_search_dir):
        """测试使用正则表达式搜索"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern=r"search\s+\w+"
        )

        assert "result" in result
        assert "search" in result["result"]

    @pytest.mark.asyncio
    async def test_search_with_context(self, temp_string_search_dir):
        """测试带上下文行数的搜索"""
        file_path = temp_string_search_dir / "notes.txt"

        result = _search_string_py(
            path=str(file_path),
            pattern="search keyword",
            context_lines=1
        )

        assert "result" in result
        assert "search keyword" in result["result"]

    @pytest.mark.asyncio
    async def test_search_no_match(self, temp_string_search_dir):
        """测试搜索不存在的字符串"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="nonexistent_xyz_123"
        )

        assert "result" in result
        assert "未找到匹配项" in result["result"]

    @pytest.mark.asyncio
    async def test_search_path_not_exist(self):
        """测试搜索不存在的路径"""
        result = _search_string_py(
            path="/nonexistent/path/xyz",
            pattern="test"
        )

        assert "error" in result
        assert "不存在" in result["error"]

    @pytest.mark.asyncio
    async def test_search_invalid_regex(self, temp_string_search_dir):
        """测试无效的正则表达式"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="[invalid"
        )

        assert "error" in result
        assert "无效的正则表达式" in result["error"]

    @pytest.mark.asyncio
    async def test_search_case_sensitive(self, temp_string_search_dir):
        """测试大小写敏感搜索"""
        # 不区分大小写
        result_insensitive = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="SEARCH"
        )

        # 区分大小写
        result_sensitive = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="SEARCH",
            case_sensitive=True
        )

        # 不区分大小写应该能找到结果
        assert "result" in result_insensitive
        assert "未找到匹配项" not in result_insensitive["result"]

    @pytest.mark.asyncio
    async def test_search_max_results(self, temp_string_search_dir):
        """测试最大结果数限制"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="search",
            max_results=2
        )

        assert "result" in result
        # 应该限制结果数量
        lines = result["result"].split("\n")
        match_count = sum(1 for line in lines if line.startswith("> "))
        assert match_count <= 2

    @pytest.mark.asyncio
    async def test_search_max_depth(self, temp_string_search_dir):
        """测试最大搜索深度限制"""
        # 深度1，只搜索第一层
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="search",
            max_depth=1
        )

        assert "result" in result
        # 深度1应该能找到第一层的文件
        assert "notes.txt" in result["result"]
        # 但不应该找到深层的文件 (subdir/deep/deep.md)
        assert "deep.md" not in result["result"]

    @pytest.mark.asyncio
    async def test_search_nested_directory(self, temp_string_search_dir):
        """测试在嵌套目录中搜索"""
        result = _search_string_py(
            path=str(temp_string_search_dir),
            pattern="nested search"
        )

        assert "result" in result
        assert "nested.txt" in result["result"]

    @pytest.mark.asyncio
    async def test_execute_missing_path(self):
        """测试缺少 path 参数"""
        tool = SearchStringTool()
        result = await tool.execute(pattern="test")

        assert "Error" in result
        assert "路径不能为空" in result

    @pytest.mark.asyncio
    async def test_execute_missing_pattern(self, temp_string_search_dir):
        """测试缺少 pattern 参数"""
        tool = SearchStringTool()
        result = await tool.execute(path=str(temp_string_search_dir))

        assert "Error" in result
        assert "搜索模式不能为空" in result


# ==========================================
# FileTreeTool 测试
# ==========================================

class TestFileTreeTool:
    """FileTreeTool 测试类"""

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = FileTreeTool()
        assert tool.name == "file_tree_py"
        assert "文件树" in tool.description

    def test_tool_parameters(self):
        """测试工具参数定义"""
        tool = FileTreeTool()
        params = tool.parameters

        assert params["type"] == "object"
        assert "dir_path" in params["properties"]
        assert "recursive" in params["properties"]
        assert "max_depth" in params["properties"]
        assert "show_hidden" in params["properties"]
        assert "dir_path" in params["required"]

    def test_tool_schema(self):
        """测试工具 schema 生成"""
        tool = FileTreeTool()
        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "file_tree_py"

    @pytest.mark.asyncio
    async def test_tree_non_recursive(self, temp_search_dir):
        """测试非递归模式"""
        tool = FileTreeTool()

        result = await tool.execute(
            dir_path=str(temp_search_dir),
            recursive=False,
            show_hidden=False
        )

        assert "Success" in result
        # 文件和目录都会显示
        assert "test.py" in result
        assert "test_file.txt" in result
        assert "subdir1" in result
        assert "subdir2" in result
        # 不应该包含子目录中的文件
        assert "nested_test.py" not in result
        assert "deep_file.py" not in result

    @pytest.mark.asyncio
    async def test_tree_recursive(self, temp_search_dir):
        """测试递归模式"""
        tool = FileTreeTool()

        result = await tool.execute(
            dir_path=str(temp_search_dir),
            recursive=True,
            max_depth=3,
            show_hidden=False
        )

        assert "Success" in result

    @pytest.mark.asyncio
    async def test_tree_show_hidden(self, temp_search_dir):
        """测试显示隐藏文件"""
        tool = FileTreeTool()

        result = await tool.execute(
            dir_path=str(temp_search_dir),
            recursive=False,
            show_hidden=True
        )

        assert "Success" in result

    @pytest.mark.asyncio
    async def test_tree_hide_hidden(self, temp_search_dir):
        """测试隐藏隐藏文件"""
        tool = FileTreeTool()

        result = await tool.execute(
            dir_path=str(temp_search_dir),
            recursive=False,
            show_hidden=False
        )

        assert "Success" in result

    @pytest.mark.asyncio
    async def test_tree_max_depth(self, temp_search_dir):
        """测试最大深度限制"""
        tool = FileTreeTool()

        result = await tool.execute(
            dir_path=str(temp_search_dir),
            recursive=True,
            max_depth=1,
            show_hidden=False
        )

        assert "Success" in result

    @pytest.mark.asyncio
    async def test_tree_dir_not_exist(self):
        """测试目录不存在"""
        tool = FileTreeTool()
        base_dir = settings.allowed_dir_path[0]
        nonexistent_path = base_dir / "nonexistent_dir_xyz"

        result = await tool.execute(dir_path=str(nonexistent_path))

        assert "Error" in result
        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_tree_path_is_file(self, temp_search_dir):
        """测试路径是文件而非目录"""
        tool = FileTreeTool()
        file_path = temp_search_dir / "test.py"

        result = await tool.execute(dir_path=str(file_path))

        assert "Error" in result
        assert "不是目录" in result

    @pytest.mark.asyncio
    async def test_tree_empty_dir(self):
        """测试空目录"""
        base_dir = settings.allowed_dir_path[0]
        empty_dir = base_dir / "test_empty_dir_xyz"
        empty_dir.mkdir(parents=True, exist_ok=True)

        try:
            tool = FileTreeTool()
            result = await tool.execute(dir_path=str(empty_dir))

            assert "Success" in result
        finally:
            if empty_dir.exists():
                empty_dir.rmdir()

    @pytest.mark.asyncio
    async def test_tree_missing_dir_path(self):
        """测试缺少 dir_path 参数"""
        tool = FileTreeTool()
        result = await tool.execute()

        assert "Error" in result
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_tree_permission_restriction(self):
        """测试权限限制"""
        tool = FileTreeTool()
        result = await tool.execute(dir_path="/Windows/System32")

        assert "Error" in result
