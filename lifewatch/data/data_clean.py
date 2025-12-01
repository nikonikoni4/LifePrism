# 数据清洗 V2（实现完整功能）
# ==============================================================================
# 功能说明：
# 1. 时间戳标准化：将ActivityWatch API返回的UTC时间转换为用户本地时间 ✅ 已实现
# 2. 数据清洗：删除持续时间小于阈值的短暂活动 ✅ 已实现
# 3. AI数据生成：为AI分析准备结构化的pandas数据 🔄 正在实现
# ==============================================================================

import pandas as pd
from datetime import datetime
from typing import Dict, List,Any
import pytz
from lifewatch.storage.database_manager import get_app_purpose_category
from lifewatch.data.get_activitywatch_data import get_window_events
from lifewatch.utils import is_multipurpose_app
from lifewatch import config
def convert_utc_to_local(utc_timestamp_str: str, target_tz: str ) -> str:
    """
    将ActivityWatch API返回的UTC时间戳转换为用户本地时间
    
    Args:
        utc_timestamp_str: API返回的UTC时间戳，格式如 "2025-11-19T08:14:52.000000+00:00"
        target_tz: 目标时区，默认为用户设置时区
    
    Rlifewatch.utils.py.utilss:
        str: 格式化后的本地时间字符串，格式如 "2025-11-19 16:14:52"
    
    Note:
        - 输入：ISO 8601格式的UTC时间戳
        - 输出：用户本地时区的格式化时间字符串
        - 保持毫秒级时间精度
    """
    try:
        # 1. 解析ISO 8601格式的UTC时间戳
        # 处理Z后缀（表示UTC）并替换为+00:00
        clean_timestamp = utc_timestamp_str.replace('Z', '+00:00')
        dt_utc = datetime.fromisoformat(clean_timestamp)
        
        # 2. 转换为用户指定的时区
        target_timezone = pytz.timezone(target_tz)
        dt_local = dt_utc.astimezone(target_timezone)
        
        # 3. 格式化输出，保持毫秒精度
        return dt_local.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        # 错误处理：如果解析失败，返回原始字符串并记录警告
        print(f"⚠️  时间戳转换失败: {utc_timestamp_str} -> {str(e)}")
        return utc_timestamp_str



def clean_activitywatch_data(raw_events: List[Dict[str, Any]],app_purpose_category_df:pd.DataFrame) :
    """
    完整的数据清洗流程：时间戳标准化 + 短活动过滤 + 数据库查询优化（返回pandas DataFrame）
    
    Args:
        raw_events: ActivityWatch原始事件数据
        app_purpose_category_df: 应用目的分类DataFrame，包含app_purpose_category_df表中的数据
    Returns:
        pd.DataFrame: 清洗后的事件数据DataFrame
        pd.DataFrame: 待分类应用数据DataFrame
        set: 待分类应用集合
    
    Process:
        1. 数据库初始化：读取app_purpose_category_df表已有应用
        2. 时间戳标准化：UTC -> 本地时间
        3. 短活动过滤：删除 < 60秒的事件
        4. 数据库查询：如果应用已存在分类数据，直接获取
    """
    print(f"🧹 开始数据清洗流程...")
    print(f"📥 原始数据: {len(raw_events)} 个事件")
    
    lower_bound = config.CLEAN_LOWER_BOUND
    removed_count = 0  # 初始化被过滤事件计数
    filtered_events_list = [] # 过滤后的事件列表
    # 已添加的待分类应用
    apps_to_classify_set = set() # 已添加的待分类应用集合 用于判断是否已经添加
    title_to_classify_set = set() # 已添加的待分类title集合 用于判断是否已经添加
    apps_to_classify_list = [] # 待分类应用列表 中间变量
    # 已经分类的应用（单一用途app和多用途title）
    if app_purpose_category_df is not None and not app_purpose_category_df.empty:
        # 获取已存在的单一用途的应用集合
        categorized_single_purpose_apps = set(app_purpose_category_df['app'].unique())
        # 获取非单一用途的title集合
        categorized_mutilpurpose_titles = set(app_purpose_category_df[app_purpose_category_df['is_multipurpose_app'] == 1]['title'].unique())
    else:
        categorized_single_purpose_apps = set()
        categorized_mutilpurpose_titles = set()
    
    # output - 使用新的字典格式配置
    filtered_events_df = pd.DataFrame(columns=config.USER_APP_BEHAVIOR_LOG['keys'])
    apps_to_classify_df = pd.DataFrame(columns=config.APP_PURPOSE_CATEGORY['keys'])

    for event in raw_events:
            duration = event.get('duration', 0)
            if duration >= lower_bound:
                # 转换时间戳
                local_timestamp = convert_utc_to_local(event.get('timestamp', ''),config.LOCAL_TIMEZONE)
                # 获得应用名称
                app_name = event.get('data', {}).get('app', None)
                
                if app_name:
                    app_name = app_name.lower().strip().split('.exe')[0]
                    # 获得title
                    title = event.get('data', {}).get('title', None)
                    if title:
                        title = title.split('和另外')[0].strip()
                    # 初始化事件数据
                    filtered_event = {
                        'id': event.get('id', ''),
                        'timestamp': local_timestamp,
                        'duration': duration,
                        'app': app_name,
                        'title': title,
                        'class_by_default': None,
                        'class_by_goals': None,
                        'is_multipurpose_app': is_multipurpose_app(app_name)
                    }
                    # 1.app已经被分类 且 app是单一用途的 ： 直接进行分类 
                    if app_name in categorized_single_purpose_apps and filtered_event['is_multipurpose_app']==0:
                        # 对于单一应用，直接从app_purpose_category_df获取分类数据
                        filtered_event['class_by_default'] = app_purpose_category_df[app_purpose_category_df['app'].str.lower() == app_name]['class_by_default'].values[0]
                        filtered_event['class_by_goals'] = app_purpose_category_df[app_purpose_category_df['app'].str.lower() == app_name]['class_by_goals'].values[0]
                        print(f"✅ 成功获取分类数据: 默认={filtered_event['class_by_default']}, 目标={filtered_event['class_by_goals']}")
                    # 2.app已经被分类 但 app是多用途的 ： 根据title进行分类
                    elif app_name in categorized_single_purpose_apps and filtered_event['title'].lower() in categorized_mutilpurpose_titles:
                        # 对于多应用场景，根据title匹配分类数据
                        filtered_event['class_by_default'] = app_purpose_category_df[app_purpose_category_df['title'].str.lower() == filtered_event['title'].lower()]['class_by_default'].values[0]
                        filtered_event['class_by_goals'] = app_purpose_category_df[app_purpose_category_df['title'].str.lower() == filtered_event['title'].lower()]['class_by_goals'].values[0]
                        print(f"✅ 成功获取分类数据: 默认={filtered_event['class_by_default']}, 目标={filtered_event['class_by_goals']}")
                   # 3. app未被分类，且是单一用途的 
                    elif filtered_event['is_multipurpose_app']==0 :
                        # 3.1 app未被分类，且是单一用途的 且 未被添加到待分类列表 ： 加入待分类列表
                        # 一个app只需要加入一次
                        if app_name not in apps_to_classify_set:
                            apps_to_classify_list.append({
                                    'app': app_name,
                                    'title': title,
                                    'is_multipurpose_app': filtered_event['is_multipurpose_app'],
                                    'app_description': None,
                                    'title_description': None,
                                    'class_by_default': None,
                                    'class_by_goals': None,
                                })
                            # 加入待分类应用集合
                            apps_to_classify_set.add(app_name)
                    # 4.app未被分类，且是多用途的 ： 加入待分类列表
                    elif filtered_event['is_multipurpose_app']==1:
                        apps_to_classify_set.add(app_name) # 加入待分类应用集合
                        # 4.1 app未被分类，且是多用途的 且 未被添加到待分类列表 ： 加入待分类列表
                        # 特别的，使用title进行分类，一个title添加一次，app名称可重复
                        if title not in title_to_classify_set:
                            apps_to_classify_list.append({
                                    'app': app_name,
                                    'title': title,
                                    'is_multipurpose_app': filtered_event['is_multipurpose_app'],
                                    'app_description': None,
                                    'title_description': None,
                                    'class_by_default': None,
                                    'class_by_goals': None,
                                })
                            # 加入待分类title集合
                            title_to_classify_set.add(title)
                    # 使用列表收集所有事件，最后一次性创建DataFrame
                    filtered_events_list.append(filtered_event)
            else:
                # 记录被过滤的短暂活动
                removed_count += 1
                print(f"🗑️  过滤短暂活动: {event.get('data', {}).get('app', 'Unknown')} - {duration:.1f}秒")
    # 一次性创建DataFrame，避免循环中的concat警告
    if filtered_events_list:
        filtered_events_df = pd.DataFrame(filtered_events_list)
    if apps_to_classify_list:
        apps_to_classify_df = pd.DataFrame(apps_to_classify_list) 
    print(f"📊 过滤统计: 总事件 {len(raw_events)} -> 保留 {len(filtered_events_df)} -> 删除 {removed_count}")
    print(f"📊 待分类统计: 总应用 {len(apps_to_classify_df)} -> 单用途 {len(apps_to_classify_df[apps_to_classify_df['is_multipurpose_app']==0])} -> 多用途 {len(apps_to_classify_df[apps_to_classify_df['is_multipurpose_app']==1])}")
    return filtered_events_df,apps_to_classify_df,apps_to_classify_set


if __name__ == "__main__":
    raw_events = get_window_events()
    # 测试数据库功能
    app_purpose_category_df = get_app_purpose_category()
    print(app_purpose_category_df)
    # 测试数据清洗功能
    filtered_events_df, apps_to_classify_df, apps_to_classify_set = clean_activitywatch_data(raw_events, app_purpose_category_df)
    print(filtered_events_df['app'])
    print(apps_to_classify_df['title'])