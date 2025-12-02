# 主流程
from lifewatch import config
from lifewatch.storage.database_manager import DatabaseManager
from lifewatch.data.get_activitywatch_data import ActivityWatchTimeRangeAccessor
from lifewatch.data.data_clean import clean_activitywatch_data
from lifewatch.crawler.app_description_fetching import AppDescriptionFetcher
from lifewatch.llm.llm_classify import call_ollama_llm_api,process_and_fill_dataframe,generate_llm_batches
from lifewatch.llm.ollama_client import OllamaClient
import pandas as pd

#  # api_key="sk-b6f3052f6c4f46a9a658bfc020d90c3f",base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
#     llm_client = LLMClient(
#         api_key="sk-b6f3052f6c4f46a9a658bfc020d90c3f",
#         base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
#     )
#     response = llm_client.sent_message_no_stream([{"role": "user", "content": prompt}],enable_thinking=False,enable_search=True)
#     llm_client.print_result_non_stream(response)

if __name__ == "__main__":
    # 判断数据库是否存在，不存在则创建数据库和数据表 app_purpose_category和user_app_behavior_log
    db_manager = DatabaseManager(config.DB_PATH)
    
    # 获取数据
    aw_accessor = ActivityWatchTimeRangeAccessor(
        base_url=config.AW_URL_CONFIG["base_url"],
        local_tz=config.LOCAL_TIMEZONE
    )
    user_behavior_logs = aw_accessor.get_window_events(hours=1) # 测试1h
    
    # 读取app_purpose_category数据表
    app_purpose_category_df = db_manager.load_app_purpose_category()
    
    print(app_purpose_category_df)
    
    # 数据清洗，返回过滤后的事件和待分类的应用
    filtered_events_df, apps_to_classify_df,apps_to_classify_set= clean_activitywatch_data(user_behavior_logs, app_purpose_category_df)
    print(apps_to_classify_set)
    print(len(apps_to_classify_df))

    



    # 查询app的描述
    app_description_fetcher = AppDescriptionFetcher("BaiDuBrowerCrawler")
    app_descriptions_dict = app_description_fetcher.fetch_batch_app_descriptions(apps_to_classify_set)
    print(app_descriptions_dict)
    # 讲app_description添加到apps_to_classify_df
    apps_to_classify_df['app_description'] = apps_to_classify_df['app'].map(app_descriptions_dict)


    print(app_descriptions_dict)
    
    # 遍历apps_to_classify_df
    for index, row in apps_to_classify_df.iterrows():
        app_name = row['app']
        if app_name in app_descriptions_dict:
            apps_to_classify_df.at[index, 'app_description'] = app_descriptions_dict[app_name]
        else:
            apps_to_classify_df.at[index, 'app_description'] = '无描述'
    print(apps_to_classify_df)
    # 调用ollama_llm_api分类
    client = OllamaClient(config.OLLAMA_BASE_URL)
    processed_df = process_and_fill_dataframe(
        apps_to_classify_df, 
        mock_llm_func=lambda batch: call_ollama_llm_api(batch,client,config.CATEGORY_A,config.CATEGORY_B))
    print(processed_df)
    # 保存到数据库
    db_manager.save_app_purpose_category(processed_df)
    # 赋值类型给filtered_events_df
    print("开始将分类结果赋值给filtered_events_df...")
    
    # 创建processed_df的查找字典，提高匹配效率
    processed_dict = {}
    for _, row in processed_df.iterrows():
        app = row['app']
        title = row.get('title', '')
        is_multipurpose = row.get('is_multipurpose_app', 0)
        
        if is_multipurpose == 0:
            # 单用途应用，以app为键
            processed_dict[('single', app.lower())] = {
                'class_by_default': row.get('class_by_default'),
                'class_by_goals': row.get('class_by_goals')
            }
        else:
            # 多用途应用，以(app, title)为键
            processed_dict[('multi', app.lower(), title.lower() if title else '')] = {
                'class_by_default': row.get('class_by_default'),
                'class_by_goals': row.get('class_by_goals')
            }
    
    # 遍历filtered_events_df进行赋值
    assigned_count = 0
    for index, row in filtered_events_df.iterrows():
        app = row['app']
        title = row.get('title', '')
        is_multipurpose = row.get('is_multipurpose_app', 0)
        
        if is_multipurpose == 0:
            # 单用途应用匹配：只匹配app
            key = ('single', app.lower())
            if key in processed_dict:
                classification = processed_dict[key]
                filtered_events_df.at[index, 'class_by_default'] = classification['class_by_default']
                filtered_events_df.at[index, 'class_by_goals'] = classification['class_by_goals']
                assigned_count += 1
                print(f"✅ 单用途应用分类成功: {app} -> {classification['class_by_default']}/{classification['class_by_goals']}")
        else:
            # 多用途应用匹配：匹配app和title
            key = ('multi', app.lower(), title.lower() if title else '')
            if key in processed_dict:
                classification = processed_dict[key]
                filtered_events_df.at[index, 'class_by_default'] = classification['class_by_default']
                filtered_events_df.at[index, 'class_by_goals'] = classification['class_by_goals']
                assigned_count += 1
                print(f"✅ 多用途应用分类成功: {app} - {title} -> {classification['class_by_default']}/{classification['class_by_goals']}")
    
    print(f"分类结果赋值完成！共赋值了 {assigned_count} 条记录")
    print(f"filtered_events_df中总记录数: {len(filtered_events_df)}")
    print(f"未分类记录数: {len(filtered_events_df[filtered_events_df['class_by_default'].isna()])}")
    
    





