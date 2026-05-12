# 在这里编写定时任务的函数和时间间隔任务函数
# 任务包括：
# 定时任务，必须严格按照顺序执行：1）每天数据分类 2）截图分析(sync service中实现)，3）日记总结（在diary service中实现） ,
# 4）活动总结, 聊天记录总结，
# 定时任务的实现需要修改的其他地方：1. 前端不在自动发出更新请求，而是定时更新 2. 
from datetime import datetime, timedelta

from jinja2 import ext
from lifeprism.llm.session import session_manager, Session
from lifeprism.utils import get_logger
from lifeprism.llm.agent.tools.lifeprismsystem import query_user_activity_summary,query_user_mood
import json
from lifeprism.llm.session import Session, session_manager,ChatHistoryManager
from lifeprism.llm.bus import InboundMessage, bus,MessageType,OutboundMessage
from lifeprism.config import settings
import asyncio
from lifeprism.utils.exceptions import ExternalServiceError
logger = get_logger(__name__)





async def summary_activities(activities : str)->str:
    ACTIVITY_SUMMARY_SYSTEM_PROMPT = """## task
你需要依据用户数据总结用户今天都做了什么

## 数据说明
1. 电脑使用统计：用户电脑高活动使用区间以及区间内的分类
2. 用户自定义行为备注：用户自行记录的时间备注，可信度更高
3. AI分析行为备注 ： 依据电脑在高密度活动区间的截图进行分析的数据，仅供参考
4. 用户待办事项 ：今日打算做的事情

## 总结重点
1. 以用户自定义行为备注和AI分析行为备注

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

# 1. 定时总结日记，更新behavior.md 和 recent_status.md
async def update_memory(date: str):
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
    chat_history_to_dream = history_manager.get_histories_to_dream() # 这里先不在进行二次处理，直接放进behavior

    # 获取心情数据，并总结
    
    



 

async def update_today_activity(start_time:str,end_time:str):
    """
    更新今天activity
    
    """



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
        history_manager = ChatHistoryManager()
        for content in all_results:
            history_manager.add_content(content)
        history_manager.save_history()

if __name__ == "__main__":
    print(datetime.now().strftime("%Y-%m-%d"))