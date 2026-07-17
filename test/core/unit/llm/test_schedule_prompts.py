"""
测试定时任务相关的 Prompt

测试目标：
1. 验证 prompt 函数能正常返回字符串
2. 验证 prompt 包含必要的关键字段
3. 验证参数注入功能正常
"""

from pathlib import Path

import pytest

from lifeprism.llm.prompts import (
    get_activity_summary_prompt,
    get_extract_chat_prompt,
    get_mood_summary_prompt,
    get_update_memory_prompt,
)


@pytest.mark.core
class TestActivitySummaryPrompt:
    """测试活动总结 prompt"""

    def test_returns_string(self):
        """验证返回字符串类型"""
        prompt = get_activity_summary_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_required_sections(self):
        """验证包含必要的章节"""
        prompt = get_activity_summary_prompt()

        # 必须包含的关键章节
        required_sections = ["## task", "## 数据说明", "## 总结内容", "## 核心原则"]

        for section in required_sections:
            assert section in prompt, f"缺少必要章节: {section}"

    def test_contains_data_types(self):
        """验证包含所有数据类型说明"""
        prompt = get_activity_summary_prompt()

        data_types = ["电脑使用统计", "用户自定义行为备注", "AI分析行为备注", "用户待办事项"]

        for data_type in data_types:
            assert data_type in prompt, f"缺少数据类型: {data_type}"

    def test_contains_core_principles(self):
        """验证包含核心原则"""
        prompt = get_activity_summary_prompt()

        assert "保持客观" in prompt
        assert "不推论" in prompt
        assert "保持简洁" in prompt


@pytest.mark.core
class TestMoodSummaryPrompt:
    """测试心情总结 prompt"""

    def test_returns_string(self):
        """验证返回字符串类型"""
        prompt = get_mood_summary_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_required_sections(self):
        """验证包含必要的章节"""
        prompt = get_mood_summary_prompt()

        required_sections = ["## 任务", "## 数据说明", "## 总结要求", "## 核心原则"]

        for section in required_sections:
            assert section in prompt, f"缺少必要章节: {section}"

    def test_contains_mood_data_fields(self):
        """验证包含心情数据字段说明"""
        prompt = get_mood_summary_prompt()

        fields = ["时间", "心情分数", "内容", "影响因素"]

        for field in fields:
            assert field in prompt, f"缺少字段说明: {field}"

    def test_contains_summary_structure(self):
        """验证包含总结结构"""
        prompt = get_mood_summary_prompt()

        structure = ["事件经过", "情绪诱因", "情绪本身", "用户反应"]

        for item in structure:
            assert item in prompt, f"缺少总结结构: {item}"


@pytest.mark.core
class TestUpdateMemoryPrompt:
    """测试更新记忆 prompt"""

    def test_returns_string(self):
        """验证返回字符串类型"""
        prompt = get_update_memory_prompt(
            recent_state_path=Path("/test/recent_state.md"),
            user_md_path=Path("/test/user.md"),
            diary_path_template="/test/diary/YYYY/MM/YYYY-MM-DD.md",
        )
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_path_injection(self):
        """验证路径参数正确注入"""
        recent_state_path = Path("/custom/path/recent_state.md")
        user_md_path = Path("/custom/path/user.md")
        diary_template = "/custom/diary/YYYY/MM/YYYY-MM-DD.md"

        prompt = get_update_memory_prompt(
            recent_state_path=recent_state_path,
            user_md_path=user_md_path,
            diary_path_template=diary_template,
        )

        # 验证路径被正确注入
        assert str(recent_state_path) in prompt
        assert str(user_md_path) in prompt
        assert diary_template in prompt

    def test_contains_required_sections(self):
        """验证包含必要的章节"""
        prompt = get_update_memory_prompt(
            recent_state_path=Path("/test/recent_state.md"),
            user_md_path=Path("/test/user.md"),
            diary_path_template="/test/diary/YYYY/MM/YYYY-MM-DD.md",
        )

        required_sections = [
            "## task",
            "## 记忆文档更新规则",
            "### 数据来源说明：behavior.md",
            "### 更新recent_state.md规则",
            "### 更新user.md",
            "## 文件路径说明",
        ]

        for section in required_sections:
            assert section in prompt, f"缺少必要章节: {section}"

    def test_contains_behavior_md_structure(self):
        """验证包含 behavior.md 结构说明"""
        prompt = get_update_memory_prompt(
            recent_state_path=Path("/test/recent_state.md"),
            user_md_path=Path("/test/user.md"),
            diary_path_template="/test/diary/YYYY/MM/YYYY-MM-DD.md",
        )

        subtitles = ["行为总结", "心情总结", "聊天记录总结", "日记总结"]

        for subtitle in subtitles:
            assert subtitle in prompt, f"缺少 subtitle 说明: {subtitle}"

    def test_contains_recent_state_structure(self):
        """验证包含 recent_state.md 结构说明"""
        prompt = get_update_memory_prompt(
            recent_state_path=Path("/test/recent_state.md"),
            user_md_path=Path("/test/user.md"),
            diary_path_template="/test/diary/YYYY/MM/YYYY-MM-DD.md",
        )

        sections = ["## 最近行为", "## 最近心理状态", "## 整体总结"]

        for section in sections:
            assert section in prompt, f"缺少 recent_state.md 结构: {section}"


@pytest.mark.core
class TestExtractChatPrompt:
    """测试提取聊天信息 prompt"""

    def test_returns_string(self):
        """验证返回字符串类型"""
        prompt = get_extract_chat_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_contains_required_sections(self):
        """验证包含必要的章节"""
        prompt = get_extract_chat_prompt()

        required_sections = ["## task", "## 提取内容", "## 不要提取的内容", "## 输出说明"]

        for section in required_sections:
            assert section in prompt, f"缺少必要章节: {section}"

    def test_contains_extraction_rules(self):
        """验证包含提取规则"""
        prompt = get_extract_chat_prompt()

        rules = ["非工具类查询或记录的事件", "情绪类事件", "用户偏好"]

        for rule in rules:
            assert rule in prompt, f"缺少提取规则: {rule}"

    def test_contains_output_format(self):
        """验证包含输出格式说明"""
        prompt = get_extract_chat_prompt()

        assert "无可提取内容" in prompt, "缺少空结果输出格式"


@pytest.mark.core
class TestPromptConsistency:
    """测试 prompt 一致性"""

    def test_all_prompts_use_markdown_format(self):
        """验证所有 prompt 都使用 Markdown 格式"""
        prompts = [
            get_activity_summary_prompt(),
            get_mood_summary_prompt(),
            get_update_memory_prompt(
                Path("/test/recent_state.md"),
                Path("/test/user.md"),
                "/test/diary/YYYY/MM/YYYY-MM-DD.md",
            ),
            get_extract_chat_prompt(),
        ]

        for prompt in prompts:
            # 验证包含 Markdown 标题
            assert "##" in prompt, "Prompt 应该使用 Markdown 格式"

    def test_all_prompts_have_task_section(self):
        """验证所有 prompt 都有任务说明"""
        prompts = [
            get_activity_summary_prompt(),
            get_mood_summary_prompt(),
            get_update_memory_prompt(
                Path("/test/recent_state.md"),
                Path("/test/user.md"),
                "/test/diary/YYYY/MM/YYYY-MM-DD.md",
            ),
            get_extract_chat_prompt(),
        ]

        for prompt in prompts:
            # 验证包含任务说明（task 或 任务）
            assert "## task" in prompt or "## 任务" in prompt, "Prompt 应该包含任务说明章节"

    def test_prompt_functions_are_pure(self):
        """验证 prompt 函数是纯函数（多次调用返回相同结果）"""
        # 测试无参数函数
        prompt1 = get_activity_summary_prompt()
        prompt2 = get_activity_summary_prompt()
        assert prompt1 == prompt2, "无参数 prompt 函数应该返回相同结果"

        # 测试有参数函数
        args = (
            Path("/test/recent_state.md"),
            Path("/test/user.md"),
            "/test/diary/YYYY/MM/YYYY-MM-DD.md",
        )
        prompt3 = get_update_memory_prompt(*args)
        prompt4 = get_update_memory_prompt(*args)
        assert prompt3 == prompt4, "有参数 prompt 函数应该返回相同结果"
