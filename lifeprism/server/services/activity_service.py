"""
Activity V2 Service 层 - 纯函数模块

实现活动统计和日志管理的业务逻辑
无状态缓存，每次调用直接访问 provider
"""

from lifeprism.repository import computer_usage_repository
from lifeprism.server.schemas.activity_schemas import (
    ActivityLogItem,
    ActivityLogsResponse,
    ActivityStatsIncludeOptions,
    ActivityStatsResponse,
)
from lifeprism.server.services.activity_stats_builder import (
    build_activity_summary,
    build_time_overview,
    get_top_app,
    get_top_title,
)
from lifeprism.utils import get_logger
from lifeprism.utils.time_utils import get_utc_now_iso

logger = get_logger(__name__)


def get_activity_stats(
    date: str,
    include_options: ActivityStatsIncludeOptions,
    history_number: int,
    future_number: int,
    category_id: str | None,
    sub_category_id: str | None,
) -> ActivityStatsResponse:
    """
    获取活动统计数据

    Args:
        date: 中心日期 (YYYY-MM-DD 格式)
        include_options: 包含选项（由 API 层解析后传入）
        history_number: 历史数据天数
        future_number: 未来数据天数
        category_id: 主分类ID筛选（可选）
        sub_category_id: 子分类ID筛选（可选）

    Returns:
        ActivityStatsResponse: 活动统计响应
    """
    result = ActivityStatsResponse(
        query={
            "date": date,
            "include_options": include_options.model_dump(),
            "history_number": history_number,
            "future_number": future_number,
            "category_id": category_id,
            "sub_category_id": sub_category_id,
        }
    )

    # 根据 include 选项按需获取数据（调用纯函数模块）
    if include_options.include_activity_summary:
        result.activity_summary = build_activity_summary(
            date, history_number, future_number, category_id, sub_category_id
        )

    if include_options.include_time_overview:
        result.time_overview = build_time_overview(date)

    if include_options.include_top_title:
        result.top_title = get_top_title(date, top_n=5)

    if include_options.include_top_app:
        result.top_app = get_top_app(date, top_n=5)

    return result


# ============================================================================
# 日志相关函数
# ============================================================================


def get_activity_logs(
    date: str | None,
    start_time: str | None,
    end_time: str | None,
    device_filter: str,
    category_id: str | None,
    sub_category_id: str | None,
    sort_by: str | None,
    sort_order: str | None,
    page: int,
    page_size: int,
) -> ActivityLogsResponse:
    """
    获取活动日志列表

    支持按日期或时间范围查询，使用 provider 的统一查询方法

    Args:
        date: 查询日期 (YYYY-MM-DD 格式)，提供时查询整天数据
        start_time: 开始时间 (UTC ISO 8601 格式)
        end_time: 结束时间 (UTC ISO 8601 格式)
        device_filter: 设备过滤 (all/pc/mobile)，当前未使用
        category_id: 主分类ID筛选
        sub_category_id: 子分类ID筛选
        sort_by: 排序字段 (duration/start_time/app)
        sort_order: 排序方向 (asc/desc)
        page: 页码
        page_size: 每页数量

    Returns:
        ActivityLogsResponse: 日志列表响应

    Note:
        必须提供 date 或 (start_time 和 end_time) 之一
    """
    # 通过 provider 的统一方法获取数据
    # sort_by 为 None 时使用默认值 start_time，避免 SQL 拼接出 uabl.None
    logs, total = computer_usage_repository.get_activity_logs(
        start_time=start_time,
        end_time=end_time,
        category_id=category_id,
        sub_category_id=sub_category_id,
        order_by=sort_by or "start_time",
        order_desc=(sort_order == "desc"),
        page=page,
        page_size=page_size,
    )

    # 转换为 ActivityLogItem 列表
    log_items = [
        ActivityLogItem(
            id=log["id"],
            start_time=log["start_time"],
            end_time=log["end_time"],
            app=log["app"],
            title=log["title"],
            duration=log["duration"],
            category_id=log.get("category_id"),
            sub_category_id=log.get("sub_category_id"),
            category=log.get("category_name"),
            sub_category=log.get("sub_category_name"),
        )
        for log in logs
    ]

    return ActivityLogsResponse(data=log_items, total=total, page=page, page_size=page_size)


def get_activity_log_detail(log_id: str) -> ActivityLogItem | None:
    """
    获取单条日志详情

    Args:
        log_id: 日志ID

    Returns:
        ActivityLogItem: 日志详情，如果不存在返回 None
    """
    log = computer_usage_repository.get_computer_usage_by_id_with_names(log_id)

    if not log:
        return None

    return ActivityLogItem(
        id=str(log["id"]),
        start_time=log["start_time"],
        end_time=log["end_time"],
        app=log["app"],
        title=log["title"],
        duration=log["duration"],
        category_id=log.get("category_id"),
        sub_category_id=log.get("sub_category_id"),
        category=log.get("category_name"),
        sub_category=log.get("sub_category_name"),
    )


def update_log_category(log_id: str, category_id: str, sub_category_id: str | None) -> bool:
    """更新日志分类

    通过 computer_usage_repository.update_by_filter 调用：
    - sub_category_id=None 表示清除为 NULL（前端"选择 -- Select --"场景）
    - 显式传入 updated_at 触发 LWW 同步（update_by_filter 不自动更新 updated_at）
    """
    affected = computer_usage_repository.update_by_filter(
        set_fields={
            "category_id": category_id,
            "sub_category_id": sub_category_id,  # None → 清除为 NULL
            "updated_at": get_utc_now_iso(),
        },
        where_conditions={"id": log_id},
    )
    return affected > 0


def batch_update_log_category(log_ids: list, category_id: str, sub_category_id: str | None) -> int:
    """批量更新日志分类，返回更新数量

    通过 computer_usage_repository.update_by_filter + IN 子句调用：
    - sub_category_id=None 表示清除为 NULL（前端"选择 -- Select --"场景）
    - 显式传入 updated_at 触发 LWW 同步（update_by_filter 不自动更新 updated_at）
    """
    if not log_ids:
        return 0
    return computer_usage_repository.update_by_filter(
        set_fields={
            "category_id": category_id,
            "sub_category_id": sub_category_id,  # None → 清除为 NULL
            "updated_at": get_utc_now_iso(),
        },
        where_conditions={"id IN": log_ids},
    )


def delete_log(log_id: str) -> bool:
    """删除单条日志

    迁移后通过 computer_usage_repository.delete_computer_usage 调用，
    底层 _generic_delete 会写墓碑到 deletion_log（因 user_app_behavior_log
    在 SYNC_TABLES 中），墓碑 record_id 使用 hash_id。
    """
    return computer_usage_repository.delete_computer_usage(log_id)


def batch_delete_logs(log_ids: list[str]) -> int:
    """批量删除日志，返回删除数量

    迁移后通过 computer_usage_repository.batch_delete_computer_usage 调用，
    底层 _generic_batch_delete 会写墓碑到 deletion_log（因 user_app_behavior_log
    在 SYNC_TABLES 中），N 条记录对应 N 条墓碑，墓碑 record_id 使用 hash_id。
    """
    return computer_usage_repository.batch_delete_computer_usage(log_ids)


def update_logs_by_app_title(
    app: str,
    title: str | None,
    is_multipurpose_app: bool,
    category_id: str,
    sub_category_id: str | None = None,
    goal_id: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
) -> int:
    """
    根据 app 和可选的 title 批量更新日志分类

    匹配逻辑：
    - 单用途应用 (is_multipurpose_app=False): 仅按 app 匹配
    - 多用途应用 (is_multipurpose_app=True): 按 app + title 匹配

    业务逻辑上移（原在 statistical_data_providers.update_logs_by_app_title）：
    1. goal_id 三态语义：None=不修改 / ""=清除为 NULL / "goal-xxx"=设置值
    2. is_multipurpose_app 判断：True=加 title 条件 / False=不加

    Args:
        app: 应用名称
        title: 窗口标题（多用途应用时必须提供）
        is_multipurpose_app: 是否为多用途应用
        category_id: 主分类ID
        sub_category_id: 子分类ID（可选，None=清除为 NULL）
        goal_id: 目标ID（None=不修改, ''=清除, 'goal-xxx'=设置）
        start_time: 开始时间 UTC ISO 8601 格式（可选）
        end_time: 结束时间 UTC ISO 8601 格式（可选）

    Returns:
        int: 成功更新的数量
    """
    # 1. 构建 set_fields（goal_id 三态语义在 Service 层处理）
    #    update_by_filter 的 None = 清除为 NULL（与 update_computer_usage 的 None=跳过不同）
    #    显式传入 updated_at 触发 LWW 同步（update_by_filter 不自动更新 updated_at）
    set_fields: dict = {
        "category_id": category_id,
        "sub_category_id": sub_category_id,
        "updated_at": get_utc_now_iso(),
    }
    if goal_id is not None:
        # None=不修改（不加入 set_fields），""=清除（设为 None），"goal-xxx"=设置
        set_fields["link_to_goal_id"] = goal_id if goal_id else None

    # 2. 构建 where_conditions（is_multipurpose_app 判断在 Service 层处理）
    where_conditions: dict = {"app": app}
    if is_multipurpose_app:
        if title is None:
            raise ValueError("多用途应用必须提供 title 参数")
        where_conditions["title"] = title

    # 时间范围（已是 UTC ISO 格式，直接传入，Provider 不做时间转换）
    if start_time:
        where_conditions["start_time >="] = start_time
    if end_time:
        where_conditions["start_time <="] = end_time

    # 3. 调用 Provider 的通用 update_by_filter
    return computer_usage_repository.update_by_filter(
        set_fields=set_fields,
        where_conditions=where_conditions,
    )
