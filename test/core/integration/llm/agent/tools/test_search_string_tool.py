"""测试 SearchStringTool - filesystem copy 2.py"""

import shutil
import sys
from pathlib import Path

import pytest

# 添加项目根目录到 sys.path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 导入 SearchStringTool（从 filesystem copy 2.py）
filesystem_copy2_path = (
    project_root / "lifeprism" / "llm" / "agent" / "tools" / "filesystem copy 2.py"
)
import importlib.util

spec = importlib.util.spec_from_file_location("filesystem_copy2", filesystem_copy2_path)
filesystem_copy2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(filesystem_copy2)
SearchStringTool = filesystem_copy2.SearchStringTool


@pytest.fixture
def temp_search_dir():
    """创建临时测试目录结构用于搜索测试"""
    from lifeprism.config import settings

    # 在允许的工作目录中创建测试目录
    base_dir = settings.allowed_dir_path[0]
    temp_dir = base_dir / "test_search_string_temp"

    # 如果目录已存在，先删除
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    temp_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试文件
    # temp_dir/
    # ├── test1.py (包含 "def search_function")
    # ├── test2.txt (包含 "search keyword")
    # ├── test3.md (包含 "# Search Title")
    # └── subdir/
    #     ├── nested.py (包含 "class SearchClass")
    #     └── data.json (包含 "search_field")

    (temp_dir / "test1.py").write_text(
        "def search_function():\n    return 'result'\n\ndef other_function():\n    pass",
        encoding="utf-8",
    )
    (temp_dir / "test2.txt").write_text(
        "This is a test file.\nIt contains search keyword here.\nAnd some other text.",
        encoding="utf-8",
    )
    (temp_dir / "test3.md").write_text(
        "# Search Title\n\nThis is markdown content.\n\n## Another Section", encoding="utf-8"
    )

    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.py").write_text(
        "class SearchClass:\n    def __init__(self):\n        self.name = 'test'", encoding="utf-8"
    )
    (subdir / "data.json").write_text(
        '{\n  "search_field": "value",\n  "other_field": "data"\n}', encoding="utf-8"
    )

    yield temp_dir

    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_in_file(temp_search_dir):
    """测试在单个文件中搜索字符串"""
    tool = SearchStringTool()
    file_path = temp_search_dir / "test1.py"

    result = await tool.execute(path=str(file_path), pattern="search_function")

    assert isinstance(result, str)
    assert "SUCCESS" in result
    assert "search_function" in result
    assert "test1.py" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_in_directory(temp_search_dir):
    """测试在目录中递归搜索字符串"""
    tool = SearchStringTool()

    result = await tool.execute(path=str(temp_search_dir), pattern="search")

    assert isinstance(result, str)
    assert "SUCCESS" in result
    # 应该找到多个文件中的匹配
    assert "test1.py" in result or "test2.txt" in result or "test3.md" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_with_regex(temp_search_dir):
    """测试使用正则表达式搜索"""
    tool = SearchStringTool()

    result = await tool.execute(path=str(temp_search_dir), pattern="def\s+\w+_function")

    assert isinstance(result, str)
    assert "SUCCESS" in result
    assert "search_function" in result or "other_function" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_with_context(temp_search_dir):
    """测试带上下文行数的搜索"""
    tool = SearchStringTool()
    file_path = temp_search_dir / "test2.txt"

    result = await tool.execute(path=str(file_path), pattern="search keyword", context_lines=1)

    assert isinstance(result, str)
    assert "SUCCESS" in result
    assert "search keyword" in result
    # 应该包含上下文行


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_no_match(temp_search_dir):
    """测试搜索不存在的字符串"""
    tool = SearchStringTool()

    result = await tool.execute(path=str(temp_search_dir), pattern="nonexistent_pattern_xyz123")

    assert isinstance(result, str)
    assert "SUCCESS" in result
    assert "未找到匹配项" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_path_not_exist():
    """测试搜索不存在的路径"""
    from lifeprism.config import settings

    tool = SearchStringTool()
    base_dir = settings.allowed_dir_path[0]
    nonexistent_path = base_dir / "nonexistent_path_xyz123"

    result = await tool.execute(path=str(nonexistent_path), pattern="test")

    assert isinstance(result, str)
    assert "ERROR" in result
    assert "不存在" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_missing_path():
    """测试缺少 path 参数"""
    tool = SearchStringTool()

    result = await tool.execute(pattern="test")

    assert isinstance(result, str)
    assert "ERROR" in result
    assert "路径不能为空" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_missing_pattern(temp_search_dir):
    """测试缺少 pattern 参数"""
    tool = SearchStringTool()

    result = await tool.execute(path=str(temp_search_dir))

    assert isinstance(result, str)
    assert "ERROR" in result
    assert "搜索模式不能为空" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_case_sensitive(temp_search_dir):
    """测试大小写敏感搜索"""
    tool = SearchStringTool()
    file_path = temp_search_dir / "test3.md"

    # 搜索大写 Search
    result = await tool.execute(path=str(file_path), pattern="Search")

    assert isinstance(result, str)
    assert "SUCCESS" in result
    assert "Search" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_search_string_in_nested_directory(temp_search_dir):
    """测试在嵌套目录中搜索"""
    tool = SearchStringTool()

    result = await tool.execute(path=str(temp_search_dir), pattern="SearchClass")

    assert isinstance(result, str)
    assert "SUCCESS" in result
    assert "SearchClass" in result
    assert "nested.py" in result


@pytest.mark.core
def test_search_string_tool_schema():
    """测试 SearchStringTool 的 schema"""
    tool = SearchStringTool()

    assert tool.name == "search_string"
    assert "搜索" in tool.description

    params = tool.parameters
    assert params["type"] == "object"
    assert "path" in params["properties"]
    assert "pattern" in params["properties"]
    assert "context_lines" in params["properties"]
    assert params["required"] == ["path", "pattern"]
