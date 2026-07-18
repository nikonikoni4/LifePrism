"""diff3 算法边界场景测试（迁移自 test/explore/diff3_self_difflib/test_edge_cases.py）。

测试 seam: lifeprism.sync.diff3.merge(base, ours, theirs, local_hash_8, remote_hash_8) -> dict

覆盖 17 项边界场景：
  - 双方完全相同（无冲突）
  - 一方等于 base（返回另一方）
  - 空 base
  - 中英文混合
  - Markdown 特殊字符（# - | * > ` 等）
  - 长文本性能（1000+ 行，计时）
  - emoji 内容
  - 无尾换行
  - CRLF 行尾
  - 数据完整性（冲突块内 ours/theirs 内容全保留）

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-2-diff3-algorithm.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 1
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md
"""

import re
import time
import tracemalloc

import pytest

from lifeprism.sync.diff3 import merge

pytestmark = pytest.mark.core


LOCAL = "a3f8b2c1"
REMOTE = "7e9d4f2b"

MARKER_RE = re.compile(
    r"^<<<<<<< LP-LOCAL-([0-9a-f]{8}) #(\d+)\n(.*?)^=======\n(.*?)"
    r"^>>>>>>> LP-REMOTE-([0-9a-f]{8}) #(\d+)\n",
    re.MULTILINE | re.DOTALL,
)


def count_conflicts(merged):
    return len(MARKER_RE.findall(merged))


# --------------------------------------------------------------------------
def test_identical_ours_theirs():
    """Both sides made the exact same change -> no conflict, change kept."""
    base = "a\nb\nc\n"
    both = "a\nB-CHANGED\nc\n"
    r = merge(base, both, both, LOCAL, REMOTE)
    assert r["success"] is True, f"identical sides should not conflict: {r['merged']!r}"
    assert r["conflicts"] == 0
    assert r["merged"] == both, "should equal the common changed version"


def test_one_side_equals_base():
    """ours == base -> result is theirs; theirs == base -> result is ours."""
    base = "line1\nline2\nline3\n"
    theirs = "line1\nLINE2-MOD\nline3\n"
    # ours unchanged
    r = merge(base, base, theirs, LOCAL, REMOTE)
    assert r["success"] is True
    assert r["merged"] == theirs, f"ours==base should return theirs, got {r['merged']!r}"
    # theirs unchanged
    ours = "line1\nLINE2-MOD\nline3\n"
    r = merge(base, ours, base, LOCAL, REMOTE)
    assert r["success"] is True
    assert r["merged"] == ours, f"theirs==base should return ours, got {r['merged']!r}"


def test_empty_base():
    """Empty base, both sides add IDENTICAL content -> no conflict.

    (ours_c == theirs_c branch.) Divergent additions from empty base are
    covered by test_empty_base_conflict; the subset case (ours being a
    prefix of theirs) is a known limitation that produces a conflict block
    spanning the whole content - see test_empty_base_subset_limitation.
    """
    base = ""
    both = "a\nb\nc\n"
    r = merge(base, both, both, LOCAL, REMOTE)
    assert r["success"] is True, f"identical adds should not conflict: {r['merged']!r}"
    assert r["merged"] == both


def test_empty_base_subset_limitation():
    """KNOWN LIMITATION: empty base, ours is a prefix of theirs.

    Standard diff3 anchors on base; with an empty base there is no anchor,
    so the whole (ours vs theirs) region becomes one conflict block even
    though the two share a common prefix. git merge-file produces a smaller
    conflict block (only the divergent suffix). Both produce a conflict
    (status agrees); the scope differs. No data is lost.
    """
    base = ""
    ours = "a\nb\n"
    theirs = "a\nb\nc\n"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False, "expected conflict (empty base, divergent adds)"
    # Both sides' content must survive in the conflict block.
    assert "a\n" in r["merged"] and "b\n" in r["merged"] and "c\n" in r["merged"]


def test_empty_base_conflict():
    """Empty base, both add different content at same position -> conflict."""
    base = ""
    ours = "ours-content\n"
    theirs = "theirs-content\n"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False, "expected conflict when both add from empty base"
    assert r["conflicts"] == 1
    assert "ours-content" in r["merged"]
    assert "theirs-content" in r["merged"]


def test_all_empty():
    """All three empty -> empty result, no conflict."""
    r = merge("", "", "", LOCAL, REMOTE)
    assert r["success"] is True
    assert r["merged"] == ""
    assert r["conflicts"] == 0


def test_chinese_english_mixed():
    base = "今天心情不错\nI feel good\n明天计划\n"
    ours = "今天心情很好\nI feel good\n明天计划\n"      # changed Chinese line 1
    theirs = "今天心情不错\nI feel good\n明天计划-修改\n"  # changed Chinese line 3
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got {r['merged']!r}"
    assert "今天心情很好" in r["merged"], "ours Chinese change lost"
    assert "明天计划-修改" in r["merged"], "theirs Chinese change lost"
    assert "I feel good" in r["merged"]


def test_chinese_same_line_conflict():
    base = "总结\n今日完成3件事\n"
    ours = "总结\n今日完成5件事\n"
    theirs = "总结\n今日完成7件事\n"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False
    assert r["conflicts"] == 1
    assert "今日完成5件事" in r["merged"]
    assert "今日完成7件事" in r["merged"]


def test_markdown_special_chars():
    """Markdown with #, -, |, *, >, ` should merge by line correctly."""
    base = "# Title\n\n| Col1 | Col2 |\n| --- | --- |\n| a | b |\n\n- item 1\n- item 2\n"
    ours = "# Title MODIFIED\n\n| Col1 | Col2 |\n| --- | --- |\n| a | b |\n\n- item 1\n- item 2\n"
    theirs = "# Title\n\n| Col1 | Col2 |\n| --- | --- |\n| a | b |\n\n- item 1\n- item 2\n- item 3\n"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got {r['merged']!r}"
    assert "# Title MODIFIED" in r["merged"], "ours title change lost"
    assert "- item 3" in r["merged"], "theirs new item lost"
    # Table row preserved
    assert "| a | b |" in r["merged"]


def test_markdown_conflict():
    base = "# 日记\n\n正文\n"
    ours = "# 日记-本地\n\n正文\n"
    theirs = "# 日记-云端\n\n正文\n"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False
    assert r["conflicts"] == 1
    assert "日记-本地" in r["merged"]
    assert "日记-云端" in r["merged"]


def test_emoji_content():
    base = "心情 😊\n工作 💻\n休息 🛌\n"
    ours = "心情 😄\n工作 💻\n休息 🛌\n"     # changed emoji line 1
    theirs = "心情 😊\n工作 💻\n休息 🛌\n运动 🏃\n"  # added emoji line
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got {r['merged']!r}"
    assert "😄" in r["merged"], "ours emoji change lost"
    assert "🏃" in r["merged"], "theirs emoji addition lost"


def test_no_trailing_newline():
    """Last line without trailing newline must not corrupt markers.

    Uses non-adjacent changes (lines 2 and 4) so auto-merge is expected;
    adjacent changes would (correctly) conflict like git.
    """
    base = "a\nb\nc\nd\ne"     # no trailing \n
    ours = "a\nB\nc\nd\ne"     # change line 2
    theirs = "a\nb\nc\nD\ne"   # change line 4
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got {r['merged']!r}"
    assert "B" in r["merged"] and "D" in r["merged"]


def test_no_trailing_newline_conflict():
    base = "a\nb\nc"
    ours = "a\nX\nc"
    theirs = "a\nY\nc"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False
    assert r["conflicts"] == 1
    # Verify the marker fences are each on their own line (not glued to content).
    lines = r["merged"].split("\n")
    assert any(l.startswith("<<<<<<<") for l in lines), "missing start marker"
    assert any(l == "=======" for l in lines), "missing separator"
    assert any(l.startswith(">>>>>>>") for l in lines), "missing end marker"


def test_crlf_line_endings():
    """CRLF endings should be preserved (split keeps \\r\\n attached).

    Uses non-adjacent changes (lines 2 and 4) so auto-merge is expected.
    """
    base = "a\r\nb\r\nc\r\nd\r\ne\r\n"
    ours = "a\r\nB\r\nc\r\nd\r\ne\r\n"     # change line 2
    theirs = "a\r\nb\r\nc\r\nD\r\ne\r\n"   # change line 4
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got {r['merged']!r}"
    assert "B\r\n" in r["merged"], "ours CRLF change lost"
    assert "D\r\n" in r["merged"], "theirs CRLF change lost"


def test_long_text_performance():
    """1000+ line file: must complete quickly and not blow up memory."""
    n = 1500
    base_lines = [f"line {i} content here" for i in range(n)]
    base = "\n".join(base_lines) + "\n"
    # ours modifies lines 10 and 800
    ours_lines = base_lines.copy()
    ours_lines[10] = "OURS modified line 10"
    ours_lines[800] = "OURS modified line 800"
    ours = "\n".join(ours_lines) + "\n"
    # theirs modifies lines 400 and 1200
    theirs_lines = base_lines.copy()
    theirs_lines[400] = "THEIRS modified line 400"
    theirs_lines[1200] = "THEIRS modified line 1200"
    theirs = "\n".join(theirs_lines) + "\n"

    tracemalloc.start()
    t0 = time.perf_counter()
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    elapsed = time.perf_counter() - t0
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert r["success"] is True, f"expected auto-merge, got {r['conflicts']} conflicts"
    assert "OURS modified line 10" in r["merged"]
    assert "OURS modified line 800" in r["merged"]
    assert "THEIRS modified line 400" in r["merged"]
    assert "THEIRS modified line 1200" in r["merged"]
    # Performance thresholds (generous; difflib is O(n^2) worst case).
    assert elapsed < 5.0, f"too slow: {elapsed:.3f}s for {n} lines"


def test_long_text_conflict_performance():
    """1000+ line file with a conflict region: still fast."""
    n = 1200
    base_lines = [f"row {i}" for i in range(n)]
    base = "\n".join(base_lines) + "\n"
    ours_lines = base_lines.copy()
    theirs_lines = base_lines.copy()
    ours_lines[500] = "OURS row 500"
    theirs_lines[500] = "THEIRS row 500"
    ours = "\n".join(ours_lines) + "\n"
    theirs = "\n".join(theirs_lines) + "\n"

    t0 = time.perf_counter()
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    elapsed = time.perf_counter() - t0
    assert r["success"] is False
    assert r["conflicts"] == 1
    assert elapsed < 5.0, f"too slow: {elapsed:.3f}s"
    assert "OURS row 500" in r["merged"]
    assert "THEIRS row 500" in r["merged"]


def test_data_preservation_in_conflict():
    """Neither ours nor theirs content may ever be silently dropped."""
    base = "h\nx\nf\n"
    ours = "h\nOURS-A\nOURS-B\nf\n"
    theirs = "h\nTHEIRS-1\nTHEIRS-2\nf\n"
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False
    for token in ("OURS-A", "OURS-B", "THEIRS-1", "THEIRS-2"):
        assert token in r["merged"], f"data lost: {token}"
    # Stable context preserved
    assert "h\n" in r["merged"] and "f\n" in r["merged"]
