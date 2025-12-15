from lifewatch.llm.llm_classify.schemas import classifyState
import logging

logger = logging.getLogger(__name__)

# 时长分割阈值（秒）
SPLIT_DURATION = 10 * 60  # 10分钟

def split_by_purpose(state: classifyState) -> tuple[classifyState, classifyState]:
    """
    将 classifyState 按单用途和多用途分开
    
    Args:
        state: 原始的 classifyState 对象
        
    Returns:
        tuple[classifyState, classifyState]: (单用途state, 多用途state)
        
    Example:
        single_state, multi_state = split_by_purpose(state)
    """
    # 分离 log_items
    single_purpose_items = []
    multi_purpose_items = []
    
    for item in state.log_items:
        app_info = state.app_registry.get(item.app)
        if app_info and not app_info.is_multipurpose:
            single_purpose_items.append(item)
        else:
            multi_purpose_items.append(item)
    
    # 构建单用途 app_registry
    single_apps = set(item.app for item in single_purpose_items)
    single_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in single_apps
    }
    
    # 构建多用途 app_registry
    multi_apps = set(item.app for item in multi_purpose_items)
    multi_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in multi_apps
    }
    
    # 创建单用途 state
    single_state = classifyState(
        app_registry=single_app_registry,
        log_items=single_purpose_items,
        goal=state.goal,
        category_tree=state.category_tree,
    )
    
    # 创建多用途 state
    multi_state = classifyState(
        app_registry=multi_app_registry,
        log_items=multi_purpose_items,
        goal=state.goal,
        category_tree=state.category_tree,
    )
    
    logger.info(f"分离完成: 单用途 {len(single_purpose_items)} 条, 多用途 {len(multi_purpose_items)} 条")
    
    return single_state, multi_state

def split_by_duartion(state: classifyState)->tuple[classifyState,classifyState]:
    """
    将 classifyState 按时长分开
    
    Args:
        state: 原始的 classifyState 对象
        
    Returns:
        tuple[classifyState, classifyState]: (短时长state, 长时长state)
        
    Example:
        short_state, long_state = split_by_duartion(state)
    """
    # 分离 log_items
    short_duration_items = []
    long_duration_items = []
    
    for item in state.log_items:
        if item.duration < SPLIT_DURATION:
            short_duration_items.append(item)
        else:
            long_duration_items.append(item)
    
    # 构建短时长 app_registry
    short_apps = set(item.app for item in short_duration_items)
    short_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in short_apps
    }
    
    # 构建长时长 app_registry
    long_apps = set(item.app for item in long_duration_items)
    long_app_registry = {
        app: info 
        for app, info in state.app_registry.items() 
        if app in long_apps
    }
    
    # 创建短时长 state
    short_state = classifyState(
        app_registry=short_app_registry,
        log_items=short_duration_items,
        goal=state.goal,
        category_tree=state.category_tree,
    )
    # 创建长时长 state
    long_state = classifyState(
        app_registry=long_app_registry,
        log_items=long_duration_items,
        goal=state.goal,
        category_tree=state.category_tree,
    )
    
    logger.info(f"按时长分离完成: 短时长(<{SPLIT_DURATION}s) {len(short_duration_items)} 条, 长时长(>={SPLIT_DURATION}s) {len(long_duration_items)} 条")
    
    return short_state, long_state
