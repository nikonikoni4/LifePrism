"""
Being 服务层
提供时间悖论测试（过去/现在/未来自我探索）的业务逻辑

纯函数风格，处理 JSON 序列化和版本管理
"""
from typing import Optional, List, Dict, Any

from lifewatch.server.providers.being_provider import being_provider
from lifewatch.utils import get_logger

logger = get_logger(__name__)


# ==================== 查询接口 ====================

def get_test_result(
    user_id: int, 
    mode: str, 
    version: int = None
) -> Optional[Dict[str, Any]]:
    """
    获取测试结果
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        version: 版本号，None 表示获取最新版本
    
    Returns:
        Optional[Dict]: 测试记录，包含 id, user_id, mode, version, content, ai_abstract
    """
    if version is None:
        return being_provider.get_latest_record(user_id, mode)
    return being_provider.get_by_user_mode_version(user_id, mode, version)


def get_all_versions(user_id: int, mode: str) -> List[Dict[str, Any]]:
    """
    获取用户某模式下的所有版本
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
    
    Returns:
        List[Dict]: 版本列表，按版本号降序排列
    """
    return being_provider.get_all_by_user_mode(user_id, mode)


def get_version_list(user_id: int, mode: str) -> List[Dict[str, Any]]:
    """
    获取版本简要列表（不包含完整 content）
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
    
    Returns:
        List[Dict]: 版本信息列表，包含 id, version, created_at, updated_at
    """
    records = being_provider.get_all_by_user_mode(user_id, mode)
    return [
        {
            'id': r.get('id'),
            'version': r.get('version'),
            'created_at': r.get('created_at'),
            'updated_at': r.get('updated_at'),
            'has_ai_abstract': r.get('ai_abstract') is not None
        }
        for r in records
    ]


# ==================== 创建/更新接口 ====================

def save_test_result(
    user_id: int, 
    mode: str, 
    content: Dict[str, Any],
    version: int = None
) -> Optional[Dict[str, Any]]:
    """
    保存测试结果
    
    如果 version 为 None，创建新版本
    如果 version 不为 None，更新指定版本
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        content: 测试内容
        version: 版本号，None 表示创建新版本
    
    Returns:
        Optional[Dict]: 保存后的记录
    """
    if version is None:
        # 创建新版本
        return being_provider.create_new_version(user_id, mode, content)
    else:
        # 更新现有版本
        success = being_provider.update_by_user_mode_version(
            user_id, mode, version, {'content': content}
        )
        if success:
            return being_provider.get_by_user_mode_version(user_id, mode, version)
        return None


def update_test_result(
    user_id: int, 
    mode: str, 
    version: int, 
    content: Dict[str, Any]
) -> bool:
    """
    更新测试结果
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        version: 版本号
        content: 测试内容
    
    Returns:
        bool: 是否成功
    """
    return being_provider.update_by_user_mode_version(
        user_id, mode, version, {'content': content}
    )


def upsert_test_result(
    user_id: int,
    mode: str,
    version: int,
    content: Dict[str, Any],
    ai_abstract: str = None
) -> bool:
    """
    UPSERT 测试结果（存在更新，不存在插入）
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        version: 版本号
        content: 测试内容
        ai_abstract: AI 总结
    
    Returns:
        bool: 是否成功
    """
    return being_provider.upsert(user_id, mode, version, content, ai_abstract)


# ==================== 删除接口 ====================

def delete_test_result(user_id: int, mode: str, version: int) -> bool:
    """
    删除测试结果
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        version: 版本号
    
    Returns:
        bool: 是否成功
    """
    return being_provider.delete_by_user_mode_version(user_id, mode, version)


# ==================== AI 总结接口（预留） ====================

def update_ai_abstract(
    user_id: int, 
    mode: str, 
    version: int, 
    ai_abstract: str
) -> bool:
    """
    更新 AI 总结
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        version: 版本号
        ai_abstract: AI 总结内容
    
    Returns:
        bool: 是否成功
    """
    return being_provider.update_by_user_mode_version(
        user_id, mode, version, {'ai_abstract': ai_abstract}
    )


def generate_ai_abstract(user_id: int, mode: str, version: int) -> Optional[str]:
    """
    生成 AI 总结（预留接口，待接入 LLM）
    
    Args:
        user_id: 用户 ID
        mode: 模式 (past/present/future)
        version: 版本号
    
    Returns:
        Optional[str]: AI 生成的总结，失败返回 None
    """
    # TODO: 接入 LLM 生成总结
    record = being_provider.get_by_user_mode_version(user_id, mode, version)
    if not record:
        logger.error(f"记录不存在 (user_id={user_id}, mode={mode}, version={version})")
        return None
    
    # 占位：后续接入 LLM
    logger.info("AI 总结生成功能待实现")
    return None
