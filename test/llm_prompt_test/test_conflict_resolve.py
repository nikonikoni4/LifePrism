"""
冲突解决 prompt 模块化测试（Issue 3 改造 2）

测试目标：
1. 验证 templates/prompts/conflict_prompts.md 存在
2. 验证 PromptLoader.load_prompt(PromptRef("conflict", "resolve_conflict")) 能加载
3. 验证 prompt 包含必要占位符：{conflict_block_with_context} / {conflict_id} / {total_conflicts}
4. 验证 prompt 不包含 {start_line} / {end_line} 占位符
5. 验证 prompt 内容包含：角色、任务、输出格式约束、上下文说明、禁止事项
6. 验证 prompt 文档明确说明"未来添加 ReadFileTool 时才需要 start_line / end_line 参数"

参考模式：
- test/llm_prompt_test/test_activity_summary.py 的 PromptLoader 导入风格
- test/core/unit/llm/test_prompt_param_validation.py 的纯静态验证逻辑（不调用真实 LLM）

设计决策（来自 ADR 2026-07-17 决策 7、8）：
- 当前方案：无 ReadFileTool，prompt 中只传一个核心参数 conflict_block_with_context
- 不传 start_line / end_line：LLM 无文件读取工具，行号对 LLM 无意义
- 未来添加 ReadFileTool 时才需要 start_line / end_line 参数
"""

from pathlib import Path

import pytest

from lifeprism.llm.prompts import PromptLoader, PromptRef

# prompt 模块文件路径（源文件）
CONFLICT_PROMPTS_FILE = (
    Path(__file__).resolve().parent.parent.parent / "templates" / "prompts" / "conflict_prompts.md"
)

# PromptRef 引用
CONFLICT_RESOLVE_PROMPT = PromptRef("conflict", "resolve_conflict")


@pytest.mark.core
class TestConflictPromptsFileExistence:
    """验证 conflict_prompts.md 模块文件存在"""

    def test_conflict_prompts_file_exists(self):
        """templates/prompts/conflict_prompts.md 应存在"""
        assert CONFLICT_PROMPTS_FILE.exists(), f"prompt 模块文件不存在: {CONFLICT_PROMPTS_FILE}"

    def test_conflict_prompts_file_is_file(self):
        """conflict_prompts.md 应是文件"""
        if CONFLICT_PROMPTS_FILE.exists():
            assert CONFLICT_PROMPTS_FILE.is_file()
        else:
            pytest.skip("conflict_prompts.md 不存在，跳过此测试")


@pytest.mark.core
class TestConflictPromptLoading:
    """验证 PromptLoader 能加载 resolve_conflict prompt"""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例（每次创建新实例以避免缓存）"""
        return PromptLoader()

    def test_load_prompt_returns_string(self, loader):
        """PromptLoader.load_prompt(PromptRef("conflict", "resolve_conflict")) 应返回字符串"""
        prompt = loader.load_prompt(CONFLICT_RESOLVE_PROMPT)
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_load_prompt_with_params(self, loader):
        """带参数加载 prompt 应正常工作"""
        prompt = loader.load_prompt(
            CONFLICT_RESOLVE_PROMPT,
            conflict_block_with_context="测试冲突块内容",
            conflict_id=1,
            total_conflicts=3,
        )
        assert isinstance(prompt, str)
        assert "测试冲突块内容" in prompt
        assert "1" in prompt
        assert "3" in prompt

    def test_load_prompt_metadata(self, loader):
        """应能获取 prompt 元数据"""
        metadata = loader.get_prompt_metadata("conflict", "resolve_conflict")
        assert "active_version" in metadata
        assert "version_history" in metadata
        assert "v1" in metadata["version_history"]

    def test_load_prompt_available_versions(self, loader):
        """应能获取 prompt 可用版本列表"""
        versions = loader.get_available_versions("conflict", "resolve_conflict")
        assert "v1" in versions
        assert len(versions) >= 1


@pytest.mark.core
class TestConflictPromptPlaceholders:
    """验证 prompt 包含必要占位符，不包含禁止的占位符"""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例"""
        return PromptLoader()

    @pytest.fixture
    def prompt_content(self, loader):
        """加载 prompt 内容（不注入参数，保留原始占位符）"""
        return loader.load_prompt(CONFLICT_RESOLVE_PROMPT)

    def test_contains_conflict_block_with_context_placeholder(self, prompt_content):
        """prompt 必须包含 {conflict_block_with_context} 占位符（核心参数）"""
        assert "{conflict_block_with_context}" in prompt_content, (
            "prompt 必须包含核心参数 {conflict_block_with_context} 占位符"
        )

    def test_contains_conflict_id_placeholder(self, prompt_content):
        """prompt 应包含 {conflict_id} 占位符（可选辅助参数）"""
        assert "{conflict_id}" in prompt_content, "prompt 应包含 {conflict_id} 占位符"

    def test_contains_total_conflicts_placeholder(self, prompt_content):
        """prompt 应包含 {total_conflicts} 占位符（可选辅助参数）"""
        assert "{total_conflicts}" in prompt_content, "prompt 应包含 {total_conflicts} 占位符"

    def test_does_not_contain_start_line_placeholder(self, prompt_content):
        """prompt 不应包含 {start_line} 占位符（当前方案无 ReadFileTool）"""
        assert "{start_line}" not in prompt_content, (
            "prompt 不应包含 {start_line} 占位符——当前方案无 ReadFileTool，行号对 LLM 无意义"
        )

    def test_does_not_contain_end_line_placeholder(self, prompt_content):
        """prompt 不应包含 {end_line} 占位符（当前方案无 ReadFileTool）"""
        assert "{end_line}" not in prompt_content, (
            "prompt 不应包含 {end_line} 占位符——当前方案无 ReadFileTool，行号对 LLM 无意义"
        )


@pytest.mark.core
class TestConflictPromptContent:
    """验证 prompt 内容包含必要章节"""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例"""
        return PromptLoader()

    @pytest.fixture
    def prompt_content(self, loader):
        """加载 prompt 内容"""
        return loader.load_prompt(CONFLICT_RESOLVE_PROMPT)

    def test_contains_role_description(self, prompt_content):
        """prompt 应包含角色说明（文件冲突解决助手）"""
        assert "冲突解决" in prompt_content or "冲突解决助手" in prompt_content, (
            "prompt 应说明 LLM 角色：文件冲突解决助手"
        )

    def test_contains_task_description(self, prompt_content):
        """prompt 应包含任务说明（基于冲突块上下文输出合并后的替换文本）"""
        assert "合并" in prompt_content or "替换" in prompt_content, (
            "prompt 应说明任务：基于冲突块上下文输出合并后的替换文本"
        )

    def test_contains_output_format_constraint(self, prompt_content):
        """prompt 应包含输出格式约束（严格 JSON）"""
        assert "JSON" in prompt_content, "prompt 应约束输出格式为严格 JSON"

    def test_contains_context_description(self, prompt_content):
        """prompt 应包含上下文说明（整块冲突上下文：base/ours/theirs + 扩展 20~30 行）"""
        assert "上下文" in prompt_content, "prompt 应说明上下文内容"
        assert "base" in prompt_content.lower() or "ours" in prompt_content.lower() or "theirs" in prompt_content.lower(), (
            "prompt 应说明上下文包含 base/ours/theirs 内容"
        )

    def test_contains_prohibition_rules(self, prompt_content):
        """prompt 应包含禁止事项（不能输出自然语言解释，不能输出 markdown code fence）"""
        assert "禁止" in prompt_content or "不能" in prompt_content, (
            "prompt 应包含禁止事项说明"
        )

    def test_contains_no_natural_language_explanation(self, prompt_content):
        """prompt 应明确禁止输出自然语言解释"""
        assert "自然语言" in prompt_content, "prompt 应明确禁止输出自然语言解释"

    def test_contains_no_markdown_code_fence(self, prompt_content):
        """prompt 应明确禁止输出 markdown code fence"""
        assert "code fence" in prompt_content.lower() or "代码块" in prompt_content or "```" in prompt_content, (
            "prompt 应明确禁止输出 markdown code fence"
        )


@pytest.mark.core
class TestConflictPromptFutureReadFileToolNote:
    """验证 prompt 文档明确说明"未来添加 ReadFileTool 时才需要 start_line / end_line 参数\""""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例"""
        return PromptLoader()

    @pytest.fixture
    def prompt_content(self, loader):
        """加载 prompt 内容"""
        return loader.load_prompt(CONFLICT_RESOLVE_PROMPT)

    def test_mentions_future_readfiletool(self, prompt_content):
        """prompt 应提及未来添加 ReadFileTool 的扩展点"""
        assert "ReadFileTool" in prompt_content, (
            "prompt 应明确说明未来添加 ReadFileTool 时的参数扩展"
        )

    def test_mentions_start_line_end_line_for_future(self, prompt_content):
        """prompt 应说明未来添加 ReadFileTool 时才需要 start_line / end_line 参数

        虽然当前方案不传 start_line / end_line（不作为占位符），
        但 prompt 文档应在说明文字中提及这两个参数名，作为未来扩展点的说明。
        """
        # prompt 不应包含 {start_line} 占位符（已在 TestConflictPromptPlaceholders 验证）
        # 但 prompt 文档应在说明文字中提及 start_line / end_line 作为未来扩展点
        assert "start_line" in prompt_content, (
            "prompt 应在文档中提及 start_line 作为未来扩展点说明"
        )
        assert "end_line" in prompt_content, (
            "prompt 应在文档中提及 end_line 作为未来扩展点说明"
        )

    def test_future_readfiletool_note_clearly_states_condition(self, prompt_content):
        """未来扩展说明应明确条件：添加 ReadFileTool 时才需要这些参数"""
        # 查找包含 ReadFileTool 和 start_line 的上下文
        readfiletool_pos = prompt_content.find("ReadFileTool")
        start_line_pos = prompt_content.find("start_line")

        assert readfiletool_pos != -1, "prompt 应提及 ReadFileTool"
        assert start_line_pos != -1, "prompt 应提及 start_line"

        # 两者应在相近的上下文中（距离不超过 500 字符）
        distance = abs(readfiletool_pos - start_line_pos)
        assert distance < 500, (
            f"ReadFileTool 和 start_line 应在同一上下文说明中，实际距离: {distance}"
        )


@pytest.mark.core
class TestConflictPromptPureFunction:
    """验证 prompt 加载是纯函数（多次调用返回相同结果）"""

    @pytest.fixture
    def loader(self):
        """创建 PromptLoader 实例"""
        return PromptLoader()

    def test_load_prompt_is_pure(self, loader):
        """多次加载 prompt 应返回相同结果"""
        prompt1 = loader.load_prompt(CONFLICT_RESOLVE_PROMPT)
        prompt2 = loader.load_prompt(CONFLICT_RESOLVE_PROMPT)
        assert prompt1 == prompt2, "多次加载 prompt 应返回相同结果"

    def test_load_prompt_with_params_is_pure(self, loader):
        """带参数多次加载 prompt 应返回相同结果"""
        prompt1 = loader.load_prompt(
            CONFLICT_RESOLVE_PROMPT,
            conflict_block_with_context="测试内容",
            conflict_id=1,
            total_conflicts=2,
        )
        prompt2 = loader.load_prompt(
            CONFLICT_RESOLVE_PROMPT,
            conflict_block_with_context="测试内容",
            conflict_id=1,
            total_conflicts=2,
        )
        assert prompt1 == prompt2, "带参数多次加载 prompt 应返回相同结果"
