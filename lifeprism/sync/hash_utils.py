"""文件同步 hash 工具函数

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.2 决策 5（hash 规范化策略）
"""

import hashlib


def compute_file_hash(content: bytes) -> str:
    """计算文件内容的规范化 hash

    规则：统一行尾符（\\r\\n → \\n）并去除每行行尾空白后计算 SHA-256。
    源文件不受影响，仅 hash 计算时做规范化。

    保留词语间的空格（避免 "hello world" 与 "helloworld" 产生相同 hash），
    仅消除操作系统换行差异（Windows ``\\r\\n`` vs Linux ``\\n``）和
    行尾 trailing 空白导致的 hash 不一致。

    Args:
        content: 文件内容的字节串

    Returns:
        SHA-256 hex 字符串（64 字符）
    """
    text = content.decode("utf-8", errors="replace")
    # 统一行尾符：\r\n → \n，孤立 \r → \n
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    # 去除每行行尾空白（trailing spaces/tabs），保留行内空格
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
