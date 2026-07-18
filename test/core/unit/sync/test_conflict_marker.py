"""冲突标记生成与解析单元测试（Issue 4）

测试 seam:
- Seam 1: build_start_marker / build_end_marker —— 冲突标记构建
- Seam 2: compute_hash_8 —— 文件 SHA-256 前 8 位计算
- Seam 3: parse_conflict_blocks —— 扫描合并文本提取冲突块（序号唯一性 + 程序匹配）
- Seam 4: match_markers —— 程序精确匹配 marker（hash/序号错误时匹配失败）

冲突标记格式（来自 PRD 决策 3 / ADR-1 决策 3）::

    <<<<<<< LP-LOCAL-{file_hash_8} #{n}
    {ours_content}
    =======
    {theirs_content}
    >>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 3、18-21
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md 决策 3
"""

import hashlib

import pytest

pytestmark = pytest.mark.core


# ==================== Seam 1: build_start_marker / build_end_marker ====================


class TestBuildMarkers:
    """冲突标记构建函数

    设计：将 marker 构建抽离为独立纯函数，便于在 diff3 输出与 LLM prompt 中复用，
    避免散落的字符串拼接导致格式不一致。
    """

    def test_build_start_marker_format(self):
        """start_marker 格式应为 ``<<<<<<< LP-LOCAL-{hash8} #{n}``"""
        from lifeprism.sync.conflict_resolution import build_start_marker

        marker = build_start_marker(local_hash_8="a3f8b2c1", n=1)
        assert marker == "<<<<<<< LP-LOCAL-a3f8b2c1 #1"

    def test_build_end_marker_format(self):
        """end_marker 格式应为 ``>>>>>>> LP-REMOTE-{hash8} #{n}``"""
        from lifeprism.sync.conflict_resolution import build_end_marker

        marker = build_end_marker(remote_hash_8="7e9d4f2b", n=1)
        assert marker == ">>>>>>> LP-REMOTE-7e9d4f2b #1"

    def test_build_start_marker_increments_with_n(self):
        """序号 #{n} 应随 n 递增"""
        from lifeprism.sync.conflict_resolution import build_start_marker

        assert build_start_marker("a3f8b2c1", 1) == "<<<<<<< LP-LOCAL-a3f8b2c1 #1"
        assert build_start_marker("a3f8b2c1", 2) == "<<<<<<< LP-LOCAL-a3f8b2c1 #2"
        assert build_start_marker("a3f8b2c1", 10) == "<<<<<<< LP-LOCAL-a3f8b2c1 #10"

    def test_build_end_marker_increments_with_n(self):
        """end_marker 序号 #{n} 应随 n 递增"""
        from lifeprism.sync.conflict_resolution import build_end_marker

        assert build_end_marker("7e9d4f2b", 1) == ">>>>>>> LP-REMOTE-7e9d4f2b #1"
        assert build_end_marker("7e9d4f2b", 5) == ">>>>>>> LP-REMOTE-7e9d4f2b #5"


# ==================== Seam 2: compute_hash_8 ====================


class TestComputeHash8:
    """compute_hash_8 取文件 SHA-256 前 8 位

    设计：与 lifeprism.sync.hash_utils.compute_file_hash 复用规范化逻辑，
    仅截取前 8 位作为冲突标记的装饰性 hash（PRD 决策 20）。
    """

    def test_hash_8_is_first_8_chars_of_sha256(self):
        """compute_hash_8 应为 SHA-256 前 8 位"""
        from lifeprism.sync.conflict_resolution import compute_hash_8

        content = "hello world"
        full_sha = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # 注意：compute_hash_8 走 compute_file_hash 的规范化路径，
        # 此处用相同规范化方式计算期望值
        from lifeprism.sync.hash_utils import compute_file_hash

        expected = compute_file_hash(content.encode("utf-8"))[:8]
        assert compute_hash_8(content) == expected
        assert len(compute_hash_8(content)) == 8

    def test_hash_8_is_hex_string(self):
        """返回值应为 8 字符的 hex 字符串"""
        from lifeprism.sync.conflict_resolution import compute_hash_8

        result = compute_hash_8("test content")
        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)

    def test_hash_8_deterministic(self):
        """相同内容产生相同 hash_8"""
        from lifeprism.sync.conflict_resolution import compute_hash_8

        assert compute_hash_8("# 行为记录\n今天心情不错") == compute_hash_8(
            "# 行为记录\n今天心情不错"
        )

    def test_hash_8_different_for_different_content(self):
        """不同内容产生不同 hash_8（极大概率）"""
        from lifeprism.sync.conflict_resolution import compute_hash_8

        assert compute_hash_8("content A") != compute_hash_8("content B")


# ==================== Seam 3: parse_conflict_blocks ====================


class TestParseConflictBlocks:
    """parse_conflict_blocks 扫描合并文本提取所有冲突块

    设计：扫描合并文本，按冲突标记切分，返回结构化 ConflictBlock 列表。
    序号 #{n} 在文件内唯一（递增 1..N），是程序匹配的真正锚点。
    """

    def test_parse_single_conflict_block(self):
        """单个冲突块：扫描后返回 1 个 ConflictBlock"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "line1\n"
            "line2\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours content\n"
            "=======\n"
            "theirs content\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "line3\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 1
        assert blocks[0].conflict_id == 1
        assert blocks[0].start_marker == "<<<<<<< LP-LOCAL-a3f8b2c1 #1"
        assert blocks[0].end_marker == ">>>>>>> LP-REMOTE-7e9d4f2b #1"
        assert "ours content" in blocks[0].ours_content
        assert "theirs content" in blocks[0].theirs_content

    def test_parse_multiple_conflict_blocks_unique_sequence_numbers(self):
        """多个冲突块：序号 #{n} 文件内唯一且递增 1..N"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

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
        assert blocks[0].conflict_id == 1
        assert blocks[1].conflict_id == 2
        # 序号唯一性
        ids = [b.conflict_id for b in blocks]
        assert len(ids) == len(set(ids)), f"序号不唯一: {ids}"
        # 序号递增 1..N
        assert ids == [1, 2]

    def test_parse_block_includes_line_numbers(self):
        """ConflictBlock 包含冲突块在文件中的行号（0-based）"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "line0\n"
            "line1\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"  # line 2
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"  # line 6
            "line7\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 1
        assert blocks[0].start_line == 2
        assert blocks[0].end_line == 6

    def test_parse_no_conflict_returns_empty_list(self):
        """无冲突标记时返回空列表"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = "line1\nline2\nline3\n"
        blocks = parse_conflict_blocks(merged)
        assert blocks == []

    def test_parse_preserves_ours_and_theirs_content_exactly(self):
        """冲突块内的 ours / theirs 内容应原样保留（数据永不丢失）"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "第一行\n"
            "第二行\n"
            "=======\n"
            "云端第一行\n"
            "云端第二行\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 1
        assert blocks[0].ours_content == "第一行\n第二行\n"
        assert blocks[0].theirs_content == "云端第一行\n云端第二行\n"

    def test_parse_handles_empty_ours_side(self):
        """ours 侧为空（一方删除场景）也能正确解析"""
        from lifeprism.sync.conflict_resolution import parse_conflict_blocks

        merged = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "=======\n"
            "theirs added\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        blocks = parse_conflict_blocks(merged)
        assert len(blocks) == 1
        assert blocks[0].ours_content == ""
        assert blocks[0].theirs_content == "theirs added\n"


# ==================== Seam 4: match_markers（程序精确匹配） ====================


class TestMatchMarkers:
    """match_markers 在文件内容中精确匹配 start_marker + end_marker

    程序匹配逻辑（PRD 决策 4、用户故事 12）：
    - 优先精确匹配 start_marker + end_marker 完整字符串
    - 失败时尝试模糊匹配（正则容忍空格变化）
    - 都失败返回 None（触发重试）

    当前方案不校验行号（PRD 决策 6 / ADR-1 决策 6）：
    LLM 无文件读取工具，行号对 LLM 无意义；程序验证基于 marker 字符串精确匹配。
    """

    def test_exact_match_succeeds(self):
        """start_marker + end_marker 在文件中精确匹配 → 返回行号区间"""
        from lifeprism.sync.conflict_resolution import match_markers

        file_content = (
            "line0\n"
            "line1\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"  # line 2
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"  # line 6
            "line7\n"
        )
        result = match_markers(
            file_content=file_content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is not None
        start_line, end_line = result
        assert start_line == 2
        assert end_line == 6

    def test_match_fails_when_hash_wrong(self):
        """start_marker 中 hash 错误时精确匹配失败，模糊匹配也失败 → 返回 None"""
        from lifeprism.sync.conflict_resolution import match_markers

        file_content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        # hash 错误：a3f8b2c1 → deadbeef
        result = match_markers(
            file_content=file_content,
            start_marker="<<<<<<< LP-LOCAL-deadbeef #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is None

    def test_match_fails_when_sequence_number_wrong(self):
        """start_marker 中序号错误时精确匹配失败，模糊匹配也失败 → 返回 None"""
        from lifeprism.sync.conflict_resolution import match_markers

        file_content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        # 序号错误：#1 → #99
        result = match_markers(
            file_content=file_content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #99",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #99",
        )
        assert result is None

    def test_match_fails_when_marker_not_in_file(self):
        """marker 在文件中完全不存在 → 返回 None"""
        from lifeprism.sync.conflict_resolution import match_markers

        file_content = "no markers here\njust regular content\n"
        result = match_markers(
            file_content=file_content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is None

    def test_fuzzy_match_succeeds_on_whitespace_variation(self):
        """marker 中空格数变化时模糊匹配应成功

        场景：LLM 输出的 marker 中意外多了一个空格（如 `LP-LOCAL-  a3f8b2c1 #1`），
        模糊匹配用正则容忍空格变化，仍能定位到原始冲突块。
        """
        from lifeprism.sync.conflict_resolution import match_markers

        file_content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "ours\n"
            "=======\n"
            "theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        # LLM 输出多了一个空格
        result = match_markers(
            file_content=file_content,
            start_marker="<<<<<<< LP-LOCAL-  a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        # 模糊匹配应成功
        assert result is not None
        start_line, end_line = result
        assert start_line == 0
        assert end_line == 4

    def test_match_returns_first_occurrence(self):
        """同一 marker 在文件中出现多次时返回第一次出现的位置

        场景：理论上同一序号 #{n} 在文件内唯一，但若 LLM 输出错误导致重复，
        程序按"首次出现"匹配，避免替换错误位置。
        """
        from lifeprism.sync.conflict_resolution import match_markers

        # 同一 marker 出现两次（极端场景）
        file_content = (
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "first ours\n"
            "=======\n"
            "first theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
            "middle\n"
            "<<<<<<< LP-LOCAL-a3f8b2c1 #1\n"
            "second ours\n"
            "=======\n"
            "second theirs\n"
            ">>>>>>> LP-REMOTE-7e9d4f2b #1\n"
        )
        result = match_markers(
            file_content=file_content,
            start_marker="<<<<<<< LP-LOCAL-a3f8b2c1 #1",
            end_marker=">>>>>>> LP-REMOTE-7e9d4f2b #1",
        )
        assert result is not None
        start_line, end_line = result
        # 应匹配第一个冲突块
        assert start_line == 0
        assert end_line == 4


# ==================== Seam 5: 集成 diff3 输出与 parse_conflict_blocks ====================


class TestDiff3OutputIntegration:
    """parse_conflict_blocks 应能解析 diff3.merge 输出的冲突标记

    复用 Issue 2 已实现的 diff3，确保 Issue 4 的解析与 Issue 2 的生成
    使用同一标记格式（PRD 决策 3）。
    """

    def test_parse_diff3_conflict_output(self):
        """diff3.merge 产生的冲突标记应能被 parse_conflict_blocks 正确解析"""
        from lifeprism.sync.conflict_resolution import (
            compute_hash_8,
            parse_conflict_blocks,
        )
        from lifeprism.sync.diff3 import merge

        base = "header\nmiddle line\nfooter\n"
        ours = "header\nOURS version\nfooter\n"
        theirs = "header\nTHEIRS version\nfooter\n"

        local_hash_8 = compute_hash_8(ours)
        remote_hash_8 = compute_hash_8(theirs)

        result = merge(base, ours, theirs, local_hash_8, remote_hash_8)
        assert result["success"] is False
        assert result["conflicts"] == 1

        blocks = parse_conflict_blocks(result["merged"])
        assert len(blocks) == 1
        assert blocks[0].conflict_id == 1
        assert "OURS version" in blocks[0].ours_content
        assert "THEIRS version" in blocks[0].theirs_content
        # start_marker / end_marker 应与 diff3 生成的格式一致
        assert blocks[0].start_marker == f"<<<<<<< LP-LOCAL-{local_hash_8} #1"
        assert blocks[0].end_marker == f">>>>>>> LP-REMOTE-{remote_hash_8} #1"

    def test_diff3_multi_conflict_blocks_have_unique_sequence_numbers(self):
        """diff3 产生的多个冲突块序号在 parse 后保持唯一性"""
        from lifeprism.sync.conflict_resolution import (
            compute_hash_8,
            parse_conflict_blocks,
        )
        from lifeprism.sync.diff3 import merge

        base = "x\n1\nx\n2\nx\n3\nx\n"
        ours = base.replace("x\n", "OURS\n")
        theirs = base.replace("x\n", "THEIRS\n")

        local_hash_8 = compute_hash_8(ours)
        remote_hash_8 = compute_hash_8(theirs)

        result = merge(base, ours, theirs, local_hash_8, remote_hash_8)
        assert result["success"] is False
        assert result["conflicts"] >= 3

        blocks = parse_conflict_blocks(result["merged"])
        ids = [b.conflict_id for b in blocks]
        assert len(ids) == len(set(ids)), f"序号不唯一: {ids}"
        # 序号应为 1..N 连续
        assert ids == list(range(1, len(blocks) + 1))
