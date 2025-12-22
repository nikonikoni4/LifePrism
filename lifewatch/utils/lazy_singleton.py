"""
懒加载单例代理

在首次访问时才实例化目标类，实现延迟初始化，
避免模块导入时立即创建实例导致的启动延迟。
"""

import threading
from typing import TypeVar, Generic, Type, Any

T = TypeVar('T')


class LazySingleton(Generic[T]):
    """
    懒加载单例代理类
    
    使用方法：
        # 原来的写法
        my_service = MyService()
        
        # 改为懒加载
        my_service = LazySingleton(MyService)
        
        # 使用时自动初始化
        my_service.some_method()  # 首次访问时才创建实例
    
    特性：
        - 线程安全：使用双重检查锁定模式
        - 透明代理：对外表现与原实例一致
        - 延迟初始化：只在首次访问属性/方法时实例化
    """
    
    def __init__(self, cls: Type[T], *args, **kwargs):
        """
        初始化懒加载代理
        
        Args:
            cls: 要懒加载的类
            *args: 传递给 cls.__init__ 的位置参数
            **kwargs: 传递给 cls.__init__ 的关键字参数
        """
        # 使用 object.__setattr__ 避免触发 __getattr__
        object.__setattr__(self, '_cls', cls)
        object.__setattr__(self, '_args', args)
        object.__setattr__(self, '_kwargs', kwargs)
        object.__setattr__(self, '_instance', None)
        object.__setattr__(self, '_lock', threading.Lock())
    
    def _ensure_initialized(self) -> T:
        """
        确保实例已初始化（双重检查锁定）
        
        Returns:
            T: 已初始化的实例
        """
        if self._instance is None:
            with self._lock:
                if self._instance is None:
                    instance = self._cls(*self._args, **self._kwargs)
                    object.__setattr__(self, '_instance', instance)
        return self._instance
    
    def __getattr__(self, name: str) -> Any:
        """代理属性访问"""
        return getattr(self._ensure_initialized(), name)
    
    def __setattr__(self, name: str, value: Any) -> None:
        """代理属性设置"""
        if name in ('_cls', '_args', '_kwargs', '_instance', '_lock'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._ensure_initialized(), name, value)
    
    def __call__(self, *args, **kwargs) -> Any:
        """代理调用（如果实例是可调用的）"""
        return self._ensure_initialized()(*args, **kwargs)
    
    def __repr__(self) -> str:
        if self._instance is None:
            return f"<LazySingleton({self._cls.__name__}) - not initialized>"
        return repr(self._instance)
