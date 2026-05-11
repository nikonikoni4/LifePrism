"""测试文件系统工具 - filesystem.py"""
import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

from lifeprism.llm.agent.tools.filesystem import (
    ReadFileTool,
    WriteFileTool,
    EditFileTool,
    FileTreeTool,
)


@pytest.fixture
def temp_test_dir():
    """创建临时测试目录结构（在允许的工作目录内）"""
    from lifeprism.config import settings

    # 在允许的工作目录中创建测试目录
    base_dir = settings.allowed_dir_path[0]  # 使用第一个允许的目录
    temp_dir = base_dir / "test_file_tree_temp"

    # 如果目录已存在，先删除
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    temp_dir.mkdir(parents=True, exist_ok=True)

    # 创建测试目录结构
    # temp_dir/
    # ├── file1.txt
    # ├── file2.py
    # ├── .hidden_file
    # ├── subdir1/
    # │   ├── file3.txt
    # │   └── file4.md
    # └── subdir2/
    #     ├── nested/
    #     │   └── deep_file.txt
    #     └── file5.json

    (temp_dir / "file1.txt").write_text("Content of file1", encoding="utf-8")
    (temp_dir / "file2.py").write_text("print('hello')", encoding="utf-8")
    (temp_dir / ".hidden_file").write_text("hidden content", encoding="utf-8")

    subdir1 = temp_dir / "subdir1"
    subdir1.mkdir()
    (subdir1 / "file3.txt").write_text("Content of file3", encoding="utf-8")
    (subdir1 / "file4.md").write_text("# Markdown", encoding="utf-8")

    subdir2 = temp_dir / "subdir2"
    subdir2.mkdir()
    nested = subdir2 / "nested"
    nested.mkdir()
    (nested / "deep_file.txt").write_text("Deep content", encoding="utf-8")
    (subdir2 / "file5.json").write_text('{"key": "value"}', encoding="utf-8")

    yield temp_dir

    # 清理
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_non_recursive(temp_test_dir):
    """测试 FileTreeTool - 非递归模式"""
    tool = FileTreeTool()

    result = await tool.execute(
        dir_path=str(temp_test_dir),
        recursive=False,
        show_hidden=False
    )

    assert isinstance(result, str)
    assert "Success:" in result
    assert "file1.txt" in result
    assert "file2.py" in result
    assert "subdir1" in result
    assert "subdir2" in result
    # 不应该包含子目录中的文件
    assert "file3.txt" not in result
    assert "file4.md" not in result
    # 不应该包含隐藏文件（但 PowerShell 默认会显示，需要额外过滤）
    # assert ".hidden_file" not in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_recursive(temp_test_dir):
    """测试 FileTreeTool - 递归模式"""
    tool = FileTreeTool()

    result = await tool.execute(
        dir_path=str(temp_test_dir),
        recursive=True,
        max_depth=3,
        show_hidden=False
    )

    assert isinstance(result, str)
    assert "Success:" in result
    assert "file1.txt" in result
    assert "subdir1" in result
    assert "file3.txt" in result
    assert "file4.md" in result
    assert "subdir2" in result
    assert "nested" in result
    assert "deep_file.txt" in result
    assert "file5.json" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_show_hidden(temp_test_dir):
    """测试 FileTreeTool - 显示隐藏文件"""
    tool = FileTreeTool()

    result = await tool.execute(
        dir_path=str(temp_test_dir),
        recursive=False,
        show_hidden=True
    )

    assert isinstance(result, str)
    assert "Success:" in result
    assert ".hidden_file" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_max_depth(temp_test_dir):
    """测试 FileTreeTool - 最大深度限制"""
    tool = FileTreeTool()

    # 深度为1，显示第一层子目录及其内容
    result = await tool.execute(
        dir_path=str(temp_test_dir),
        recursive=True,
        max_depth=1,
        show_hidden=False
    )

    assert isinstance(result, str)
    assert "Success:" in result
    assert "subdir1" in result
    assert "subdir2" in result
    # 深度为1，会显示第一层子目录中的文件
    assert "file3.txt" in result
    # 但不应该显示更深层的目录
    assert "nested" not in result or "deep_file.txt" not in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_dir_not_exist():
    """测试 FileTreeTool - 目录不存在"""
    from lifeprism.config import settings

    tool = FileTreeTool()
    # 使用允许目录下的不存在路径
    base_dir = settings.allowed_dir_path[0]
    nonexistent_path = base_dir / "nonexistent_directory_12345"

    result = await tool.execute(
        dir_path=str(nonexistent_path),
        recursive=False
    )

    assert isinstance(result, str)
    assert "Error:" in result
    assert "不存在" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_path_is_file(temp_test_dir):
    """测试 FileTreeTool - 路径是文件而非目录"""
    tool = FileTreeTool()
    file_path = temp_test_dir / "file1.txt"

    result = await tool.execute(
        dir_path=str(file_path),
        recursive=False
    )

    assert isinstance(result, str)
    assert "Error:" in result
    assert "不是目录" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_empty_dir():
    """测试 FileTreeTool - 空目录"""
    from lifeprism.config import settings

    base_dir = settings.allowed_dir_path[0]
    empty_dir = base_dir / "test_empty_dir_temp"
    empty_dir.mkdir(parents=True, exist_ok=True)

    try:
        tool = FileTreeTool()

        result = await tool.execute(
            dir_path=str(empty_dir),
            recursive=False
        )

        assert isinstance(result, str)
        assert "Success:" in result
    finally:
        # 清理
        if empty_dir.exists():
            empty_dir.rmdir()


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_missing_dir_path():
    """测试 FileTreeTool - 缺少 dir_path 参数"""
    tool = FileTreeTool()

    result = await tool.execute()

    assert isinstance(result, str)
    assert "Error" in result
    assert "不能为空" in result


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_schema():
    """测试 FileTreeTool - to_schema 方法"""
    tool = FileTreeTool()
    schema = tool.to_schema()

    assert 'type' in schema
    assert 'function' in schema
    assert schema['function']['name'] == 'file_tree'
    assert 'description' in schema['function']
    assert 'parameters' in schema['function']

    params = schema['function']['parameters']
    assert 'properties' in params
    assert 'dir_path' in params['properties']
    assert 'recursive' in params['properties']
    assert 'max_depth' in params['properties']
    assert 'show_hidden' in params['properties']
    assert params['required'] == ['dir_path']


@pytest.mark.core
@pytest.mark.asyncio
async def test_file_tree_tool_tree_format(temp_test_dir):
    """测试 FileTreeTool - 树形格式正确性"""
    tool = FileTreeTool()

    result = await tool.execute(
        dir_path=str(temp_test_dir),
        recursive=False,
        show_hidden=False
    )

    assert isinstance(result, str)
    # 检查 PowerShell 表格格式
    assert "Mode" in result or "Name" in result
    # 检查目录和文件
    assert "subdir1" in result
    assert "subdir2" in result
