"""
测试 SessionManager 的缓存行为和内存释放
"""
import weakref
import gc
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../..')))

from lifeprism.llm.session.manager import SessionManager, Session


def test_remove_from_cache_releases_memory_when_no_other_refs():
    """
    验证：从cache删除session后，如果没有其他引用，对象会被垃圾回收释放内存
    """
    manager = SessionManager()
    
    # 创建一个session并缓存
    session = manager.get_or_create_session()
    session_id = session.id
    
    # 使用weakref跟踪对象是否被释放
    weak_ref = weakref.ref(session)
    
    # 确保session在cache中
    assert session_id in manager._cache
    assert manager._cache[session_id] is session
    
    # 删除局部变量引用
    del session
    
    # 从cache中删除
    result = manager.remove_from_cache(session_id)
    assert result is True
    
    # 确保cache中已删除
    assert session_id not in manager._cache
    
    # 强制垃圾回收
    gc.collect()
    
    # 验证weakref引用的对象已被回收
    assert weak_ref() is None, "Session对象应该被垃圾回收，内存已释放"


def test_session_still_usable_after_remove_from_cache_if_referenced():
    """
    验证：从cache删除session后，如果其他地方还有引用，对象仍然可用
    """
    manager = SessionManager()
    
    # 创建一个session并缓存
    session = manager.get_or_create_session()
    session_id = session.id
    
    # 添加一些消息
    session.add_message(role='user', content='测试消息')
    session.add_message(role='assistant', content='回复消息')
    
    # 从cache中删除
    result = manager.remove_from_cache(session_id)
    assert result is True
    
    # 确保cache中已删除
    assert session_id not in manager._cache
    
    # 但session对象仍然可用，因为我们持有引用
    assert session.id == session_id
    assert len(session.messages) == 2
    assert session.messages[0]['content'] == '测试消息'
    assert session.messages[1]['content'] == '回复消息'
    
    # 可以继续操作
    session.add_message(role='user', content='继续对话')
    assert len(session.messages) == 3


def test_get_or_create_session_reload_after_remove_from_cache():
    """
    验证：从cache删除session后，再次get_or_create会重新加载（如果文件存在）
    """
    manager = SessionManager()
    
    # 创建一个session并缓存
    session1 = manager.get_or_create_session()
    session_id = session1.id
    
    # 添加消息并保存
    session1.add_message(role='user', content='保存的消息')
    manager.save_session(session1)
    
    # 从cache中删除
    manager.remove_from_cache(session_id)
    assert session_id not in manager._cache
    
    # 重新加载
    session2 = manager.get_or_create_session(session_id)
    
    # 验证重新加载的session内容一致
    assert session2.id == session_id
    assert len(session2.messages) == 1
    assert session2.messages[0]['content'] == '保存的消息'
    
    # 两个是不同的对象（重新加载的）
    assert session1 is not session2