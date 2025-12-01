from lifewatch import config 

def is_multipurpose_app(app: str) -> bool:
    """
    判断是否为浏览器应用
    
    Args:
        app: 应用名称，如 "msedge.exe"
    
    Returns:
        bool: True表示是浏览器，False表示是普通应用
    
    Note:
        - 使用set数据结构，查询效率为O(1)
        - 不区分大小写，支持各种命名格式
    """
    return app.lower() in config.MULTIPURPOSE_APP
