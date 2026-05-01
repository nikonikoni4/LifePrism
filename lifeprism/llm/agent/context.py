# context 模块负责加载各种外置文件，构建system prompt
from typing import Any
from lifeprism.llm.bus import InboundMessage, MessageType
from lifeprism.config import settings
from pathlib import Path
from lifeprism.llm.agent.skill import SkillLoad

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
        """ 构建系统提示词 """
        parts = []
        type = msg.type
        base = settings.lifeprism_data_path
        if type == MessageType.CHAT:
            # 1. 加载基础文档
            # 加载agent.md + bootstrap.md + user.md + memory.md
            
            agent_path    = base + "/agent/chat/agent.md"
            bootstrap_path = base + "/agent/chat/bootstrap.md"
            user_path     = base + "/user/user.md"
            memory_path   = base + "/agent/chat/memory.md"

            for path in [agent_path, bootstrap_path, user_path, memory_path]:
                content = Context._read_file(path)
                if content:
                    parts.append(content)
            # 2. 加载skill
            skill_loader = SkillLoad()
            skill_load_list = (msg.extra or {}).get("skill_list",None)
            parts.append(skill_loader.load_skills(skill_load_list))
            # 3. 加载可用skill list 
            parts.append(skill_loader.load_frontmatters(skill_load_list))

            return "\n\n".join(parts)
        elif type == MessageType.CLASSIFY:
            classify_preference_path = base + "agent/classify/classify_preference.md"
            content = Context._read_file(classify_preference_path)
            if content:
                return (msg.extra or {}).get("system_prompt", "") + "\n\n" + content
            else:
                return (msg.extra or {}).get("system_prompt", "")
        
        elif type == MessageType.GENERAL_TASK :
            # 通用调用，不添加额外的上下文
            return (msg.extra or {}).get("system_prompt", "")
            
    @staticmethod
    def build_prompt(system_prompt: str, message: list[dict[str, Any]]):
        return [{"role": "system", "content": system_prompt}] + message


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