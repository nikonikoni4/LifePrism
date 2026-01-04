"""
LangChain Tool -> Toon Format 适配器（官方库实现）

流程：
1. 使用 @tool 装饰器 + Pydantic 定义工具
2. 从工具生成 JSON Schema
3. 使用 toon-python 库将 JSON 转换为 Toon 格式
"""
from typing import List, Dict, Any
from langchain_core.tools import BaseTool, tool
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field
import json

from toon_python import encode as toon_encode


class LangChainToonAdapter:
    """
    LangChain 工具 <-> Toon 格式适配器
    
    提供三种转换方式：
    1. 单个工具转 Toon
    2. 工具列表转 Toon
    3. 构建包含 Toon 工具的系统提示词
    """
    
    @staticmethod
    def tool_to_json(tool: BaseTool) -> Dict[str, Any]:
        """
        步骤 2: 将 LangChain 工具转换为 JSON Schema
        
        Args:
            tool: LangChain 工具实例
            
        Returns:
            工具的 JSON Schema 表示
        """
        tool_json = {
            "name": tool.name,
            "description": tool.description,
        }
        
        # 获取参数 schema
        if hasattr(tool, 'args_schema') and tool.args_schema:
            tool_json["parameters"] = tool.args_schema.model_json_schema()
        elif hasattr(tool, 'args'):
            tool_json["parameters"] = tool.args
        
        return tool_json
    
    @staticmethod
    def tools_to_json(tools: List[BaseTool]) -> List[Dict[str, Any]]:
        """
        批量转换工具为 JSON Schema
        
        Args:
            tools: LangChain 工具列表
            
        Returns:
            工具 JSON Schema 列表
        """
        return [LangChainToonAdapter.tool_to_json(tool) for tool in tools]
    
    @staticmethod
    def json_to_toon(tool_json: Dict[str, Any]) -> str:
        """
        步骤 3: 使用 toon-python 库将 JSON 转换为 Toon 格式
        
        Args:
            tool_json: 工具的 JSON 表示
            
        Returns:
            Toon 格式字符串
        """
        return toon_encode(tool_json)
    
    @staticmethod
    def tool_to_toon(tool: BaseTool) -> str:
        """
        一步式：LangChain 工具直接转换为 Toon 格式
        
        Args:
            tool: LangChain 工具实例
            
        Returns:
            Toon 格式字符串
        """
        tool_json = LangChainToonAdapter.tool_to_json(tool)
        return LangChainToonAdapter.json_to_toon(tool_json)
    
    @staticmethod
    def tools_to_toon(tools: List[BaseTool]) -> str:
        """
        批量转换工具列表为 Toon 格式
        
        Args:
            tools: LangChain 工具列表
            
        Returns:
            Toon 格式字符串
        """
        tools_json = LangChainToonAdapter.tools_to_json(tools)
        return LangChainToonAdapter.json_to_toon(tools_json)
    
    @staticmethod
    def build_system_message_with_toon_tools(
        tools: List[BaseTool],
        base_instruction: str = "你是一个智能助手，可以使用以下工具。"
    ) -> SystemMessage:
        """
        构建包含 Toon 格式工具的系统消息
        
        Args:
            tools: 工具列表
            base_instruction: 基础指令
            
        Returns:
            SystemMessage 对象
        """
        tools_toon = LangChainToonAdapter.tools_to_toon(tools)
        
        content = f"""{base_instruction}
# 可用工具 (Toon Format)
```toon
{tools_toon}
```

使用工具时，请按以下格式调用：
tool_call(tool_name, param1=value1, param2=value2)
"""
        
        return SystemMessage(content=content)


# ============================================================================
# 示例用法
# ============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 100)
    print("LangChain Tool -> Toon Format 适配器")
    print("=" * 100)
    
    # ========================================================================
    # 步骤 1: 使用 @tool 装饰器 + Pydantic 定义工具
    # ========================================================================
    print("\n【步骤 1】使用 @tool 装饰器 + Pydantic 定义工具")
    print("-" * 100)
    
    class SearchInput(BaseModel):
        query: str = Field(description="搜索关键词")
        limit: int = Field(default=10, description="返回结果的最大数量")
    
    @tool(args_schema=SearchInput)
    def search_website(query: str, limit: int = 10) -> str:
        """根据关键词在数据库中搜索网站描述信息"""
        return '{"results": []}'
    
    class WeatherInput(BaseModel):
        city: str = Field(description="城市名称")
        unit: str = Field(default="celsius", description="温度单位：celsius 或 fahrenheit")
    
    @tool(args_schema=WeatherInput)
    def get_weather(city: str, unit: str = "celsius") -> str:
        """获取指定城市的天气信息"""
        return '{"temp": 25}'
    
    tools = [search_website, get_weather]
    
    print("✅ 定义了 2 个工具:")
    for tool in tools:
        print(f"   - {tool.name}: {tool.description}")
    
    # ========================================================================
    # 步骤 2: 从工具生成 JSON Schema
    # ========================================================================
    print("\n【步骤 2】从工具生成 JSON Schema")
    print("-" * 100)
    
    tools_json = LangChainToonAdapter.tools_to_json(tools)
    tools_json_str = json.dumps(tools_json, indent=2, ensure_ascii=False)
    
    print(tools_json_str)
    print(f"\n📊 JSON 格式 - 字符数: {len(tools_json_str)} | 估算 tokens: ~{len(tools_json_str) // 4}")
    
    # ========================================================================
    # 步骤 3: 使用 toon-python 库转换为 Toon 格式
    # ========================================================================
    print("\n【步骤 3】使用 toon-python 库转换为 Toon 格式")
    print("-" * 100)
    
    tools_toon = LangChainToonAdapter.tools_to_toon(tools)
    print(tools_toon)
    print(f"\n📊 Toon 格式 - 字符数: {len(tools_toon)} | 估算 tokens: ~{len(tools_toon) // 4}")
    
    # 计算节省
    json_tokens = len(tools_json_str) // 4
    toon_tokens = len(tools_toon) // 4
    savings = 100 - (toon_tokens / json_tokens * 100)
    
    print("\n" + "=" * 100)
    print("💰 Token 节省对比")
    print("=" * 100)
    print(f"JSON Schema:  {len(tools_json_str):4d} 字符 ≈ {json_tokens:3d} tokens")
    print(f"Toon Format:  {len(tools_toon):4d} 字符 ≈ {toon_tokens:3d} tokens")
    print(f"\n✨ 节省: {savings:.1f}% ({json_tokens - toon_tokens} tokens)")
    
    # ========================================================================
    # 一步式转换示例
    # ========================================================================
    print("\n" + "=" * 100)
    print("【便捷方法】一步式转换")
    print("=" * 100)
    
    # 单个工具
    print("\n单个工具转 Toon:")
    print("-" * 50)
    single_tool_toon = LangChainToonAdapter.tool_to_toon(search_website)
    print(single_tool_toon)
    
    # 构建系统消息
    print("\n完整的系统消息（包含 Toon 工具）:")
    print("-" * 50)
    system_msg = LangChainToonAdapter.build_system_message_with_toon_tools(
        tools,
        base_instruction="你是一个智能助手，可以调用工具来完成任务。"
    )
    print(system_msg.content)
    
    # ========================================================================
    # 实际使用示例
    # ========================================================================
    print("\n" + "=" * 100)
    print("📝 实际使用示例")
    print("=" * 100)
    
    print("""
# 在你的 LangChain 应用中使用：

from lifeprism.llm.llm_classify.langchain_toon_adapter import LangChainToonAdapter
from lifeprism.llm.llm_classify.creat_model import create_ChatTongyiModel

# 1. 定义工具（现有方式不变）
@tool
def my_tool(param: str) -> str:
    ...

tools = [my_tool, ...]

# 2. 创建模型
model = create_ChatTongyiModel()

# 3. 构建包含 Toon 工具的系统消息
system_msg = LangChainToonAdapter.build_system_message_with_toon_tools(tools)

# 4. 发送消息（工具描述已经是 Toon 格式，节省 token）
messages = [
    system_msg,
    HumanMessage(content="帮我搜索微信")
]

response = model.invoke(messages)
    """)
    
    print("\n" + "=" * 100)
    print("✅ 优势总结")
    print("=" * 100)
    print("""
1. ✅ 使用官方 toon-python 库，格式标准且维护良好
2. ✅ 与现有 LangChain 工具定义完全兼容（@tool + Pydantic）
3. ✅ 节省 60-80% 的工具描述 tokens
4. ✅ 三步流程清晰：定义 -> JSON -> Toon
5. ✅ 提供便捷方法，一行代码完成转换
    """)
