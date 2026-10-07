"""日期章节写入与原子替换回归。"""

import pytest

from lifeprism.llm.utils.md_os import write_date_md

pytestmark = pytest.mark.regression


def test_subheading_search_stays_in_target_date(tmp_path):
    path = tmp_path / "behavior.md"
    path.write_text(
        "## 2026-10-07\n### 行为总结\n今天行为\n\n## 2026-10-08\n### 聊天记录总结\n未来聊天\n",
        encoding="utf-8",
    )
    write_date_md(path, "2026-10-07", "今天聊天", "聊天记录总结", mode="overwrite")
    today, future = path.read_text(encoding="utf-8").split("## 2026-10-08")
    assert "今天聊天" in today
    assert "未来聊天" in future
    assert "今天聊天" not in future


def test_failed_atomic_replace_preserves_behavior(tmp_path, monkeypatch):
    import lifeprism.llm.utils.md_os as md

    path = tmp_path / "behavior.md"
    path.write_text("## 2026-10-07\n### 聊天记录总结\n原内容\n", encoding="utf-8")
    original = path.read_bytes()

    def fail(*args):
        raise OSError("replace failed")

    monkeypatch.setattr(md.os, "replace", fail, raising=False)
    with pytest.raises(OSError, match="replace failed"):
        write_date_md(path, "2026-10-07", "新内容", "聊天记录总结", mode="overwrite")
    assert path.read_bytes() == original
    assert list(tmp_path.glob("*.tmp")) == []
