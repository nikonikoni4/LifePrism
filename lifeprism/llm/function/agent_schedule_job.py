# 在这里编写定时任务的函数和时间间隔任务函数
# 任务包括：
# 定时任务，必须严格按照顺序执行：1）每天数据分类 2）截图分析(sync service中实现)，3）日记总结（在diary service中实现） ,
# 4）活动总结, 聊天记录总结，
# 定时任务的实现需要修改的其他地方：1. 前端不在自动发出更新请求，而是定时更新 2. 
from ast import In
from datetime import datetime, timedelta

from jinja2 import ext
import lifeprism
from lifeprism.llm.session import session_manager, Session
from lifeprism.utils import get_logger
from lifeprism.llm.agent.tools.lifeprismsystem import query_user_activity_summary,query_user_mood
import json
from lifeprism.llm.session import Session, session_manager,ChatHistoryManager
from lifeprism.llm.bus import InboundMessage, bus,MessageType,OutboundMessage
from lifeprism.config import settings
import asyncio
from lifeprism.utils.exceptions import ExternalServiceError
from lifeprism.llm.utils.md_os import write_date_md,extract_date_logs_from_file,read_md
logger = get_logger(__name__)

async def summary_activities(activities : str)->str:
    ACTIVITY_SUMMARY_SYSTEM_PROMPT = """## task
你需要依据用户数据总结用户今天都做了什么

## 数据说明
1. 电脑使用统计：用户电脑高活动使用区间以及区间内的分类
2. 用户自定义行为备注：用户自行记录的时间备注，可信度更高
3. AI分析行为备注 ： 依据电脑在高密度活动区间的截图进行分析的数据，仅供参考
4. 用户待办事项 ：今日打算做的事情

## 总结内容
1. 今日概览：以用户自定义备注和AI分析行为为核心，辅以待办事项，全面回顾今日动态。
2. 电脑使用统计：简要概括电脑使用情况，需列出各分类的时长与占比。

## 核心原则
1. 保持客观，不推论，不猜测
2. 保持简洁

"""
    
    if activities:
        result = await bus.send(
            InboundMessage(
                MessageType.DREAM_TASK,
                extra = {"system_prompt":ACTIVITY_SUMMARY_SYSTEM_PROMPT}
            )
        )
        if result.response and result.response.content:
            return result.response.content
        else:
            logger.error(f"活动总结llm返回数据错误,{result}")
            raise ExternalServiceError(f"活动总结llm返回数据错误,{result}")
    else:
        logger.warning("没有总结数据")
        return "无今日活动数据"

def get_mood_data(start_time: str, end_time: str) -> str:
    """获取心情数据

    Args:
        start_time: 开始时间，格式为 'YYYY-MM-DD HH:MM:SS'
        end_time: 结束时间，格式为 'YYYY-MM-DD HH:MM:SS'

    Returns:
        str: 格式化的心情数据字符串
    """
    # 将时间格式从 'YYYY-MM-DD HH:MM:SS' 转换为 'YYYY-MM-DD'
    start_date = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')
    end_date = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').strftime('%Y-%m-%d')

    # 调用 query_user_mood 获取心情数据
    mood_data = query_user_mood(start_date, end_date)

    return mood_data

async def summary_moods(mood_data: str) -> str:
    """总结心情数据

    Args:
        mood_data: 心情数据字符串

    Returns:
        str: 心情总结内容
    """
    MOOD_SUMMARY_SYSTEM_PROMPT = """## 任务
你需要对用户的心情记录进行客观总结。

## 数据说明
每条心情记录包含：
1. 时间：心情记录的时间
2. 心情分数：用户的心情评分（1-10分）
3. 内容：用户对心情的描述
4. 影响因素：导致该心情的因素

## 总结要求
对每条心情记录，按以下结构进行客观描述（有则写，无则跳过）：
1. 事件经过：简单描述发生了什么
2. 情绪诱因：是什么让这个情绪发生的
3. 情绪本身：用户的情绪状态是什么
4. 用户反应：面对这个情绪，用户的反应是什么

## 核心原则
1. 不要推敲或猜测
2. 仅从客观角度描述，不带任何评价
3. 如果某个组成部分数据中没有，就不写
4. 保持简洁
"""
    # 检查是否有心情数据
    if not mood_data or "无心情记录" in mood_data:
        logger.warning("没有心情数据")
        return "无心情记录"

    # 调用 LLM 进行总结
    result = await bus.send(
        InboundMessage(
            MessageType.DREAM_TASK,
            content=f"## 需要总结的心情数据\n{mood_data}",
            extra={"system_prompt": MOOD_SUMMARY_SYSTEM_PROMPT}
        )
    )

    # 处理返回结果
    if result.response and result.response.content:
        return result.response.content
    else:
        logger.error(f"心情总结 LLM 返回数据错误: {result}")
        raise ExternalServiceError(f"心情总结 LLM 返回数据错误: {result}")

async def update_memory(date:str,date_offset = 7)->None:
    """
    依据behavior.md更新记忆文档
    args : 
        date : 结束时间 YYYY-MM-DD, 包括这一天
        date_offset ： 时间偏移量，用于计算开始时间 date - date_offset
    """ 
    if date_offset<0:
        date_offset = 0
        logger.warning("date_offset为负")
    UPDATE_MEMPRY_SYSTEMP_PROMPT = f"""
    ## task
    你需要依据用户这几天的数据更新记忆文档
    ## 记忆文档更新规则
    ### 数据来源说明：behavior.md 
    记忆更新的数据来源，不用调用工具阅读，更新记忆时会主动传入
    1. 文本结构：
    ```md
    ## YYYY-MM-DD
    ### subtitle
    ```
    2. subtitle有4个：
        - 行为总结 ： 包含电脑使用数据总结和某天的行为总结（由电脑屏幕截图AI分析和用户自定义添加的行为数据综合总结而来）
        - 心情总结 ： 由用户添加的心情数据总结而来，注意心情数据仅反映特定时刻的情绪状态，并不具备长期代表性
        - 聊天记录总结 ： 由用户与AI对话的聊天记录总结而来
        - 日记总结 ： 由用户自己编写的日记总结而来 
    3. 数据说明：当日记总结表现出涉及到人生价值，世界观，强烈情绪和重要事件等比较重要的内容时，调用工具读取具体的日记内容了解详情。
    ### 更新recent_state.md规则
    1. 文本结构：
    ```md
    # recent_state.md
    ## 最近行为

    ## 最近心理状态

    ## 整体总结
    ```
    2. 写入规则
        - 最近行为：参考每天都行为总结，聊天数据，日记总结。
            1. 分析电脑使用数据趋势，各分类时间使用趋势
            2. 分析最近在进行的任务和所做的事情
        - 最近心理状态： 参考聊天数据，心情总结，日记总结或具体日记。
            心理状态编写分为两种情况：
            1. 数据足够充足：至少7天中有4天以上每天都有日记或2~3条心情记录或有情绪相关的聊天数据
            2. 数据不够充足：不满足情况1

            情况1编写：从情绪数据中总结出情绪变化趋势与用户最近情绪状态（日记越近，权重越大）
            情况2编写：由于数据量足够小，可以简单复述心情、日记或聊天数据，说明时间点和提示：由于用户数据量小，而单次心情数据仅反映特定时刻的情绪状态，并不具备长期代表性，无法进行心情总结，仅仅简单复述心情、日记或聊天数据
        - 整体总结
            结合行为和心理状态，简单客观的总结最近状态

    3. 编写规则：直接覆盖原recent_state.md文件

    ### 更新user.md
    1. 文本结构
    ```md
    # USER.md
    ## 基本信息
    1. 用户名称：
    2. 职业或专业方向：
    3. 爱好
    ## 社会关系
    ## 价值观
    ## 核心偏好（AI 回答风格、沟通偏好）
    ## 习惯与禁忌
    ```
    2. 什么时候更新user.md：当数据中涉及user.md文本结构的相关内容时进行更新
    3. 更新方法：1. 阅读user.md 2. 不要使用write_file工具覆写，使用edit_file修改
    ## 文件路径说明
    1. recent_state.md : {settings.lifeprism_data_path / "user/daily_data/recent_state.md"}
    2. user.md : {settings.lifeprism_data_path / "user/user.md"}
    3. 日记路径说明 : {settings.lifeprism_data_path / "dialy/YYYY/MM/YYYY-MM-DD.md"} 比如2026-04-01日记位置为:{settings.lifeprism_data_path / "dialy/2026/04/2026-04-01.md"}
    """
    # 获取behavior.md 
    end_time = datetime.strptime(date,"%Y-%m-%d")
    start_time = end_time - timedelta(days = date_offset)
    start_date = start_time.strftime("%Y-%m-%d")
     
    behavior_md = extract_date_logs_from_file(settings.lifeprism_data_path / "user/daily_data/behavior.md",start_date,date)
    # 获取当前的recent_state.md
    recent_state_md = read_md(settings.lifeprism_data_path / "user/daily_data/recent_state.md")
    
    # 构建content
    content = f"""
    你需要帮我更新recent_state.md 文档，如果涉及到user.md相关内容,也需要更新user.md文档。
    ## 近7天的behavior.md内容
    {behavior_md}
    ## 之前的recent_state.md内容仅作参考
    {recent_state_md}
    """
    await bus.send(
        InboundMessage(
            MessageType.DREAM_TASK,
            content=content,
            extra = {'system_prompt':UPDATE_MEMPRY_SYSTEMP_PROMPT}
        )
    )
    



# 1. 定时总结日记，更新behavior.md 和 recent_status.md
async def dreaming(date: str):
    """更新用户记忆
    从数据库中获取用户最近的聊天记录，查看最近一天的心情变化和日记内容，总结为behavior.md 和 recent_status.md 或其他记忆文件
    
    Args:
        date (str): 要总结的日期，格式为 '%Y-%m-%d'
        总结时间说明 date 04:00:00 ~ date + 1 04:00:00
    """
    # 获取用户活动, 总结用户活动
    next_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    start_time = date + " 04:00:00"
    end_time = next_date + " 04:00:00"
    activities = query_user_activity_summary(set(["computer_usage_stats", "user_behavior_notes", "ai_behavior_notes"]),start_time,end_time)
    activities_summary_content = summary_activities(activities)
    # 获取未处理的聊天记录总结
    history_manager = ChatHistoryManager()
    # 获取昨天history 数据
    # 这里潜在的问题是，process_session_message处理的时间是3天以内的
    # 也就是说，今天的chat_history,json可能包含之前几天的聊天记录内容。
    # 这里不进行区别，时间尺度没有那么重要，不进行区别
    
    # 获取心情数据，并总结
    mood_data = get_mood_data(start_time, end_time)
    mood_summary_content = await summary_moods(mood_data)

    # 将内容写入behavior.md
    path = settings.lifeprism_data_path / "user/daily_data/behavior.md"
    date = datetime.now().strftime('%Y-%m-%d')
    # 日记总结是单独的函数，在该函数调用之前执行
    write_date_md(path,date,activities_summary_content,"行为总结")
    write_date_md(path,date,chat_history_to_dream,"聊天总结")
    write_date_md(path,date,mood_summary_content,"心情总结")
    

    # 总结内容到recent_state.md和user.md
    update_memory(date)

 




# 2. 时间间隔任务：

async def extract_from_chat_messages(session:Session)->str|None:
    """从历史消息中提取有效信息"""
    summary_system_prompt = """## task 
    你需要从用户的聊天内容中提取有用信息
    ## 提取内容
    1. 非工具类查询或记录的事件，需要确认事情发生的时间(避免时间逻辑上出错)，发生的经过，用户的反应
    2. 对于情绪类事件，（如果有点话）需要记录诱发原因，用户的反应，用户的心情
    3. 用户偏好
    提取说明：对于event中的非工具累时间和情绪累事件提取组成部分（比如，用户描述事情发生的时间，诱发原因等）是如果有才记录，如果没有则不记录
    ## 不要提取的内容
    纯工具查询或记录过程不要提取
    ## 输出说明
    1. 若有满足提取内容的消息则进行提取
    2. 若没有满足提取内容的消息，则输出：无可提取内容
    """
    # 将message[获取所有消息记录中长度不等于last_processed_loc的消息:]转化为str
    message = session.messages[session.last_processed_loc]
    summary_raw_content = json.dumps(message)
    result:OutboundMessage= await bus.send(InboundMessage(
        type = MessageType.DREAM_TASK,
        content = f"## 需要总结的内容 \n {summary_raw_content}",
        extra={"system_prompt":summary_system_prompt}
    ))
    session.last_processed_loc = len(session.messages)
    session_manager.save_session(session)
    
    if result.response and result.response.content and result.response.content  != "无可提取内容" :
        return result.response.content
    return None

def format_chat_history(history: list[dict]) -> str:
    """
    格式化聊天历史记录为 Markdown 格式

    Args:
        history: 聊天历史记录列表，每项包含 content 字段

    Returns:
        str: 格式化后的 Markdown 字符串，如果没有有效内容则返回空字符串

    Example:
        >>> history = [
        ...     {"timestamp": "2026-05-12T14:30:45", "content": "讨论了异步编程"},
        ...     {"timestamp": "2026-05-12T15:45:30", "content": "设计数据库方案"}
        ... ]
        >>> print(format_chat_history(history))
        1. 讨论了异步编程

        2. 设计数据库方案
    """
    if not history:
        return ""

    formatted_history = []
    index = 1
    for item in history:
        content = item.get("content", "")
        if content:
            formatted_history.append(f"{index}. {content}")
            index += 1

    return "\n\n".join(formatted_history) if formatted_history else ""

async def process_session_message(days_offset :int = 3):
    """
    将当前的session中没有提取的会话进行提取，将结果放入chat_history.json中
    每隔2h执行一次
    args :
        days_offset : 处理日期限制，旧session不在处理

    """
    # 1. 加载session meta,获取需要处理的消息
    _session_to_process = []
    session_list = session_manager.show_session_list()
    for session_id in session_list:
        meta_data = session_manager.get_session_metadata(session_id)
        if meta_data.get("message_len",None):
            message_len = meta_data["message_len"]
            last_processed_loc = meta_data.get("last_processed_loc",0)
            update_at = datetime.fromisoformat(meta_data.get("update_at", datetime.now().isoformat()))
            # 判断是否有未处理消息 且 update_at > 今天 - days_offset
            if message_len > last_processed_loc and update_at > datetime.now() - timedelta(days=days_offset):
                _session_to_process.append(session_id)
    # 处理消息（分组处理，每组最多10个）
    history_manager = ChatHistoryManager()
    if _session_to_process:
        BATCH_SIZE = 10
        all_results = []

        # 分组处理
        for i in range(0, len(_session_to_process), BATCH_SIZE):
            batch = _session_to_process[i:i + BATCH_SIZE]
            batch_results = await asyncio.gather(
                *[extract_from_chat_messages(session_id) for session_id in batch]
            )
            all_results.extend(batch_results)

        # 删除加载的session_id
        for session_id in _session_to_process:
            session_manager.remove_from_cache(session_id)

        # 创建history

        for content in all_results:
            history_manager.add_content(content)
        history_manager.save_history()
    # 将chat_history 更新到behavior
    history = history_manager.get_histories_to_dream()
    if history:
        history_content = format_chat_history(history)
        if history_content:
            write_date_md(
                settings.lifeprism_data_path / "user/daily_data/behavior.md",
                datetime.now().strftime('%Y-%m-%d'),
                history_content,
                "聊天记录总结"
            )
            # 更新 last_processed_time
            history_manager.save_history(datetime.now())

if __name__ == "__main__":
    # 测试 format_chat_history 函数
    print("=== 测试 format_chat_history ===\n")

    # 测试用例1：正常数据
    test_history_1 = [
        {"timestamp": "2026-05-12T14:30:45", "content": "用户询问了关于 Python 异步编程的问题"},
        {"timestamp": "2026-05-12T15:45:30", "content": "讨论了数据库设计方案"},
        {"timestamp": "2026-05-12T16:20:15", "content": "用户分享了今天的工作进展"}
    ]
    result_1 = format_chat_history(test_history_1)
    print("测试用例1 - 正常数据:")
    print(result_1)
    print("\n" + "="*50 + "\n")

    # 测试用例2：空列表
    test_history_2 = []
    result_2 = format_chat_history(test_history_2)
    print("测试用例2 - 空列表:")
    print(f"结果: '{result_2}' (应该为空字符串)")
    print("\n" + "="*50 + "\n")

    # 测试用例3：包含缺失字段的数据
    test_history_3 = [
        {"timestamp": "2026-05-12T14:30:45", "content": "有效内容"},
        {"timestamp": "2026-05-12T15:45:30"},  # 缺少 content
        {"content": "缺少时间戳的内容（但仍然有效）"},  # 缺少 timestamp
        {"timestamp": "2026-05-12T16:20:15", "content": "另一条有效内容"}
    ]
    result_3 = format_chat_history(test_history_3)
    print("测试用例3 - 包含缺失字段:")
    print(result_3)
    print("\n" + "="*50 + "\n")

    # 测试用例4：只有 content 字段
    test_history_4 = [
        {"content": "第一条内容"},
        {"content": "第二条内容"},
        {"content": "第三条内容"}
    ]
    result_4 = format_chat_history(test_history_4)
    print("测试用例4 - 只有 content 字段:")
    print(result_4)
    print("\n" + "="*50 + "\n")

    print("所有测试完成！")