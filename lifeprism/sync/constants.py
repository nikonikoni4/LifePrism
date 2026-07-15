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
