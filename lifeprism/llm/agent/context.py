# context 模块负责加载各种外置文件，构建system prompt
from typing import Any
from lifeprism.llm.bus import InboundMessage, MessageType
from lifeprism.config import settings
from pathlib import Path


class Context:
    def __init__(self):
        pass

    @staticmethod
    def _read_file(path: str) -> str | None:
        p = Path(path)
        if p.exists():
            return p.read_text(encoding="utf-8")
        return None

    @staticmethod
    def build_system_prompt(msg:InboundMessage):
        parts = []
        type = msg.type
        base = settings.lifeprism_data_path
        if type == MessageType.CHAT:
            # 加载agent.md + bootstrap.md + user.md + memory.md
            
            agent_path    = base + "/agent/chat/agent.md"
            bootstrap_path = base + "/agent/chat/bootstrap.md"
            user_path     = base + "/user/user.md"
            memory_path   = base + "/agent/chat/memory.md"

            for path in [agent_path, bootstrap_path, user_path, memory_path]:
                content = Context._read_file(path)
                if content:
                    parts.append(content)

            return "\n\n".join(parts)
        elif type == MessageType.CLASSIFY:
            classify_preference_path = base + "agent/classify/classify_preference.md"
            content = Context._read_file(classify_preference_path)
            if content:
                return (msg.extra or {}).get("system_prompt", "") + "\n\n" + content
            else:
                return (msg.extra or {}).get("system_prompt", "")
            

    @staticmethod
    def build_prompt(system_prompt: str, message: list[dict[str, Any]]):
        return [{"role": "system", "content": system_prompt}] + message
