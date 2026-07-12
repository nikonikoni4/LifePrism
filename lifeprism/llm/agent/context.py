# context 模块负责加载各种外置文件，构建system prompt
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lifeprism.config import ALLOWED_DIRS, settings
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
    def build_prompt(system_prompt: str, message: list[dict[str, Any]]):
        return [{"role": "system", "content": system_prompt}] + message

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

        return f"## runtime\n 当前时间（UTC ISO 8601）：{datetime.now(timezone.utc).isoformat()}\n 当前对话方式：{channel_type}\n"

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

    # 如果还需要测试最终 build_prompt 合并消息的效果可以看下面：
    print("\n============== 测试 build_prompt 合并 User Message ===============")
    final_messages = Context.build_prompt((sys_prompt or ""), [{"role": "user", "content": "你好"}])
    import json

    print(json.dumps(final_messages, ensure_ascii=False, indent=2))
