"""
应用描述处理器模块
负责判断、提取和缩写应用描述
"""

from lifewatch.llm import OllamaClient


class AppDescriptionProcessor:
    """应用描述处理器，负责判断、提取和缩写应用描述"""
    
    def __init__(self, llm_client: OllamaClient):
        """
        初始化处理器
        
        Args:
            llm_client: Ollama客户端实例
        """
        self.client = llm_client
    
    def is_app_description(self, app_name: str, text: str) -> bool:
        """
        判断文本是否为指定应用程序的描述
        
        Args:
            app_name: 应用程序名称
            text: 输入文本
            
        Returns:
            bool: 如果是该应用程序描述则返回True，否则返回False
        """
        prompt = f"""
        请判断以下文本是否包含对{app_name}的用途定性描述（功能、用途、类型说明）。
        重要规则：
        1. 如果文本明确说明了{app_name}是什么类型的应用（如：浏览器、编辑器、播放器、管理器、游戏等），提取用途定性描述
        2. 如果文本只是描述{app_name}的新闻、发布信息、市场动态，不提取定性描述
        3. 如果文本包含"发布"、"宣布"、"财报"、"促销"等新闻词汇，不提取定性描述
        4. 如果文本与{app_name}无关，不提取定性描述
        处理要求：
        - 如果包含定性描述，返回格式：是
        - 如果不包含定性描述，返回：否
        - 定性描述要简洁准确，说明应用的核心类型和功能
        待处理文本：{text}
        
        请严格按规则判断，仅回答"是"或"否"。
        """
        response = self.client.generate(prompt)
        if response:
            return "是" in response.strip()
        return False
    
    def get_app_description_abbr(self, app_name: str, text: str) -> str:
        """
        获取应用程序的定性描述缩写
        
        Args:
            app_name: 应用程序名称
            text: 应用程序描述文本
            
        Returns:
            str: 应用程序的定性描述
        """
        prompt = f"""
        请从以下文本中提取关于{app_name}应用的定性描述，格式为：{app_name}是[用途定性描述]
        注意：
        可能包含非{app_name}应用的描述，只提取关于{app_name}的描述。
        要求：
        1. 提取最核心的定性描述（功能、用途、类型说明），说明这是什么类型的应用
        2. 格式统一为：{app_name}是[用途定性描述]
        待处理文本：{text}
        请仅返回定性描述，不要包含其他内容。
        示例输出：{app_name}是社交应用程式。
        """
        response = self.client.generate(prompt)
        if response:
            return response.strip()
        return ""
