from lifewatch.llm.llm_classify.schemas.classify_shemas import classifyState,LogItem,Goal,AppInFo,MultiNodeResult
from lifewatch.llm.llm_classify.utils.create_model import create_ChatTongyiModel
from langgraph.graph import StateGraph, START, END
from langchain_core.messages import SystemMessage, HumanMessage
from lifewatch.llm.llm_classify.providers.lw_data_providers import lw_data_providers
import json
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# step 0 : 创建模型
chat_model = create_ChatTongyiModel()

# step 1: 获取所有app的描述
def get_app_description(state: classifyState):
    # 判断那些app没有描述
    app_to_web_search = []
    app_titles_map = {}  # 存储每个app对应的titles样本
    for app, app_info in state.app_registry.items():
        if app_info.description == None or app_info.description == "":
            app_to_web_search.append(app)
            # 收集该app的titles信息（如果有的话）
            if app_info.titles:
                app_titles_map[app] = app_info.titles[:2]  # 最多取1个title样本
    if app_to_web_search:
        # 构建包含titles信息的软件列表描述
        app_info_list = []
        for app in app_to_web_search:
            if app in app_titles_map:
                app_info_list.append(f"{app} (窗口标题示例: {app_titles_map[app]})")
            else:
                app_info_list.append(app)
        
        system_message = SystemMessage(content="""
        你是一个软件程序识别专家。你的任务是通过 web 搜索识别软件应用程序，并提供准确、精炼的描述。
        **输入说明：**
        - 软件列表可能包含窗口标题示例，格式为：软件名 (窗口标题示例: [...])
        - 以web搜索为主,title信息为辅
        **输出要求：**
        - 返回 JSON 对象格式
        - 每个软件用一句话（不超过20字）描述核心功能
        - 描述要准确、专业，突出主要用途
        - 如果搜索后仍无法确定，返回 None
        """)
        user_message = HumanMessage(content=f"""
        请通过 web 搜索识别以下软件应用程序，并用一句简短的话描述每个软件的核心功能和用途。
        参考窗口标题可以帮助你更准确地理解软件用途。
        待识别的软件列表：
        {app_info_list}
        返回格式JSON（注意：key只需要软件名称，不包含标题信息）：
            {{"<软件名称>": "<精炼的功能描述>"}}
        示例：
        输入: ["weixin (窗口标题示例: ['张三', '工作群'])", "vscode"]
        输出: {{"weixin": "腾讯开发的即时通讯和社交平台","vscode": "微软开发的轻量级代码编辑器"}}
        """)
        messages = [system_message, user_message]
        
        # 重试机制
        app_description = None
        for attempt in range(3):
            try:
                results = chat_model.invoke(messages)
                
                # 提取 token 使用情况
                token_usage = results.response_metadata.get('token_usage', {})
                # 累加或更新 token usage (这里简单覆盖，或者你可以选择累加)
                if 'get_app_description' not in state.node_token_usage.keys():
                    state.node_token_usage['get_app_description'] = token_usage
                else:
                    for key,_  in token_usage.items():
                        state.node_token_usage['get_app_description'][key] += token_usage[key]
                app_description = json.loads(results.content)
                break # 解析成功，跳出循环
            except Exception as e:
                print(f"get_app_description 输出格式错误 (第 {attempt + 1} 次尝试), 错误: {e}")
                if attempt == 2: # 最后一次尝试也失败
                    return state

        if not app_description:
            return state

        for app in app_to_web_search:
            desc = app_description.get(app, None)
            if desc:
                # 更新 description，保持 is_multipurpose titles不变
                state.app_registry[app] = AppInFo(
                    description=desc,
                    is_multipurpose=state.app_registry[app].is_multipurpose,
                    titles=state.app_registry[app].titles
                )
        # 更新数据库
        lw_data_providers.update_app_description([
            {"app": app, "app_description": state.app_registry[app].description}
            for app in app_to_web_search
        ])
    print(f"get_app_description token usage: {state.node_token_usage['get_app_description']}")
    return state

if __name__ == "__main__":
    from lifewatch.llm.llm_classify.classify.data_loader import get_real_data,filter_by_duration,deduplicate_log_items
    
    def get_state(hours = 36) -> classifyState:
        state = get_real_data(hours=hours)
        state = filter_by_duration(state, min_duration=60)
        state = deduplicate_log_items(state)
        print(f"\n去重后的日志（前10条）:")
        for item in state.log_items[:10]:
            multipurpose = "多用途" if state.app_registry[item.app].is_multipurpose else "单用途"
            print(f"  {item.app} ({multipurpose}) | {item.title} | {item.duration}s")
        
        # 测试过滤功能
        print(f"\n测试过滤功能（只保留 duration >= 60 秒的记录）:")
        print(f"  - 过滤后 log_items: {len(state.log_items)} 条")
        print(f"  - 过滤后 app_registry: {len(state.app_registry)} 个应用")
        return state
    state = get_state(hours=24)
    state = get_app_description(state)