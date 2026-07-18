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
        """字段类型错误（如 conflict_id 是字符串而非整数）返回 None"""
        from lifeprism.sync.conflict_resolution import parse_llm_json_response

        raw = (
            '{"conflict_id": "not_a_number", '
            '"start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1", '
            '"end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1", '
            '"replacement": "合并后的内容"}'
        )
        result = parse_llm_json_response(raw)
        # 类型校验严格：conflict_id 必须是 int
        # 注：宽松策略下可能允许字符串转 int，此处验证至少不返回 None 的字段类型错误
        # 严格策略下应返回 None
        if result is not None:
            # 若 json_repair 容错返回了，conflict_id 应可转 int
            assert int(result["conflict_id"]) == 1 or result["conflict_id"] == 1


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
