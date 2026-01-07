# 执行器定义
from lifeprism.llm.llm_classify.tests.data_driving_agent.schemas import Context, NodeDefinition, ExecutionPlan
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from lifeprism.llm.llm_classify.tools.database_tools import (
    get_daily_stats,
    get_multi_days_stats,
    query_behavior_logs,
    query_goals,
    query_psychological_assessment
)


class Executor:
    # 默认工具调用次数限制
    DEFAULT_TOOLS_USAGE_LIMIT = {
        "get_daily_stats": 1,
        "get_multi_days_stats": 1,
        "query_behavior_logs": 10,
        "query_goals": 1,
        "query_psychological_assessment": 1
    }

    def __init__(self, plan: ExecutionPlan, user_message: str, tools_limit: dict[str, int] | None = None):
        self.plan = plan
        self.context = Context(messages=[HumanMessage(content=user_message)])
        self.tools_map = {
            "get_daily_stats": get_daily_stats,
            "get_multi_days_stats": get_multi_days_stats,
            "query_behavior_logs": query_behavior_logs,
            "query_goals": query_goals,
            "query_psychological_assessment": query_psychological_assessment
        }
        # 保存初始工具限制配置，用于 reset
        # 先使用默认配置，再用 tools_limit 中的值覆盖
        self._initial_tools_limit = self.DEFAULT_TOOLS_USAGE_LIMIT.copy()
        if tools_limit:
            self._initial_tools_limit.update(tools_limit)
        self.tools_usage_limit = self._initial_tools_limit.copy()
        # tokens 使用统计
        self.tokens_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }

    def reset_tools_limit(self):
        """重置工具调用次数限制为初始配置"""
        self.tools_usage_limit = self._initial_tools_limit.copy()
    
    def reset_tokens_usage(self):
        """重置 tokens 使用统计"""
        self.tokens_usage = {
            'input_tokens': 0,
            'output_tokens': 0,
            'total_tokens': 0
        }
    
    def _accumulate_tokens(self, result) -> None:
        """
        累加 tokens 使用量
        
        args:
            result: LLM 返回的结果对象
        """
        if hasattr(result, 'response_metadata') and 'token_usage' in result.response_metadata:
            token_usage = result.response_metadata['token_usage']
            self.tokens_usage['input_tokens'] += token_usage.get('input_tokens', 0)
            self.tokens_usage['output_tokens'] += token_usage.get('output_tokens', 0)
            self.tokens_usage['total_tokens'] += token_usage.get('total_tokens', 0)
    
    def get_history(self) -> str:
        """返回格式化的历史消息字符串"""
        result = []
        for message in self.context["messages"]:
            if isinstance(message, HumanMessage):
                result.append(f"user: {message.content}")
            elif isinstance(message, ToolMessage):
                result.append(f"tool: {message.content}")
            elif isinstance(message, AIMessage):
                result.append(f"assistant: {message.content}")
        return "\n".join(result) if result else ""

    def _create_llm_with_tools(self, tools: list[str] | None):
        """创建 LLM，如果有工具则绑定"""
        llm = create_ChatTongyiModel(enable_search=False, enable_thinking=False)
        if tools:
            # 获取工具对象
            tool_objects = [self.tools_map[t] for t in tools]
            llm = llm.bind_tools(tool_objects)
        return llm
    
    def _validate_tools(self, tools: list[str] | None):
        """验证工具是否存在"""
        if not tools:
            return
        for tool in tools:
            if tool not in self.tools_map:
                raise ValueError(f"工具 {tool} 不存在，可用工具: {list(self.tools_map.keys())}")
    
    def _tools_limit_prompt(self, tools: list[str] | None) -> str:
        """
        生成工具调用次数限制的 prompt
        
        args : 
            tools : list[str] 调用的工具名称列表
        return : 
            str : 工具调用次数限制的 prompt
        """
        if not tools:
            return ""
        
        lines = []
        for tool in tools:
            remaining = self.tools_usage_limit.get(tool, 0)
            lines.append(f"工具 {tool} 可以调用 {remaining} 次")
        return "\n".join(lines)
    
    def _can_use_tool(self, tool_name: str) -> bool:
        """
        判断指定工具是否还能调用
        
        args:
            tool_name: 工具名称
        return:
            bool: 是否可以调用
        """
        return self.tools_usage_limit.get(tool_name, 0) > 0
    
    def _consume_tool_usage(self, tool_name: str) -> None:
        """
        消耗一次工具调用次数
        
        args:
            tool_name: 工具名称
        """
        if tool_name in self.tools_usage_limit:
            self.tools_usage_limit[tool_name] -= 1

    def _get_prompt(self, node: NodeDefinition) -> str:
        """构建节点的 prompt"""
        tools_limit_prompt = self._tools_limit_prompt(node.tools)

        return f"""
# 历史消息
{self.get_history()}
# 工具可调用次数限制，请合理安排工具调用:
{tools_limit_prompt}
# 你需要按照下面要求完成任务：
{node.task_prompt}
"""

    def _execute_tool_call(self, tool_call: dict) -> tuple[bool, str | None]:
        """
        执行单个工具调用
        
        args:
            tool_call: 工具调用信息，包含 name, args, id
        return:
            tuple[bool, str | None]: (是否执行成功, 工具返回结果或错误信息)
        """
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")
        
        # 验证工具是否存在
        if tool_name not in self.tools_map:
            error_msg = f"未知工具: {tool_name}，可用工具: {list(self.tools_map.keys())}"
            print(f"    ✗ {error_msg}")
            return False, error_msg
        
        # 检查工具是否还有调用次数
        if not self._can_use_tool(tool_name):
            error_msg = f"工具 {tool_name} 调用次数已用完"
            print(f"    ✗ {error_msg}")
            # 添加错误信息到 context
            self.context["messages"].append(ToolMessage(
                content=error_msg,
                tool_call_id=tool_id
            ))
            return False, error_msg
        
        # 执行工具
        print(f"    - 执行工具: {tool_name}, args: {tool_args}")
        tool_result = self.tools_map[tool_name].invoke(tool_args)
        
        # 消耗调用次数
        self._consume_tool_usage(tool_name)
        print(f"    - 工具 {tool_name} 剩余调用次数: {self.tools_usage_limit[tool_name]}")
        
        # 添加 ToolMessage 到 context
        self.context["messages"].append(ToolMessage(
            content=str(tool_result),
            tool_call_id=tool_id
        ))
        
        return True, str(tool_result)
    
    def _has_available_tools(self, tools: list[str] | None) -> bool:
        """
        检查是否还有可用的工具调用次数
        
        args:
            tools: 当前节点可用的工具列表
        return:
            bool: 是否还有可用的工具
        """
        if not tools:
            return False
        return any(self._can_use_tool(tool) for tool in tools)

    def _execute_node(self, node: NodeDefinition):
        """
        执行单个节点，包含工具调用循环
        
        循环逻辑：
        1. 调用 LLM
        2. 如果返回 tool_calls → 执行工具 → 添加 ToolMessage → 回到步骤 1
        3. 如果返回纯文本 → 结束循环
        4. 如果所有工具调用次数用完 → 结束循环
        """
        print(f"执行节点：{node.node_name}")
        
        # 验证工具
        self._validate_tools(node.tools)
        
        # 创建 LLM（带工具）
        llm = self._create_llm_with_tools(node.tools)
        result = None
        
        # ⭐ 工具调用循环 ⭐
        while True:
            # 构建 prompt
            prompt = self._get_prompt(node)
            
            # 1. 调用 LLM
            result = llm.invoke(prompt)
            
            # 2. 累加 tokens 使用量
            self._accumulate_tokens(result)
            
            # 3. 添加 AIMessage 到 context
            self.context["messages"].append(result)
            
            # 3. 检查是否有 tool_calls
            if not (hasattr(result, 'tool_calls') and result.tool_calls):
                print(f"  → LLM 返回最终结果")
                break
            
            # 4. 执行工具调用
            print(f"  → LLM 请求调用 {len(result.tool_calls)} 个工具")
            
            executed_count = 0
            for tool_call in result.tool_calls:
                success, _ = self._execute_tool_call(tool_call)
                if success:
                    executed_count += 1
            
            # 5. 检查是否还有可用的工具
            if not self._has_available_tools(node.tools):
                print(f"  → 所有工具调用次数已用完")
                break
            
            # 6. 如果本轮没有成功执行任何工具，结束循环
            if executed_count == 0:
                print(f"  → 本轮没有成功执行任何工具")
                break
            
            # 7. 继续循环，让 LLM 看到工具结果
            print(f"  → 继续调用 LLM，查看工具结果...")
        
        return result.content
    
    def execute(self):
        """
        执行整个计划
        
        Returns:
            dict: 包含执行结果的字典
                - content: 最终输出内容
                - messages: 所有消息列表
                - tokens_usage: tokens 使用量统计
                    - input_tokens: 输入 token 数量
                    - output_tokens: 输出 token 数量
                    - total_tokens: 总 token 数量
        """
        print(f"\n开始执行计划: {self.plan.task}\n")

        # 重置工具调用次数和 tokens 统计
        self.reset_tools_limit()
        self.reset_tokens_usage()

        content = None
        for node in self.plan.nodes:
            content = self._execute_node(node)
        
        print(f"\n计划执行完成！")
        print(f"📊 Tokens 使用统计: 输入={self.tokens_usage['input_tokens']}, 输出={self.tokens_usage['output_tokens']}, 总计={self.tokens_usage['total_tokens']}\n")
        
        return {
            "content": content,
            "messages": self.context["messages"],
            "tokens_usage": self.tokens_usage
        }

if __name__ == "__main__":
    from lifeprism.llm.llm_classify.tests.data_driving_agent.plans import get_daily_summary_plan
    plan,tools_limit = get_daily_summary_plan("2026-01-05",json_path=r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\llm_classify\tests\data_driving_agent\pattern\daily_summary_plan.json",pattern_name="simple")
    executor = Executor(plan, "总结 2026-01-05 的使用情况",tools_limit=tools_limit)
    result = executor.execute()
    
    # 格式化输出
    print("\n" + "=" * 80)
    print("📊 AI 生成的行为总结")
    print("=" * 80 + "\n")
    print(result["content"])
    print("\n" + "=" * 80)
    print(f"📈 统计信息：共产生 {len(result['messages'])} 条消息")
    tokens = result["tokens_usage"]
    print(f"🔢 Tokens 使用: 输入={tokens['input_tokens']}, 输出={tokens['output_tokens']}, 总计={tokens['total_tokens']}")
    print("=" * 80)


    
