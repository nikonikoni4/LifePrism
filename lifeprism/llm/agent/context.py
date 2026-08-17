# context 模块负责加载各种外置文件，构建system prompt
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytz

from lifeprism.config import ALLOWED_DIRS, get_user_timezone, settings
from lifeprism.llm.agent.skill import SkillLoad
from lifeprism.llm.bus import ChannelType, InboundMessage, MessageType
from lifeprism.utils import get_logger

logger = get_logger(__name__)


class Context:
    def __init__(self):
        pass

    @staticmethod
    def _read_file(path: str, **kwargs) -> str | None:
        """
        读取文件并注入参数

        Args:
            path: 文件路径
            **kwargs: 要注入的参数，文件中的 {key} 会被替换为对应的值

        Returns:
            str | None: 文件内容，如果文件不存在返回 None
        """
        p = Path(path)
        if p.exists():
            content = p.read_text(encoding="utf-8")
            if kwargs:
                # 提取文档中所有的 {key} 参数
                placeholders = set(re.findall(r"\{(\w+)\}", content))
                missing_keys = placeholders - set(kwargs.keys())
                if missing_keys:
                    logger.warning("文件 %s 中存在未注入的参数: %s", path, missing_keys)

                class SafeDict(dict):
                    def __missing__(self, key):
                        return "{" + key + "}"

                content = content.format_map(SafeDict(kwargs))
            return content
        return None

    @staticmethod
    def build_system_prompt(msg: InboundMessage) -> str:
        """构建系统提示词"""
        parts = []
        type = msg.type
        base = str(settings.lifeprism_data_path)

        if type == MessageType.CHAT:
            # 1. 系统环境层
            parts.append(Context._build_identity())
            # 2. agent定义层和用户定义层
            parts.append(Context._build_bootstrap())
            # 3. 加载用户最近状态
            parts.append(Context._bulid_recent_state())
            # 4. 加载永远可用的和激活的skill
            skill_loader = SkillLoad()
            skill_load_list = (msg.extra or {}).get("skill_list", None)
            # 加载特定的skills和allow_skill
            parts.append(skill_loader.load_skills(skill_load_list))
            # 5. 加载可用skill list
            parts.append(skill_loader.load_frontmatters(skill_load_list))
            logger.debug("systemp prompt " + "\n\n".join(parts))
            return "\n\n".join(parts)
        elif type == MessageType.CLASSIFY:
            classify_preference_path = base + "agent/classify/classify_preference.md"
            content = Context._read_file(classify_preference_path)
            if content:
                return (msg.extra or {}).get("system_prompt", "") + "\n\n" + content
            else:
                return (msg.extra or {}).get("system_prompt", "")

        else:
            # 通用调用，不添加额外的上下文
            return (msg.extra or {}).get("system_prompt", "")

    @staticmethod
    def build_prefix_messages(msg: InboundMessage) -> list[dict[str, Any]]:
        """构建前缀消息：system prompt + 可选的 custom prompt 注入

        前缀消息位于稳定前缀区（system 之后、会话历史之前），在每次 LLM 调用的
        组装期动态拼接，不写入 session 历史（对 auto_compact 免疫、修改即时生效）。

        custom prompt 仅 CHAT 类型且内容非空时注入，以 user role 承载
        （层级低于 system，用户规则不凌驾于系统规则），
        参考 ADR docs/adr/2026-08-18-custom-prompt-user-role-injection.md

        Args:
            msg: 入站消息

        Returns:
            list[dict[str, Any]]: 前缀消息列表，至少包含一条 system 消息
        """
        prefix = [{"role": "system", "content": Context.build_system_prompt(msg)}]
        if msg.type == MessageType.CHAT:
            custom_message = Context._build_custom_prompt_message()
            if custom_message:
                prefix.append(custom_message)
        return prefix

    @staticmethod
    def _build_custom_prompt_message() -> dict[str, Any] | None:
        """构建 custom prompt 注入消息

        读取 agent/chat/custom_prompt.md，内容 strip 后为空（含文件不存在）时返回 None。
        文件内容保持纯净，来源说明与管理方式在拼接时注入 system-reminder 块内。

        Returns:
            dict[str, Any] | None: user role 注入消息；无内容时返回 None
        """
        custom_prompt_path = settings.lifeprism_data_path / "agent/chat/custom_prompt.md"
        content = Context._read_file(str(custom_prompt_path))
        # "空"的定义与 sync/file_filter.is_empty_content 对齐：strip 后为空视为无内容
        if not content or not content.strip():
            return None
        agent_chat_dir = settings.lifeprism_data_path / "agent/chat"
        return {
            "role": "user",
            "content": (
                "<system-reminder>\n"
                "# custom prompt\n"
                f"以下内容来自 {custom_prompt_path}，是用户为 AI 制定的自定义规则，"
                "优先级高于默认行为，必须遵守。\n"
                "管理方式：你可以用 write_file/edit_file 直接修改该文件；"
                f"也可以在 {agent_chat_dir} 下创建其他规则文件"
                "（需在该文件内列出文件链接和内容摘要，按需用 read_file 渐进加载）。\n\n"
                f"{content}\n"
                "</system-reminder>"
            ),
        }

    @staticmethod
    def _build_identity() -> str:
        """构建系统运行环境提示词"""
        content = Context._read_file(str(settings.lifeprism_data_path) + "/agent/chat/identity.md")
        if not content:
            content = """# identity
            - 名称 :
- 身份 : lifeprism的系统AI助手，意在帮助用户查询和管理他们的生活数据，并且结合各种数据来回答用户的问题，为用户的生活记录与自我了解提供支持。
- 性格 : 温暖
            """
        if (
            (
                not content
                or ": " not in content
                or content.split("- 名称 :")[1].split("\n")[0].strip() == ""
            )
            or ": " in content
            and content.split("- 名称 :")[1].split("\n")[0].strip() == ""
        ):
            content += "你当前名称为空，需要向用户询问你的名字, 随后利用文件修改问工具修改`<工作目录>/agent/chat/identity.md`的内容"
        content += f"\n你当前工作目录是：{str(settings.lifeprism_data_path.resolve())},你能够阅读和操作的目录是：{str(settings.lifeprism_data_path.resolve())}/{ALLOWED_DIRS}"
        return content

    @staticmethod
    def _build_expand_dir() -> str:
        """构建额外工作目录列表"""
        expand_meta_path = (
            settings.lifeprism_data_path / "localData/expand_dir/expand_meta_data.json"
        )
        if not expand_meta_path.exists():
            return "无"
        try:
            with open(expand_meta_path, encoding="utf-8") as f:
                expand_list = json.load(f)
            if not expand_list:
                return "无"
            lines = []
            for item in expand_list:
                path = item.get("path", "")
                path_name = item.get("path_name", "")
                description = item.get("description", "")
                lines.append(f"- {path} ({path_name}): {description}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("读取 expand_meta_data.json 失败: %s", e)
            return "无"

    @staticmethod
    def _build_bootstrap() -> str:
        """构建引导文档提示词"""
        parts = []
        # 判断bootstrap.md 是否存在
        bootstrap_path = str(settings.lifeprism_data_path) + "/agent/chat/bootstrap.md"
        bootstrap_file = Context._read_file(bootstrap_path)
        if bootstrap_file:
            parts.append(f"{bootstrap_file}")
        # bootstrap.md 不存在 或 json 不存在 或 json bootstrap 为 False
        # 添加 soul.md agent.md tool.md user.md
        soul_path = str(settings.lifeprism_data_path / "agent/chat/soul.md")
        agent_path = str(settings.lifeprism_data_path / "agent/chat/agent.md")
        tool_path = str(settings.lifeprism_data_path / "agent/chat/tool.md")
        user_path = str(settings.lifeprism_data_path / "user/user.md")

        # 构建 agent.md 的注入参数
        agent_params = {
            "agent_path": str(settings.lifeprism_data_path / "agent"),
            "user_path": str(settings.lifeprism_data_path / "user"),
            "diary_path": str(settings.lifeprism_data_path / "diary"),
            "expand_dir": Context._build_expand_dir(),
        }

        soul_content = Context._read_file(soul_path)
        agent_content = Context._read_file(agent_path, **agent_params)
        tool_content = Context._read_file(tool_path)
        user_content = Context._read_file(user_path)

        if soul_content:
            parts.append(f"\n{soul_content}")
        if agent_content:
            parts.append(f"\n{agent_content}")
        if tool_content:
            parts.append(f"\n{tool_content}")
        if user_content:
            parts.append(f"\n{user_content}")
        return "\n\n".join(parts)

    @staticmethod
    def _build_run_context(msg: InboundMessage) -> str:
        """构建运行上下文提示词"""
        if msg.channel == ChannelType.WECHAT:
            channel_type = "微信"
        elif msg.channel == ChannelType.LOCAL:
            channel_type = "本地"
        else:
            channel_type = "未知"

        tz_name = get_user_timezone()
        tz = pytz.timezone(tz_name)
        now_local = datetime.now(timezone.utc).astimezone(tz)
        return (
            f"## runtime\n"
            f" 当前时间：{now_local.strftime('%Y-%m-%d %H:%M:%S')}（时区：{tz_name}）\n"
            f" 当前对话方式：{channel_type}\n"
        )

    @staticmethod
    def _build_user_message(msg: InboundMessage) -> list[dict[str, Any]]:
        """构建用户消息提示词"""

        return [
            {
                "type": "text",
                "text": f"{Context._build_run_context(msg)}## user's message",
            },
            *msg.content,
        ]

    @staticmethod
    def _bulid_recent_state():
        path = str(settings.lifeprism_data_path / "user/daily_data/recent_state.md")
        return Context._read_file(path)


if __name__ == "__main__":
    from unittest.mock import MagicMock

    from lifeprism.llm.bus import MessageType

    print("============== 开始测试构建 CHAT 类型的 System Prompt ==============")

    # 使用 MagicMock 模拟 InboundMessage，避免必须填写其他必填字段(如uuid/时间戳等)的错误
    mock_msg = MagicMock()
    mock_msg.type = MessageType.CHAT
    # 我们测试要求全量加载 lifeprism_use 这个 skill
    mock_msg.extra = {"skill_list": ["lifeprism_use"]}

    sys_prompt = Context.build_system_prompt(mock_msg)

    if sys_prompt:
        print(sys_prompt)
    else:
        print("未生成任何提示词，请检查基础文档路径下是否有对应文件。")

    print("\n==================================================================")

    # 如果还需要测试最终 build_prefix_messages 合并消息的效果可以看下面：
    print("\n============== 测试 build_prefix_messages 合并 User Message ===============")
    final_messages = Context.build_prefix_messages(mock_msg) + [{"role": "user", "content": "你好"}]
    import json

    print(json.dumps(final_messages, ensure_ascii=False, indent=2))
