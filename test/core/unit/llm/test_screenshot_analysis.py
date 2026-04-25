"""测试 screenshot_analysis 模块的 get_today_todolist 函数"""
import pytest
from datetime import datetime

from lifeprism.llm.function.screenshot_analysis import get_today_todolist, merage_results_list


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


@pytest.mark.core
class TestMerageResultsList:
    """测试 merage_results_list 函数"""

    def test_empty_list(self):
        """测试空列表"""
        result = merage_results_list([])
        assert result == []

    def test_single_item_list(self):
        """测试单个元素的列表"""
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:30',
                'screenshot_count': 5,
                'behavior': 'Reading'
            }
        ]
        result = merage_results_list(input_list)
        assert len(result) == 1
        assert result[0]['screenshot_count'] == 5
        assert result[0]['behavior'] == 'Reading'

    def test_multiple_items_no_merge(self):
        """测试多个不相关的项目（时间不连续，不应该合并）"""
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:30',
                'screenshot_count': 5,
                'behavior': 'Reading'
            },
            {
                'start_time': '11:00',
                'end_time': '11:30',
                'screenshot_count': 3,
                'behavior': 'Writing'
            },
            {
                'start_time': '14:00',
                'end_time': '14:30',
                'screenshot_count': 7,
                'behavior': 'Coding'
            }
        ]
        result = merage_results_list(input_list)
        assert len(result) == 3
        assert result[0]['screenshot_count'] == 5
        assert result[0]['behavior'] == 'Reading'
        assert result[1]['screenshot_count'] == 3
        assert result[1]['behavior'] == 'Writing'
        assert result[2]['screenshot_count'] == 7
        assert result[2]['behavior'] == 'Coding'

    def test_multiple_items_with_merge(self):
        """测试多个相邻的项目（时间连续，应该合并）"""
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:30',
                'screenshot_count': 5,
                'behavior': 'Reading'
            },
            {
                'start_time': '10:30',
                'end_time': '11:00',
                'screenshot_count': 3,
                'behavior': 'Writing'
            }
        ]
        result = merage_results_list(input_list)
        assert len(result) == 1
        assert result[0]['screenshot_count'] == 8  # 5 + 3
        assert result[0]['behavior'] == 'ReadingWriting'

    def test_mixed_merge_and_no_merge(self):
        """测试混合场景：部分项目需要合并，部分不需要"""
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:30',
                'screenshot_count': 5,
                'behavior': 'Reading'
            },
            {
                'start_time': '10:30',
                'end_time': '11:00',
                'screenshot_count': 3,
                'behavior': 'Writing'
            },
            {
                'start_time': '12:00',
                'end_time': '12:30',
                'screenshot_count': 7,
                'behavior': 'Coding'
            },
            {
                'start_time': '12:30',
                'end_time': '13:00',
                'screenshot_count': 2,
                'behavior': 'Testing'
            },
            {
                'start_time': '15:00',
                'end_time': '15:30',
                'screenshot_count': 4,
                'behavior': 'Debugging'
            }
        ]
        result = merage_results_list(input_list)
        assert len(result) == 3

        # 第一个合并组
        assert result[0]['screenshot_count'] == 8  # 5 + 3
        assert result[0]['behavior'] == 'ReadingWriting'

        # 第二个合并组
        assert result[1]['screenshot_count'] == 9  # 7 + 2
        assert result[1]['behavior'] == 'CodingTesting'

        # 第三个单独项
        assert result[2]['screenshot_count'] == 4
        assert result[2]['behavior'] == 'Debugging'

    def test_three_consecutive_merges(self):
        """测试三个连续的项目全部合并"""
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:20',
                'screenshot_count': 2,
                'behavior': 'A'
            },
            {
                'start_time': '10:20',
                'end_time': '10:40',
                'screenshot_count': 3,
                'behavior': 'B'
            },
            {
                'start_time': '10:40',
                'end_time': '11:00',
                'screenshot_count': 5,
                'behavior': 'C'
            }
        ]
        result = merage_results_list(input_list)
        assert len(result) == 1
        assert result[0]['screenshot_count'] == 10  # 2 + 3 + 5
        assert result[0]['behavior'] == 'ABC'

    def test_none_values_in_behavior(self):
        """测试 behavior 为 None 的情况
        
        注意: 当前实现不支持 None 值，会抛出 TypeError
        如果需要支持 None，应该将其视为空字符串处理
        """
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:30',
                'screenshot_count': 5,
                'behavior': None
            },
            {
                'start_time': '10:30',
                'end_time': '11:00',
                'screenshot_count': 3,
                'behavior': 'Reading'
            }
        ]
        # 当前实现会抛出 TypeError，因为 += 不支持 None + str
        # 这是实现的一个限制，需要在代码中处理 None 值
        with pytest.raises(TypeError):
            merage_results_list(input_list)

    def test_preserves_other_fields(self):
        """测试保留其他字段不变
        
        注意: 当前实现不会更新 end_time
        合并后的 end_time 保持为第一个项目的时间
        这可能是设计决策，也可能是需要修复的 bug
        """
        input_list = [
            {
                'start_time': '10:00',
                'end_time': '10:30',
                'screenshot_count': 5,
                'behavior': 'Reading',
                'extra_field': 'value1',
                'id': 1
            },
            {
                'start_time': '10:30',
                'end_time': '11:00',
                'screenshot_count': 3,
                'behavior': 'Writing',
                'extra_field': 'value2',
                'id': 2
            }
        ]
        result = merage_results_list(input_list)
        assert len(result) == 1
        assert result[0]['start_time'] == '10:00'
        # end_time 保持为第一个项目的时间，不会更新为合并后的最后时间
        assert result[0]['end_time'] == '10:30'
        assert result[0]['screenshot_count'] == 8
        assert result[0]['behavior'] == 'ReadingWriting'
        assert result[0]['extra_field'] == 'value1'
        assert result[0]['id'] == 1


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
