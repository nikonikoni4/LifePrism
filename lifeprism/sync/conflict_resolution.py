"""文件冲突解决端到端流程（Issue 4）

实现 diff3 + LLM 串行 + 重试降级的完整冲突解决流程：
1. ``build_start_marker`` / ``build_end_marker`` —— 冲突标记构建
2. ``compute_hash_8`` —— 文件 SHA-256 前 8 位（装饰冲突标记用）
3. ``parse_conflict_blocks`` —— 扫描合并文本提取所有冲突块
4. ``match_markers`` —— 程序精确/模糊匹配 marker 字符串
5. ``parse_llm_json_response`` —— 解析 LLM 输出 JSON（json_repair 容错）
6. ``expand_conflict_context`` —— 扩展冲突块上下文（前 20~30 行 + 冲突块 + 后 20~30 行）
7. ``resolve_conflict_blocks`` —— 串行处理冲突块（重试 + 降级 keep_ours）

设计原则：
- LLM 降级为"内容建议者"：只输出 JSON 替换指令，不持有文件工具
- 程序升级为"决策执行者"：验证 marker + 执行替换 + 处理重试降级
- 数据永不丢失：所有冲突场景 ours/theirs 内容均完整保留
- 串行处理（理解 B）：一个冲突一次 LLM 调用，基于更新后的文件继续

冲突标记格式（PRD 决策 3 / ADR-1 决策 3）::

    <<<<<<< LP-LOCAL-{file_hash_8} #{n}
    {ours_content}
    =======
    {theirs_content}
    >>>>>>> LP-REMOTE-{remote_file_hash_8} #{n}

LLM 输出 JSON 格式（PRD 决策 4）::

    {
      "conflict_id": 1,
      "start_marker": "<<<<<<< LP-LOCAL-a3f8b2c1 #1",
      "end_marker": ">>>>>>> LP-REMOTE-7e9d4f2b #1",
      "replacement": "合并后的内容"
    }

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-4-conflict-resolution-end-to-end.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 3-6、10、11
- ADR: docs/adr/2026-07-17-conflict-resolution-diff3-replaces-llm.md 决策 3-7
- ADR: docs/adr/2026-07-17-conflict-failure-policy.md（失败降级策略）
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

from lifeprism.sync.hash_utils import compute_file_hash
from lifeprism.utils import get_logger

logger = get_logger(__name__)


# ==================== 数据结构 ====================


@dataclass
class ConflictBlock:
    """单个冲突块的结构化信息

    Attributes:
        conflict_id: 冲突块序号（1..N，文件内唯一）
        start_marker: 起始标记字符串（如 ``<<<<<<< LP-LOCAL-a3f8b2c1 #1``）
        end_marker: 结束标记字符串（如 ``>>>>>>> LP-REMOTE-7e9d4f2b #1``）
        ours_content: 本地版本内容（原样保留）
        theirs_content: 云端版本内容（原样保留）
        start_line: 起始标记所在行号（0-based）
        end_line: 结束标记所在行号（0-based）
    """

    conflict_id: int
    start_marker: str
    end_marker: str
    ours_content: str
    theirs_content: str
    start_line: int
    end_line: int


@dataclass
class ResolveResult:
    """冲突解决结果

    Attributes:
        final_content: 最终合并后的文件内容
        resolved_count: 成功替换的冲突块数
        failed_count: 失败降级的冲突块数
        failed_blocks: 失败的冲突块 conflict_id 列表
    """

    final_content: str
    resolved_count: int = 0
    failed_count: int = 0
    failed_blocks: list[int] = field(default_factory=list)


# ==================== 冲突标记构建 ====================


def build_start_marker(local_hash_8: str, n: int) -> str:
    """构建冲突块起始标记

    Args:
        local_hash_8: 本地文件 SHA-256 前 8 位
        n: 冲突块序号（1-based）

    Returns:
        起始标记字符串，如 ``<<<<<<< LP-LOCAL-a3f8b2c1 #1``
    """
    return f"<<<<<<< LP-LOCAL-{local_hash_8} #{n}"


def build_end_marker(remote_hash_8: str, n: int) -> str:
    """构建冲突块结束标记

    Args:
        remote_hash_8: 云端文件 SHA-256 前 8 位
        n: 冲突块序号（1-based）

    Returns:
        结束标记字符串，如 ``>>>>>>> LP-REMOTE-7e9d4f2b #1``
    """
    return f">>>>>>> LP-REMOTE-{remote_hash_8} #{n}"


def compute_hash_8(content: str) -> str:
    """计算文件内容的 SHA-256 前 8 位（装饰冲突标记用）

    复用 ``lifeprism.sync.hash_utils.compute_file_hash`` 的规范化逻辑
    （行尾统一 + trailing 空白去除），仅截取前 8 位作为冲突标记装饰。

    Args:
        content: 文件内容字符串

    Returns:
        8 字符的 hex 字符串
    """
    return compute_file_hash(content.encode("utf-8"))[:8]


# ==================== 冲突块解析 ====================


# 起始标记正则：<<<<<<< LP-LOCAL-{8 hex chars} #{n}
_START_MARKER_PATTERN = re.compile(r"^<<<<<<< LP-LOCAL-([0-9a-f]{8}) #(\d+)$")
# 结束标记正则：>>>>>>> LP-REMOTE-{8 hex chars} #{n}
_END_MARKER_PATTERN = re.compile(r"^>>>>>>> LP-REMOTE-([0-9a-f]{8}) #(\d+)$")
# 分隔符正则：=======
_SEPARATOR_PATTERN = re.compile(r"^=======$")


def parse_conflict_blocks(merged: str) -> list[ConflictBlock]:
    """扫描合并文本提取所有冲突块

    按 diff3 输出的冲突标记格式扫描，返回结构化 ConflictBlock 列表。
    序号 #{n} 在文件内唯一（递增 1..N），是程序匹配的真正锚点。

    Args:
        merged: 含冲突标记的合并文本

    Returns:
        ConflictBlock 列表，按出现顺序排列；无冲突时返回空列表
    """
    if not merged:
        return []

    lines = merged.split("\n")
    blocks: list[ConflictBlock] = []
    i = 0
    n_lines = len(lines)

    while i < n_lines:
        line = lines[i]
        start_match = _START_MARKER_PATTERN.match(line)
        if not start_match:
            i += 1
            continue

        # 解析起始标记（local_hash_8 仅用于日志，此处不使用）
        conflict_id = int(start_match.group(2))
        start_marker = line
        start_line = i

        # 收集 ours 内容（直到 =======）
        ours_lines: list[str] = []
        i += 1
        separator_found = False
        while i < n_lines:
            if _SEPARATOR_PATTERN.match(lines[i]):
                separator_found = True
                break
            ours_lines.append(lines[i])
            i += 1

        if not separator_found:
            # 格式错误：缺少 ======= 分隔符，跳过此标记
            logger.warning(
                "parse_conflict_blocks: 冲突块 %d 缺少 ======= 分隔符，跳过",
                conflict_id,
            )
            i += 1
            continue

        # 收集 theirs 内容（直到 >>>>>>>）
        theirs_lines: list[str] = []
        i += 1  # 跳过 =======
        end_found = False
        end_marker = None
        end_line = -1
        while i < n_lines:
            end_match = _END_MARKER_PATTERN.match(lines[i])
            if end_match:
                end_marker = lines[i]
                end_line = i
                end_found = True
                break
            theirs_lines.append(lines[i])
            i += 1

        if not end_found:
            # 格式错误：缺少结束标记，跳过
            logger.warning(
                "parse_conflict_blocks: 冲突块 %d 缺少结束标记，跳过",
                conflict_id,
            )
            i += 1
            continue

        # 恢复 ours/theirs 内容（join 后补 \n，保持原样）
        # 注意：split("\n") 会丢失末尾换行信息，需根据原始文本恢复
        # 但对于冲突块内的内容，diff3 输出时每行都以 \n 结尾，
        # 所以 join("\n") + "\n" 是合理的恢复方式（仅当内容非空时）
        ours_content = "\n".join(ours_lines)
        theirs_content = "\n".join(theirs_lines)
        if ours_lines:
            ours_content += "\n"
        if theirs_lines:
            theirs_content += "\n"

        blocks.append(
            ConflictBlock(
                conflict_id=conflict_id,
                start_marker=start_marker,
                end_marker=end_marker,
                ours_content=ours_content,
                theirs_content=theirs_content,
                start_line=start_line,
                end_line=end_line,
            )
        )
        i += 1  # 跳过结束标记

    return blocks


# ==================== Marker 匹配 ====================


def _normalize_marker(marker: str) -> str:
    """将 marker 字符串中的空白字符规范化（去除所有空白）

    用于模糊匹配：LLM 输出的 marker 可能含额外空格（如 ``LP-LOCAL-  a3f8b2c1``），
    规范化后（去除所有空白）与文件行同样规范化后比较，容忍空格数量变化。

    采用"去除所有空白"策略而非"压缩为单空格"：因为 LLM 可能在不该有空格的地方
    插入空格（如 ``LP-LOCAL-  a3f8b2c1``），文件中却是 ``LP-LOCAL-a3f8b2c1``
    （无空格）。去除所有空白后两者一致。

    Args:
        marker: 原始 marker 字符串

    Returns:
        规范化后的 marker 字符串（无任何空白字符）
    """
    return re.sub(r"\s+", "", marker)


def match_markers(
    file_content: str,
    start_marker: str,
    end_marker: str,
) -> tuple[int, int] | None:
    """在文件内容中匹配 start_marker + end_marker

    匹配逻辑（PRD 决策 4 / 用户故事 12）：
    1. 优先精确匹配：在文件行中查找完全相同的 start_marker 和 end_marker
    2. 失败时尝试模糊匹配：去除所有空白后比较（容忍空格数量变化）
    3. 都失败返回 None（触发重试）

    匹配要求：start_marker 在 end_marker 之前出现，且 end_marker 在 start_marker 之后。

    Args:
        file_content: 文件内容字符串
        start_marker: 起始标记字符串
        end_marker: 结束标记字符串

    Returns:
        (start_line, end_line) 元组（0-based）；匹配失败返回 None
    """
    if not file_content:
        return None

    lines = file_content.split("\n")

    # 1. 精确匹配
    start_line = None
    end_line = None
    for i, line in enumerate(lines):
        if start_line is None and line == start_marker:
            start_line = i
        elif start_line is not None and line == end_marker:
            end_line = i
            break

    if start_line is not None and end_line is not None and end_line > start_line:
        return (start_line, end_line)

    # 2. 模糊匹配（去除所有空白后比较，容忍空格数量变化）
    norm_start = _normalize_marker(start_marker)
    norm_end = _normalize_marker(end_marker)

    start_line = None
    end_line = None
    for i, line in enumerate(lines):
        norm_line = _normalize_marker(line)
        if start_line is None and norm_line == norm_start:
            start_line = i
        elif start_line is not None and norm_line == norm_end:
            end_line = i
            break

    if start_line is not None and end_line is not None and end_line > start_line:
        return (start_line, end_line)

    return None


# ==================== LLM JSON 解析 ====================


def parse_llm_json_response(raw: str) -> dict | None:
    """解析 LLM 返回的 JSON 字符串

    使用 ``json_repair`` 容错解析（处理多余逗号、单引号、markdown code fence 等）。
    校验必需字段：conflict_id（int）、start_marker（str）、end_marker（str）、replacement（str）。

    Args:
        raw: LLM 返回的原始字符串

    Returns:
        解析后的 dict（含 conflict_id, start_marker, end_marker, replacement）；
        解析失败或字段缺失/类型错误返回 None
    """
    if not raw or not raw.strip():
        return None

    # 剥离 markdown code fence（```json ... ``` 或 ``` ... ```）
    text = raw.strip()
    if text.startswith("```"):
        # 移除首行（```json 或 ```）
        lines = text.split("\n")
        if len(lines) >= 2:
            # 移除首行
            lines = lines[1:]
            # 移除末尾 ```（如果存在）
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)

    try:
        from json_repair import repair_json

        # repair_json 返回 dict 或 list；loads 后校验
        repaired = repair_json(text, return_objects=True)
    except Exception as e:
        # LEGITIMATE: json_repair 第三方库容错，解析失败时返回 None 触发重试
        logger.warning("json_repair 解析失败，返回 None: %s", e, exc_info=True)
        return None

    if not isinstance(repaired, dict):
        return None

    # 校验必需字段
    required_fields = ["conflict_id", "start_marker", "end_marker", "replacement"]
    for field_name in required_fields:
        if field_name not in repaired:
            return None

    # 类型校验
    conflict_id = repaired["conflict_id"]
    start_marker = repaired["start_marker"]
    end_marker = repaired["end_marker"]
    replacement = repaired["replacement"]

    # conflict_id 应为 int（或可转 int 的字符串/float）
    if isinstance(conflict_id, bool):
        return None  # bool 是 int 的子类，但不应被接受
    if isinstance(conflict_id, str):
        try:
            conflict_id = int(conflict_id)
        except ValueError:
            return None
    elif isinstance(conflict_id, float):
        if not conflict_id.is_integer():
            return None
        conflict_id = int(conflict_id)
    elif not isinstance(conflict_id, int):
        return None

    # start_marker / end_marker 应为 str
    if not isinstance(start_marker, str) or not isinstance(end_marker, str):
        return None

    # replacement 应为 str
    if not isinstance(replacement, str):
        return None

    return {
        "conflict_id": conflict_id,
        "start_marker": start_marker,
        "end_marker": end_marker,
        "replacement": replacement,
    }


# ==================== 上下文扩展 ====================


def expand_conflict_context(
    file_content: str,
    start_line: int,
    end_line: int,
    context_lines: int = 25,
) -> str:
    """扩展冲突块上下文

    PRD 决策 11 / 用户故事 16：
    - 整块冲突上下文 = 冲突标记前 20~30 行 + 完整冲突块 + 冲突标记后 20~30 行
    - 到文件边界则取消该侧扩展
    - 整块作为一个参数 {conflict_block_with_context} 提供

    Args:
        file_content: 文件内容字符串
        start_line: 冲突块起始标记行号（0-based）
        end_line: 冲突块结束标记行号（0-based）
        context_lines: 上下文扩展行数（默认 25，在 20~30 范围内）

    Returns:
        整块冲突上下文字符串（含前扩展 + 冲突块 + 后扩展）
    """
    if not file_content:
        return ""

    lines = file_content.split("\n")
    n_lines = len(lines)

    # 前扩展：start_line 之前 context_lines 行
    before_start = max(0, start_line - context_lines)
    before_lines = lines[before_start:start_line]

    # 冲突块本身（含 start_line 到 end_line，闭区间）
    conflict_lines = lines[start_line : end_line + 1]

    # 后扩展：end_line 之后 context_lines 行
    after_end = min(n_lines, end_line + 1 + context_lines)
    after_lines = lines[end_line + 1 : after_end]

    # 拼接（用 \n 连接，与原文件行尾风格一致）
    all_lines = before_lines + conflict_lines + after_lines
    return "\n".join(all_lines)


# ==================== 串行冲突解决（重试 + 降级） ====================


def _execute_replacement(
    file_content: str, start_line: int, end_line: int, replacement: str
) -> str:
    """执行替换：将 file_content 中 [start_line, end_line] 行替换为 replacement

    语义说明：替换"含 start_marker 到 end_marker（含标记本身）的整块内容"。
    当 end_marker 是文件最后一行且原文件以 ``\\n`` 结尾时，
    ``split("\\n")`` 会在末尾产生空字符串 ``""``，此时若 replacement 非空，
    应丢弃该空字符串，让 replacement 自身决定末尾换行形式
    （避免 ``"\\n".join(["merged content", ""])`` 强制添加 ``\\n``）。

    Args:
        file_content: 原始文件内容
        start_line: 起始行号（0-based，含）
        end_line: 结束行号（0-based，含）
        replacement: 替换文本

    Returns:
        替换后的文件内容
    """
    lines = file_content.split("\n")
    before = lines[:start_line]
    after = lines[end_line + 1 :]

    # replacement 可能不含末尾换行，需保持行结构一致
    replacement_lines = replacement.split("\n") if replacement else []

    # 处理原文件末尾换行：当 end_marker 是文件最后一行且原文件以 \n 结尾时，
    # after 会是 [""]（来自 split 末尾空字符串）。
    # 若 replacement 非空，丢弃该空字符串，让 replacement 自身决定末尾形式；
    # 若 replacement 为空（删除冲突块），保留 [""] 以维持原文件末尾换行。
    if replacement_lines and after == [""]:
        after = []

    new_lines = before + replacement_lines + after
    return "\n".join(new_lines)


def resolve_conflict_blocks(
    file_content: str,
    conflict_blocks: list[ConflictBlock],
    llm_caller: Callable[[str], str],
    max_retries: int = 3,
) -> ResolveResult:
    """串行处理冲突块（重试 + 降级）

    PRD 决策 5 / 用户故事 11：
    - 程序按"理解 B"串行处理：一个冲突一次 LLM 调用，处理完一个再处理下一个
    - 每个冲突块基于更新后的文件继续（行号变化不是问题，marker 字符串匹配）

    PRD 决策 6 / 用户故事 12-14：
    - 重试机制：最多 max_retries 次
    - 重试触发条件：JSON 解析失败 / marker 不匹配
    - 重试失败 → 当前冲突块降级 keep_ours（保留本地版本）+ WARNING 日志
    - 单个冲突块失败不中断整个文件处理

    Args:
        file_content: 原始合并文本（含冲突标记）
        conflict_blocks: 冲突块列表
        llm_caller: LLM 调用回调（接收 prompt 字符串，返回 LLM 响应字符串）
        max_retries: 最大重试次数（默认 3）

    Returns:
        ResolveResult：最终内容 + 成功/失败统计
    """
    if not conflict_blocks:
        return ResolveResult(final_content=file_content)

    current_content = file_content
    resolved_count = 0
    failed_count = 0
    failed_blocks: list[int] = []
    total_conflicts = len(conflict_blocks)

    for block in conflict_blocks:
        success = False
        for attempt in range(1, max_retries + 1):
            # 重新定位当前冲突块（基于更新后的文件）
            match_result = match_markers(
                file_content=current_content,
                start_marker=block.start_marker,
                end_marker=block.end_marker,
            )
            if match_result is None:
                # marker 在文件中找不到（可能被前一个替换破坏）
                logger.warning(
                    "resolve_conflict_blocks: 冲突块 %d marker 不在文件中（attempt=%d/%d）",
                    block.conflict_id,
                    attempt,
                    max_retries,
                )
                # 尝试调用 LLM 让它返回正确 marker（但仍可能失败）
                # 此处继续走 LLM 流程，由 LLM 输出的 marker 重新匹配

            # 构建 prompt（基于当前文件内容）
            # 如果 marker 找不到，使用 block 中记录的原始位置构建上下文
            if match_result is not None:
                start_line, end_line = match_result
                # 更新 block 的行号信息用于上下文扩展
                prompt = _build_resolve_prompt_with_lines(
                    conflict_block=block,
                    file_content=current_content,
                    start_line=start_line,
                    end_line=end_line,
                    total_conflicts=total_conflicts,
                )
            else:
                # marker 找不到，使用 block 中原始行号（可能已过期）
                prompt = _build_resolve_prompt_with_lines(
                    conflict_block=block,
                    file_content=current_content,
                    start_line=block.start_line,
                    end_line=block.end_line,
                    total_conflicts=total_conflicts,
                )

            # 调用 LLM
            try:
                raw_response = llm_caller(prompt)
            except Exception as e:
                # LEGITIMATE: LLM 调用属于第三方服务边界，异常类型不可预测
                logger.warning(
                    "resolve_conflict_blocks: 冲突块 %d LLM 调用异常（attempt=%d/%d, error=%s）",
                    block.conflict_id,
                    attempt,
                    max_retries,
                    e,
                    exc_info=True,
                )
                continue

            # 解析 JSON
            parsed = parse_llm_json_response(raw_response)
            if parsed is None:
                logger.warning(
                    "resolve_conflict_blocks: 冲突块 %d JSON 解析失败（attempt=%d/%d）",
                    block.conflict_id,
                    attempt,
                    max_retries,
                )
                continue

            # 用 LLM 返回的 marker 重新匹配（LLM 应返回原始 marker）
            llm_match = match_markers(
                file_content=current_content,
                start_marker=parsed["start_marker"],
                end_marker=parsed["end_marker"],
            )
            if llm_match is None:
                logger.warning(
                    "resolve_conflict_blocks: 冲突块 %d LLM 返回的 marker 不匹配（attempt=%d/%d）",
                    block.conflict_id,
                    attempt,
                    max_retries,
                )
                continue

            # 执行替换
            start_line, end_line = llm_match
            current_content = _execute_replacement(
                file_content=current_content,
                start_line=start_line,
                end_line=end_line,
                replacement=parsed["replacement"],
            )
            success = True
            logger.debug(
                "resolve_conflict_blocks: 冲突块 %d 替换成功（attempt=%d/%d）",
                block.conflict_id,
                attempt,
                max_retries,
            )
            break

        if success:
            resolved_count += 1
        else:
            # 降级 keep_ours：将冲突块替换为 ours 内容
            # 重新定位 marker（使用 block 中原始 marker）
            match_result = match_markers(
                file_content=current_content,
                start_marker=block.start_marker,
                end_marker=block.end_marker,
            )
            if match_result is not None:
                start_line, end_line = match_result
                current_content = _execute_replacement(
                    file_content=current_content,
                    start_line=start_line,
                    end_line=end_line,
                    replacement=block.ours_content.rstrip("\n"),
                )
                logger.warning(
                    "resolve_conflict_blocks: 冲突块 %d 重试 %d 次失败，降级 keep_ours",
                    block.conflict_id,
                    max_retries,
                )
            else:
                # marker 找不到，无法降级替换，保留原样（含冲突标记）
                logger.error(
                    "resolve_conflict_blocks: 冲突块 %d 降级失败（marker 不在文件中），"
                    "保留原始冲突标记",
                    block.conflict_id,
                )
            failed_count += 1
            failed_blocks.append(block.conflict_id)

    logger.info(
        "resolve_conflict_blocks: 串行处理完成，成功=%d, 失败=%d, 总计=%d",
        resolved_count,
        failed_count,
        total_conflicts,
    )

    return ResolveResult(
        final_content=current_content,
        resolved_count=resolved_count,
        failed_count=failed_count,
        failed_blocks=failed_blocks,
    )


def _build_resolve_prompt_with_lines(
    conflict_block: ConflictBlock,
    file_content: str,
    start_line: int,
    end_line: int,
    total_conflicts: int,
    context_lines: int = 25,
) -> str:
    """构建冲突解决 prompt（基于精确行号）

    辅助函数：使用匹配到的精确行号扩展上下文，构建 prompt。

    Args:
        conflict_block: 当前冲突块
        file_content: 当前文件内容
        start_line: 起始标记行号（0-based）
        end_line: 结束标记行号（0-based）
        total_conflicts: 冲突块总数
        context_lines: 上下文扩展行数

    Returns:
        填充后的 prompt 字符串
    """
    # 扩展上下文
    context = expand_conflict_context(
        file_content=file_content,
        start_line=start_line,
        end_line=end_line,
        context_lines=context_lines,
    )

    # 尝试使用 PromptLoader 加载模板
    try:
        from lifeprism.llm.prompts.prompt_loader import PromptLoader, Prompts

        loader = PromptLoader()
        return loader.load_prompt(
            Prompts.Conflict.RESOLVE_CONFLICT,
            conflict_id=conflict_block.conflict_id,
            total_conflicts=total_conflicts,
            conflict_block_with_context=context,
        )
    except Exception as e:
        # LEGITIMATE: 辅助操作兜底，prompt 加载失败不影响主流程
        logger.warning("PromptLoader 加载失败，使用 fallback: %s", e, exc_info=True)
        return (
            f"## 文件冲突需要解决\n\n"
            f"当前是第 {conflict_block.conflict_id} 个冲突"
            f"（共 {total_conflicts} 个）。\n\n"
            f"### 整块冲突上下文\n\n```\n{context}\n```\n\n"
            f"### 输出要求\n\n"
            f"输出严格 JSON，包含字段：\n"
            f"- conflict_id: {conflict_block.conflict_id}\n"
            f"- start_marker: 精确复制上下文中的 <<<<<<< 行\n"
            f"- end_marker: 精确复制上下文中的 >>>>>>> 行\n"
            f"- replacement: 合并后的替换文本\n"
        )
