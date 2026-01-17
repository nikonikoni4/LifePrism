from lifeprism.llm.custom_prompt.chatbot_prompt.summary_prompt import daily_summary_template,multi_days_summary_template
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from lifeprism.llm.llm_classify.tools.database_tools import (
    get_daily_stats,
    get_multi_days_stats,
    query_behavior_timeline,
    query_daily_todos,
    get_daily_breakdown,
    query_behavior_logs,
    query_goals,
    query_psychological_assessment,
    query_daily_notes,
    query_daily_summaries,
    query_weekly_focus,
    query_goal_time_distribution
)
from lifeprism.storage.base_providers.lw_base_data_provider import LWBaseDataProvider
import logging
import asyncio
from lifeprism.llm.llm_linear_executor.llm_linear_executor.os_plan import load_plan_from_template
from lifeprism.llm.llm_linear_executor.llm_linear_executor.executor import Executor
from typing import Literal
from lifeprism.llm.llm_classify.providers.llm_lw_data_provider import llm_lw_data_provider
from lifeprism.llm.llm_linear_executor.llm_linear_executor.llm_factory import create_llm_factory
from lifeprism.config import settings 
logger = logging.getLogger(__name__)
daily_json_path = "lifeprism/llm/custom_prompt/skills/user_behavior_summary/pattern/daily_summary_plan.json"
multi_days_json_path = "lifeprism/llm/custom_prompt/skills/user_behavior_summary/pattern/weekly_summary_plan.json"

async def daily_summary(date : str, pattern ="complex"):
    """
    生成每日总结（异步版本）
    
    Args:
        date: 日期字符串，格式 YYYY-MM-DD
        pattern: 总结模式，可选值: "simple", "complex", "custom"
    Returns:
        dict: 包含总结内容和 tokens 使用量的字典
            - content: 总结内容
            - tokens_usage: tokens 使用量信息
                - input_tokens: 输入 token 数量
                - output_tokens: 输出 token 数量
                - total_tokens: 总 token 数量
    """
    # 获取执行计划和工具限制
    plan = load_plan_from_template(daily_json_path, pattern,replacements={"{date}":date})
    
    # 准备工具映射
    tools_map = {
        "get_daily_stats": get_daily_stats,
        "get_multi_days_stats": get_multi_days_stats,
        "query_behavior_timeline": query_behavior_timeline,
        "query_daily_todos": query_daily_todos,
        "get_daily_breakdown": get_daily_breakdown,
        "query_behavior_logs": query_behavior_logs,
        "query_goals": query_goals,
        "query_psychological_assessment": query_psychological_assessment,
        "query_daily_notes": query_daily_notes,
        "query_daily_summaries": query_daily_summaries,
        "query_weekly_focus": query_weekly_focus,
        "query_goal_time_distribution": query_goal_time_distribution
    }

    # 创建 LLM 工厂
    llm_factory = create_llm_factory(
            model=settings.model,
            api_key= settings.api_key,
        )
    # 创建异步执行器并执行
    executor = Executor(
        plan=plan,
        tools_map=tools_map,
        llm_factory=llm_factory
    )
    result = await executor.aexecute()
    
    # 保存 tokens 使用量到数据库
    session_id = f"summary-{date}"
    tokens_usage = result["tokens_usage"]
    try:
        def save_tokens():
            usage_data = {
                'input_tokens': tokens_usage['input_tokens'],
                'output_tokens': tokens_usage['output_tokens'],
                'total_tokens': tokens_usage['total_tokens'],
                'search_count': 0,
                'result_items_count': 0,
                'mode': 'summary'
            }
            llm_lw_data_provider.upsert_session_tokens_usage(session_id, usage_data)
        
        await asyncio.to_thread(save_tokens)
        logger.info(f"已保存每日总结的 tokens 使用量: {session_id}, total_tokens={tokens_usage['total_tokens']}")
    except Exception as e:
        logger.error(f"保存 tokens 使用量失败: {e}")
    
    return {
        'content': result["content"],
        'tokens_usage': tokens_usage
    }


 
async def multi_days_summary(start_date: str, end_date: str, pattern: str = "complex"):
    """
    生成多日总结（异步版本）
    
    Args:
        start_date: 开始日期字符串，格式 YYYY-MM-DD
        end_date: 结束日期字符串，格式 YYYY-MM-DD
        pattern: 总结模式，可选值: "simple", "complex", "custom"
    
    Returns:
        dict: 包含总结内容和 tokens 使用量的字典
            - content: 总结内容
            - tokens_usage: tokens 使用量信息
                - input_tokens: 输入 token 数量
                - output_tokens: 输出 token 数量
                - total_tokens: 总 token 数量
    """
    # 获取执行计划和工具限制
    plan = load_plan_from_template(
        multi_days_json_path, 
        pattern,
        replacements={
            "{start_date}": start_date,
            "{end_date}": end_date
        }
    )
    
    # 准备工具映射
    tools_map = {
        "get_daily_stats": get_daily_stats,
        "get_multi_days_stats": get_multi_days_stats,
        "query_behavior_timeline": query_behavior_timeline,
        "query_daily_todos": query_daily_todos,
        "get_daily_breakdown": get_daily_breakdown,
        "query_behavior_logs": query_behavior_logs,
        "query_goals": query_goals,
        "query_psychological_assessment": query_psychological_assessment,
        "query_daily_notes": query_daily_notes,
        "query_daily_summaries": query_daily_summaries,
        "query_weekly_focus": query_weekly_focus,
        "query_goal_time_distribution": query_goal_time_distribution
    }

    # 创建 LLM 工厂
    
    llm_factory = create_llm_factory(
            model=settings.model,
            api_key= settings.api_key,
        )
    # 创建异步执行器并执行
    executor = Executor(
        plan=plan,
        tools_map=tools_map,
        llm_factory=llm_factory
    )
    result = await executor.aexecute()
    
    # 保存 tokens 使用量到数据库
    session_id = f"summary-{start_date}_to_{end_date}"
    tokens_usage = result["tokens_usage"]
    try:
        def save_tokens():
            usage_data = {
                'input_tokens': tokens_usage['input_tokens'],
                'output_tokens': tokens_usage['output_tokens'],
                'total_tokens': tokens_usage['total_tokens'],
                'search_count': 0,
                'result_items_count': 0,
                'mode': 'summary'
            }
            llm_lw_data_provider.upsert_session_tokens_usage(session_id, usage_data)
        
        await asyncio.to_thread(save_tokens)
        logger.info(f"已保存多日总结的 tokens 使用量: {session_id}, total_tokens={tokens_usage['total_tokens']}")
    except Exception as e:
        logger.error(f"保存 tokens 使用量失败: {e}")
    
    return {
        'content': result["content"],
        'tokens_usage': tokens_usage
    }

if __name__ == '__main__':
    async def main():
        result = await multi_days_summary(start_date="2026-01-08", end_date="2026-01-14", pattern="complex")
        print(result["content"])
        print(result["tokens_usage"])
    
    asyncio.run(main())

