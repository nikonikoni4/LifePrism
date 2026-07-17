"""EditFileTool 单元测试"""

import os
import tempfile
from pathlib import Path

import pytest

from lifeprism.llm.agent.tools.filesystem import EditFileTool, _replace_content


@pytest.mark.core
class TestEditFileTool:
    """EditFileTool 测试类"""

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
    def temp_file_simple(self, temp_dir):
        """创建简单的临时文件"""
        content = """第一行内容
第二行内容
第三行内容
第四行内容
第五行内容
"""
        temp_path = os.path.join(temp_dir, "test_simple.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        yield temp_path

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
"""
        temp_path = os.path.join(temp_dir, "test_frontmatter.md")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        yield temp_path

    @pytest.fixture
    def temp_file_with_duplicates(self, temp_dir):
        """创建包含重复内容的临时文件"""
        content = """重复内容
其他内容
重复内容
更多内容
重复内容
"""
        temp_path = os.path.join(temp_dir, "test_duplicates.txt")
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(content)
        yield temp_path

    def test_tool_properties(self):
        """测试工具基本属性"""
        tool = EditFileTool()

        assert tool.name == "edit_file"
        assert "替换内容" in tool.description
        assert tool.parameters["type"] == "object"
        assert "file_path" in tool.parameters["properties"]
        assert "old_content" in tool.parameters["properties"]
        assert "new_content" in tool.parameters["properties"]
        assert "replace_all" in tool.parameters["properties"]
        assert set(tool.parameters["required"]) == {"file_path", "old_content", "new_content"}

    def test_tool_parameters_defaults(self):
        """测试参数默认值"""
        tool = EditFileTool()
        params = tool.parameters["properties"]

        assert params["replace_all"]["default"] is False

    @pytest.mark.asyncio
    async def test_execute_success_simple_replace(self, temp_dir, temp_file_simple):
        """测试成功执行简单替换"""
        tool = EditFileTool(workspace=Path(temp_dir))
        result = await tool.execute(
            file_path=temp_file_simple, old_content="第二行内容", new_content="第二行已修改"
        )

        assert result.startswith("Success:")
        assert "更新成功" in result

        # 验证文件内容
        with open(temp_file_simple, "r", encoding="utf-8") as f:
            content = f.read()
        assert "第二行已修改" in content
        assert "第二行内容" not in content

    @pytest.mark.asyncio
    async def test_execute_success_insert_content(self, temp_dir, temp_file_simple):
        """测试成功执行插入内容（原文+新增）"""
        tool = EditFileTool(workspace=Path(temp_dir))
        old_content = "第二行内容\n第三行内容"
        new_content = "第二行内容\n新增的一行\n第三行内容"

        result = await tool.execute(
            file_path=temp_file_simple, old_content=old_content, new_content=new_content
        )

        assert result.startswith("Success:")

        # 验证文件内容
        with open(temp_file_simple, "r", encoding="utf-8") as f:
            content = f.read()
        assert "新增的一行" in content

    @pytest.mark.asyncio
    async def test_execute_replace_all_false(self, temp_dir, temp_file_with_duplicates):
        """测试只替换第一个匹配项"""
        tool = EditFileTool(workspace=Path(temp_dir))
        result = await tool.execute(
            file_path=temp_file_with_duplicates,
            old_content="重复内容",
            new_content="已修改",
            replace_all=False,
        )

        assert result.startswith("Success:")
        assert "替换了第 1 个匹配项" in result
        assert "共找到 3 个匹配项" in result

        # 验证只替换了第一个
        with open(temp_file_with_duplicates, "r", encoding="utf-8") as f:
            content = f.read()
        assert content.count("已修改") == 1
        assert content.count("重复内容") == 2

    @pytest.mark.asyncio
    async def test_execute_replace_all_true(self, temp_dir, temp_file_with_duplicates):
        """测试替换所有匹配项"""
        tool = EditFileTool(workspace=Path(temp_dir))
        result = await tool.execute(
            file_path=temp_file_with_duplicates,
            old_content="重复内容",
            new_content="已修改",
            replace_all=True,
        )

        assert result.startswith("Success:")
        assert "替换了 3 个匹配项" in result

        # 验证所有都被替换
        with open(temp_file_with_duplicates, "r", encoding="utf-8") as f:
            content = f.read()
        assert content.count("已修改") == 3
        assert "重复内容" not in content

    @pytest.mark.asyncio
    async def test_execute_update_frontmatter(self, temp_dir, temp_file_with_frontmatter):
        """测试更新 frontmatter"""
        tool = EditFileTool(workspace=Path(temp_dir))
        result = await tool.execute(
            file_path=temp_file_with_frontmatter,
            old_content="version: 1.0",
            new_content="version: 2.0",
        )

        assert result.startswith("Success:")

        # 验证 frontmatter 被更新
        with open(temp_file_with_frontmatter, "r", encoding="utf-8") as f:
            content = f.read()
        assert "version: 2.0" in content
        assert "version: 1.0" not in content

    @pytest.mark.asyncio
    async def test_execute_file_not_found(self, temp_dir):
        """测试文件不存在"""
        tool = EditFileTool(workspace=Path(temp_dir))
        nonexistent_path = os.path.join(temp_dir, "nonexistent.txt")
        result = await tool.execute(
            file_path=nonexistent_path, old_content="test", new_content="new"
        )

        assert result.startswith("Error:")
        assert "不存在" in result

    @pytest.mark.asyncio
    async def test_execute_old_content_not_found(self, temp_dir, temp_file_simple):
        """测试 old_content 不存在"""
        tool = EditFileTool(workspace=Path(temp_dir))
        result = await tool.execute(
            file_path=temp_file_simple, old_content="不存在的内容", new_content="新内容"
        )

        assert result.startswith("Error:")
        assert "未找到要替换的内容" in result

    @pytest.mark.asyncio
    async def test_execute_empty_file_path(self):
        """测试空文件路径"""
        tool = EditFileTool()
        result = await tool.execute(file_path="", old_content="test", new_content="new")

        assert result.startswith("Error:")
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_execute_empty_old_content(self, temp_dir, temp_file_simple):
        """测试空 old_content"""
        tool = EditFileTool(workspace=Path(temp_dir))
        result = await tool.execute(file_path=temp_file_simple, old_content="", new_content="new")

        assert result.startswith("Error:")
        assert "不能为空" in result

    @pytest.mark.asyncio
    async def test_execute_permission_denied(self, temp_dir, temp_file_simple):
        """测试权限拒绝"""
        # 创建一个只允许访问其他目录的工具
        other_dir = tempfile.mkdtemp()
        try:
            tool = EditFileTool(workspace=Path(other_dir))
            result = await tool.execute(
                file_path=temp_file_simple, old_content="test", new_content="new"
            )

            assert result.startswith("Error:")
            assert "没有权限访问该文件" in result
        finally:
            import shutil

            if os.path.exists(other_dir):
                shutil.rmtree(other_dir)

    @pytest.mark.asyncio
    async def test_execute_no_permission_restriction(self, temp_file_simple):
        """测试无权限限制"""
        tool = EditFileTool(workspace=None, allowed_dirs=None)
        result = await tool.execute(
            file_path=temp_file_simple, old_content="第二行内容", new_content="第二行已修改"
        )

        assert result.startswith("Success:")

    def test_replace_content_basic(self, temp_file_simple):
        """测试基本内容替换"""
        result = _replace_content(
            file_path=temp_file_simple, old_content="第二行内容", new_content="第二行已修改"
        )

        assert "message" in result
        assert "replaced_count" in result
        assert result["replaced_count"] == 1

        # 验证文件内容
        with open(temp_file_simple, "r", encoding="utf-8") as f:
            content = f.read()
        assert "第二行已修改" in content

    def test_replace_content_multiline(self, temp_file_simple):
        """测试多行内容替换"""
        old_content = "第二行内容\n第三行内容"
        new_content = "第二行已修改\n第三行已修改"

        result = _replace_content(
            file_path=temp_file_simple, old_content=old_content, new_content=new_content
        )

        assert result["replaced_count"] == 1

        # 验证文件内容
        with open(temp_file_simple, "r", encoding="utf-8") as f:
            content = f.read()
        assert "第二行已修改" in content
        assert "第三行已修改" in content

    def test_replace_content_replace_all_false(self, temp_file_with_duplicates):
        """测试只替换第一个"""
        result = _replace_content(
            file_path=temp_file_with_duplicates,
            old_content="重复内容",
            new_content="已修改",
            replace_all=False,
        )

        assert result["replaced_count"] == 1
        assert "共找到 3 个匹配项" in result["message"]

    def test_replace_content_replace_all_true(self, temp_file_with_duplicates):
        """测试替换所有"""
        result = _replace_content(
            file_path=temp_file_with_duplicates,
            old_content="重复内容",
            new_content="已修改",
            replace_all=True,
        )

        assert result["replaced_count"] == 3

    def test_replace_content_file_not_exists(self):
        """测试文件不存在"""
        result = _replace_content(
            file_path="/nonexistent/file.txt", old_content="test", new_content="new"
        )

        assert "error" in result
        assert "不存在" in result["error"]

    def test_replace_content_old_content_not_found(self, temp_file_simple):
        """测试 old_content 不存在"""
        result = _replace_content(
            file_path=temp_file_simple, old_content="不存在的内容", new_content="新内容"
        )

        assert "error" in result
        assert "未找到要替换的内容" in result["error"]

    def test_replace_content_with_special_chars(self, temp_file_simple):
        """测试包含特殊字符的替换"""
        # 先添加包含特殊字符的内容
        with open(temp_file_simple, "a", encoding="utf-8") as f:
            f.write("\n特殊字符: $100 (50%)\n")

        result = _replace_content(
            file_path=temp_file_simple, old_content="$100 (50%)", new_content="$200 (100%)"
        )

        assert result["replaced_count"] == 1

        # 验证文件内容
        with open(temp_file_simple, "r", encoding="utf-8") as f:
            content = f.read()
        assert "$200 (100%)" in content

    def test_replace_content_empty_new_content(self, temp_file_simple):
        """测试新内容为空（删除内容）"""
        result = _replace_content(
            file_path=temp_file_simple, old_content="第二行内容\n", new_content=""
        )

        assert result["replaced_count"] == 1

        # 验证内容被删除
        with open(temp_file_simple, "r", encoding="utf-8") as f:
            content = f.read()
        assert "第二行内容" not in content

    @pytest.mark.asyncio
    async def test_tool_schema_generation(self):
        """测试工具 schema 生成"""
        tool = EditFileTool()
        schema = tool.to_schema()

        assert schema["type"] == "function"
        assert schema["function"]["name"] == "edit_file"
        assert "parameters" in schema["function"]
        assert schema["function"]["parameters"]["type"] == "object"
