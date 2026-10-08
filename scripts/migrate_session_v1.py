"""旧版 session jsonl 迁移到 myagent 新格式。

背景
----
旧格式由 ``lifeprism.llm.session.manager.Session`` 写出：

* 首行 ``{"_type": "metadata", name, created_at, updated_at, last_compacted_loc, ...}``
  （没有 session_id，id 取自文件名）
* 后续每行是一条裸 message dict：``{"role", "content", "timestamp", ...}``；
  assistant 带 ``tool_calls``（OpenAI wire 格式）与 ``reasoning_content``，
  tool 带 ``tool_call_id``，压缩总结是 ``is_compact_summary=true`` 的 user 消息。

新格式由 ``myagent.agent.core.session`` 写出：

* 首行 ``SessionMetaData.meta_data()``
* 后续每行一条 ``SessionRecordData.to_record_dict()`` 事件记录

迁移只保证关键消息不丢：user message、assistant message、tool call、tool result。
旧格式没有的字段（usage、request/header 快照、流式 chunk）一律不伪造——留空后由
运行时在下次请求时自行补写。两条硬约束来自新格式的读取侧实现：

1. ``Session.derive_messages()`` 只认 ``surface_op="append"`` 的记录，故
   user/message、assistant/message、tool/result 打 ``append``，tool/call 留 None。
2. ``seq`` 必须 1..N 连续，因为 ``derive_messages`` 用 ``record_list[seq - 1]`` 取记录。

用法
----
    python scripts/migrate_session_v1.py \\
        --src    localData/session \\
        --backup localData/backups/session_v0 \\
        --out    localData/session/chat

只扫描 ``--src`` 根目录下的 ``*.jsonl``，不递归子目录。每个文件先复制到
``--backup``，迁移写盘成功后才从 ``--src`` 移除（迁移语义）。加 ``--keep-source``
只备份不移除；加 ``--dry-run`` 只解析和报告，不写盘、不备份、不移除。

Args:
    --src: 旧 session 所在目录，只读根目录一层。
    --backup: 旧文件备份目录。
    --out: 迁移后新文件的输出目录。
    --keep-source: 保留源文件，只备份不移除。
    --dry-run: 只解析和报告，不产生任何磁盘写入。

Raises:
    SystemExit: 目录不存在或参数非法时以非零码退出。
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import shutil
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from myagent.agent.core.provider import Message, RawToolCall, Usage  # noqa: E402
from myagent.agent.core.session.session import Session  # noqa: E402
from myagent.agent.core.session.types import (  # noqa: E402
    AssistantMessageData,
    SessionData,
    SessionMetaData,
    SessionRecordData,
    StepEndData,
    StepStartData,
    ToolCallData,
    ToolResultData,
    TurnEndData,
    TurnStartData,
    UserMessageData,
)

logger = logging.getLogger("migrate_session_v1")


def _parse_old_file(path: Path) -> tuple[dict, list[dict]]:
    """读取旧版 session 文件。

    Args:
        path: 旧版 jsonl 文件路径。

    Returns:
        ``(metadata dict, message dict 列表)`` 二元组。

    Raises:
        ValueError: 文件为空，或首行不是 ``_type=metadata`` 的旧版元信息。
        json.JSONDecodeError: 某一行不是合法 JSON。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("文件为空")
    meta = json.loads(lines[0])
    if meta.get("_type") != "metadata":
        raise ValueError(f"首行不是旧版 metadata（_type={meta.get('_type')!r}）")
    messages = [json.loads(line) for line in lines[1:] if line.strip()]
    return meta, messages


def _parse_utc(raw: str | None) -> datetime.datetime | None:
    """解析旧文件时间戳。

    旧代码用 ``datetime.now(UTC).isoformat()`` 写盘，但历史上也存在 naive 字符串，
    这里统一按 UTC 补齐时区（与 ``lifeprism.llm.session.manager`` 的兼容做法一致）。

    Args:
        raw: ISO 8601 时间字符串，None 或空串返回 None。

    Returns:
        带时区的 datetime；输入为空时返回 None。
    """
    if not raw:
        return None
    parsed = datetime.datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.UTC)
    return parsed


def _to_raw_tool_calls(raw: list[dict] | None) -> list[RawToolCall] | None:
    """把旧格式的 tool_calls 转成 ``RawToolCall`` 列表。

    旧格式是 OpenAI wire 形态 ``{"id", "type", "function": {"name", "arguments"}}``，
    新格式的 ``RawToolCall`` 是扁平结构。arguments 走 ``from_wire`` 解析，与运行时
    产出路径保持同一套规则。

    Args:
        raw: 旧格式的 tool_calls 列表，None 或空列表返回 None。

    Returns:
        ``RawToolCall`` 列表；无有效调用时返回 None。
    """
    if not raw:
        return None
    calls: list[RawToolCall] = []
    for item in raw:
        function = item.get("function") or {}
        call_id = item.get("id") or ""
        name = function.get("name") or ""
        if not call_id or not name:
            logger.warning(
                "tool_call 缺少 id 或 name，已跳过: %s",
                json.dumps(item, ensure_ascii=False)[:200],
            )
            continue
        calls.append(
            RawToolCall.from_wire(id=call_id, name=name, raw_arguments=function.get("arguments"))
        )
    return calls or None


def _build_records(messages: list[dict]) -> list[SessionRecordData]:
    """把旧格式的 message 序列折叠成新格式的事件记录序列。

    折叠规则：一条 user 消息开启一轮（turn）；轮内每出现一条 assistant 消息就开启
    一步（step），该步的 tool 消息跟在它后面；下一条 assistant 消息开启新的一步。
    这正好对应新格式里 "一步 = 一次 LLM 调用 + 执行其请求的工具" 的定义。

    Args:
        messages: 旧格式 message dict 列表，需已按压缩位置裁剪。

    Returns:
        ``SessionRecordData`` 列表，seq 从 1 连续递增。
    """
    records: list[SessionRecordData] = []
    seq = 0
    turn = 0
    step = 0
    turn_open = False
    step_open = False
    step_has_assistant = False
    # 边界事件（turn/start、step/end 等）没有自己的旧时间戳，沿用最近一条消息的时间，
    # 保证整条时间轴单调、且会话的 updated_at 不会因为迁移而被顶到"刚刚"
    last_ts: datetime.datetime | None = None
    # call_id -> tool_name：旧格式的 tool 消息不记工具名，靠前面的 tool/call 反查
    tool_names: dict[str, str] = {}

    def emit(
        event_type: str,
        data: SessionData,
        surface_op: str | None = None,
        timestamp: datetime.datetime | None = None,
    ) -> None:
        nonlocal seq, last_ts
        seq += 1
        stamp = timestamp or last_ts or datetime.datetime.now(datetime.UTC)
        last_ts = stamp
        records.append(
            SessionRecordData(
                type=event_type,
                seq=seq,
                turn=turn,
                step=None if event_type in Session.NO_STEP_EVENTS else step,
                surface_op=surface_op,
                data=data,
                timestamp=stamp,
            )
        )

    def close_step() -> None:
        nonlocal step_open
        if step_open:
            emit("step/end", StepEndData(reason_type="success", reason_text=""))
            step_open = False

    def close_turn() -> None:
        nonlocal turn_open
        if turn_open:
            close_step()
            emit("turn/end", TurnEndData(reason_type="success", reason_text="", error_type=""))
            turn_open = False

    def open_turn(timestamp: datetime.datetime | None) -> None:
        nonlocal turn, step, turn_open
        turn += 1
        step = 0
        turn_open = True
        emit("turn/start", TurnStartData(), timestamp=timestamp)

    def open_step(timestamp: datetime.datetime | None) -> None:
        nonlocal step, step_open, step_has_assistant
        step += 1
        step_open = True
        step_has_assistant = False
        emit("step/start", StepStartData(), timestamp=timestamp)

    def text_of(message: dict) -> str | list:
        """取出 content；旧数据里 None 统一落成空串，避免下游 to_dict 报空内容。"""
        content = message.get("content")
        return "" if content is None else content

    for message in messages:
        role = message.get("role")
        ts = _parse_utc(message.get("timestamp"))
        if role == "user":
            close_turn()
            open_turn(ts)
            open_step(ts)
            emit(
                "user/message",
                UserMessageData(message=Message(role="user", content=text_of(message))),
                surface_op="append",
                timestamp=ts,
            )
        elif role == "assistant":
            # 防御：旧文件理论上不会出现"首条即 assistant"，出现时补一个空轮兜住
            if not turn_open:
                open_turn(ts)
            if step_open and step_has_assistant:
                close_step()
            if not step_open:
                open_step(ts)
            tool_calls = _to_raw_tool_calls(message.get("tool_calls"))
            emit(
                "assistant/message",
                AssistantMessageData(
                    message=Message(
                        role="assistant",
                        content=text_of(message),
                        tool_calls=tool_calls,
                        reasoning_content=message.get("reasoning_content"),
                    ),
                    usage=Usage(),
                ),
                surface_op="append",
                timestamp=ts,
            )
            step_has_assistant = True
            for call in tool_calls or []:
                tool_names[call.id] = call.name
                emit(
                    "tool/call",
                    ToolCallData(call_id=call.id, tool_name=call.name, arguments=call.raw_arguments),
                    timestamp=ts,
                )
        elif role == "tool":
            if not turn_open:
                open_turn(ts)
            if not step_open:
                open_step(ts)
            call_id = message.get("tool_call_id") or ""
            emit(
                "tool/result",
                ToolResultData(
                    call_id=call_id,
                    tool_name=tool_names.get(call_id, ""),
                    message=Message(role="tool", content=text_of(message), tool_call_id=call_id),
                ),
                surface_op="append",
                timestamp=ts,
            )
        else:
            logger.warning("跳过不支持的 role=%r", role)

    close_turn()
    return records


def _build_meta(session_id: str, meta: dict) -> SessionMetaData:
    """由旧版 metadata 构造新格式的 ``SessionMetaData``。

    cwd 旧格式没有记录，留空串（新格式的 ``SessionStore.load`` 同样把 cwd 还原为空串）。
    extra 留空 dict，由运行时按需写入 ``last_processed_turn`` 等业务游标。

    Args:
        session_id: 取自文件名的会话 id。
        meta: 旧版首行 metadata dict。

    Returns:
        新格式元信息实例。
    """
    return SessionMetaData(
        cwd="",
        session_id=session_id,
        name=meta.get("name") or session_id,
        created_at=_parse_utc(meta.get("created_at")) or datetime.datetime.now(datetime.UTC),
        updated_at=_parse_utc(meta.get("updated_at")),
        parent_session_id=None,
        extra={},
    )


def _migrate_one(path: Path, out_dir: Path, *, keep_source: bool, backup_dir: Path) -> dict:
    """迁移单个文件：备份 → 转格式 → 写盘 → （可选）移除源文件。

    Args:
        path: 旧版 jsonl 文件路径。
        out_dir: 新格式文件输出目录。
        keep_source: True 时保留源文件，只备份不移除。
        backup_dir: 旧文件备份目录。

    Returns:
        本次迁移的统计 dict：``session_id`` / ``messages`` / ``records`` / ``compacted``。

    Raises:
        ValueError: 文件格式不是旧版 session。
    """
    session_id = path.stem
    meta, messages = _parse_old_file(path)

    # 压缩语义：last_compacted_loc 之前的消息已被摘要替换，直接全迁会重复历史，
    # 故从该位置开始（该位置本身是压缩总结消息，保留）。
    compacted_loc = int(meta.get("last_compacted_loc") or 0)
    if compacted_loc < 0:
        compacted_loc = 0
    kept = messages[compacted_loc:]

    records = _build_records(kept)
    new_meta = _build_meta(session_id, meta)

    lines = [json.dumps(new_meta.meta_data(), ensure_ascii=False)]
    lines.extend(json.dumps(record.to_record_dict(), ensure_ascii=False) for record in records)

    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup_dir / path.name)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{session_id}.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")

    if not keep_source:
        path.unlink()

    return {
        "session_id": session_id,
        "messages": len(kept),
        "records": len(records),
        "compacted": compacted_loc,
    }


def _build_parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(
        description="把旧版 session jsonl 迁移到 myagent 新格式",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--src", required=True, type=Path, help="旧 session 目录，只扫根目录一层")
    parser.add_argument("--backup", required=True, type=Path, help="旧文件备份目录")
    parser.add_argument("--out", required=True, type=Path, help="新格式文件输出目录")
    parser.add_argument("--keep-source", action="store_true", help="保留源文件，只备份不移除")
    parser.add_argument("--dry-run", action="store_true", help="只解析和报告，不写盘")
    return parser


def main(argv: list[str] | None = None) -> int:
    """脚本入口。

    Args:
        argv: 命令行参数，None 时取 ``sys.argv[1:]``。

    Returns:
        进程退出码，0 表示全部成功，1 表示存在失败文件。
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)

    src: Path = args.src
    if not src.is_dir():
        logger.error("源目录不存在: %s", src)
        return 1

    files = sorted(p for p in src.glob("*.jsonl") if p.is_file())
    if not files:
        logger.warning("源目录下没有 *.jsonl: %s", src)
        return 0

    logger.info("发现 %d 个旧 session 文件: %s", len(files), src)
    failed = 0
    total_records = 0
    for path in files:
        try:
            if args.dry_run:
                meta, messages = _parse_old_file(path)
                compacted_loc = int(meta.get("last_compacted_loc") or 0)
                records = _build_records(messages[compacted_loc:])
                total_records += len(records)
                logger.info(
                    "[dry-run] %s: 消息 %d(裁剪 %d) -> 记录 %d",
                    path.stem, len(messages) - compacted_loc, compacted_loc, len(records),
                )
                continue
            stat = _migrate_one(
                path, args.out, keep_source=args.keep_source, backup_dir=args.backup
            )
            total_records += stat["records"]
            logger.info(
                "%s: 消息 %d(裁剪 %d) -> 记录 %d",
                stat["session_id"], stat["messages"], stat["compacted"], stat["records"],
            )
        except (ValueError, json.JSONDecodeError) as exc:
            failed += 1
            logger.error("迁移失败 %s: %s", path.name, exc)

    if args.dry_run:
        logger.info("[dry-run] 共 %d 个文件，%d 条记录，未产生任何磁盘写入", len(files), total_records)
    else:
        logger.info("完成: %d 个文件，%d 条记录，失败 %d 个", len(files), total_records, failed)
        logger.info("备份目录: %s", args.backup)
        logger.info("输出目录: %s", args.out)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
