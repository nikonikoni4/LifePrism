"""
测试 prompts_md_load 对嵌套 markdown 代码块的支持
"""

from pathlib import Path

import pytest

from lifeprism.llm.utils.md_os import prompts_md_load


@pytest.fixture
def test_prompts_file():
    """使用已存在的测试文件"""
    # 使用 test/debug 目录下的测试文件
    return Path("test/debug/test_prompts.md")


@pytest.mark.core
def test_nested_md_blocks(test_prompts_file):
    """测试嵌套 markdown 代码块的解析

    场景：prompt 内容中包含多个嵌套的 markdown 代码块
    预期：应该正确提取最外层代码块的内容，保留所有内部代码块
    """
    data = prompts_md_load(test_prompts_file)

    # 验证文件级元数据
    assert data["module"] == "test"
    assert data["description"] == "测试嵌套代码块解析"

    # 验证 test_prompt 存在
    assert "test_prompt" in data["prompts"]
    test_prompt = data["prompts"]["test_prompt"]

    # 验证版本信息
    assert "v1" in test_prompt["versions"]
    v1_content = test_prompt["versions"]["v1"]

    # 验证内容完整性 - 应该包含所有部分
    assert "### task" in v1_content
    assert "这是一个测试 prompt" in v1_content

    # 验证第一个内部代码块被保留
    assert "## YYYY-MM-DD" in v1_content
    assert "### subtitle" in v1_content
    assert "这是内部代码块后面的内容" in v1_content

    # 验证第二个内部代码块被保留
    assert "# document.md" in v1_content
    assert "## section" in v1_content
    assert "这是第二个内部代码块后面的内容" in v1_content

    # 验证结尾内容
    assert "### 结束" in v1_content
    assert "这是最后的内容" in v1_content

    # 验证内部代码块的数量（2个内部代码块 = 4个 ```）
    assert v1_content.count("```") == 4

    # 验证不应该包含最外层的 ```md 标记
    assert not v1_content.startswith("```md")
    assert not v1_content.endswith("```")


@pytest.mark.core
def test_simple_md_block(test_prompts_file):
    """测试简单的 markdown 代码块（无嵌套）

    场景：prompt 内容中没有嵌套代码块
    预期：应该正确提取内容，不包含最外层标记
    """
    data = prompts_md_load(test_prompts_file)

    # 验证 simple_prompt 存在
    assert "simple_prompt" in data["prompts"]
    simple_prompt = data["prompts"]["simple_prompt"]

    # 验证版本信息
    assert "v1" in simple_prompt["versions"]
    v1_content = simple_prompt["versions"]["v1"]

    # 验证内容完整性
    assert "### task" in v1_content
    assert "这是一个简单的 prompt" in v1_content
    assert "### 规则" in v1_content
    assert "规则一" in v1_content
    assert "规则二" in v1_content

    # 验证没有内部代码块
    assert v1_content.count("```") == 0

    # 验证不应该包含最外层的 ```md 标记
    assert not v1_content.startswith("```md")
    assert not v1_content.endswith("```")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
