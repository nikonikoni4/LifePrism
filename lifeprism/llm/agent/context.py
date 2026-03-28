# context 模块负责加载各种外置文件，构建system prompt
# 占位
from typing import Any
from lifeprism.llm.bus import MessageType
class Context:
    def __init__(self):
        pass
    @staticmethod
    def build_system_prompt(type):
        if type == MessageType.CHAT:
            return ""
        elif type == MessageType.CLASSIFY:
            return ""
    
    @staticmethod
    def build_prompt(system_prompt:str,message:list[dict[str,Any]]):
        return [{"role":"system","content":system_prompt}] + message