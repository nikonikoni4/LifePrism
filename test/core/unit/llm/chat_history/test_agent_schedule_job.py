"""测试 agent_schedule_job 模块"""
from lifeprism.llm.function.agent_schedule_job import format_chat_history


def test_format_chat_history():
    """测试 format_chat_history 函数"""
    print("=== 测试 format_chat_history ===\n")

    # 测试用例1：正常数据
    test_history_1 = [
        {"timestamp": "2026-05-12T14:30:45", "content": "用户询问了关于 Python 异步编程的问题"},
        {"timestamp": "2026-05-12T15:45:30", "content": "讨论了数据库设计方案"},
        {"timestamp": "2026-05-12T16:20:15", "content": "用户分享了今天的工作进展"}
    ]
    result_1 = format_chat_history(test_history_1)
    print("测试用例1 - 正常数据:")
    print(result_1)
    print("\n" + "="*50 + "\n")

    # 测试用例2：空列表
    test_history_2 = []
    result_2 = format_chat_history(test_history_2)
    print("测试用例2 - 空列表:")
    print(f"结果: '{result_2}' (应该为空字符串)")
    print("\n" + "="*50 + "\n")

    # 测试用例3：包含缺失字段的数据
    test_history_3 = [
        {"timestamp": "2026-05-12T14:30:45", "content": "有效内容"},
        {"timestamp": "2026-05-12T15:45:30"},  # 缺少 content
        {"content": "缺少时间戳的内容（但仍然有效）"},  # 缺少 timestamp
        {"timestamp": "2026-05-12T16:20:15", "content": "另一条有效内容"}
    ]
    result_3 = format_chat_history(test_history_3)
    print("测试用例3 - 包含缺失字段:")
    print(result_3)
    print("\n" + "="*50 + "\n")

    # 测试用例4：只有 content 字段
    test_history_4 = [
        {"content": "第一条内容"},
        {"content": "第二条内容"},
        {"content": "第三条内容"}
    ]
    result_4 = format_chat_history(test_history_4)
    print("测试用例4 - 只有 content 字段:")
    print(result_4)
    print("\n" + "="*50 + "\n")

    print("所有测试完成！")


if __name__ == "__main__":
    test_format_chat_history()
