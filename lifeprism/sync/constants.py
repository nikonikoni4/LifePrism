"""文件同步共享常量

客户端和云端共用，避免重复定义导致不一致。
"""

import gzip

# 排除同步的文件名：
# - chat_history.json: 由 dreaming task 写入，云端无 dreaming 不变更
# - bootstrap.md: Agent 启动引导配置，由模板初始化，各端独立维护
# 参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 2
EXCLUDED_FILENAMES = {"chat_history.json", "bootstrap.md"}

# gzip 解压后最大允许大小（50MB），防止 zip bomb 导致 OOM
MAX_DECOMPRESSED_SIZE = 50 * 1024 * 1024

# 同步范围：除 window_events 外的所有需要同步的静态表（30 张）
# 客户端和云端共用（云端 full-clear 端点需要访问此列表）
# TODO PRD 2: 恢复同步前需先解决 chain_id 外键映射问题（chain_id 改引用 hash_id）
#   habit_chains 和 habit_chain_nodes 因 chain_id 引用 habit_chains.id（自增 id），
#   同步后两端 id 不一致导致外键断裂，临时从 SYNC_TABLES 移除。
#   详见 docs/known-limitations/habit-chain-tables-not-synced.md
#   详见 ADR docs/adr/2026-07-22-habit-chain-tables-not-synced.md
#   注意：HASH_ID_PREFIXES 仍包含这两张表，hash_id 字段照加，为恢复同步做准备。
SYNC_TABLES = [
    # 用户输入数据（13张）
    "mood_entries",
    "diary",
    "todo_list",
    "goal",
    "goal_journal",
    "plan_doc",
    "daily_focus",
    "weekly_focus",
    "habits",
    "habit_challenges",
    "habit_checkins",
    "timeline_custom_block",
    "time_paradoxes",
    # 元数据（8张）
    "category",
    "sub_category",
    "mood_types",
    "mood_impacts",
    "user_values",
    "commitments",
    "custom_record_types",
    "custom_record_fields",
    # Monitor 数据（3张）
    "user_app_behavior_log",
    "behavior_analysis",
    "raw_behavior_analysis",
    # 缓存表（3张）
    "multi_purpose_map_cache",
    "single_purpose_map_cache",
    "category_map_cache",
    # 统计数据（1张）
    "tokens_usage_log",
    # 微信账户状态（1张）- 替代原 channel/wechat/account.json 文件存储
    # 走数据库同步的记录级 LWW，参考 ADR 2026-07-14-file-sync-conflict-resolution.md 决策 4
    "wechat_account_state",
    # 注意：deletion_log 已从 SYNC_TABLES 移除，墓碑仅通过专用通道
    # （_pull_deletion_log / _push_deletion_log / _cleanup_deletion_log）同步，
    # 避免双重同步和循环引用。参考 PRD 3 + ADR docs/adr/2026-07-22-deletion-sync-tombstone.md
]

# 需要 hash_id 字段的 AUTOINCREMENT 表前缀映射
# 同时作为"哪些表需要 hash_id"的判断依据（_generic_insert 用 HASH_ID_PREFIXES.get(table_name) 判断）
# 参考 ADR: docs/adr/2026-07-22-hash-id-sync-only-identifier.md（hash_id 定位为同步专用标识）
# 注意：daily_focus/weekly_focus/category_map_cache 在 m016 迁移中补充（m015 遗漏），
# 参考 ADR docs/adr/2026-07-24-add-hash-id-to-remaining-autoincrement-tables.md
HASH_ID_PREFIXES = {
    "timeline_custom_block": "tcb-",
    "time_paradoxes": "tp-",
    "mood_impacts": "mi-",
    "habit_chains": "hc-",
    "habit_chain_nodes": "hcn-",
    "user_app_behavior_log": "awbl-",
    # 以下 3 张表在 m016 迁移中补充（m015 审计时遗漏）
    "daily_focus": "df-",
    "weekly_focus": "wf-",
    "category_map_cache": "cmc-",
}


def generate_hash_id(prefix: str) -> str:
    """生成 hash_id（同步专用标识）

    格式: {prefix}{uuid.uuid4().hex[:12]}
    - prefix 来自 HASH_ID_PREFIXES（如 "tcb-", "mi-"）
    - 12 位 hex = 48 bit 熵，单表内碰撞概率极低

    供以下路径统一调用，避免直接 INSERT 绕过 _generic_insert 时缺失 hash_id：
    - _generic_insert 兜底
    - m015 迁移脚本回填
    - data_initializer / mood_providers / being_provider 等直写路径

    Args:
        prefix: hash_id 前缀（来自 HASH_ID_PREFIXES）

    Returns:
        形如 "tcb-a1b2c3d4e5f6" 的 hash_id
    """
    import uuid

    return f"{prefix}{uuid.uuid4().hex[:12]}"


# 文件同步白名单：相对 lifeprism_data_path 的路径
# 对齐 Agent 工具白名单（ALLOWED_DIRS = user/diary/agent）+ session（会话层写入）
# 参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 2
SYNC_DIRECTORIES = [
    "session/",  # 聊天会话 JSONL（Agent 会话层写入）
    "diary/",  # 日记 MD（Agent write_file/edit_file）
    "agent/",  # Agent 身份/记忆/chat 配置（Agent write_file/edit_file）
    "user/",  # 用户级数据（Agent write_file/edit_file，排除 chat_history.json）
]

# 文件推送分批大小：每批最多推送 FILE_BATCH_SIZE 个文件
# 单文件经 gzip+base64 编码后通常几 KB~几百 KB，50 个/批约 5MB，云端内存安全
FILE_BATCH_SIZE = 50

# 数据库推送分批大小：每批最多推送 DB_PUSH_BATCH_SIZE 条记录
# 与 push_to_remote 的 batch_size 保持一致，平衡内存与 HTTP 调用次数
DB_PUSH_BATCH_SIZE = 1000

# 首次同步相关 HTTP timeout（秒）
# 初始化状态检查：轻量查询，60s 足够
INITIALIZATION_STATUS_TIMEOUT = 60.0
# full-clear：涉及大量文件删除，用更长 timeout
FULL_CLEAR_TIMEOUT = 300.0
# mark-initialized：轻量写操作，60s 足够
MARK_INITIALIZED_TIMEOUT = 60.0
# 数据库推送：大批量数据，用更长 timeout
PUSH_ENDPOINT_TIMEOUT = 300.0


def safe_gzip_decompress(compressed: bytes) -> bytes:
    """安全解压 gzip 数据，限制解压后大小防止 zip bomb

    Args:
        compressed: gzip 压缩的字节串

    Returns:
        解压后的字节串

    Raises:
        ValueError: 解压后数据超过 MAX_DECOMPRESSED_SIZE
    """
    data = gzip.decompress(compressed)
    if len(data) > MAX_DECOMPRESSED_SIZE:
        raise ValueError(f"解压后文件超过 {MAX_DECOMPRESSED_SIZE // 1024 // 1024}MB 限制")
    return data
