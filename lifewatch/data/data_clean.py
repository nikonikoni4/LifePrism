"""
功能介绍: 接受aw的数据,依据单和多用途提取需要识别的item(重复内容跳过)
TODO: 合并成一个单独的类
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import pytz
from lifewatch.llm.llm_classify.providers.lw_data_providers import get_app_purpose_category
from lifewatch.data.aw_data_reader import get_window_events
from lifewatch.utils import is_multipurpose_app
from lifewatch import config
from lifewatch.config.database import get_table_columns
from lifewatch.llm.llm_classify import AppInFo, LogItem, classifyState
from lifewatch.utils import get_logger
logger = get_logger(__name__)


def create_dict_from_table_columns(table_name: str, values: dict = None) -> dict:
    """
    根据数据库表配置动态创建字典
    
    Args:
        table_name: 表名，用于获取列配置
        values: 可选的字段值字典，未提供的字段默认为None
    
    Returns:
        dict: 包含所有表列的字典，未提供的值为None
    """
    columns = get_table_columns(table_name)
    result = {col: None for col in columns}
    if values:
        for key, value in values.items():
            if key in result:
                result[key] = value
    return result


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
        # print(f"⚠️  时间戳转换失败: {utc_timestamp_str} -> {str(e)}")
        logger.warning(f"时间戳转换失败: {utc_timestamp_str} -> {str(e)}")
        return utc_timestamp_str




def clean_activitywatch_data(raw_events: List[Dict[str, Any]], app_purpose_category_df: pd.DataFrame) -> Tuple[pd.DataFrame, classifyState]:
    """
    完整的数据清洗流程：时间戳标准化 + 短活动过滤 + 数据库查询优化
    
    Args:
        raw_events: ActivityWatch原始事件数据
        app_purpose_category_df: 应用目的分类DataFrame，包含app_purpose_category_df表中的数据
    
    Returns:
        Tuple[pd.DataFrame, classifyState]:
            - filtered_events_df: 清洗后的事件数据DataFrame
            - classify_state: 包含待分类应用信息的classifyState对象
                - app_registry: 应用注册表 {app: AppInFo}
                - log_items: 待分类的日志项列表
                - result_items: 初始为None
    
    Process:
        1. 数据库初始化：读取app_purpose_category_df表已有应用
        2. 时间戳标准化：UTC -> 本地时间
        3. 短活动过滤：删除 < 60秒的事件
        4. 数据库查询：如果应用已存在分类数据，直接获取
        5. 构建classifyState：收集待分类应用的信息
    """
    logger.info(f"🧹 开始数据清洗流程...")
    logger.info(f"📥 原始数据: {len(raw_events)} 个事件")
    
    lower_bound = config.CLEAN_LOWER_BOUND
    removed_count = 0  # 初始化被过滤事件计数
    filtered_events_list = []  # 过滤后的事件列表
    
    # 已添加的待分类应用
    apps_to_classify_set = set()  # 已添加的待分类应用集合 用于判断是否已经添加
    title_to_classify_set = set()  # 已添加的待分类title集合 用于判断是否已经添加
    
    # classifyState 组件
    app_registry: Dict[str, AppInFo] = {}  # 应用注册表
    log_items: List[LogItem] = []  # 待分类日志项
    log_item_id_counter = 0  # LogItem ID 计数器
    
    # 已经分类的应用（单一用途app和多用途title）
    if app_purpose_category_df is not None and not app_purpose_category_df.empty:
        # 获取已存在的单一用途的应用集合
        categorized_single_purpose_apps = set(app_purpose_category_df['app'].unique())
        # 获取非单一用途的title集合
        categorized_mutilpurpose_titles = set(app_purpose_category_df[app_purpose_category_df['is_multipurpose_app'] == 1]['title'].unique())
    else:
        categorized_single_purpose_apps = set()
        categorized_mutilpurpose_titles = set()
    
    # output - 使用动态字典格式配置
    filtered_events_df = pd.DataFrame(columns=get_table_columns('user_app_behavior_log'))

    for event in raw_events:
        duration = event.get('duration', 0)
        if duration >= lower_bound:
            # 转换时间戳
            local_start_time = convert_utc_to_local(event.get('timestamp', ''), config.LOCAL_TIMEZONE)
            # 计算结束时间
            start_dt = datetime.strptime(local_start_time, '%Y-%m-%d %H:%M:%S')
            end_dt = start_dt + timedelta(seconds=duration)
            local_end_time = end_dt.strftime('%Y-%m-%d %H:%M:%S')
            # 获得应用名称
            app_name = event.get('data', {}).get('app', None)
            
            if app_name:
                app_name = app_name.lower().strip().split('.exe')[0]
                # 获得title
                title = event.get('data', {}).get('title', None)
                if title:
                    title = title.split('和另外')[0].strip()
                
                is_multipurpose = is_multipurpose_app(app_name)
                
                # 使用动态字典创建事件数据
                filtered_event = create_dict_from_table_columns('user_app_behavior_log', {
                    'id': event.get('id', ''),
                    'start_time': local_start_time,
                    'end_time': local_end_time,
                    'duration': duration,
                    'app': app_name,
                    'title': title,
                    'is_multipurpose_app': 1 if is_multipurpose else 0
                })
                
                # 1.app已经被分类 且 app是单一用途的 ： 直接进行分类 
                if app_name in categorized_single_purpose_apps and not is_multipurpose:
                    # 对于单一应用，直接从app_purpose_category_df获取分类数据
                    filtered_event['category'] = app_purpose_category_df[app_purpose_category_df['app'].str.lower() == app_name]['category'].values[0]
                    filtered_event['sub_category'] = app_purpose_category_df[app_purpose_category_df['app'].str.lower() == app_name]['sub_category'].values[0]
                    logger.debug(f"✅ 成功获取分类数据: 默认={filtered_event['category']}, 目标={filtered_event['sub_category']}")
                
                # 2.app已经被分类 但 app是多用途的 ： 根据title进行分类
                elif app_name in categorized_single_purpose_apps and title and title.lower() in categorized_mutilpurpose_titles:
                    # 对于多应用场景，根据title匹配分类数据
                    filtered_event['category'] = app_purpose_category_df[app_purpose_category_df['title'].str.lower() == title.lower()]['category'].values[0]
                    filtered_event['sub_category'] = app_purpose_category_df[app_purpose_category_df['title'].str.lower() == title.lower()]['sub_category'].values[0]
                    logger.debug(f"✅ 成功获取分类数据: 默认={filtered_event['category']}, 目标={filtered_event['sub_category']}")
                
                # 3. app未被分类，且是单一用途的 
                elif not is_multipurpose:
                    # 3.1 app未被分类，且是单一用途的 且 未被添加到待分类列表 ： 加入待分类列表
                    # 一个app只需要加入一次
                    if app_name not in apps_to_classify_set:
                        # 添加到 app_registry
                        app_registry[app_name] = AppInFo(
                            description="",  # 待LLM填充
                            is_multipurpose=False,
                            titles=[title]
                        )
                        apps_to_classify_set.add(app_name)
                    
                    # 创建 LogItem 并添加到 log_items
                    log_items.append(LogItem(
                        id=log_item_id_counter,
                        app=app_name,
                        duration=int(duration),
                        title=title
                    ))
                    log_item_id_counter += 1
                
                # 4.app未被分类，且是多用途的 ： 加入待分类列表
                elif is_multipurpose:
                    # 确保 app 在 registry 中
                    if app_name not in apps_to_classify_set:
                        app_registry[app_name] = AppInFo(
                            description="",  # 待LLM填充
                            is_multipurpose=True,
                            titles=[]
                        )
                        apps_to_classify_set.add(app_name)
                    
                    # 4.1 app未被分类，且是多用途的 且 未被添加到待分类列表 ： 加入待分类列表
                    # 特别的，使用title进行分类，一个title添加一次，app名称可重复
                    if title and title not in title_to_classify_set:
                        # 添加 title 到对应 app 的 titles 列表
                        if app_registry[app_name].titles is not None:
                            app_registry[app_name].titles.append(title)
                        
                        # 创建 LogItem 并添加到 log_items
                        log_items.append(LogItem(
                            id=log_item_id_counter,
                            app=app_name,
                            duration=int(duration),
                            title=title
                        ))
                        log_item_id_counter += 1
                        title_to_classify_set.add(title)
                
                # 使用列表收集所有事件，最后一次性创建DataFrame
                filtered_events_list.append(filtered_event)
        else:
            # 记录被过滤的短暂活动
            removed_count += 1
    
    # 一次性创建DataFrame，避免循环中的concat警告
    if filtered_events_list:
        filtered_events_df = pd.DataFrame(filtered_events_list)
    
    # 构建 classifyState
    classify_state = classifyState(
        app_registry=app_registry,
        log_items=log_items,
        result_items=None
    )
    
    # 统计日志
    single_count = len([item for item in log_items if not app_registry.get(item.app, AppInFo(description="", is_multipurpose=False)).is_multipurpose])
    multi_count = len([item for item in log_items if app_registry.get(item.app, AppInFo(description="", is_multipurpose=False)).is_multipurpose])
    
    logger.info(f"📊 过滤统计: 总事件 {len(raw_events)} -> 保留 {len(filtered_events_df)} -> 删除 {removed_count}")
    logger.info(f"📊 待分类统计: 总项目 {len(log_items)} -> 单用途 {single_count} -> 多用途 {multi_count}")
    logger.info(f"📊 应用注册表: {len(app_registry)} 个应用")
    return filtered_events_df, classify_state


if __name__ == "__main__":
    raw_events = get_window_events(hours=1)
    # 测试数据库功能
    app_purpose_category_df = get_app_purpose_category()
    print(app_purpose_category_df)
    # 测试数据清洗功能
    filtered_events_df, classify_state = clean_activitywatch_data(raw_events, app_purpose_category_df)
    print(f"过滤后事件数: {len(filtered_events_df)}")
    print(f"待分类应用: {list(classify_state.app_registry.keys())}")
    print(f"待分类日志项数: {len(classify_state.log_items)}")