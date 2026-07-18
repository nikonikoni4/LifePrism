"""diff3 算法 7 经典 3-way merge 场景测试（迁移自 test/explore/diff3_self_difflib/test_scenarios.py）。

测试 seam: lifeprism.sync.diff3.merge(base, ours, theirs, local_hash_8, remote_hash_8) -> dict

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-2-diff3-algorithm.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 1（用户故事 1-5）
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md 决策 1
"""

import re

import pytest

from lifeprism.sync.diff3 import merge

pytestmark = pytest.mark.core


LOCAL = "a3f8b2c1"
REMOTE = "7e9d4f2b"

MARKER_RE = re.compile(
    r"^<<<<<<< LP-LOCAL-(?P<loc>[0-9a-f]{8}) #(?P<n>\d+)\n"
    r"(?P<ours>.*?)"
    r"^=======\n"
    r"(?P<theirs>.*?)"
    r"^>>>>>>> LP-REMOTE-(?P<rem>[0-9a-f]{8}) #(?P<n2>\d+)\n",
    re.MULTILINE | re.DOTALL,
)


def parse_conflicts(merged, local_hash, remote_hash):
    """解析 merged 文本中所有冲突块。

    Returns:
        list[dict]: 每个元素包含 n / local / remote / ours / theirs 字段。
    Raises:
        AssertionError: 任一冲突块格式不规范。
    """
    blocks = []
    for m in MARKER_RE.finditer(merged):
        assert m.group("loc") == local_hash, (
            f"local hash mismatch: {m.group('loc')} != {local_hash}")
        assert m.group("rem") == remote_hash, (
            f"remote hash mismatch: {m.group('rem')} != {remote_hash}")
        assert m.group("n") == m.group("n2"), (
            f"mismatched sequence number in block: {m.group('n')} vs {m.group('n2')}")
        blocks.append({
            "n": int(m.group("n")),
            "local": m.group("loc"),
            "remote": m.group("rem"),
            "ours": m.group("ours"),
            "theirs": m.group("theirs"),
        })
    return blocks


def assert_unique_sequence_numbers(merged, local_hash, remote_hash):
    """冲突块序号在文件内必须唯一。"""
    blocks = parse_conflicts(merged, local_hash, remote_hash)
    nums = [b["n"] for b in blocks]
    assert len(nums) == len(set(nums)), f"sequence numbers not unique: {nums}"
    return blocks


# --------------------------------------------------------------------------
# Scenario 1: both sides change DIFFERENT regions -> auto-merge success
# --------------------------------------------------------------------------
def test_scenario_1_different_regions():
    base = "L1\nL2\nL3\nL4\nL5\n"
    ours = "L1\nL2-OURS\nL3\nL4\nL5\n"      # changed L2
    theirs = "L1\nL2\nL3\nL4-THEIRS\nL5\n"  # changed L4

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got conflicts={r['conflicts']}"
    assert r["conflicts"] == 0
    assert "L2-OURS" in r["merged"], "ours change lost"
    assert "L4-THEIRS" in r["merged"], "theirs change lost"
    # Unchanged lines preserved
    for line in ("L1\n", "L3\n", "L5\n"):
        assert line in r["merged"], f"lost stable line {line!r}"
    # No markers
    assert "<<<<<<<" not in r["merged"]
    assert "=======" not in r["merged"]
    assert ">>>>>>>" not in r["merged"]


# --------------------------------------------------------------------------
# Scenario 2: both sides change SAME line with different content -> conflict
# --------------------------------------------------------------------------
def test_scenario_2_same_line_different():
    base = "header\nmiddle line\nfooter\n"
    ours = "header\nOURS version\nfooter\n"
    theirs = "header\nTHEIRS version\nfooter\n"

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False, "expected a conflict"
    assert r["conflicts"] == 1, f"expected 1 conflict, got {r['conflicts']}"
    blocks = assert_unique_sequence_numbers(r["merged"], LOCAL, REMOTE)
    assert blocks[0]["n"] == 1
    assert "OURS version" in blocks[0]["ours"], "ours content missing from conflict"
    assert "THEIRS version" in blocks[0]["theirs"], "theirs content missing from conflict"
    # Stable context preserved outside conflict
    assert "header\n" in r["merged"]
    assert "footer\n" in r["merged"]


# --------------------------------------------------------------------------
# Scenario 3: one side deletes, other modifies -> conflict
# --------------------------------------------------------------------------
def test_scenario_3_delete_vs_modify():
    base = "keep1\ntarget\nkeep2\n"
    ours = "keep1\nkeep2\n"             # deleted target
    theirs = "keep1\ntarget-MOD\nkeep2\n"  # modified target

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False, "expected a conflict (delete vs modify)"
    assert r["conflicts"] == 1, f"expected 1 conflict, got {r['conflicts']}"
    blocks = assert_unique_sequence_numbers(r["merged"], LOCAL, REMOTE)
    # ours side of the conflict should be empty (deleted)
    assert blocks[0]["ours"].strip() == "", (
        f"ours side should be empty for delete, got {blocks[0]['ours']!r}")
    assert "target-MOD" in blocks[0]["theirs"], "theirs modification missing"
    assert "keep1\n" in r["merged"] and "keep2\n" in r["merged"]


# --------------------------------------------------------------------------
# Scenario 4: one side empty file, other has content -> conflict
# --------------------------------------------------------------------------
def test_scenario_4_empty_vs_content():
    base = "original line 1\noriginal line 2\n"
    ours = ""                                  # empty file
    theirs = "original line 1\noriginal line 2\nNEW\n"

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False, "expected a conflict (empty vs content)"
    assert r["conflicts"] >= 1, "expected at least 1 conflict"
    blocks = assert_unique_sequence_numbers(r["merged"], LOCAL, REMOTE)
    # The NEW content from theirs must survive somewhere in the output
    assert "NEW\n" in r["merged"], "theirs new content lost"
    # The ours side of at least one conflict should be empty
    assert any(b["ours"].strip() == "" for b in blocks), (
        "expected at least one empty ours side")


# --------------------------------------------------------------------------
# Scenario 5: both ADD content at DIFFERENT positions -> auto-merge success
# --------------------------------------------------------------------------
def test_scenario_5_add_different_positions():
    base = "head\nmid\ntail\n"
    ours = "HEAD-NEW\nhead\nmid\ntail\n"        # added at start
    theirs = "head\nmid\ntail\nTAIL-NEW\n"      # added at end

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, f"expected auto-merge, got conflicts={r['conflicts']}"
    assert r["conflicts"] == 0
    assert "HEAD-NEW\n" in r["merged"], "ours addition lost"
    assert "TAIL-NEW\n" in r["merged"], "theirs addition lost"
    for line in ("head\n", "mid\n", "tail\n"):
        assert line in r["merged"], f"lost stable line {line!r}"
    assert "<<<<<<<" not in r["merged"]


# --------------------------------------------------------------------------
# Scenario 6: both ADD content at SAME position -> conflict
# --------------------------------------------------------------------------
def test_scenario_6_add_same_position():
    base = "anchor\n"
    ours = "anchor\nOURS-ADD\n"
    theirs = "anchor\nTHEIRS-ADD\n"

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False, "expected a conflict (both add at same spot)"
    assert r["conflicts"] == 1, f"expected 1 conflict, got {r['conflicts']}"
    blocks = assert_unique_sequence_numbers(r["merged"], LOCAL, REMOTE)
    assert "OURS-ADD" in blocks[0]["ours"], "ours addition missing from conflict"
    assert "THEIRS-ADD" in blocks[0]["theirs"], "theirs addition missing from conflict"
    assert "anchor\n" in r["merged"], "anchor lost"


# --------------------------------------------------------------------------
# Scenario 7: one side moves a whole block -> auto-merge success
# --------------------------------------------------------------------------
def test_scenario_7_block_move():
    base = "A\nB\nC\nD\nE\n"
    # ours moves B,C,D to after E; theirs unchanged
    ours = "A\nE\nB\nC\nD\n"
    theirs = base

    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is True, (
        f"expected auto-merge for block move, got conflicts={r['conflicts']}")
    assert r["conflicts"] == 0
    # The moved ordering should be preserved (ours' reordering wins because
    # theirs == base is unchanged).
    assert r["merged"] == "A\nE\nB\nC\nD\n", f"unexpected move result: {r['merged']!r}"


# --------------------------------------------------------------------------
# Extra: multi-conflict sequence numbering uniqueness
# --------------------------------------------------------------------------
def test_multi_conflict_unique_numbers():
    base = "x\n1\nx\n2\nx\n3\nx\n"
    # Change every "x" differently on both sides -> 3+ conflicts
    ours = base.replace("x\n", "OURS\n")
    theirs = base.replace("x\n", "THEIRS\n")
    r = merge(base, ours, theirs, LOCAL, REMOTE)
    assert r["success"] is False
    assert r["conflicts"] >= 3, f"expected >=3 conflicts, got {r['conflicts']}"
    blocks = assert_unique_sequence_numbers(r["merged"], LOCAL, REMOTE)
    nums = sorted(b["n"] for b in blocks)
    assert nums == list(range(1, r["conflicts"] + 1)), (
        f"sequence numbers should be 1..N contiguous, got {nums}")
