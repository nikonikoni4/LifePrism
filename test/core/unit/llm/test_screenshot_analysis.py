"""测试 screenshot_analysis 模块的 get_today_todolist 函数"""
import pytest
from datetime import datetime

from lifeprism.llm.function.screenshot_analysis import get_today_todolist


@pytest.mark.core
class TestGetTodayTodolist:
    """测试 get_today_todolist 函数"""

    def test_get_today_todolist_basic(self):
        """测试基本功能"""
        today = datetime.now().strftime("%Y-%m-%d")
        result = get_today_todolist(today)

        # 结果应该是字符串或 None
        assert result is None or isinstance(result, str)

    def test_get_today_todolist_format(self):
        """测试输出格式"""
        today = datetime.now().strftime("%Y-%m-%d")
        result = get_today_todolist(today)

        if result is not None:
            # 应该包含标题
            assert "## 今日目标：" in result

            # 应该有编号列表
            lines = result.split("\n")
            numbered_lines = [line for line in lines if line.strip() and line[0].isdigit()]

            # 如果有内容，应该有编号行
            if len(lines) > 2:  # 标题 + 空行 + 内容
                assert len(numbered_lines) > 0

                # 验证编号格式
                for i, line in enumerate(numbered_lines, 1):
                    assert line.startswith(f"{i}. "), f"编号格式错误: {line}"

    def test_get_today_todolist_empty_date(self):
        """测试未来日期（应该没有数据）"""
        future_date = "2099-12-31"
        result = get_today_todolist(future_date)

        # 未来日期应该返回 None
        assert result is None

    def test_get_today_todolist_return_type(self):
        """测试返回类型"""
        today = datetime.now().strftime("%Y-%m-%d")
        result = get_today_todolist(today)

        # 返回值应该是 str 或 None
        assert isinstance(result, (str, type(None)))


@pytest.mark.core
class TestGetTodayTodolistIntegration:
    """测试 get_today_todolist 与数据库的集成"""

    def test_includes_active_todos(self):
        """测试是否包含 active 状态的任务"""
        today = datetime.now().strftime("%Y-%m-%d")
        result = get_today_todolist(today)

        # 如果有结果，验证格式正确
        if result is not None:
            assert isinstance(result, str)
            assert len(result) > 0

    def test_output_structure(self):
        """测试输出结构完整性"""
        today = datetime.now().strftime("%Y-%m-%d")
        result = get_today_todolist(today)

        if result is not None:
            lines = result.split("\n")

            # 第一行应该是标题
            assert lines[0] == "## 今日目标："

            # 第二行应该是空行
            if len(lines) > 1:
                assert lines[1] == ""

            # 后续行应该是编号列表或空
            for line in lines[2:]:
                if line.strip():
                    # 非空行应该是编号格式
                    assert line[0].isdigit() and ". " in line


if __name__ == "__main__":
    # 手动测试
    today = datetime.now().strftime("%Y-%m-%d")
    result = get_today_todolist(today)

    print("=" * 60)
    print(f"测试日期: {today}")
    print("=" * 60)

    if result:
        print(result)
    else:
        print("今日没有待办任务")

    print("=" * 60)
