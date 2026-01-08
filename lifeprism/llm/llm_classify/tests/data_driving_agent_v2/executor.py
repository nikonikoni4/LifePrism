# 执行器定义 V2
# 支持多线程 Context 和 4 种节点类型分发

from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.data_driving_schemas import (
    Context, NodeDefinition, ExecutionPlan, NodeType, ThreadMeta
)
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from lifeprism.llm.llm_classify.tools.database_tools import (
    get_daily_stats,
    get_multi_days_stats,
    query_behavior_logs,
    query_goals,
    query_psychological_assessment
)
from typing import Callable
from lifeprism.utils import get_logger,DEBUG
logger = get_logger(__name__)
class Executor:
    """
    数据驱动执行器 V2
    
    支持特性:
    - 多线程 Context 消息隔离
    - 4 种节点类型分发执行 (llm_auto, tool, query, planning)
    - data_out 机制: 子线程向父线程输出结果
    """
    
    # 默认工具调用次数限制
    DEFAULT_TOOLS_USAGE_LIMIT = {
        "get_daily_stats": 1,
        "get_multi_days_stats": 1,
        "query_behavior_logs": 10,
        "query_goals": 1,
        "query_psychological_assessment": 1
    }

    def __init__(
        self, 
        plan: ExecutionPlan, 
        user_message: str, 
        main_thread_id: str = "main",
        tools_limit: dict[str, int] | None = None
    ):
        self.plan = plan
        self.main_thread_id = main_thread_id
        
        # 新的多线程 Context 结构
        self.context: Context = {
            "messages": {
                main_thread_id: [HumanMessage(content=user_message)]
            },
            "data_out": {},
            "thread_meta": {
                main_thread_id: {"parent_thread": None}
            }
        }
        
        # 工具映射
        self.tools_map = {
            "get_daily_stats": get_daily_stats,
            "get_multi_days_stats": get_multi_days_stats,
            "query_behavior_logs": query_behavior_logs,
            "query_goals": query_goals,
            "query_psychological_assessment": query_psychological_assessment
        }
        
        # 工具使用限制
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
        
        # 节点类型 -> 处理函数 映射
        self._node_handlers: dict[NodeType, Callable[[NodeDefinition], str]] = {
            "llm-first": self._execute_llm_first_node,
            "tool-first": self._execute_tool_first_node,
            "planning": self._execute_planning_node,
        }
        self.role_map = {
            "llm-first": "assistant",
            "tool-first": "tool",
            "planning": "assistant"
        }


    # =========================================================================
    # Context 辅助方法
    # =========================================================================
    def _get_thread_messages(self, thread_id: str) -> list:
        """获取指定线程的消息列表"""
        return self.context["messages"].get(thread_id, [])

    def _add_message_to_thread(self, thread_id: str, message) -> None:
        """添加消息到指定线程"""
        if thread_id not in self.context["messages"]:
            raise ValueError(f"线程 {thread_id} 不存在")
        self.context["messages"][thread_id].append(message)

    def _create_thread(self, thread_id: str, parent_thread_id: str | None = None, node: NodeDefinition | None = None) -> None:
        """
        创建新线程，并根据 node 的 data_in 配置注入初始消息
        
        Args:
            thread_id: 新线程ID
            parent_thread_id: 父线程ID
            node: 节点定义，用于获取 data_in 配置
        """
        if thread_id in self.context["messages"]:
            return  # 线程已存在，直接返回
        
        self.context["messages"][thread_id] = []
        self.context["thread_meta"][thread_id] = {"parent_thread": parent_thread_id}
        
        # 处理 data_in：注入初始消息到新线程
        if node is not None:
            # 确定数据来源线程：优先使用 data_in_thread，否则使用 parent_thread_id
            source_thread = node.data_in_thread or parent_thread_id
            
            if source_thread and source_thread in self.context["messages"]:
                source_msgs = self.context["messages"][source_thread]
                
                # 检查源线程是否有数据
                if source_msgs:
                    if node.data_in_slice:
                        # 使用指定的切片范围
                        start, end = node.data_in_slice
                        injected = source_msgs[start:end]
                    else:
                        # 默认：取最后一条消息
                        injected = [source_msgs[-1]]
                    
                    # 注入消息到新线程
                    if injected:
                        self.context["messages"][thread_id].extend(injected)
                        logger.debug(f"    → data_in: 从 '{source_thread}' 注入 {len(injected)} 条消息到 '{thread_id}'")

    def _set_data_out(self, thread_id: str, node_type: str, description: str, content: str) -> None:
        """设置线程的输出数据"""
        self.context["data_out"][thread_id] = {
            "role": self.role_map[node_type],
            "content": f"{description}{content}" if description else content
        }

    def _merge_data_out_to_parent(self, child_thread_id: str) -> None:
        """将子线程的 data_out 合并到父线程的 messages"""
        if child_thread_id not in self.context["data_out"]:
            return
        
        parent_id = self.context["thread_meta"].get(child_thread_id, {}).get("parent_thread")
        if parent_id and parent_id in self.context["messages"]:
            data = self.context["data_out"][child_thread_id]
            self._add_message_to_thread(parent_id, AIMessage(content=data["content"]))

    # =========================================================================
    # 工具管理方法
    # =========================================================================
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
        """累加 tokens 使用量"""
        if hasattr(result, 'response_metadata') and 'token_usage' in result.response_metadata:
            token_usage = result.response_metadata['token_usage']
            self.tokens_usage['input_tokens'] += token_usage.get('input_tokens', 0)
            self.tokens_usage['output_tokens'] += token_usage.get('output_tokens', 0)
            self.tokens_usage['total_tokens'] += token_usage.get('total_tokens', 0)

    def _validate_tools(self, tools: list[str] | None):
        """验证工具是否存在"""
        if not tools:
            return
        for tool in tools:
            if tool not in self.tools_map:
                raise ValueError(f"工具 {tool} 不存在，可用工具: {list(self.tools_map.keys())}")

    def _can_use_tool(self, tool_name: str) -> bool:
        """判断指定工具是否还能调用"""
        return self.tools_usage_limit.get(tool_name, 0) > 0
    
    def _consume_tool_usage(self, tool_name: str) -> None:
        """消耗一次工具调用次数"""
        if tool_name in self.tools_usage_limit:
            self.tools_usage_limit[tool_name] -= 1

    def _has_available_tools(self, tools: list[str] | None) -> bool:
        """检查是否还有可用的工具调用次数"""
        if not tools:
            return False
        return any(self._can_use_tool(tool) for tool in tools)

    def _tools_limit_prompt(self, tools: list[str] | None) -> str:
        """生成工具调用次数限制的 prompt"""
        if not tools:
            return ""
        lines = []
        for tool in tools:
            remaining = self.tools_usage_limit.get(tool, 0)
            lines.append(f"工具 {tool} 可以调用 {remaining} 次")
        return "\n".join(lines)

    def _create_llm_with_tools(self, tools: list[str] | None):
        """创建 LLM，如果有工具则绑定"""
        llm = create_ChatTongyiModel(enable_search=False, enable_thinking=False)
        if tools:
            tool_objects = [self.tools_map[t] for t in tools]
            llm = llm.bind_tools(tool_objects)
        return llm

    # =========================================================================
    # Prompt 构建
    # =========================================================================
    def get_history(self, thread_id: str) -> str:
        """返回指定线程的格式化历史消息字符串"""
        result = []
        messages = self._get_thread_messages(thread_id)
        for message in messages:
            if isinstance(message, HumanMessage):
                result.append(f"user: {message.content}")
            elif isinstance(message, ToolMessage):
                result.append(f"tool: {message.content}")
            elif isinstance(message, AIMessage):
                # 如果有 tool_calls，需要格式化输出
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    tool_calls_str = ", ".join([
                        f"{tc.get('name', 'unknown')}({tc.get('args', {})})" 
                        for tc in message.tool_calls
                    ])
                    result.append(f"assistant: [调用工具: {tool_calls_str}]")
                    if message.content:
                        result.append(f"assistant: {message.content}")
                else:
                    result.append(f"assistant: {message.content}")
        return "\n".join(result) if result else ""

    def _get_prompt(self, node: NodeDefinition) -> str:
        """构建节点的 prompt"""
        tools_limit_prompt = self._tools_limit_prompt(node.tools)
        return f"""
# 历史消息
{self.get_history(node.thread_id)}
# 工具可调用次数限制，请合理安排工具调用:
{tools_limit_prompt}
# 你需要按照下面要求完成任务：
{node.task_prompt}
"""

    # =========================================================================
    # 工具执行
    # =========================================================================
    def _execute_tool_call_for_thread(self, tool_call: dict, thread_id: str) -> tuple[bool, str | None]:
        """执行工具调用并将结果添加到指定线程"""
        tool_name = tool_call.get("name", "")
        tool_args = tool_call.get("args", {})
        tool_id = tool_call.get("id", "")
        
        if tool_name not in self.tools_map:
            error_msg = f"未知工具: {tool_name}，可用工具: {list(self.tools_map.keys())}"
            logger.info(f"    ✗ {error_msg}")
            return False, error_msg
        
        if not self._can_use_tool(tool_name):
            error_msg = f"工具 {tool_name} 调用次数已用完"
            logger.info(f"    ✗ {error_msg}")
            self._add_message_to_thread(thread_id, ToolMessage(content=error_msg, tool_call_id=tool_id))
            return False, error_msg
        
        logger.info(f"    - 执行工具: {tool_name}, args: {tool_args}")
        tool_result = self.tools_map[tool_name].invoke(tool_args)
        self._consume_tool_usage(tool_name)
        logger.info(f"    - 工具 {tool_name} 剩余调用次数: {self.tools_usage_limit[tool_name]}")
        
        self._add_message_to_thread(thread_id, ToolMessage(content=str(tool_result), tool_call_id=tool_id))
        return True, str(tool_result)

    # =========================================================================
    # 节点处理器
    # =========================================================================
    
    def _llm_tool_loop(self, node: NodeDefinition, llm) -> str:
        """
        LLM 工具调用循环
        
        使用 messages 列表调用 LLM，支持多轮工具调用直到 LLM 返回最终结果
        """
        # 添加任务 prompt 到线程
        tools_limit_prompt = self._tools_limit_prompt(node.tools)
        initial_task_prompt = f"""工具可调用次数限制，请合理安排工具调用:
{tools_limit_prompt}
你需要按照下面要求完成任务：
{node.task_prompt}"""
        self._add_message_to_thread(node.thread_id, HumanMessage(content=initial_task_prompt))
        
        result = None
        round_count = 0
        while True:
            round_count += 1
            logger.debug(f"[DEBUG] 第 {round_count} 轮循环")
            
            messages = self._get_thread_messages(node.thread_id)
            result = llm.invoke(messages)
            self._accumulate_tokens(result)
            self._add_message_to_thread(node.thread_id, result)
            
            # 无 tool_calls，结束
            if not (hasattr(result, 'tool_calls') and result.tool_calls):
                logger.debug(f"    → LLM 返回最终结果（无 tool_calls）")
                break
            
            # 执行工具
            logger.debug(f"    → LLM 请求调用 {len(result.tool_calls)} 个工具")
            executed = 0
            for tool_call in result.tool_calls:
                success, _ = self._execute_tool_call_for_thread(tool_call, node.thread_id)
                if success:
                    executed += 1
            
            # 无成功执行或工具用完，结束
            if executed == 0:
                logger.debug(f"    → 本轮没有成功执行任何工具")
                break
            if not self._has_available_tools(node.tools):
                logger.debug(f"    → 所有工具调用次数已用完")
                break
        
        logger.debug(f"[DEBUG] 工具循环完成，共 {round_count} 轮")
        return result.content if result else ""

    def _llm_single_call(self, node: NodeDefinition, llm) -> str:
        """
        单次 LLM 调用（可能包含一次工具调用）
        """
        prompt = self._get_prompt(node)
        result = llm.invoke(prompt)
        self._accumulate_tokens(result)
        self._add_message_to_thread(node.thread_id, result)
        
        # 如果有 tool_calls，执行一次
        if hasattr(result, 'tool_calls') and result.tool_calls:
            for tool_call in result.tool_calls:
                self._execute_tool_call_for_thread(tool_call, node.thread_id)
        
        return result.content

    def _execute_llm_first_node(self, node: NodeDefinition) -> str:
        """
        LLM-First 节点执行器
        
        流程：LLM思考 -> [可选]调用工具 -> [可选]循环
        
        配置选项：
        - tools: 可用工具列表
        - enable_tool_loop: 是否启用工具调用循环
        """
        logger.info(f"执行节点 [llm-first]: {node.node_name}")
        
        # 验证工具
        if node.tools:
            self._validate_tools(node.tools)
            logger.info(f"    - 可用工具: {node.tools}")
            logger.info(f"    - 工具循环: {'启用' if node.enable_tool_loop else '禁用'}")
        
        # 创建 LLM（可能带工具）
        llm = self._create_llm_with_tools(node.tools)
        
        if node.enable_tool_loop and node.tools:
            # 启用循环：使用 messages 列表调用
            final_content = self._llm_tool_loop(node, llm)
        else:
            # 不启用循环：单次调用
            final_content = self._llm_single_call(node, llm)
        
        # 处理 data_out
        if node.data_out:
            self._set_data_out(node.thread_id, node.node_type, 
                              node.data_out_description, final_content)
        
        return final_content

    def _execute_tool_first_node(self, node: NodeDefinition) -> str:
        """
        Tool-First 节点执行器
        
        流程：执行初始工具 -> [可选]LLM分析 -> [可选]调用更多工具 -> [可选]循环
        
        配置选项：
        - initial_tool_name: 初始工具名称（必需）
        - initial_tool_args: 初始工具参数
        - task_prompt: LLM 任务描述（为空时只返回工具结果）
        - tools: 后续可用工具列表
        - enable_tool_loop: 是否启用工具调用循环
        """
        logger.info(f"执行节点 [tool-first]: {node.node_name}")
        
        # 验证初始工具配置
        if not node.initial_tool_name:
            raise ValueError(f"tool-first 节点 {node.node_name} 必须指定 initial_tool_name")
        if node.initial_tool_name not in self.tools_map:
            raise ValueError(f"工具 {node.initial_tool_name} 不存在")
        
        # 检查初始工具调用限制
        if not self._can_use_tool(node.initial_tool_name):
            error_msg = f"工具 {node.initial_tool_name} 调用次数已用完"
            logger.info(f"    ✗ {error_msg}")
            self._add_message_to_thread(node.thread_id,
                ToolMessage(content=error_msg, tool_call_id="initial_tool"))
            return error_msg
        
        # 执行初始工具
        tool_args = node.initial_tool_args or {}
        logger.info(f"    - 执行初始工具: {node.initial_tool_name}")
        logger.info(f"    - 工具参数: {tool_args}")
        tool_result = self.tools_map[node.initial_tool_name].invoke(tool_args)
        self._consume_tool_usage(node.initial_tool_name)
        logger.info(f"    - 工具 {node.initial_tool_name} 剩余调用次数: {self.tools_usage_limit[node.initial_tool_name]}")
        
        # 添加工具结果到上下文
        self._add_message_to_thread(node.thread_id,
            ToolMessage(content=str(tool_result), tool_call_id="initial_tool"))
        
        # 如果没有 task_prompt，直接返回工具结果
        if not node.task_prompt:
            final_content = str(tool_result)
        else:
            # 验证额外工具
            if node.tools:
                self._validate_tools(node.tools)
                logger.info(f"    - 后续可用工具: {node.tools}")
                logger.info(f"    - 工具循环: {'启用' if node.enable_tool_loop else '禁用'}")
            
            # 创建 LLM（可能带额外工具）
            llm = self._create_llm_with_tools(node.tools)
            
            if node.enable_tool_loop and node.tools:
                # 启用循环
                final_content = self._llm_tool_loop(node, llm)
            else:
                # 单次调用
                final_content = self._llm_single_call(node, llm)
        
        # 处理 data_out
        if node.data_out:
            self._set_data_out(node.thread_id, node.node_type,
                              node.data_out_description, final_content)
        
        return final_content


    def _execute_planning_node(self, node: NodeDefinition) -> str:
        """
        规划节点（暂未实现）
        
        TODO: 后续迭代实现
        - 调用 LLM 生成子计划 (使用 SubExecutorPlan schema)
        - 创建子线程
        - 递归执行子计划
        - 结果合并
        """
        raise NotImplementedError(
            f"planning 节点 {node.node_name} 尚未实现，请在后续迭代中添加支持"
        )

    # =========================================================================
    # 主执行方法
    # =========================================================================
    def execute(self) -> dict:
        """
        执行整个计划
        
        Returns:
            dict: 包含执行结果的字典
                - content: 最终输出内容
                - messages: 所有消息（按 thread_id 组织）
                - tokens_usage: tokens 使用量统计
                - data_out: 各线程的输出数据
        """
        logger.info(f"\n开始执行计划: {self.plan.task}\n")

        # 重置工具调用次数和 tokens 统计
        self.reset_tools_limit()
        self.reset_tokens_usage()

        content = None
        for node in self.plan.nodes:
            # 确保线程存在，使用节点定义的 parent_thread_id
            if node.thread_id not in self.context["messages"]:
                # 优先使用节点定义的 parent_thread_id，否则默认为 main_thread_id
                parent_id = node.parent_thread_id if node.parent_thread_id else self.main_thread_id
                self._create_thread(node.thread_id, parent_id, node)
            
            # 使用处理器分发
            handler = self._node_handlers.get(node.node_type)
            if not handler:
                raise ValueError(f"未知节点类型: {node.node_type}")
            
            content = handler(node)
            
            # 如果节点设置了 data_out，合并到父线程
            if node.data_out:
                self._merge_data_out_to_parent(node.thread_id)
        
        logger.info(f"\n计划执行完成！")
        logger.info(f"📊 Tokens 使用统计: 输入={self.tokens_usage['input_tokens']}, "
              f"输出={self.tokens_usage['output_tokens']}, 总计={self.tokens_usage['total_tokens']}\n")
        
        return {
            "content": content,
            "messages": self.context["messages"],
            "tokens_usage": self.tokens_usage,
            "data_out": self.context["data_out"]
        }


# =============================================================================
# 测试代码
# =============================================================================
if __name__ == "__main__":
    # 创建测试计划 - 使用 llm_auto 和 query 节点
    # 
    from lifeprism.llm.llm_classify.tests.data_driving_agent_v2.load_plans import load_plan_from_template
    plan,tools_limit= load_plan_from_template(json_path=r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\llm_classify\tests\data_driving_agent_v2\patterns\test_plan.json",
                        pattern_name="test1",date = "2026-01-03")
    executor = Executor(plan, "请帮我总结 2026-01-03 的使用情况",tools_limit=tools_limit)
    result = executor.execute()
    
    # 格式化输出
    print("\n" + "=" * 80)
    print("📊 AI 生成的行为总结")
    print("=" * 80 + "\n")
    print(result["content"])
    print("\n" + "=" * 80)
    print(f"📈 统计信息：共产生 {sum(len(msgs) for msgs in result['messages'].values())} 条消息")
    tokens = result["tokens_usage"]
    print(f"🔢 Tokens 使用: 输入={tokens['input_tokens']}, 输出={tokens['output_tokens']}, 总计={tokens['total_tokens']}")
    print("=" * 80)