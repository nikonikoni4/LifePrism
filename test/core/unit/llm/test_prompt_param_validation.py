"""
测试 PromptLoader 参数校验功能

测试目标：
1. 验证缺少必需参数时抛出 ValueError
2. 验证传入未知参数时抛出 ValueError
3. 验证参数匹配时正常加载
4. 验证无 params 声明时跳过校验（向后兼容）
"""

import pytest
from pathlib import Path
from lifeprism.llm.prompts import PromptLoader, Prompts


@pytest.mark.core
class TestPromptParamValidation:
    """测试参数校验功能"""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例"""
        return PromptLoader()

    def test_missing_required_params(self, loader):
        """缺少必需参数时应抛出 ValueError"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md"
                # 缺少 user_md_path 和 diary_path_template
            )

        error_msg = str(exc_info.value)
        assert "缺少必需参数" in error_msg
        assert "user_md_path" in error_msg
        assert "diary_path_template" in error_msg

    def test_unknown_params(self, loader):
        """传入未知参数时应抛出 ValueError"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md",
                user_md_path="/test/user.md",
                diary_path_template="/test/diary/{date}.md",
                unknown_param="some_value"  # 未知参数
            )

        error_msg = str(exc_info.value)
        assert "未知参数" in error_msg
        assert "unknown_param" in error_msg

    def test_valid_params(self, loader):
        """参数匹配时应正常加载"""
        prompt = loader.load_prompt(
            Prompts.Schedule.UPDATE_MEMORY,
            recent_state_path="/test/recent_state.md",
            user_md_path="/test/user.md",
            diary_path_template="/test/diary/{date}.md"
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # 验证参数已注入
        assert "/test/recent_state.md" in prompt
        assert "/test/user.md" in prompt

    def test_no_params_declaration_backward_compatible(self, loader):
        """无 params 声明的 prompt 应跳过校验（向后兼容）"""
        # activity_summary 没有 params 声明
        prompt = loader.load_prompt(
            Prompts.Schedule.ACTIVITY_SUMMARY,
            # 即使传入额外参数也不应报错
            some_extra_param="value"
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_error_message_includes_version(self, loader):
        """错误信息应包含版本号"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                version="v1",
                recent_state_path="/test/recent_state.md"
            )

        error_msg = str(exc_info.value)
        assert "v1" in error_msg

    def test_error_message_includes_prompt_name(self, loader):
        """错误信息应包含 prompt 名称"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md"
            )

        error_msg = str(exc_info.value)
        assert "update_memory" in error_msg

    def test_all_declared_params_required(self, loader):
        """所有声明的参数都是必需的（无 optional 概念）"""
        # 只传部分参数
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md",
                user_md_path="/test/user.md"
                # 缺少 diary_path_template
            )

        error_msg = str(exc_info.value)
        assert "diary_path_template" in error_msg

    def test_param_validation_before_format(self, loader):
        """参数校验应在 format() 之前执行"""
        # 如果校验在 format 之后，这个测试会失败
        # 因为 format 会尝试替换不存在的参数
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md"
            )

        # 应该是参数校验错误，而不是 format 错误
        assert "缺少必需参数" in str(exc_info.value)


@pytest.mark.core
class TestPromptParamValidationWithTemplate:
    """使用 schedule_prompts.md 测试参数校验"""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例"""
        return PromptLoader()

    def test_update_memory_all_params(self, loader):
        """测试 update_memory 完整参数"""
        prompt = loader.load_prompt(
            Prompts.Schedule.UPDATE_MEMORY,
            recent_state_path="/test/recent_state.md",
            user_md_path="/test/user.md",
            diary_path_template="/test/diary/{date}.md"
        )

        assert isinstance(prompt, str)
        assert "/test/recent_state.md" in prompt
        assert "/test/user.md" in prompt

    def test_update_memory_missing_one_param(self, loader):
        """测试 update_memory 缺少单个参数"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md",
                user_md_path="/test/user.md"
                # 缺少 diary_path_template
            )

        error_msg = str(exc_info.value)
        assert "缺少必需参数" in error_msg
        assert "diary_path_template" in error_msg

    def test_update_memory_missing_multiple_params(self, loader):
        """测试 update_memory 缺少多个参数"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md"
                # 缺少 user_md_path 和 diary_path_template
            )

        error_msg = str(exc_info.value)
        assert "缺少必需参数" in error_msg
        assert "user_md_path" in error_msg
        assert "diary_path_template" in error_msg

    def test_update_memory_unknown_param(self, loader):
        """测试 update_memory 传入未知参数"""
        with pytest.raises(ValueError) as exc_info:
            loader.load_prompt(
                Prompts.Schedule.UPDATE_MEMORY,
                recent_state_path="/test/recent_state.md",
                user_md_path="/test/user.md",
                diary_path_template="/test/diary/{date}.md",
                extra_field="should_fail"
            )

        error_msg = str(exc_info.value)
        assert "未知参数" in error_msg
        assert "extra_field" in error_msg

    def test_activity_summary_no_params(self, loader):
        """测试 activity_summary 无参数声明（向后兼容）"""
        # 即使传入额外参数也不应报错
        prompt = loader.load_prompt(
            Prompts.Schedule.ACTIVITY_SUMMARY,
            some_extra_param="value"
        )

        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_mood_summary_no_params(self, loader):
        """测试 mood_summary 无参数声明（向后兼容）"""
        prompt = loader.load_prompt(Prompts.Schedule.MOOD_SUMMARY)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
