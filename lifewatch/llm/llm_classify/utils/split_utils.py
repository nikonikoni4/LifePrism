from lifewatch.llm.llm_classify.schemas import classifyState
import logging
from lifewatch.config.settings_manager import settings
logger = logging.getLogger(__name__)


def split_by_purpose(state: classifyState) -> classifyState:
    """
    将 classifyState 按单用途和多用途分开，填充到对应字段
    
    Args:
        state: 原始的 classifyState 对象
        
    Returns:
        classifyState: 更新后的 state，包含:
            - log_items_for_single: 单用途数据
            - log_items_for_multi (多用途部分保留用于后续处理)
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
    
    logger.info(f"按用途分离完成: 单用途 {len(single_purpose_items)} 条, 多用途 {len(multi_purpose_items)} 条")
    
    return {
        "log_items_for_single": single_purpose_items,
        "log_items_for_multi": multi_purpose_items,
    }


def split_by_duration(state: classifyState) -> classifyState:
    """
    将多用途 log_items 按时长分开，填充到对应字段
    
    Args:
        state: 包含多用途数据的 classifyState 对象（需要先调用 split_by_purpose）
        
    Returns:
        classifyState: 更新后的 state，包含:
            - log_items_for_multi_short: 短时长数据
            - log_items_for_multi_long: 长时长数据
    """
    # 直接从 log_items_for_multi 获取多用途数据
    multi_purpose_items = state.log_items_for_multi
    
    # 按时长分离
    short_duration_items = []
    long_duration_items = []
    
    for item in multi_purpose_items:
        if item.duration < settings.long_log_threshold:
            short_duration_items.append(item)
        else:
            long_duration_items.append(item)
    
    logger.info(f"按时长分离完成: 短时长(<{settings.long_log_threshold}s) {len(short_duration_items)} 条, 长时长(>={settings.long_log_threshold}s) {len(long_duration_items)} 条")
    
    return {
        "log_items_for_multi_short": short_duration_items,
        "log_items_for_multi_long": long_duration_items,
    }
