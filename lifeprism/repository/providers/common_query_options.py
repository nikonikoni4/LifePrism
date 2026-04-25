
from dataclasses import dataclass, replace
from typing import Optional, List, Dict, Any, Tuple
@dataclass(frozen=True)
class QueryOptions:
    """
    查询选项（通用的不可变查询参数类）

    设计原则：
    1. 不可变：使用 frozen=True，避免参数复用导致的 bug
    2. 通用：使用 filters 统一处理所有筛选条件
    3. 便捷：提供 with_*() 方法，方便创建新对象

    优先级说明：
    - 分页与限制：page + page_size 优先于 limit
      - 如果同时设置了 page 和 page_size，使用分页逻辑（LIMIT page_size OFFSET offset）
      - 否则如果设置了 limit，使用结果数量限制（LIMIT limit）
      - 都未设置则不限制结果数量
    """

    # 时间范围
    date_range: Optional[Tuple[str, str]] = None
    time_range: Optional[Tuple[str, str]] = None

    # 通用筛选
    filters: Optional[Dict[str, Any]] = None

    # 排序
    order_by: Optional[str] = None
    order_desc: bool = True

    # 分页
    page: Optional[int] = None
    page_size: Optional[int] = None

    # 结果数量限制
    limit: Optional[int] = None

    # 字段选择
    fields: Optional[List[str]] = None

    def __post_init__(self):
        """参数验证"""
        if self.page is not None and self.page < 1:
            raise ValueError("page must be >= 1")
        if self.page_size is not None:
            if self.page_size < 1 or self.page_size > 1000:
                raise ValueError("page_size must be between 1 and 1000")
        if self.limit is not None and self.limit < 1:
            raise ValueError("limit must be >= 1")

    def with_date_range(self, start: str, end: str) -> 'QueryOptions':
        """返回新对象，修改日期范围"""
        return replace(self, date_range=(start, end))

    def with_time_range(self, start: str, end: str) -> 'QueryOptions':
        """返回新对象，修改时间范围"""
        return replace(self, time_range=(start, end))

    def with_filters(self, **filters) -> 'QueryOptions':
        """返回新对象，合并筛选条件"""
        new_filters = {**(self.filters or {}), **filters}
        return replace(self, filters=new_filters)

    def with_order(self, field: str, desc: bool = True) -> 'QueryOptions':
        """返回新对象，修改排序"""
        return replace(self, order_by=field, order_desc=desc)

    def with_page(self, page: int, page_size: int = 20) -> 'QueryOptions':
        """返回新对象，设置分页"""
        return replace(self, page=page, page_size=page_size)

    def with_limit(self, limit: int) -> 'QueryOptions':
        """返回新对象，设置结果数量限制"""
        return replace(self, limit=limit)

    def with_fields(self, *fields: str) -> 'QueryOptions':
        """返回新对象，设置返回字段"""
        return replace(self, fields=list(fields))