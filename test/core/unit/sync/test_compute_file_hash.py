"""
compute_file_hash 单元测试

测试 seam: compute_file_hash(content: bytes) -> str（纯函数）

参考 ADR: docs/adr/2026-07-14-file-sync-conflict-resolution.md v2.1 决策 5（hash 规范化策略）
"""
import hashlib

import pytest

from lifeprism.sync.hash_utils import compute_file_hash

pytestmark = pytest.mark.core


# SHA-256 of empty string ""（独立计算的已知常量）
EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


class TestComputeFileHashNormalizeWhitespace:
    """compute_file_hash 统一行尾符 + 去除行尾空白后计算 SHA-256"""

    def test_line_ending_normalization(self):
        """Windows CRLF 和 Linux LF 产生相同 hash"""
        hash_crlf = compute_file_hash(b"line1\r\nline2\r\n")
        hash_lf = compute_file_hash(b"line1\nline2\n")
        assert hash_crlf == hash_lf, "CRLF 和 LF 应产生相同 hash"

    def test_trailing_whitespace_stripped(self):
        """行尾 trailing 空白被去除，不影响 hash"""
        h1 = compute_file_hash(b"hello\n")
        h2 = compute_file_hash(b"hello   \n")
        h3 = compute_file_hash(b"hello\t\n")
        assert h1 == h2, "行尾空格应被去除"
        assert h1 == h3, "行尾制表符应被去除"

    def test_internal_spaces_preserved(self):
        """行内空格被保留，影响 hash"""
        h1 = compute_file_hash(b"hello world")
        h2 = compute_file_hash(b"helloworld")
        assert h1 != h2, "不同内容应产生不同 hash"

    def test_hash_is_sha256_hex_string(self):
        """返回值应为 64 字符的 SHA-256 hex 字符串"""
        result = compute_file_hash(b"hello world")
        assert len(result) == 64, "SHA-256 hex 应为 64 字符"
        assert all(c in "0123456789abcdef" for c in result), "应只包含 hex 字符"


class TestComputeFileHashDeterministic:
    """compute_file_hash 对空文件、纯空白文件返回确定性 hash"""

    def test_empty_file_returns_empty_string_sha256(self):
        """空文件返回空字符串的 SHA-256"""
        assert compute_file_hash(b"") == EMPTY_SHA256

    def test_whitespace_only_returns_newline_sha256(self):
        """纯空白文件规范化后为换行符，返回对应 SHA-256"""
        # "   ".rstrip() -> "" -> join -> "" (empty string between newlines)
        # "   " -> normalize: replace \r\n, \r, then split("\n") -> ["   "], rstrip each -> [""], join -> ""
        # So "   " -> "" -> sha256("")
        assert compute_file_hash(b"   ") == EMPTY_SHA256
        # "\n" -> split("\n") -> ["", ""], rstrip each -> ["", ""], join -> "\n"
        # So "\n" normalizes to "\n"
        assert compute_file_hash(b"\n") == hashlib.sha256(b"\n").hexdigest()
        # "\t" -> split("\n") -> ["\t"], rstrip -> [""], join -> ""
        assert compute_file_hash(b"\t") == EMPTY_SHA256

    def test_same_content_same_hash(self):
        """相同内容产生相同 hash"""
        h1 = compute_file_hash(b"  hello   world  ")
        h2 = compute_file_hash(b"  hello   world  ")
        assert h1 == h2
