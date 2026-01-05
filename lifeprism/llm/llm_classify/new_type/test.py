from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from lifeprism.utils import get_logger, DEBUG
from typing import Annotated, TypedDict
import operator

# 导入工具
from lifeprism.llm.llm_classify.new_type.tools import (
    query_behavior_logs,
    query_goals,
    query_time_paradoxes,
    get_logs_by_time,
    get_user_focus_notes
)

logger = get_logger(__name__, DEBUG)

# 定义状态
class AgentState(TypedDict):
    messages: Annotated[list, operator.add]
    tool_call_count: int


def run_agent():
    """
    运行智能体，最多调用4轮工具
    """
    # 创建模型并绑定工具
    model = create_ChatTongyiModel()
    
    # 定义可用工具列表
    tools = [
        query_behavior_logs,
        query_goals,
        query_time_paradoxes,
        get_logs_by_time,
        get_user_focus_notes
    ]
    
    # 绑定工具到模型
    model_with_tools = model.bind_tools(tools)
    
    # 创建工具名称到函数的映射
    tool_map = {
        "query_behavior_logs": query_behavior_logs,
        "query_goals": query_goals,
        "query_time_paradoxes": query_time_paradoxes,
        "get_logs_by_time": get_logs_by_time,
        "get_user_focus_notes": get_user_focus_notes
    }
    
    # 初始化消息
    system_prompt = """你是一个智能助手，总结用户上午，中午，下午，晚上四个时间段都做了什么。
请根据需要调用工具，收集足够的信息后生成总结报告。"""
     
    user_prompt = "请总结用户2026-01-01的一天活动。先获取整体概况，再根据需要深入了解细节。"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    max_tool_rounds = 20
    current_round = 0
    
    logger.debug(f"=== 开始智能体执行 ===")
    logger.debug(f"用户请求: {user_prompt}")
    
    while current_round < max_tool_rounds:
        current_round += 1
        logger.debug(f"\n{'='*60}")
        logger.debug(f"=== 第 {current_round} 轮工具调用 ===")
        logger.debug(f"{'='*60}")
        
        # 调用模型
        response = model_with_tools.invoke(messages)
        
        # 检查是否有工具调用
        if not response.tool_calls:
            logger.debug("模型决定不再调用工具，生成最终回复")
            logger.debug(f"\n=== 最终回复 ===\n{response.content}")
            break
        
        # 处理工具调用
        logger.debug(f"模型请求调用 {len(response.tool_calls)} 个工具:")
        
        # 添加 AI 消息
        messages.append(response)
        
        # 执行每个工具调用
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            
            logger.debug(f"\n  📌 工具: {tool_name}")
            logger.debug(f"  📝 参数: {tool_args}")
            
            # 执行工具
            if tool_name in tool_map:
                try:
                    result = tool_map[tool_name].invoke(tool_args)
                    logger.debug(f"  ✅ 结果预览: {str(result)[:200]}...")
                except Exception as e:
                    result = f"工具执行错误: {e}"
                    logger.debug(f"  ❌ 错误: {e}")
            else:
                result = f"未知工具: {tool_name}"
                logger.debug(f"  ❌ 未知工具")
            
            # 添加工具结果消息
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": str(result)
            })
    
    else:
        # 达到最大轮次，强制生成总结
        logger.debug(f"\n{'='*60}")
        logger.debug("达到最大工具调用轮次，生成最终总结...")
        logger.debug(f"{'='*60}")
        
        messages.append({
            "role": "user", 
            "content": "你已经收集了足够的信息，请现在生成用户2026-01-02的一天活动总结报告。"
        })
        
        final_response = model.invoke(messages)
        logger.debug(f"\n=== 最终回复 ===\n{final_response.content}")
        return final_response.content
    
    return response.content


if __name__ == "__main__":
    print("=" * 60)
    print("智能体日活动总结测试")
    print("=" * 60)
    
    result = run_agent()
    
    print("\n" + "=" * 60)
    print("最终总结报告:")
    print("=" * 60)
    print(result)
