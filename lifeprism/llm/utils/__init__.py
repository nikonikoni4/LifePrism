"""
工具类模块
"""
from .llm_factory import (
    create_llm,
    get_provider_id,
    get_provider_capabilities,
    list_providers,
)
from .format_prompt_utils import (
    format_goals_for_prompt,
    format_category_tree_for_prompt,
    format_log_items_table,
    )
from .parse_utils import (
    parse_classification_result,
    extract_json_from_response,
    parse_token_usage
)
from .split_utils import (
    split_by_duration,
    split_by_purpose,

)
from .md_os import(
    read_md,
    extract_behavior_logs_from_file,
    write_behavior_md
)
from .density_utils import (
    compute_bucket_density,
    build_time_segments,
)

__all__ = [
    # 向后兼容
    "create_ChatTongyiModel",
    # 新的统一工厂函数
    "create_llm",
    "get_provider_id",
    "get_provider_capabilities",
    "list_providers",
    # 其他工具
    "format_goals_for_prompt",
    "format_category_tree_for_prompt",
    "format_log_items_table",
    "parse_classification_result",
    "extract_json_from_response",
    "split_by_duration",
    "split_by_purpose",
    "parse_token_usage",
    "read_md",
    "extract_behavior_logs_from_file",
    "write_behavior_md",
    "compute_bucket_density",
    "build_time_segments",
]