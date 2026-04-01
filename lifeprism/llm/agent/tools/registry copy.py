# 工具注册类
# 统一管理工具
# 需要实现： 1. 添加工具 name : tool类 2. 执行函数 3. 返回可使用工具列表schemas
from typing import Any
from lifeprism.llm.agent.tools.base import Tool 

class ToolRegistry:

    def __init__(self):
        self._tools:dict[str,Tool] = {} # name : tool
        

    def registry(self,tool :Tool):
        """注册工具"""
        self._tools[tool.name] = tool

    def unregistry(self,name :str):
        self._tools.pop(name,None)

    async def execute(self,name : str ,parameters):
        """ 执行工具 """
        tool = self._tools.get(name,None)
        if tool is None:
            raise ValueError(f"工具名称错误, {name}错误或未注册")
        # 验证参数
        tool.validate_params(**parameters)
        # 异步执行
        return await tool.execute(parameters)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    def get_descriptions(self,allow_tools : list[str]) -> list[dict[str:Any]] :
        """ 返回可用的工具schemas """
        # 没有传入则默认允许所有的工具
        if not allow_tools:
            allow_tools = self._tools.keys()
        tools = []

        for name,tool in self._tools.items():
            if name in allow_tools :
                tools.append(tool.to_schemas())
        return tools
    

    @property
    def tool_names(self) -> list[str]:
        """ 获取已经注册的工具 """
        return list(self._tools.keys()) 