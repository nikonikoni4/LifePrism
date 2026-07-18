"""基于 Python 标准库 difflib 自研的 3-way merge（diff3）算法。

参考 ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md

算法原理（diff3 经典三步法）：
    1. 用 ``difflib.SequenceMatcher(autojunk=False)`` 分别计算
       ``(base, ours)`` 与 ``(base, theirs)`` 的匹配块。
    2. 取两组匹配块在 base 轴上的交集——这些是"双方都未改动"的同步点
       (sync regions)。
    3. 同步点之间的间隙为 change chunk，逐块分类：
       - ``ours_c == theirs_c`` → 双方做了相同修改，直接采用（含双方都删除）
       - ``ours_c == base_c``   → 本地未动，采用云端
       - ``theirs_c == base_c`` → 云端未动，采用本地
       - 否则 → 产生冲突标记
    4. 移动处理：当 sync region 在 ours/theirs 维度上需要回退（说明内容
       被搬到别处）时跳过该 sync，等价于把移动按 delete+insert 处理，
       与标准 diff3 行为一致。
    5. 行切分仅按 ``\\n``（保留 ``\\r\\n``），与 ``git merge-file`` 行语义对齐。

冲突标记格式（来自 PRD 决策 3，含 hash 与序号字段，由 Issue 4 扩展实现）::

    <<<<<<< LP-LOCAL-{local_hash_8} #{n}
    {ours_content}
    =======
    {theirs_content}
    >>>>>>> LP-REMOTE-{remote_hash_8} #{n}

安全属性：
    - 数据永不丢失：所有冲突场景 ours/theirs 内容均完整保留（在合并结果或
      冲突块中）。
    - 确定性：相同输入永远相同输出，可复现、可测试。
    - 零外部依赖：仅用 Python 标准库 ``difflib``。
"""

import difflib


def _split_lines(text: str) -> list[str]:
    """将文本按 ``\\n`` 切分为行列表，保留行尾符。

    仅按 ``\\n`` 切分（不像 ``str.splitlines`` 那样还会切 ``\\r``、``\\v``、
    ``\\f``），这样 ``\\r\\n`` 行尾会完整保留在每一行末尾，与
    ``git merge-file`` 的行语义对齐。

    Args:
        text: 待切分的文本。

    Returns:
        行列表；空文本返回空列表。最后一行无 ``\\n`` 也作为一行保留。
    """
    if not text:
        return []
    lines: list[str] = []
    start = 0
    n = len(text)
    for i in range(n):
        if text[i] == "\n":
            lines.append(text[start : i + 1])
            start = i + 1
    if start < n:
        lines.append(text[start:])
    return lines


def _find_sync_regions(
    base_lines: list[str],
    ours_lines: list[str],
    theirs_lines: list[str],
) -> list[tuple[int, int, int, int]]:
    """找出 base 中同时在 ours 和 theirs 里都匹配（未改动）的区域。

    Returns:
        元组列表 ``(base_start, base_end, ours_start, theirs_start)``，
        按 ``base_start`` 升序排列，且在 base 轴上不重叠。
    """
    sm_o = difflib.SequenceMatcher(None, base_lines, ours_lines, autojunk=False)
    sm_t = difflib.SequenceMatcher(None, base_lines, theirs_lines, autojunk=False)

    blocks_o = sm_o.get_matching_blocks()  # Match(a=base, b=ours, size)
    blocks_t = sm_t.get_matching_blocks()  # Match(a=base, b=theirs, size)

    # Each matching block defines a base range [a, a+size) matched in the
    # other side. Intersect every (block_o, block_t) pair on the base axis.
    # blocks_o are non-overlapping in base, blocks_t are non-overlapping in
    # base, so the resulting intersections are non-overlapping in base.
    sync: list[tuple[int, int, int, int]] = []
    for a_o, b_o, sz_o in blocks_o:
        if sz_o == 0:
            continue
        for a_t, b_t, sz_t in blocks_t:
            if sz_t == 0:
                continue
            lo = max(a_o, a_t)
            hi = min(a_o + sz_o, a_t + sz_t)
            if lo < hi:
                ours_idx = b_o + (lo - a_o)
                theirs_idx = b_t + (lo - a_t)
                sync.append((lo, hi, ours_idx, theirs_idx))

    sync.sort()
    # Merge adjacent regions whose ours/theirs indices are also continuous.
    merged: list[tuple[int, int, int, int]] = []
    for region in sync:
        if merged:
            prev = merged[-1]
            prev_len = prev[1] - prev[0]
            if (
                region[0] == prev[1]
                and region[2] == prev[2] + prev_len
                and region[3] == prev[3] + prev_len
            ):
                merged[-1] = (prev[0], region[1], prev[2], prev[3])
                continue
        merged.append(region)
    return merged


def _build_chunks(
    base_lines: list[str],
    ours_lines: list[str],
    theirs_lines: list[str],
) -> list[tuple]:
    """沿 sync regions 走一遍，构造合并分块序列。

    Returns:
        分块列表，每个元素是下列二元组之一：

        - ``('stable', lines)`` —— 三方在该区域完全相同。
        - ``('change', base_lines, ours_lines, theirs_lines)`` —— 该区域至少
          有一方发生了改动。

    若某个 sync region 在 ours 或 theirs 维度上需要回退（说明内容被搬到
    别处），则跳过它——与标准 diff3 把移动视为 delete+insert 的行为一致。
    """
    sync_regions = _find_sync_regions(base_lines, ours_lines, theirs_lines)

    chunks: list[tuple] = []
    b_pos = 0
    o_pos = 0
    t_pos = 0

    for sync_start, sync_end, o_start, t_start in sync_regions:
        # Monotonicity: skip sync regions that would rewind ours/theirs.
        if o_start < o_pos or t_start < t_pos or sync_start < b_pos:
            continue
        # Emit a change chunk for the region before this sync point if any
        # side advanced.
        if sync_start > b_pos or o_start > o_pos or t_start > t_pos:
            chunks.append(
                (
                    "change",
                    base_lines[b_pos:sync_start],
                    ours_lines[o_pos:o_start],
                    theirs_lines[t_pos:t_start],
                )
            )
        # Emit the stable region (identical in all three sides).
        chunks.append(("stable", base_lines[sync_start:sync_end]))
        b_pos = sync_end
        o_pos = o_start + (sync_end - sync_start)
        t_pos = t_start + (sync_end - sync_start)

    # Trailing change chunk after the last sync region.
    if b_pos < len(base_lines) or o_pos < len(ours_lines) or t_pos < len(theirs_lines):
        chunks.append(
            (
                "change",
                base_lines[b_pos:],
                ours_lines[o_pos:],
                theirs_lines[t_pos:],
            )
        )

    return chunks


def _ensure_trailing_newline(result: list[str]) -> None:
    """确保 result 中最后一行以 ``\\n`` 结尾，使后续冲突标记独占一行。"""
    if result and not result[-1].endswith("\n"):
        result[-1] = result[-1] + "\n"


def _append_conflict(
    result: list[str],
    ours_c: list[str],
    theirs_c: list[str],
    local_hash_8: str,
    remote_hash_8: str,
    n: int,
) -> None:
    """向 result 追加一个冲突块。

    生成格式（PRD 决策 3）::

        <<<<<<< LP-LOCAL-{local_hash_8} #{n}
        {ours_content}
        =======
        {theirs_content}
        >>>>>>> LP-REMOTE-{remote_hash_8} #{n}

    若 ours_c / theirs_c 末尾无换行，会补一个空行让结束标记独占一行。
    """
    _ensure_trailing_newline(result)
    result.append(f"<<<<<<< LP-LOCAL-{local_hash_8} #{n}\n")
    result.extend(ours_c)
    if ours_c and not ours_c[-1].endswith("\n"):
        result.append("\n")
    result.append("=======\n")
    result.extend(theirs_c)
    if theirs_c and not theirs_c[-1].endswith("\n"):
        result.append("\n")
    result.append(f">>>>>>> LP-REMOTE-{remote_hash_8} #{n}\n")


def merge(
    base: str,
    ours: str,
    theirs: str,
    local_hash_8: str,
    remote_hash_8: str,
) -> dict[str, object]:
    """对 ours 与 theirs 基于 base 执行 3-way merge。

    Args:
        base: 公共祖先内容（parent_hash 对应的文件内容）。
        ours: 本地当前文件内容。
        theirs: 云端当前文件内容。
        local_hash_8: 本地文件 SHA-256 前 8 位（装饰冲突标记 LOCAL 端用）。
        remote_hash_8: 云端文件 SHA-256 前 8 位（装饰冲突标记 REMOTE 端用）。

    Returns:
        dict 含三个字段：

        - ``success`` (bool): 自动合并是否成功（无冲突标记）。
        - ``merged`` (str): 合并后的内容；无冲突时为干净的合并文本，
          有冲突时含冲突标记。**数据永不丢失**——所有冲突场景中 ours 与
          theirs 的内容均完整保留在合并结果或冲突块中。
        - ``conflicts`` (int): 冲突块数量。
    """
    base_lines = _split_lines(base)
    ours_lines = _split_lines(ours)
    theirs_lines = _split_lines(theirs)

    chunks = _build_chunks(base_lines, ours_lines, theirs_lines)

    result: list[str] = []
    conflicts = 0
    for chunk in chunks:
        if chunk[0] == "stable":
            result.extend(chunk[1])
            continue
        _, base_c, ours_c, theirs_c = chunk
        if ours_c == theirs_c:
            # Both sides made the identical change (including both deleting).
            result.extend(ours_c)
        elif ours_c == base_c:
            # Ours unchanged here -> take theirs.
            result.extend(theirs_c)
        elif theirs_c == base_c:
            # Theirs unchanged here -> take ours.
            result.extend(ours_c)
        else:
            conflicts += 1
            _append_conflict(result, ours_c, theirs_c, local_hash_8, remote_hash_8, conflicts)

    merged = "".join(result)
    return {
        "success": conflicts == 0,
        "merged": merged,
        "conflicts": conflicts,
    }
