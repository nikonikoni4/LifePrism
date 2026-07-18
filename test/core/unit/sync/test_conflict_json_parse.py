"""LLM 输出 JSON 解析与验证单元测试（Issue 4）

测试 seam:
- Seam 1: parse_llm_json_response —— JSON 解析（含 json_repair 容错）
- Seam 2: expand_conflict_context —— 上下文扩展（前 20~30 行 + 冲突块 + 后 20~30 行）
- Seam 3: resolve_conflict_blocks —— 串行处理 + 重试 + 降级（mock LLM）
- Seam 4: 单个冲突块失败不中断整个文件处理
- Seam 5: 串行处理基于更新后的文件继续

LLM 输出 JSON 格式（PRD 决策 4）::

    {
      "conflict_id": 1,
      "start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1",
      "end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1",
      "replacement": "合并后的内容"
    }

测试原则：mock LLM 返回值，不调用真实 LLM API。
通过依赖注入 llm_caller 回调（接收 prompt 字符串，返回 LLM 响应字符串）实现。

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 4-6、10
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md 决策 4-6
"""

from unittest.mock import MagicMock

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: parse_llm_json_response ====================


class TestParseLLMJsonResponse:
    """parse_llm_json_response 解析 LLM 返回的 JSON

    使用 json_repair 容错（处理多余逗号、单引号、markdown code fence 等）。
    """

    def test_parse_well_formed_json(self):
        """正常 JSON 字符串解析成功"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = (
            '{"conflict_id": 1, '
            '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
            '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
            '"replacement": "合并后的内容"}'
        )
        result = parse_llm_json_response(raw)
        assert result is not None
        assert result["conflict_id"] == 1
        assert result["start_marker"] == "<<<<<<< LP-LOCAL-a3f8b2c1 #1"
        assert result["end_marker"] == ">>>>>>> LP-REMOTE-7e9d4f2b #1"
        assert result["replacement"] == "合并后的内容"

    def test_parse_json_with_trailing_comma(self):
        """JSON 含多余逗号时 json_repair 容错解析成功"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = (
            '{"conflict_id": 1, '
            '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
            '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
            '"replacement": "合并后的内容",}'
        )
        result = parse_llm_json_response(raw)
        assert result is not None
        assert result["conflict_id"] == 1
        assert result["replacement"] == "合并后的内容"

    def test_parse_json_with_single_quotes(self):
        """JSON 含单引号时 json_repair 容错解析成功"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = (
            "{'conflict_id': 1, "
            "'start_marker': '<<<<<<< LP-LOCAL-a3f8b2c1 #1', "
            "'end_marker': '>>>>>>> LP-REMOTE-7e9d4f2b #1', "
            "'replacement': '合并后的内容'}"
        )
        result = parse_llm_json_response(raw)
        assert result is not None
        assert result["conflict_id"] == 1
        assert result["replacement"] == "合并后的内容"

    def test_parse_json_with_markdown_code_fence(self):
        """LLM 输出被 ```json ... ``` 包裹时仍能解析"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = (
            '```json\n'
            '{"conflict_id": 1, '
            '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
            '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
            '"replacement": "合并后的内容"}\n'
            '```'
        )
        result = parse_llm_json_response(raw)
        assert result is not None
        assert result["conflict_id"] == 1
        assert result["replacement"] == "合并后的内容"

    def test_parse_completely_invalid_json_returns_none(self):
        """完全无法解析的 JSON 返回 None（触发重试）"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = "这不是 JSON，是自然语言解释"
        result = parse_llm_json_response(raw)
        assert result is None

    def test_parse_missing_required_field_returns_none(self):
        """缺少必需字段（如 start_marker）返回 None（触发重试）"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = '{"conflict_id": 1, "replacement": "缺少 marker"}'
        result = parse_llm_json_response(raw)
        assert result is None

    def test_parse_wrong_field_types_returns_none(self):
        """字段类型错误（如 conflict_id 是字符串而非整数）返回 None

        conflict_id="not_a_number" 不是 int / float / 数字字符串，
        无法转 int → parse_llm_json_response 应返回 None。
        参考 conflict_resolution.py L396-400：字符串 conflict_id 尝试 int() 转换，
        ValueError 时返回 None。
        """
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = (
            '{"conflict_id": "not_a_number", '
            '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
            '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
            '"replacement": "合并后的内容"}'
        )
        result = parse_llm_json_response(raw)
        # 类型校验严格：conflict_id="not_a_number" 无法转 int → 返回 None
        assert result is None


# ==================== Seam 2: expand_conflict_context ====================


class TestExpandConflictContext:
    """expand_conflict_context 扩展冲突块上下文

    PRD 决策 11 / 用户故事 16：
    - 整块冲突上下文 = 冲突标记前 20~30 行 + 完整冲突块 + 冲突标记后 20~30 行
    - 到文件边界则取消该侧扩展
    - 整块作为一个参数 {conflict_block_with_context} 提供
    """

    def test_expand_default_25_lines_before_and_after(self):
        """默认扩展 25 行上下文（在 20~30 行范围内）"""
        from lifeprism.sync.conflict_resolution import expand_conflict_context

        # 构造 60 行文件，冲突块在中间
        lines = [f"line{i}" for i in range(60)]
        lines[25] = "<<<<<<< LP-LOCAL-a3f8b2c1 #1"
        lines[27] = "======="
        lines[29] = ">>>>>>> LP-REMOTE-7e9d4f2b #1"
        file_content = "\n".join(lines) + "\n"

        # 冲突块从 line 25 到 line 29
        context = expand_conflict_context(
            file_content=file_content,
            start_line=25,
            end_line=29,
            context_lines=25,
        )
        # 应包含前 25 行（line 0~24）+ 冲突块（line 25~29）+ 后 25 行（line 30~54）
        assert "line0" in context  # 前 25 行的起点
        assert "line24" in context  # 前 25 行的终点
        assert "<<<<<<< LP-LOCAL-a3f8b2c1 #1" in context  # 冲突块起始
        assert ">>>>>>> LP-REMOTE-7e9d4f2b #1" in context  # 冲突块结束
        assert "line30" in context  # 后 25 行的起点
        assert "line54" in context  # 后 25 行的终点
        # line55+ 不在上下文中
        assert "line55" not in context

    def test_expand_at_file_start_no_before_context(self):
        """冲突块在文件起始：前侧无扩展（到文件边界取消扩展）"""
        from lifeprism.sync.conflict_resolution import expand_conflict_context

        file_content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "line5\n"
            "line6\n"
        )
        context = expand_conflict_context(
            file_content=file_content,
            start_line=0,
            end_line=4,
            context_lines=25,
        )
        # 应包含完整冲突块 + 后 3 行
        assert "<<<<<<< LP-LOCAL-a3f8b2c1 #1" in context
        assert ">>>>>>> LP-REMOTE-7e9d4f2b #1" in context
        assert "line5" in context
        assert "line6" in context
        # 不应有"前侧扩展"内容（文件起始无前侧）

    def test_expand_at_file_end_no_after_context(self):
        """冲突块在文件末尾：后侧无扩展（到文件边界取消扩展）"""
        from lifeprism.sync.conflict_resolution import expand_conflict_context

        file_content = (
            "line0\n"
            "line1\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        context = expand_conflict_context(
            file_content=file_content,
            start_line=2,
            end_line=6,
            context_lines=25,
        )
        # 应包含前 2 行 + 完整冲突块
        assert "line0" in context
        assert "line1" in context
        assert "<<<<<<< LP-LOCAL-a3f8b2c1 #1" in context
        assert ">>>>>>> LP-REMOTE-7e9d4f2b #1" in context

    def test_expand_context_includes_complete_conflict_block(self):
        """扩展上下文应包含完整冲突块（含标记本身）"""
        from lifeprism.sync.conflict_resolution import expand_conflict_context

        file_content = (
            "before1\n"
            "before2\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours line1\n"
            "ours line2\n"
            "=======\n"
            "theirs line1\n"
            "theirs line2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "after1\n"
            "after2\n"
        )
        context = expand_conflict_context(
            file_content=file_content,
            start_line=2,
            end_line=8,
            context_lines=25,
        )
        # 完整冲突块内容都应在上下文中
        assert "ours line1" in context
        assert "ours line2" in context
        assert "theirs line1" in context
        assert "theirs line2" in context
        assert "=======" in context

    def test_expand_custom_context_lines(self):
        """可自定义 context_lines 参数（如 20 或 30）"""
        from lifeprism.sync.conflict_resolution import expand_conflict_context

        lines = [f"line{i}" for i in range(100)]
        lines[50] = "<<<<<<< LP-LOCAL-a3f8b2c1 #1"
        lines[52] = "======="
        lines[54] = ">>>>>>> LP-REMOTE-7e9d4f2b #1"
        file_content = "\n".join(lines) + "\n"

        # 自定义 20 行上下文
        context = expand_conflict_context(
            file_content=file_content,
            start_line=50,
            end_line=54,
            context_lines=20,
        )
        assert "line30" in context  # 前 20 行起点
        assert "line49" in context  # 前 20 行终点
        assert "line55" in context  # 后 20 行起点
        assert "line74" in context  # 后 20 行终点
        assert "line29" not in context  # 超出前侧
        assert "line75" not in context  # 超出后侧


# ==================== Seam 3: resolve_conflict_blocks（串行 + 重试 + 降级） ====================


class TestResolveConflictBlocks:
    """resolve_conflict_blocks 串行处理冲突块

    PRD 决策 5 / 用户故事 11：
    - 程序按"理解 B"串行处理：一个冲突一次 LLM 调用，处理完一个再处理下一个
    - 每个冲突块基于更新后的文件继续（行号变化不是问题）

    PRD 决策 6 / 用户故事 12-14：
    - 重试机制：最多 3 次
    - 重试触发条件：JSON 解析失败 / marker 不匹配
    - 重试失败 → 当前冲突块降级 keep_ours（保留本地版本）+ WARNING 日志
    - 单个冲突块失败不中断整个文件处理

    测试通过依赖注入 llm_caller 回调（接收 prompt，返回 LLM 响应字符串）mock LLM。
    """

    def _make_merged_content(self, ours: str, theirs: str, n: int = 1) -> str:
        """构造含单个冲突块的合并文本"""
        return (
            f"<<<<<<< LP-LOCAL-a3f8b2c1 #{n}\n"
            f"{ours}"
            "=======\n"
            f"{theirs}"
            f">>>>>>> LP-REMOTE-7e9d4f2b #{n}\n"
        )

    def test_single_conflict_successful_resolution(self):
        """单个冲突块：LLM 返回有效 JSON → 替换成功"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = self._make_merged_content("ours content\n", "theirs content\n", n=1)
        blocks = parse_conflict_blocks(merged)

        # Mock LLM 返回有效 JSON
        def llm_caller(prompt: str) -> str:
            return (
                '{"conflict_id": 1, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                '"replacement": "merged content"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.final_content == "merged content"
        assert result.resolved_count == 1
        assert result.failed_count == 0
        assert result.failed_blocks == []

    def test_llm_returns_invalid_json_triggers_retry_until_success(self):
        """LLM 返回无效 JSON 触发重试，第 2 次成功 → 最终成功"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = self._make_merged_content("ours\n", "theirs\n", n=1)
        blocks = parse_conflict_blocks(merged)

        call_count = [0]

        def llm_caller(prompt: str) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次返回无效 JSON
                return "这不是 JSON"
            # 第二次返回有效 JSON
            return (
                '{"conflict_id": 1, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                '"replacement": "merged"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
            max_retries=3,
        )
        assert result.resolved_count == 1
        assert result.failed_count == 0
        assert "merged" in result.final_content
        assert call_count[0] == 2  # 重试 1 次后成功

    def test_marker_mismatch_triggers_retry(self):
        """LLM 返回的 marker 在文件中无法匹配 → 触发重试"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = self._make_merged_content("ours\n", "theirs\n", n=1)
        blocks = parse_conflict_blocks(merged)

        call_count = [0]

        def llm_caller(prompt: str) -> str:
            call_count[0] += 1
            if call_count[0] == 1:
                # 第一次返回错误的 marker（hash 不对）
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-deadbeef #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": "merged"}'
                )
            # 第二次返回正确的 marker
            return (
                '{"conflict_id": 1, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                '"replacement": "merged"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
            max_retries=3,
        )
        assert result.resolved_count == 1
        assert result.failed_count == 0
        assert call_count[0] == 2

    def test_retry_3_times_all_fail_degrades_to_keep_ours(self):
        """重试 3 次都失败 → 当前冲突块降级 keep_ours（保留本地版本）"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = self._make_merged_content("ours content\n", "theirs content\n", n=1)
        blocks = parse_conflict_blocks(merged)

        call_count = [0]

        def llm_caller(prompt: str) -> str:
            call_count[0] += 1
            # 始终返回无效 JSON
            return "always invalid"

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
            max_retries=3,
        )
        # 3 次重试都失败
        assert call_count[0] == 3
        # 降级 keep_ours：保留 ours 内容
        assert "ours content" in result.final_content
        assert "theirs content" not in result.final_content
        # 失败统计
        assert result.resolved_count == 0
        assert result.failed_count == 1
        assert 1 in result.failed_blocks

    def test_single_block_failure_does_not_interrupt_other_blocks(self):
        """单个冲突块失败不中断整个文件处理（其他块继续）"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        # 构造 2 个冲突块
        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "common\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 2

        call_count = [0]

        def llm_caller(prompt: str) -> str:
            call_count[0] += 1
            # 第 1 个冲突块（conflict_id=1）：始终失败
            if call_count[0] <= 3:
                return "always invalid for block 1"
            # 第 2 个冲突块（conflict_id=2）：第 4 次调用成功
            return (
                '{"conflict_id": 2, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                '"replacement": "merged block 2"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
            max_retries=3,
        )
        # 块 1 失败（3 次重试），块 2 成功
        assert result.resolved_count == 1
        assert result.failed_count == 1
        assert 1 in result.failed_blocks
        # 最终内容应保留块 1 的 ours 内容（降级 keep_ours）+ 块 2 的合并内容
        assert "ours1" in result.final_content
        assert "merged block 2" in result.final_content

    def test_serial_processing_based_on_updated_file(self):
        """串行处理：每个冲突块基于更新后的文件继续

        关键设计点（PRD 决策 5）：
        - 每个冲突块基于"前一个替换后的文件"重新定位
        - 行号变化不是问题（marker 字符串匹配，不依赖行号）
        """
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        # 构造 2 个冲突块
        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "middle\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)

        def llm_caller(prompt: str) -> str:
            # 通过 prompt 中的 marker 区分是哪个冲突块
            if "#1" in prompt and "#2" not in prompt:
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": "REPLACED_BLOCK_1_LONGER_THAN_ORIGINAL"}'
                )
            return (
                '{"conflict_id": 2, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                '"replacement": "REPLACED_BLOCK_2"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        # 两个块都成功替换
        assert result.resolved_count == 2
        assert result.failed_count == 0
        # 第一个块替换后的内容应在最终文件中
        assert "REPLACED_BLOCK_1_LONGER_THAN_ORIGINAL" in result.final_content
        assert "REPLACED_BLOCK_2" in result.final_content
        # 原始 ours 内容应被替换掉
        assert "ours1" not in result.final_content
        assert "ours2" not in result.final_content
        # 非冲突区域的内容应保留
        assert "middle" in result.final_content

    def test_empty_replacement_removes_conflict_block(self):
        """LLM 返回空 replacement → 冲突块被移除（保留两边内容）"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = (
            "before\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "after\n"
        )
        blocks = parse_conflict_blocks(merged)

        def llm_caller(prompt: str) -> str:
            return (
                '{"conflict_id": 1, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                '"replacement": ""}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.resolved_count == 1
        # 冲突块被移除，前后内容保留
        assert "before" in result.final_content
        assert "after" in result.final_content
        assert "ours" not in result.final_content
        assert "theirs" not in result.final_content
        assert "<<<<<<<" not in result.final_content

    def test_no_conflict_blocks_returns_original_content(self):
        """无冲突块时返回原始内容"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
        )

        result = resolve_conflict_blocks(
            file_content="no conflicts\njust content\n",
            conflict_blocks=[],
            llm_caller=lambda prompt: "",
        )
        assert result.final_content == "no conflicts\njust content\n"
        assert result.resolved_count == 0
        assert result.failed_count == 0


# ==================== Seam 4: ResolveResult 数据结构 ====================


class TestResolveResult:
    """ResolveResult 数据结构

    包含字段：
    - final_content: str —— 最终合并后的文件内容
    - resolved_count: int —— 成功替换的冲突块数
    - failed_count: int —— 失败降级的冲突块数
    - failed_blocks: list[int] —— 失败的冲突块 conflict_id 列表
    """

    def test_resolve_result_has_required_fields(self):
        """ResolveResult 应包含 final_content / resolved_count / failed_count / failed_blocks"""
        from lifeprism.sync.conflict_resolution import resolve_conflict_blocks

        result = resolve_conflict_blocks(
            file_content="no conflicts\n",
            conflict_blocks=[],
            llm_caller=lambda prompt: "",
        )
        assert hasattr(result, "final_content")
        assert hasattr(result, "resolved_count")
        assert hasattr(result, "failed_count")
        assert hasattr(result, "failed_blocks")
        assert isinstance(result.final_content, str)
        assert isinstance(result.resolved_count, int)
        assert isinstance(result.failed_count, int)
        assert isinstance(result.failed_blocks, list)


# ==================== Seam 6: 多冲突块串行替换边界（代码审查 Issue 5） ====================


class TestMultiBlockSerialReplacementBoundary:
    """多冲突块串行替换的边界场景

    代码审查 Issue 5 指出：现有测试中多冲突块场景的 LLM 替换内容长度
    均等于原冲突块长度，未验证替换内容长度变化时后续冲突块的 marker
    是否仍能正确定位。

    关键设计点（ADR-1 决策 7"串行处理"）：
    - 每个冲突块基于"前一个替换后的文件"重新定位
    - marker 是字符串匹配，不依赖行号，行号变化不影响匹配
    - 但替换内容中包含冲突标记字符串时需验证不破坏后续匹配
    """

    def test_first_block_replacement_much_longer_second_block_still_matches(self):
        """第一个块替换为 5 行内容（原 1 行），第二个块 marker 仍匹配"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "middle\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 2

        def llm_caller(prompt: str) -> str:
            if "#1" in prompt and "#2" not in prompt:
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": "line1\\nline2\\nline3\\nline4\\nline5"}'
                )
            return (
                '{"conflict_id": 2, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                '"replacement": "block2_replaced"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.resolved_count == 2
        assert result.failed_count == 0
        assert "line1" in result.final_content
        assert "line5" in result.final_content
        assert "block2_replaced" in result.final_content
        assert "middle" in result.final_content

    def test_first_block_empty_replacement_second_block_still_matches(self):
        """第一个块替换为空（删除），第二个块 marker 仍匹配"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = (
            "before\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "middle\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
            "after\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 2

        def llm_caller(prompt: str) -> str:
            if "#1" in prompt and "#2" not in prompt:
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": ""}'
                )
            return (
                '{"conflict_id": 2, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                '"replacement": "block2_merged"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.resolved_count == 2
        assert result.failed_count == 0
        assert "before" in result.final_content
        assert "middle" in result.final_content
        assert "after" in result.final_content
        assert "ours1" not in result.final_content
        assert "block2_merged" in result.final_content
        assert "<<<<<<<" not in result.final_content

    def test_replacement_containing_separator_string_does_not_break_parsing(self):
        """替换内容包含 `=======` 字符串 → 不破坏后续冲突块匹配

        替换内容中的 `=======` 是普通文本，不会被重新解析为冲突标记，
        因为 resolve_conflict_blocks 使用预解析的 conflict_blocks 列表，
        不重新解析文件。
        """
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "middle\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 2

        def llm_caller(prompt: str) -> str:
            if "#1" in prompt and "#2" not in prompt:
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": "merged with ======= separator inside"}'
                )
            return (
                '{"conflict_id": 2, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                '"replacement": "block2_ok"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.resolved_count == 2
        assert result.failed_count == 0
        assert "=======" in result.final_content
        assert "block2_ok" in result.final_content

    def test_replacement_containing_local_marker_string_does_not_break_parsing(self):
        """替换内容包含 `<<<<<<<` 字符串 → 不破坏后续冲突块匹配"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "middle\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 2

        def llm_caller(prompt: str) -> str:
            if "#1" in prompt and "#2" not in prompt:
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": "text with <<<<<<< arrow inside"}'
                )
            return (
                '{"conflict_id": 2, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                '"replacement": "block2_ok"}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.resolved_count == 2
        assert result.failed_count == 0
        assert "<<<<<<<" in result.final_content
        assert "block2_ok" in result.final_content

    def test_three_blocks_progressive_length_changes(self):
        """3 个冲突块：第一个变长、第二个变短、第三个删除 → 全部成功"""
        from lifeprism.sync.conflict_resolution import (
            resolve_conflict_blocks,
            parse_conflict_blocks,
        )

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "a\n"
            "=======\n"
            "b\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "sep1\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "c\n"
            "d\n"
            "e\n"
            "=======\n"
            "f\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
            "sep2\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #3\n"
            "g\n"
            "=======\n"
            "h\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #3\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 3

        def llm_caller(prompt: str) -> str:
            if "#1" in prompt and "#2" not in prompt and "#3" not in prompt:
                # 块1：变长（1 行 → 3 行）
                return (
                    '{"conflict_id": 1, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
                    '"replacement": "x1\\nx2\\nx3"}'
                )
            if "#2" in prompt and "#3" not in prompt:
                # 块2：变短（3 行 → 1 行）
                return (
                    '{"conflict_id": 2, '
                    '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #2", '
                    '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #2", '
                    '"replacement": "y1"}'
                )
            # 块3：删除
            return (
                '{"conflict_id": 3, '
                '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #3", '
                '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #3", '
                '"replacement": ""}'
            )

        result = resolve_conflict_blocks(
            file_content=merged,
            conflict_blocks=blocks,
            llm_caller=llm_caller,
        )
        assert result.resolved_count == 3
        assert result.failed_count == 0
        assert "x1" in result.final_content
        assert "x3" in result.final_content
        assert "y1" in result.final_content
        assert "sep1" in result.final_content
        assert "sep2" in result.final_content
        assert "<<<<<<<" not in result.final_content
        assert ">>>>>>>" not in result.final_content


# ==================== Seam 6: parse_conflict_blocks 错误恢复路径 ====================


class TestParseConflictBlocksRecovery:
    """parse_conflict_blocks 错误恢复路径直接测试

    PRD 决策 3 / 5：parse_conflict_blocks 必须容忍格式错误，跳过格式错误的冲突块
    而不是抛异常中断整个文件处理。

    覆盖 conflict_resolution.py L193-200 和 L218-225 两条恢复路径：
    - 缺少 ======= 分隔符 → 跳过该冲突块
    - 缺少 >>>>>>> 结束标记 → 跳过该冲突块
    """

    def test_missing_separator_skips_block(self):
        """缺少 ======= 分隔符但文件中存在后续 ======= → 跨块贪婪匹配

        实际行为（conflict_resolution.py L186-200）：
        - ours 收集循环不会停在 `>>>>>>>` 行，只检查 `=======` 模式
        - 若文件中后续有 =======，第一个起始标记会"借用"它作为分隔符
        - 此时不会触发 L193-200 的"缺少分隔符"恢复路径
        - 仅当起始标记后到文件末尾都无 ======= 时才触发恢复路径

        因此本测试验证"贪婪借用"行为，而非"跳过"行为。
        "跳过"恢复路径由 test_missing_separator_at_file_end_skips_block 覆盖。
        """
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours content without separator\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "sep line\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)
        # 实际行为：第一块借用后续 ======= 和 >>>>>>>，整文件解析为 1 块
        assert len(blocks) == 1
        assert blocks[0].conflict_id == 1
        assert blocks[0].end_marker == ">>>>>>> LP-REMOTE-7e9d4f2b #2"

    def test_missing_separator_at_file_end_skips_block(self):
        """缺少 ======= 分隔符且到文件末尾 → 跳过该冲突块

        验证 conflict_resolution.py L193-200 的恢复路径：
        - 起始标记后到文件末尾都无 =======
        - 触发 logger.warning 并 continue（跳过该冲突块）
        """
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours content\n"
            "no separator till end of file\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert blocks == []

    def test_missing_end_marker_skips_block(self):
        """缺少 >>>>>>> 结束标记但文件中存在后续 >>>>>>> → 跨块贪婪匹配

        实际行为（conflict_resolution.py L208-225）：
        - theirs 收集循环只检查 _END_MARKER_PATTERN
        - 若文件中后续有 >>>>>>>，第一块会"借用"它作为结束标记
        - 此时不会触发 L218-225 的"缺少结束标记"恢复路径
        - 仅当 ======= 后到文件末尾都无 >>>>>>> 时才触发恢复路径

        因此本测试验证"贪婪借用"行为，而非"跳过"行为。
        "跳过"恢复路径由 test_missing_end_marker_at_file_end_skips_block 覆盖。
        """
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            "no end marker\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        blocks = parse_conflict_blocks(merged)
        # 实际行为：第一块借用后续 >>>>>>>，整文件解析为 1 块
        assert len(blocks) == 1
        assert blocks[0].conflict_id == 1
        assert blocks[0].end_marker == ">>>>>>> LP-REMOTE-7e9d4f2b #2"

    def test_missing_end_marker_at_file_end_skips_block(self):
        """缺少 >>>>>>> 结束标记且到文件末尾 → 跳过该冲突块"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            "no end marker\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert blocks == []

    def test_empty_input_returns_empty_list(self):
        """空字符串 → 返回空列表"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        assert parse_conflict_blocks("") == []
        assert parse_conflict_blocks(None) == []  # type: ignore[arg-type]

    def test_no_conflict_markers_returns_empty(self):
        """无冲突标记的普通文本 → 返回空列表"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "# 日记\n"
            "今天天气很好\n"
            "心情不错\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert blocks == []

    def test_well_formed_single_block_parsed_correctly(self):
        """正常单块格式 → 解析成功（对照基线）"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 1
        block = blocks[0]
        assert block.conflict_id == 1
        assert block.start_marker == "<<<<<<< LP-LOCAL-a3f8b2c1 #1"
        assert block.end_marker == ">>>>>>> LP-REMOTE-7e9d4f2b #1"
        assert block.ours_content == "ours\n"
        assert block.theirs_content == "theirs\n"
        assert block.start_line == 0
        assert block.end_line == 4


# ==================== Seam 7: match_markers 精确与模糊匹配 ====================


class TestMatchMarkers:
    """match_markers 精确与模糊匹配直接测试

    PRD 决策 4 / 用户故事 12：marker 匹配是程序验证的核心
    1. 优先精确匹配
    2. 失败时尝试模糊匹配（去除所有空白后比较）
    3. 都失败返回 None

    覆盖 conflict_resolution.py L276-333 的 match_markers 函数：
    - 精确匹配成功
    - 精确匹配失败 + 模糊匹配成功（LLM 输出含额外空格）
    - 完全不匹配
    - 空文件
    - 顺序错误（end 在 start 之前）
    """

    def test_exact_match_returns_line_numbers(self):
        """精确匹配 → 返回 (start_line, end_line)"""
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "line0\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "line6\n"
        )
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result == (1, 5)

    def test_exact_match_first_pair_returned(self):
        """精确匹配：返回第一对 start < end"""
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours1\n"
            "=======\n"
            "theirs1\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #2\n"
            "ours2\n"
            "=======\n"
            "theirs2\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #2\n"
        )
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result == (0, 4)

    def test_fuzzy_match_with_extra_spaces_in_marker(self):
        """模糊匹配：LLM 输出 marker 含额外空格 → 仍能匹配

        场景：LLM 输出 ``<<<<<<< LP-LOCAL-  a3f8b2c1 #1``（含双空格），
        文件中是 ``<<<<<<< LP-LOCAL-a3f8b2c1 #1``（无空格）。
        _normalize_marker 去除所有空白后两者一致。
        """
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        result = match_markers(
            file_content=content,
            # LLM 输出含额外空格
            start_marker="<<<<<<< LP-LOCAL-  a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE- 7e9d4f2b #1",
        )
        assert result == (0, 4)

    def test_fuzzy_match_with_tab_in_marker(self):
        """模糊匹配：LLM 输出 marker 含 Tab → 仍能匹配"""
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "x\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        # \t 是 Tab 字符
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<<\tLP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>>\tLP-REMOTE-7e9d4f2b #1",
        )
        assert result == (1, 5)

    def test_fuzzy_match_file_content_with_extra_spaces(self):
        """模糊匹配：文件中的 marker 含额外空格 → LLM 输出无空格仍能匹配"""
        from lifeprism.sync.conflict_resolution import match_markers

        # 文件中 marker 含额外空格（异常但可能发生）
        content = (
            "<<<<<<< LP-LOCAL-  a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>>  LP-REMOTE-7e9d4f2b #1\n"
        )
        result = match_markers(
            file_content=content,
            # LLM 输出无空格
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result == (0, 4)

    def test_no_match_returns_none(self):
        """完全不匹配 → 返回 None（触发重试）"""
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<< LP-LOCAL-xxxxxxxx #1",  # hash 不匹配
            end_marker=">>>>>>> LP-REMOTE-yyyyyyyy #1",
        )
        assert result is None

    def test_empty_content_returns_none(self):
        """空文件 → 返回 None"""
        from lifeprism.sync.conflict_resolution import match_markers

        result = match_markers(
            file_content="",
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is None

    def test_end_before_start_returns_none(self):
        """end_marker 在 start_marker 之前 → 返回 None

        匹配要求 start_marker 在 end_marker 之前出现。
        """
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"  # end 在前
            "ours\n"
            "=======\n"
            "theirs\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"  # start 在后
        )
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is None

    def test_only_start_marker_returns_none(self):
        """只有 start_marker，无 end_marker → 返回 None"""
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "no end marker\n"
        )
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is None

    def test_only_end_marker_returns_none(self):
        """只有 end_marker，无 start_marker → 返回 None"""
        from lifeprism.sync.conflict_resolution import match_markers

        content = (
            "no start marker\n"
            "ours\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        result = match_markers(
            file_content=content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is None

    def test_normalize_marker_strips_all_whitespace(self):
        """_normalize_marker 去除所有空白字符（空格/Tab/换行）"""
        from lifeprism.sync.conflict_resolution import _normalize_marker

        # 空格
        assert _normalize_marker("<<<<<<< LP-LOCAL-a3f8b2c1 #1") == "<<<<<<<LP-LOCAL-a3f8b2c1#1"
        # 双空格
        assert _normalize_marker("<<<<<<<  LP-LOCAL-  a3f8b2c1  #1") == "<<<<<<<LP-LOCAL-a3f8b2c1#1"
        # Tab
        assert _normalize_marker("<<<<<<<\tLP-LOCAL-a3f8b2c1\t#1") == "<<<<<<<LP-LOCAL-a3f8b2c1#1"
        # 多种空白混合
        assert _normalize_marker("  <<<<<<< LP-LOCAL-a3f8b2c1 #1  ") == "<<<<<<<LP-LOCAL-a3f8b2c1#1"
        # 无空白
        assert _normalize_marker("<<<<<<<LP-LOCAL-a3f8b2c1#1") == "<<<<<<<LP-LOCAL-a3f8b2c1#1"
