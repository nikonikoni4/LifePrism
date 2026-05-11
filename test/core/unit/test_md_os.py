"""Tests for md_os module - loaded directly to avoid circular imports."""
import pytest
import sys
import tempfile
from pathlib import Path

# Load md_os directly using importlib to avoid circular import issues
# that arise when importing from lifeprism.llm.utils
import importlib.util

def _load_md_os():
    """Load md_os module directly from file path."""
    # test/core/unit/test_md_os.py -> project root: go up 4 levels
    md_os_path = Path(__file__).resolve().parent.parent.parent.parent / "lifeprism" / "llm" / "utils" / "md_os.py"
    spec = importlib.util.spec_from_file_location("md_os", md_os_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["md_os"] = module
    spec.loader.exec_module(module)
    return module

_md_os = _load_md_os()
write_date_md = _md_os.write_date_md
extract_date_md = _md_os.extract_date_md
read_md = _md_os.read_md


@pytest.mark.core
class TestWriteBehaviorMd:

    def test_write_date_md_create_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-16"
            content = "这是第一次写入的内容"

            write_date_md(file_path=file_path, date=date, content=content, subheading="日记总结", mode="append")

            assert file_path.exists()
            file_content = file_path.read_text(encoding="utf-8")
            assert f"## {date}" in file_content
            assert f"### 日记总结" in file_content
            assert content in file_content

    def test_write_date_md_append_new_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            initial_content = "## 2026-04-15\n### 日记总结\n旧的一天\n\n"
            file_path.write_text(initial_content, encoding="utf-8")

            date = "2026-04-16"
            content = "新的一天追加内容"

            write_date_md(file_path=file_path, date=date, content=content, subheading="日记总结", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            assert "## 2026-04-15" in file_content
            assert "旧的一天" in file_content
            assert f"## {date}" in file_content
            assert content in file_content

    def test_write_date_md_append_existing_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-16"
            initial_content = f"## {date}\n### 日记总结\n上午的内容。\n\n"
            file_path.write_text(initial_content, encoding="utf-8")

            content = "下午的续写内容。"
            write_date_md(file_path=file_path, date=date, content=content, subheading="日记总结", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            assert "上午的内容。" in file_content
            assert "下午的续写内容。" in file_content
            assert file_content.strip().endswith("下午的续写内容。")

    def test_write_date_md_overwrite_existing_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-16"
            initial_content = f"## {date}\n### 日记总结\n需要被覆盖的内容。\n\n## 2026-04-17\n### 日记总结\n明天。\n"
            file_path.write_text(initial_content, encoding="utf-8")

            content = "全新的内容！"
            write_date_md(file_path=file_path, date=date, content=content, subheading="日记总结", mode="overwrite")

            file_content = file_path.read_text(encoding="utf-8")
            assert "需要被覆盖的内容" not in file_content
            assert "全新的内容！" in file_content
            assert "## 2026-04-17" in file_content
            assert "明天" in file_content

    def test_write_date_md_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            file_path.write_text("## 2026-04-16\n### 日记总结\n内容\n", encoding="utf-8")

            with pytest.raises(ValueError) as excinfo:
                write_date_md(file_path=file_path, date="2026-04-16", content="test", subheading="日记总结", mode="unknown_mode")

            assert "Unknown mode: unknown_mode" in str(excinfo.value)

    def test_write_date_md_insert_between_dates_in_order(self):
        """新日期应插入到比它小的日期之后、比它大的日期之前（升序保序）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            # 初始文件：只有 04-01 和 04-17，中间缺少 04-12
            initial = "## 2026-04-01\n### 日记总结\n04-01 的内容\n\n## 2026-04-17\n### 日记总结\n04-17 的内容\n"
            file_path.write_text(initial, encoding="utf-8")

            write_date_md(file_path=file_path, date="2026-04-12", content="04-12 的内容", subheading="日记总结", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            pos_12 = file_content.index("## 2026-04-12")
            pos_17 = file_content.index("## 2026-04-17")
            pos_01 = file_content.index("## 2026-04-01")

            # 04-01 < 04-12 < 04-17
            assert pos_01 < pos_12 < pos_17, (
                f"日期顺序错误: 04-01@{pos_01}, 04-12@{pos_12}, 04-17@{pos_17}"
            )
            assert "04-12 的内容" in file_content

    def test_write_date_md_insert_smallest_date_at_front(self):
        """新日期比文件中所有日期都小时，应插入到最前面"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            initial = "## 2026-04-17\n### 日记总结\n04-17 的内容\n"
            file_path.write_text(initial, encoding="utf-8")

            write_date_md(file_path=file_path, date="2026-04-01", content="04-01 的内容", subheading="日记总结", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            pos_01 = file_content.index("## 2026-04-01")
            pos_17 = file_content.index("## 2026-04-17")

            assert pos_01 < pos_17, f"04-01 应在 04-17 前面，实际 pos_01={pos_01}, pos_17={pos_17}"

    def test_write_date_md_append_new_date_is_largest(self):
        """新日期比所有已有日期都大时，应追加到文件末尾"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            initial = "## 2026-04-01\n### 日记总结\n04-01 的内容\n\n## 2026-04-12\n### 日记总结\n04-12 的内容\n"
            file_path.write_text(initial, encoding="utf-8")

            write_date_md(file_path=file_path, date="2026-04-17", content="04-17 的内容", subheading="日记总结", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            pos_12 = file_content.index("## 2026-04-12")
            pos_17 = file_content.index("## 2026-04-17")

            assert pos_12 < pos_17, f"04-17 应排在 04-12 后面，实际 pos_12={pos_12}, pos_17={pos_17}"


@pytest.mark.core
class TestWriteBehaviorMdSubheading:
    """Tests for write_date_md requiring subheading parameter."""

    def test_write_date_md_requires_subheading(self):
        """write_date_md must raise ValueError when subheading is None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            with pytest.raises(ValueError):
                write_date_md(file_path, "2026-04-18", "content", subheading=None)

    def test_write_date_md_requires_subheading_empty_string(self):
        """write_date_md must raise ValueError when subheading is empty string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            with pytest.raises(ValueError):
                write_date_md(file_path, "2026-04-18", "content", subheading="")

    def test_write_date_md_with_subheading_creates_heading_structure(self):
        """write_date_md should create ## date -> ### subheading structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-18"
            subheading = "日记总结"
            content = "这是日记内容"

            write_date_md(file_path, date, content, subheading=subheading)

            file_content = file_path.read_text(encoding="utf-8")
            assert f"## {date}" in file_content
            assert f"### {subheading}" in file_content
            assert content in file_content


@pytest.mark.core
class TestExtractBehaviorMdSubheading:
    """Tests for extract_date_md subheading filtering."""

    def test_extract_date_md_reads_named_subheading_only(self):
        """extract_date_md should only return content under the specified subheading."""
        markdown = """
## 2026-04-18

### 日记总结
summary body

### 其他内容
other body
"""
        result = extract_date_md(markdown, "2026-04-18", subheading="日记总结")
        assert result["2026-04-18"] == "summary body"

    def test_extract_date_md_reads_all_subheadings_by_default(self):
        """extract_date_md with subheading='all' should return all subheading content."""
        markdown = """
## 2026-04-18

### 日记总结
summary body

### 其他内容
other body
"""
        result = extract_date_md(markdown, "2026-04-18", subheading="all")
        assert "日记总结" not in result["2026-04-18"]  # subheading names not included in body
        assert "summary body" in result["2026-04-18"]
        assert "other body" in result["2026-04-18"]
