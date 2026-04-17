import pytest
import tempfile
from pathlib import Path
from lifeprism.llm.utils.md_os import write_behavior_md

@pytest.mark.core
class TestWriteBehaviorMd:

    def test_write_behavior_md_create_new_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-16"
            content = "这是第一次写入的内容"
            
            write_behavior_md(file_path=file_path, date=date, content=content, mode="append")
            
            assert file_path.exists()
            file_content = file_path.read_text(encoding="utf-8")
            assert f"## {date}" in file_content
            assert content in file_content

    def test_write_behavior_md_append_new_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            initial_content = "## 2026-04-15\n旧的一天\n\n"
            file_path.write_text(initial_content, encoding="utf-8")
            
            date = "2026-04-16"
            content = "新的一天追加内容"
            
            write_behavior_md(file_path=file_path, date=date, content=content, mode="append")
            
            file_content = file_path.read_text(encoding="utf-8")
            assert "## 2026-04-15" in file_content
            assert "旧的一天" in file_content
            assert f"## {date}" in file_content
            assert content in file_content

    def test_write_behavior_md_append_existing_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-16"
            initial_content = f"## {date}\n上午的内容。\n\n"
            file_path.write_text(initial_content, encoding="utf-8")
            
            content = "下午的续写内容。"
            write_behavior_md(file_path=file_path, date=date, content=content, mode="append")
            
            file_content = file_path.read_text(encoding="utf-8")
            assert "上午的内容。" in file_content
            assert "下午的续写内容。" in file_content
            assert file_content.strip().endswith("下午的续写内容。")

    def test_write_behavior_md_overwrite_existing_date(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            date = "2026-04-16"
            initial_content = f"## {date}\n需要被覆盖的内容。\n\n## 2026-04-17\n明天。\n"
            file_path.write_text(initial_content, encoding="utf-8")
            
            content = "全新的内容！"
            write_behavior_md(file_path=file_path, date=date, content=content, mode="overwrite")
            
            file_content = file_path.read_text(encoding="utf-8")
            assert "需要被覆盖的内容" not in file_content
            assert "全新的内容！" in file_content
            assert "## 2026-04-17" in file_content
            assert "明天" in file_content

    def test_write_behavior_md_invalid_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            file_path.write_text("## 2026-04-16\n内容\n", encoding="utf-8")
            
            with pytest.raises(ValueError) as excinfo:
                write_behavior_md(file_path=file_path, date="2026-04-16", content="test", mode="unknown_mode")
            
            assert "Unknown mode: unknown_mode" in str(excinfo.value)

    def test_write_behavior_md_insert_between_dates_in_order(self):
        """新日期应插入到比它小的日期之后、比它大的日期之前（升序保序）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            # 初始文件：只有 04-01 和 04-17，中间缺少 04-12
            initial = "## 2026-04-01\n04-01 的内容\n\n## 2026-04-17\n04-17 的内容\n"
            file_path.write_text(initial, encoding="utf-8")

            write_behavior_md(file_path=file_path, date="2026-04-12", content="04-12 的内容", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            pos_12 = file_content.index("## 2026-04-12")
            pos_17 = file_content.index("## 2026-04-17")
            pos_01 = file_content.index("## 2026-04-01")

            # 04-01 < 04-12 < 04-17
            assert pos_01 < pos_12 < pos_17, (
                f"日期顺序错误: 04-01@{pos_01}, 04-12@{pos_12}, 04-17@{pos_17}"
            )
            assert "04-12 的内容" in file_content

    def test_write_behavior_md_insert_smallest_date_at_front(self):
        """新日期比文件中所有日期都小时，应插入到最前面"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            initial = "## 2026-04-17\n04-17 的内容\n"
            file_path.write_text(initial, encoding="utf-8")

            write_behavior_md(file_path=file_path, date="2026-04-01", content="04-01 的内容", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            pos_01 = file_content.index("## 2026-04-01")
            pos_17 = file_content.index("## 2026-04-17")

            assert pos_01 < pos_17, f"04-01 应在 04-17 前面，实际 pos_01={pos_01}, pos_17={pos_17}"

    def test_write_behavior_md_append_new_date_is_largest(self):
        """新日期比所有已有日期都大时，应追加到文件末尾"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "behavior.md"
            initial = "## 2026-04-01\n04-01 的内容\n\n## 2026-04-12\n04-12 的内容\n"
            file_path.write_text(initial, encoding="utf-8")

            write_behavior_md(file_path=file_path, date="2026-04-17", content="04-17 的内容", mode="append")

            file_content = file_path.read_text(encoding="utf-8")
            pos_12 = file_content.index("## 2026-04-12")
            pos_17 = file_content.index("## 2026-04-17")

            assert pos_12 < pos_17, f"04-17 应排在 04-12 后面，实际 pos_12={pos_12}, pos_17={pos_17}"
