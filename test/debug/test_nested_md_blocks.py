"""
测试 prompts_md_load 是否正确处理嵌套的 markdown 代码块
"""

from pathlib import Path

import pytest

from lifeprism.llm.utils.md_os import prompts_md_load


@pytest.mark.debug
def test_nested_md_blocks_in_prompt():
    """测试嵌套 markdown 代码块的解析

    场景：prompt 内容中包含示例 markdown 代码块
    预期：应该正确提取最外层代码块的内容，保留内部代码块
    """
    # 使用实际的 schedule_prompts.md 文件
    prompts_file = Path("templates/prompts/schedule_prompts.md")

    if not prompts_file.exists():
        pytest.skip(f"测试文件不存在: {prompts_file}")

    # 加载 prompts
    data = prompts_md_load(prompts_file)

    # 检查 update_memory prompt 是否正确加载
    assert "update_memory" in data["prompts"], "update_memory prompt 不存在"

    update_memory = data["prompts"]["update_memory"]
    assert "v1" in update_memory["versions"], "v1 版本不存在"

    v1_content = update_memory["versions"]["v1"]

    # 验证内容包含嵌套的代码块
    # 应该包含 behavior.md 的结构说明
    assert "## YYYY-MM-DD" in v1_content, "缺少 behavior.md 结构说明"
    assert "### subtitle" in v1_content, "缺少 subtitle 说明"

    # 应该包含 recent_state.md 的结构说明
    assert "# recent_state.md" in v1_content, "缺少 recent_state.md 结构说明"
    assert "## 最近行为" in v1_content, "缺少'最近行为'标题"

    # 验证不应该在内部代码块的 ``` 处截断
    # 如果正确解析，应该包含完整的更新规则
    assert "更新recent_state.md规则" in v1_content, "内容被错误截断"

    print("✓ 嵌套代码块解析正确")
    print(f"✓ v1 内容长度: {len(v1_content)} 字符")
    print(f"✓ 包含的代码块数量: {v1_content.count('```')}")


@pytest.mark.debug
def test_simple_md_block():
    """测试简单的 markdown 代码块（无嵌套）

    场景：prompt 内容中没有嵌套代码块
    预期：应该正确提取内容
    """
    prompts_file = Path("templates/prompts/schedule_prompts.md")

    if not prompts_file.exists():
        pytest.skip(f"测试文件不存在: {prompts_file}")

    data = prompts_md_load(prompts_file)

    # 检查 activity_summary prompt（没有嵌套代码块）
    assert "activity_summary" in data["prompts"]

    activity_summary = data["prompts"]["activity_summary"]
    assert "v1" in activity_summary["versions"]

    v1_content = activity_summary["versions"]["v1"]

    # 验证内容完整
    assert "### task" in v1_content
    assert "你需要依据用户数据总结用户今天都做了什么" in v1_content
    assert "### 核心原则" in v1_content

    print("✓ 简单代码块解析正确")


if __name__ == "__main__":
    test_nested_md_blocks_in_prompt()
    test_simple_md_block()
    print("\n所有测试通过！")
