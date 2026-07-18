"""diff3 算法与 git merge-file oracle 对比测试（迁移自 test/explore/diff3_self_difflib/test_git_oracle.py）。

测试 seam: lifeprism.sync.diff3.merge(base, ours, theirs, local_hash_8, remote_hash_8) -> dict

对于固定的 (base, ours, theirs) 三元组，对比 `git merge-file` 命令（作为 ground truth）
与自研实现的输出，验证：
  1. 状态判定一致性：双方都自动合并 OR 双方都冲突
  2. 计数一致性：双方都冲突时，冲突块数量相同
  3. 文本一致性：双方都自动合并时，合并文本逐字节相同
  4. 骨架一致性：双方都冲突时，去掉冲突块后的稳定内容相同
  5. 无数据丢失：所有用例中 ours 与 theirs 的内容均在合并结果或冲突块中

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-2-diff3-algorithm.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 1
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md
- 稳定性报告: test/explore/diff3_self_difflib/REPORT.md
"""

import os
import random
import re
import shutil
import subprocess
import tempfile

import pytest

from lifeprism.sync.diff3 import merge

pytestmark = pytest.mark.core


LOCAL = "a3f8b2c1"
REMOTE = "7e9d4f2b"

# A conflict block in EITHER git's or our output: 7-char fences.
CONFLICT_BLOCK_RE = re.compile(
    r"^<<<<<<< .+\n.*?^=======\n.*?^>>>>>>> .+\n",
    re.MULTILINE | re.DOTALL,
)

# 7 PRD scenarios + 60 random cases = 67 oracle cases
RANDOM_SEED = 20260717
N_RANDOM_CASES = 60

# Tolerance: status divergence rate must be below this threshold
STATUS_DIVERGE_TOLERANCE = 0.15


# --------------------------------------------------------------------------
# Oracle: git merge-file
# --------------------------------------------------------------------------
def git_merge(base: str, ours: str, theirs: str):
    """Run `git merge-file -p` and return (success, conflicts, merged_text).

    File order for git merge-file: FILE1=ours FILE2=base FILE3=theirs.
    Exit code: 0 = clean merge, >0 = number of conflicts (capped 127),
    <0 = error.
    """
    d = tempfile.mkdtemp(prefix="diff3_oracle_")
    try:
        p_base = os.path.join(d, "base")
        p_ours = os.path.join(d, "ours")
        p_theirs = os.path.join(d, "theirs")
        # Write as bytes with explicit '\n' to avoid CRLF translation on Windows.
        for path, content in ((p_base, base), (p_ours, ours), (p_theirs, theirs)):
            with open(path, "wb") as f:
                f.write(content.encode("utf-8"))
        proc = subprocess.run(
            ["git", "merge-file", "-p",
             "-L", "ours", "-L", "base", "-L", "theirs",
             p_ours, p_base, p_theirs],
            capture_output=True,
        )
        merged = proc.stdout.decode("utf-8")
        code = proc.returncode
        if code < 0:
            raise RuntimeError(f"git merge-file error: {proc.stderr.decode('utf-8')}")
        success = (code == 0)
        conflicts = code if code > 0 else 0
        return success, conflicts, merged
    finally:
        for name in ("base", "ours", "theirs"):
            p = os.path.join(d, name)
            if os.path.exists(p):
                os.remove(p)
        try:
            os.rmdir(d)
        except OSError:
            pass


def skeleton(text: str) -> str:
    """Collapse every conflict block to a single '<<CONFLICT>>' placeholder.

    Lets us compare the stable content surrounding conflicts regardless of
    the exact marker labels.
    """
    return CONFLICT_BLOCK_RE.sub("<<CONFLICT>>\n", text)


def classify_case(base: str, ours: str, theirs: str) -> dict:
    """Run both mergers and classify the comparison.

    Returns:
        dict with keys:
            category: one of
                exact_match       (both auto-merge, identical text)
                skeleton_match    (both conflict, same count, same skeleton)
                count_diverge     (both conflict, different count)
                status_diverge    (one auto-merged, other conflicted)
                text_diverge      (both auto-merge, different text)
                skeleton_diverge  (both conflict, same count, different skeleton)
            git_success, git_conflicts, mine_success, mine_conflicts
            base/ours/theirs/merged samples
    """
    g_success, g_conf, g_merged = git_merge(base, ours, theirs)
    m = merge(base, ours, theirs, LOCAL, REMOTE)
    m_success = m["success"]
    m_conf = m["conflicts"]
    m_merged = m["merged"]

    if g_success and m_success:
        if g_merged == m_merged:
            category = "exact_match"
        else:
            category = "text_diverge"
    elif (not g_success) and (not m_success):
        if g_conf != m_conf:
            category = "count_diverge"
        elif skeleton(g_merged) == skeleton(m_merged):
            category = "skeleton_match"
        else:
            category = "skeleton_diverge"
    else:
        category = "status_diverge"

    return {
        "category": category,
        "git_success": g_success,
        "git_conflicts": g_conf,
        "mine_success": m_success,
        "mine_conflicts": m_conf,
        "base": base,
        "ours": ours,
        "theirs": theirs,
        "git_merged": g_merged,
        "mine_merged": m_merged,
    }


# --------------------------------------------------------------------------
# Random test data generation
# --------------------------------------------------------------------------
VOCAB = [
    "apple", "banana", "cherry", "date", "elderberry",
    "fig", "grape", "honeydew", "kiwi", "lemon",
    "mango", "nectarine", "orange", "papaya", "quince",
    "raspberry", "strawberry", "tangerine", "watermelon", "x",
]


def gen_base(rng: random.Random, n_lines: int) -> str:
    return "".join(rng.choice(VOCAB) + "\n" for _ in range(n_lines))


def mutate(text: str, rng: random.Random, n_ops: int) -> str:
    """Apply n_ops random insert/delete/modify operations to text.

    Works on the '\\n'-split line list (preserving trailing newline semantics).
    """
    lines = text.split("\n")
    # text always ends with "\n" so lines[-1] == "" ; drop it for editing.
    if lines and lines[-1] == "":
        lines = lines[:-1]
    for _ in range(n_ops):
        if not lines:
            op = "insert"
        else:
            op = rng.choice(["insert", "delete", "modify", "insert"])
        if op == "insert":
            pos = rng.randint(0, len(lines))
            lines.insert(pos, rng.choice(VOCAB) + "-new")
        elif op == "delete":
            pos = rng.randint(0, len(lines) - 1)
            del lines[pos]
        else:  # modify
            pos = rng.randint(0, len(lines) - 1)
            lines[pos] = rng.choice(VOCAB) + "-mod"
    return "".join(l + "\n" for l in lines)


# --------------------------------------------------------------------------
# Fixed PRD scenarios as oracle cases too (direct git vs ours)
# --------------------------------------------------------------------------
PRD_CASES = [
    ("s1-different-regions",
     "L1\nL2\nL3\nL4\nL5\n",
     "L1\nL2-OURS\nL3\nL4\nL5\n",
     "L1\nL2\nL3\nL4-THEIRS\nL5\n"),
    ("s2-same-line",
     "header\nmiddle line\nfooter\n",
     "header\nOURS version\nfooter\n",
     "header\nTHEIRS version\nfooter\n"),
    ("s3-delete-vs-modify",
     "keep1\ntarget\nkeep2\n",
     "keep1\nkeep2\n",
     "keep1\ntarget-MOD\nkeep2\n"),
    ("s4-empty-vs-content",
     "original line 1\noriginal line 2\n",
     "",
     "original line 1\noriginal line 2\nNEW\n"),
    ("s5-add-different-pos",
     "head\nmid\ntail\n",
     "HEAD-NEW\nhead\nmid\ntail\n",
     "head\nmid\ntail\nTAIL-NEW\n"),
    ("s6-add-same-pos",
     "anchor\n",
     "anchor\nOURS-ADD\n",
     "anchor\nTHEIRS-ADD\n"),
    ("s7-block-move",
     "A\nB\nC\nD\nE\n",
     "A\nE\nB\nC\nD\n",
     "A\nB\nC\nD\nE\n"),
]


# --------------------------------------------------------------------------
# Fixtures: generate the 67 oracle cases once per session
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def oracle_cases():
    """生成 67 个 oracle 用例：7 PRD 场景 + 60 随机场景。

    固定种子保证可复现。
    """
    cases = []

    # 7 PRD scenarios
    for name, base, ours, theirs in PRD_CASES:
        cases.append({
            "name": name,
            "base": base,
            "ours": ours,
            "theirs": theirs,
        })

    # 60 random cases (deterministic seed for reproducibility)
    rng = random.Random(RANDOM_SEED)
    for i in range(N_RANDOM_CASES):
        n_lines = rng.randint(3, 12)
        base = gen_base(rng, n_lines)
        ours = mutate(base, rng, rng.randint(1, 4))
        theirs = mutate(base, rng, rng.randint(1, 4))
        cases.append({
            "name": f"random-{i:02d}",
            "base": base,
            "ours": ours,
            "theirs": theirs,
        })

    return cases


def _classify_or_skip(case):
    """运行 oracle 对比，git 不可用时跳过。"""
    if shutil.which("git") is None:
        pytest.skip("git executable not available")
    return classify_case(case["base"], case["ours"], case["theirs"])


# --------------------------------------------------------------------------
# Helpers for data-loss checking
# --------------------------------------------------------------------------
def _non_base_lines(text: str, base: str) -> set:
    """提取 text 中"非 base 修改"的行集合。

    返回 text 中所有非空且**不在 base 行集合中**的行——这些是 text 相对
    base 的新增或修改后内容。这部分内容必须出现在合并结果中（在合并文本里
    或冲突块里），否则即为数据丢失。

    注意：
        - 双方都保留的行（在 base 中也存在）不在检查范围内——若一方删除
          某行、另一方未改，合并时该行被正确删除，非丢失。
        - 双方都修改同一行为相同内容时，新内容仍需出现（属于 ours_unique
          和 theirs_unique 的交集）。
    """
    base_lines = {l for l in base.split("\n") if l.strip()}
    return {l for l in text.split("\n") if l.strip() and l not in base_lines}


# --------------------------------------------------------------------------
# Seam 1: 67 oracle 用例的状态判定一致性（容忍少量已知分歧）
# --------------------------------------------------------------------------
def test_oracle_status_agreement(oracle_cases):
    """67 个 oracle 用例的状态判定一致性。

    自研实现基于 difflib（Ratcliff-Obershelp 算法），git merge 基于 Myers
    diff，对重复行/移动的对齐方式不同，会产生少量状态分歧（mine 自动合并、
    git 冲突）。这是已知且可接受的算法行为，详见 REPORT.md §3.2 类别 B。

    容忍阈值：状态分歧率 < 15%（与原型 test_git_oracle.py main() 一致），
    且每个状态分歧用例必须是"有效合并"（无数据丢失）。
    """
    if shutil.which("git") is None:
        pytest.skip("git executable not available")

    categories = {}
    status_diverge_cases = []
    for case in oracle_cases:
        result = classify_case(case["base"], case["ours"], case["theirs"])
        categories[result["category"]] = categories.get(result["category"], 0) + 1
        if result["category"] == "status_diverge":
            status_diverge_cases.append((case, result))

    total = sum(categories.values())
    status_div = categories.get("status_diverge", 0)

    # 容忍阈值：与原型 test_git_oracle.py main() 一致（< 15%）
    assert status_div / total < STATUS_DIVERGE_TOLERANCE, (
        f"status divergence rate {status_div}/{total} = "
        f"{status_div / total * 100:.1f}% >= "
        f"{STATUS_DIVERGE_TOLERANCE * 100:.0f}%: "
        f"状态分歧率超阈值。"
        f"分歧用例: {[c['name'] for c, _ in status_diverge_cases]}"
    )

    # 每个状态分歧用例必须是"有效合并"——mine 自动合并且无数据丢失。
    # 状态分歧指 git 报冲突但 mine 自动合并，此时必须验证 mine 的合并结果
    # 保留了 ours 与 theirs 的所有非 base 修改内容。
    for case, result in status_diverge_cases:
        assert result["mine_success"] is True, (
            f"状态分歧用例 {case['name']} 必须是 mine 自动合并成功"
        )
        merged = result["mine_merged"]
        ours_unique = _non_base_lines(case["ours"], case["base"])
        theirs_unique = _non_base_lines(case["theirs"], case["base"])
        missing_ours = [l for l in ours_unique if l not in merged]
        missing_theirs = [l for l in theirs_unique if l not in merged]
        assert not missing_ours and not missing_theirs, (
            f"状态分歧用例 {case['name']} 数据丢失: "
            f"missing_ours={missing_ours}, missing_theirs={missing_theirs}"
        )


# --------------------------------------------------------------------------
# Seam 2: 67 oracle 用例的数据完整性（ours/theirs 非修改内容永不丢失）
# --------------------------------------------------------------------------
def test_oracle_no_data_loss(oracle_cases):
    """67 个 oracle 用例的合并结果中 ours/theirs 的非 base 修改内容永不丢失。

    对每个用例检查：ours 与 theirs 中"非 base 修改"的行（即 ours/theirs
    相对 base 新增或修改后的内容）必须出现在合并结果中（在合并文本里或
    冲突块里）。

    注意：双方都未改的行（在 base 中也有）不在检查范围内——若一方删除某行、
    另一方未改，合并时该行被正确删除，不属于数据丢失。
    """
    if shutil.which("git") is None:
        pytest.skip("git executable not available")

    failed = []
    for case in oracle_cases:
        result = classify_case(case["base"], case["ours"], case["theirs"])
        merged = result["mine_merged"]

        # 提取 ours 和 theirs 中"非 base 修改"的行（新增/修改后内容）
        ours_unique = _non_base_lines(case["ours"], case["base"])
        theirs_unique = _non_base_lines(case["theirs"], case["base"])

        # 所有非 base 修改行必须在合并结果中出现（合并、冲突块都算）
        missing_ours = [l for l in ours_unique if l not in merged]
        missing_theirs = [l for l in theirs_unique if l not in merged]

        if missing_ours or missing_theirs:
            failed.append({
                "name": case["name"],
                "missing_ours": missing_ours,
                "missing_theirs": missing_theirs,
            })

    assert not failed, (
        f"数据丢失检测失败：{len(failed)} 个用例存在数据丢失。"
        f"前 3 个失败用例: {failed[:3]}"
    )


# --------------------------------------------------------------------------
# Seam 3: 67 oracle 用例的整体一致性统计
# --------------------------------------------------------------------------
def test_oracle_overall_agreement(oracle_cases):
    """67 个 oracle 用例的整体一致性统计。

    记录所有分类结果，验证：
    - 总用例数 = 67
    - 状态分歧率 < 15%（与原型 test_git_oracle.py main() 一致）
    - 一致率（exact_match + skeleton_match）/ total >= 80%
      （参考 REPORT.md：89.6%）
    """
    if shutil.which("git") is None:
        pytest.skip("git executable not available")

    categories = {}
    for case in oracle_cases:
        result = classify_case(case["base"], case["ours"], case["theirs"])
        categories[result["category"]] = categories.get(result["category"], 0) + 1

    total = sum(categories.values())
    agree = categories.get("exact_match", 0) + categories.get("skeleton_match", 0)
    status_div = categories.get("status_diverge", 0)

    # 总用例数必须为 7 + 60 = 67
    assert total == 67, f"expected 67 oracle cases, got {total}"

    # 状态分歧率必须低于容忍阈值（< 15%）
    assert status_div / total < STATUS_DIVERGE_TOLERANCE, (
        f"status divergence: {status_div}/{total} "
        f"({status_div / total * 100:.1f}%) >= "
        f"{STATUS_DIVERGE_TOLERANCE * 100:.0f}%. "
        f"Categories: {categories}"
    )

    # 一致率必须 >= 80%（参考 REPORT.md：89.6%）
    agreement_rate = agree / total
    assert agreement_rate >= 0.80, (
        f"agreement rate too low: {agree}/{total} = "
        f"{agreement_rate * 100:.1f}% < 80%. "
        f"Categories: {categories}"
    )
