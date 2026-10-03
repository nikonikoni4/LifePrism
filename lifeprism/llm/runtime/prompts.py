"""把 LifePrism 生产提示词直接注册到 myagent 的 SystemPrompt 上。"""

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from myagent.agent.core.systemprompt import PrompSection, SystemPrompt

from lifeprism.config import ALLOWED_DIRS, get_user_timezone
from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType
from lifeprism.llm.runtime.skills import SkillLoad
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def read_prompt(path: Path, params: dict[str, str] | None = None) -> str:
    """读取磁盘上的提示词文件并替换 ``{name}`` 占位符。

    每次模型请求都会调用，因此修改提示词文件无需重启即可生效。只有出现在
    ``params`` 中的占位符会被替换；未知的 ``{...}`` 原样保留，使提示词文本里的
    字面量 JSON 花括号不受影响。

    Args:
        path: 待读取的提示词文件。
        params: 占位符名称到替换文本的映射。传 ``None`` 等同于空映射，此时原样
            返回文件内容。

    Returns:
        替换已知占位符后的文件内容；``path`` 不存在时返回空字符串。
    """
    if not path.is_file():
        return ""
    content = path.read_text(encoding="utf-8")
    values = params or {}
    return re.sub(r"\{(\w+)\}", lambda match: values.get(match[1], match[0]), content)


def _expand_dirs(data_path: Path) -> str:
    """把用户配置的额外目录说明渲染为提示词中的列表行。

    Args:
        data_path: LifePrism 数据根目录，其中包含
            ``localData/expand_dir/expand_meta_data.json``。

    Returns:
        每条记录渲染为一行 ``- path (name): description``；元数据文件缺失、
        为空或读取失败时返回 ``"无"``。
    """
    path = data_path / "localData/expand_dir/expand_meta_data.json"
    if not path.exists():
        return "无"
    try:
        entries = json.loads(path.read_text(encoding="utf-8"))
        return (
            "\n".join(
                f"- {item.get('path', '')} ({item.get('path_name', '')}): {item.get('description', '')}"
                for item in entries
            )
            or "无"
        )
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("读取额外目录说明失败: %s", exc)
        return "无"


def register_prompts(
    prompt: SystemPrompt, message: InboundMessage, data_path: Path
) -> dict[str, dict]:
    """为单条入站消息把 LifePrism 提示词栈挂载到 ``prompt`` 上。

    各 section 以回调而非渲染后的文本注册，因此内核每次请求都会重新读取提示词
    文件，修改无需重启即可生效。聊天消息会获得完整的身份、工具、技能与运行时
    栈；单一用途任务只获得身份覆盖和各自的偏好文件。

    Args:
        prompt: 待配置的内核提示词对象；注册前会先清空。
        message: 提供消息类型、渠道以及 ``extra`` 中 ``system_prompt``、
            ``skill_list`` 字段的入站消息。
        data_path: LifePrism 数据根目录，其中包含 ``agent/``、``user/`` 与
            ``localData/`` 下的提示词来源。

    Returns:
        各已注册 section 的占位符参数，外加 ``custom_prompt`` 与 ``runtime``，
        供调用方与内核保持一致。
    """
    prompt.clear()
    render_params: dict[str, dict] = {}

    def section(name: str, order: int, callback) -> None:
        """注册一个具名 section，并为其初始化占位符参数。"""
        prompt.register_section(PrompSection(name=name, order=order, text=callback))
        render_params[name] = {}

    extra = message.extra or {}
    if message.type != MessageType.CHAT:
        # Override the kernel's default identity for single-purpose jobs.
        section("identity", 0, lambda: extra.get("system_prompt", ""))
        if message.type == MessageType.CLASSIFY:
            section(
                "classify_preference",
                1,
                lambda: read_prompt(data_path / "agent/classify/classify_preference.md"),
            )
        return render_params

    def identity() -> str:
        """返回聊天身份提示词，并附上可操作目录范围说明。"""
        text = (
            read_prompt(data_path / "agent/chat/identity.md")
            or "# identity\n你是 LifePrism 的生活记录与数据分析助手。"
        )
        return text + f"\n你当前工作目录是：{data_path.resolve()}，允许操作的目录：{ALLOWED_DIRS}"

    def parameters() -> dict[str, str]:
        """返回各文件型 section 共用的占位符取值。"""
        return {
            "data_path": str(data_path),
            "agent_path": str(data_path / "agent"),
            "user_path": str(data_path / "user"),
            "diary_path": str(data_path / "diary"),
            "expand_dir": _expand_dirs(data_path),
        }

    section("identity", 0, identity)
    for order, name, relative in (
        (1, "soul", "agent/chat/soul.md"),
        (2, "agent", "agent/chat/agent.md"),
        (3, "tool", "agent/chat/tool.md"),
        (4, "user", "user/user.md"),
        (5, "recent_state", "user/daily_data/recent_state.md"),
    ):
        section(
            name, order, lambda relative=relative: read_prompt(data_path / relative, parameters())
        )
    skills = SkillLoad()
    skills.skill_path = data_path / "agent/skills"
    selected = extra.get("skill_list")
    section("loaded_skills", 6, lambda: skills.load_skills(selected))
    section("available_skills", 7, lambda: skills.load_frontmatters(selected))

    def reminder() -> str:
        """返回用户自定义规则文件，并包装为 system reminder section。"""
        path = data_path / "agent/chat/custom_prompt.md"
        text = read_prompt(path, parameters()).strip()
        if not text:
            return ""
        return f"# custom prompt\n以下内容来自 {path}，是用户自定义规则。\n{text}"

    def runtime_context() -> str:
        """返回当前用户本地时间与本次对话所用渠道。"""
        tz_name = get_user_timezone()
        now = datetime.now(UTC).astimezone(ZoneInfo(tz_name))
        channel = "微信" if message.channel == ChannelType.WECHAT else "本地"
        return f"## runtime\n当前时间：{now:%Y-%m-%d %H:%M:%S}（时区：{tz_name}）\n当前对话方式：{channel}"

    prompt.register_system_reminder(reminder, name="custom_prompt")
    prompt.register_context(runtime_context, name="runtime")
    render_params.update(custom_prompt={}, runtime={})
    return render_params
