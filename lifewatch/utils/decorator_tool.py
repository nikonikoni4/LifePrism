from functools import wraps

def refresh_after(*callbacks):
    """
    执行方法后调用指定回调函数的装饰器
    
    Args:
        *callbacks: 要在方法执行后调用的函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            for callback in callbacks:
                callback()
            return result
        return wrapper
    return decorator
