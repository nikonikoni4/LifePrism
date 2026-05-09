
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

    参数说明：
    - date_range: 日期范围过滤，格式为 (start_date, end_date)，如 ("2024-01-01", "2024-12-31")
                  保留在此日期范围内的记录（闭区间）
    - time_range: 时间范围过滤，格式为 (start_time, end_time)，如 ("2026-04-01 09:00", "2026-04-02 18:00")
                  保留在此时间范围内的记录（闭区间）
    - filters: 通用筛选条件字典，语义为"保留匹配的记录"（WHERE 条件）
               例如 {"category": "work", "status": "active"} 表示只保留 category=work 且 status=active 的记录
               具体支持的字段和匹配规则由各 Provider 实现决定
    - order_by: 排序字段名，如 "created_at"、"priority" 等
    - order_desc: 是否降序排序，True=降序（默认），False=升序
    - page: 页码，从 1 开始。需与 page_size 配合使用
    - page_size: 每页记录数，范围 [1, 1000]。需与 page 配合使用
    - limit: 结果数量限制，当不使用分页时生效。例如 limit=10 表示最多返回 10 条记录
    - fields: 返回字段列表，如 ["id", "title", "created_at"]。None 表示返回所有字段
    """

    date_range: Optional[Tuple[str, str]] = None
    time_range: Optional[Tuple[str, str]] = None
    filters: Optional[Dict[str, Any]] = None
    order_by: Optional[str] = None
    order_desc: bool = True
    page: Optional[int] = None
    page_size: Optional[int] = None
    limit: Optional[int] = None
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
        """返回新对象，修改日期范围,闭区间[]"""
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