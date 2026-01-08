from lifeprism.llm.custom_prompt.chatbot_prompt.summary_prompt import daily_summary_template,multi_days_summary_template
from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
from lifeprism.llm.llm_classify.tools.database_tools import get_daily_stats,get_multi_days_stats
from lifeprism.storage.base_providers.lw_base_data_provider import LWBaseDataProvider
import logging
import asyncio
from lifeprism.llm.llm_classify.data_driving_agent.load_plans import get_daily_summary_plan
from lifeprism.llm.llm_classify.data_driving_agent.async_executor import AsyncExecutor
from typing import Literal
from lifeprism.llm.llm_classify.providers.llm_lw_data_provider import llm_lw_data_provider
logger = logging.getLogger(__name__)
json_path = r"D:\desktop\软件开发\LifeWatch-AI\lifeprism\llm\custom_prompt\skills\user_behavior_summary\pattern\daily_summary_plan.json"

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
    plan, tools_limit = get_daily_summary_plan(date,json_path, pattern)
    print(plan)
    # 创建异步执行器并执行
    executor = AsyncExecutor(
        plan=plan,
        user_message=f"总结 {date} 的使用情况",
        tools_limit=tools_limit
    )
    result = await executor.execute()
    
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



async def daily_summary_old(date : str, options : list):
    """
    生成每日总结（异步版本）
    
    Args:
        date: 日期字符串，格式 YYYY-MM-DD
        options: 总结选项列表
            behavior_stats: 各时段的主分类和子分类的占比统计
            longest_activities: 各时段内最长的活动记录
            goal_time_spent: 各目标花费的时间
            user_notes: 用户手动添加的时间块备注
            tasks: 今日重点内容
    Returns:
        dict: 包含总结内容和 tokens 使用量的字典
            - content: 总结内容
            - tokens_usage: tokens 使用量信息
                - input_tokens: 输入 token 数量
                - output_tokens: 输出 token 数量
                - total_tokens: 总 token 数量
    """
    llm = create_ChatTongyiModel(temperature=0.5)
    start_time = date + " 00:00:00"
    end_time = date + " 23:59:59"
    
    # 在线程池中运行同步的工具调用，避免阻塞事件循环
    result = await asyncio.to_thread(
        get_daily_stats.invoke,
        {
            "start_time": start_time,
            "end_time": end_time,
            "split_count": 4, 
            "options": options
        }
    )
    
    prompt_template = daily_summary_template(input_variables=["user_data", "options"])
    prompt_input = prompt_template.format(
        options=options,
        user_data=result,
    )
    
    # 使用异步调用 LLM
    output = await llm.ainvoke(input=prompt_input)
    
    # 提取 tokens 使用量
    tokens_usage = {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0
    }
    
    if hasattr(output, 'response_metadata') and 'token_usage' in output.response_metadata:
        token_usage = output.response_metadata['token_usage']
        tokens_usage = {
            'input_tokens': token_usage.get('input_tokens', 0),
            'output_tokens': token_usage.get('output_tokens', 0),
            'total_tokens': token_usage.get('total_tokens', 0)
        }
    
    # 保存 tokens 使用量到数据库（在线程池中运行）
    session_id = f"summary-{date}"
    try:
        def save_tokens():
            provider = LWBaseDataProvider()
            usage_data = {
                'input_tokens': tokens_usage['input_tokens'],
                'output_tokens': tokens_usage['output_tokens'],
                'total_tokens': tokens_usage['total_tokens'],
                'search_count': 0,
                'result_items_count': 0,
                'mode': 'summary'
            }
            provider.upsert_session_tokens_usage(session_id, usage_data)
        
        await asyncio.to_thread(save_tokens)
        logger.info(f"已保存每日总结的 tokens 使用量: {session_id}, total_tokens={tokens_usage['total_tokens']}")
    except Exception as e:
        logger.error(f"保存 tokens 使用量失败: {e}")
    
    return {
        'content': output.content,
        'tokens_usage': tokens_usage
    }

async def multi_days_summary(start_time : str, end_time : str, split_count : int, options : list):
    """
    生成多日总结（异步版本）
    
    Args:
        start_time: 开始时间字符串，格式 YYYY-MM-DD HH:MM:SS
        end_time: 结束时间字符串，格式 YYYY-MM-DD HH:MM:SS
        split_count: 分割数量
        options: 总结选项列表
    
    Returns:
        dict: 包含总结内容和 tokens 使用量的字典
            - content: 总结内容
            - tokens_usage: tokens 使用量信息
                - input_tokens: 输入 token 数量
                - output_tokens: 输出 token 数量
                - total_tokens: 总 token 数量
    """
    llm = create_ChatTongyiModel(temperature=0.5)
    
    # 在线程池中运行同步的工具调用
    result = await asyncio.to_thread(
        get_multi_days_stats.invoke,
        {
            "start_time": start_time,
            "end_time": end_time,
            "split_count": split_count, 
            "options": options
        }
    )
    
    prompt_template = multi_days_summary_template(input_variables=["user_data", "options"])
    prompt_input = prompt_template.format(
        options=options,
        user_data=result,
    )
    
    # 使用异步调用 LLM
    output = await llm.ainvoke(input=prompt_input)
    
    # 提取 tokens 使用量
    tokens_usage = {
        'input_tokens': 0,
        'output_tokens': 0,
        'total_tokens': 0
    }
    
    if hasattr(output, 'response_metadata') and 'token_usage' in output.response_metadata:
        token_usage = output.response_metadata['token_usage']
        tokens_usage = {
            'input_tokens': token_usage.get('input_tokens', 0),
            'output_tokens': token_usage.get('output_tokens', 0),
            'total_tokens': token_usage.get('total_tokens', 0)
        }
    
    # 保存 tokens 使用量到数据库
    start_date = start_time.split(' ')[0]
    end_date = end_time.split(' ')[0]
    session_id = f"summary-{start_date}_to_{end_date}"
    
    try:
        def save_tokens():
            provider = LWBaseDataProvider()
            usage_data = {
                'input_tokens': tokens_usage['input_tokens'],
                'output_tokens': tokens_usage['output_tokens'],
                'total_tokens': tokens_usage['total_tokens'],
                'search_count': 0,
                'result_items_count': 0,
                'mode': 'summary'
            }
            provider.upsert_session_tokens_usage(session_id, usage_data)
        
        await asyncio.to_thread(save_tokens)
        logger.info(f"已保存多日总结的 tokens 使用量: {session_id}, total_tokens={tokens_usage['total_tokens']}")
    except Exception as e:
        logger.error(f"保存 tokens 使用量失败: {e}")
    
    return {
        'content': output.content,
        'tokens_usage': tokens_usage
    }

if __name__ == '__main__':
    async def main():
        result = await daily_summary(date="2025-12-28", options=["all"])
        print(result["content"])
        print(result["tokens_usage"])
    
    asyncio.run(main())

