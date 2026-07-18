"""文件过滤模块：空文件与 template 文件过滤

在文件同步扫描阶段（_refresh_current_hashes）预防性地过滤掉两类不应进入
file_sync_state 的文件，从根本上解决云端空文档覆盖本地实文档的 bug 根因。

过滤规则（PRD 决策 7、8）：
1. **空文件**：内容 strip() 后为空 → 跳过（PRD 决策 7）
2. **Template 文件**：文件 hash 在 template_hashes 集合中 → 跳过（PRD 决策 8）

数据源单一：template_hashes 集合从 templates/ 目录派生，不硬编码（PRD 决策 8）。

参考:
- Issue: .scratch/file-conflict-resolution-redesign/issue/issue-1-empty-and-template-file-filter.md
- PRD: .scratch/file-conflict-resolution-redesign/prd.md 决策 7、8（用户故事 22-25）
- ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md
- Bug 根因: docs/history-bugs/2026-07-14-sync-client-not-started-and-empty-file-lww-overwrite.md
"""

from pathlib import Path

from lifeprism.sync.hash_utils import compute_file_hash
from lifeprism.utils import get_logger

logger = get_logger(__name__)


def is_empty_content(content_bytes: bytes) -> bool:
    """判断文件内容是否为空（strip 后为空）

    PRD 决策 7：空文件不写入 file_sync_state，从根本上解决空文档覆盖问题。

    "空"的定义：内容解码后 strip() 返回空字符串。包含：
    - 完全空字节串
    - 仅空格/制表符
    - 仅换行符（\\n / \\r\\n / \\r）
    - 上述空白字符的任意组合

    Args:
        content_bytes: 文件内容的字节串

    Returns:
        True 表示内容为空（应被过滤），False 表示有实际内容
    """
    text = content_bytes.decode("utf-8", errors="replace")
    return text.strip() == ""


def compute_template_hashes(templates_dir: Path) -> set[str]:
    """计算 templates/ 目录下所有文件的 hash 集合

    PRD 决策 8：启动时计算 templates/ 目录所有文件 hash，加载到 template_hashes 集合。
    数据源单一：仅从 templates/ 目录派生，不硬编码。

    设计要点：
    - 递归扫描 templates/ 目录下所有文件（含子目录）
    - 使用 compute_file_hash 计算 hash（与 _refresh_current_hashes 一致，确保 hash 可比对）
    - 目录条目本身被跳过（只对文件计算 hash）
    - 目录不存在或为空时返回空集合（不抛异常，避免阻塞同步流程）

    Args:
        templates_dir: templates 目录路径

    Returns:
        set[str]: 所有 template 文件的 hash 集合；目录不存在/为空时返回空集合
    """
    hashes: set[str] = set()

    if not templates_dir.exists():
        logger.warning(
            "compute_template_hashes: templates 目录不存在，返回空集合: %s",
            templates_dir,
        )
        return hashes

    for source in templates_dir.rglob("*"):
        # 仅对文件计算 hash，跳过目录条目本身
        if not source.is_file():
            continue
        try:
            content_bytes = source.read_bytes()
        except OSError:
            logger.warning(
                "compute_template_hashes: 读取 template 文件失败，跳过: %s",
                source,
                exc_info=True,
            )
            continue
        hashes.add(compute_file_hash(content_bytes))

    logger.info(
        "compute_template_hashes: template_hashes 集合加载完成，共 %d 个 hash",
        len(hashes),
    )
    return hashes


def should_filter_file(content_bytes: bytes, template_hashes: set[str]) -> bool:
    """判断文件是否应被过滤（不写入 file_sync_state）

    PRD 决策 7 + 8 的组合判定。两个条件独立判定，任一命中即过滤：
    1. 文件内容 strip() 后为空 → 过滤
    2. 文件 hash 在 template_hashes 集合中 → 过滤

    空判定优先于 hash 判定：
    - 空文件无需计算 hash，性能更优
    - 即使 template_hashes 为空集，空文件仍会被过滤（独立条件）

    Args:
        content_bytes: 文件内容的字节串
        template_hashes: template 文件 hash 集合（由 compute_template_hashes 生成）

    Returns:
        True 表示应被过滤（跳过不写入 file_sync_state），False 表示通过过滤
    """
    # 优先判定空内容：性能更优，且不依赖 template_hashes
    if is_empty_content(content_bytes):
        return True

    # hash 命中 template_hashes 集合 → 视为 template 文件，过滤
    file_hash = compute_file_hash(content_bytes)
    return file_hash in template_hashes
