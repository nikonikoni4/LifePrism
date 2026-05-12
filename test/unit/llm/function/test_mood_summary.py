"""
心情数据获取和总结功能测试
"""
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from datetime import datetime, timedelta
from lifeprism.llm.function.agent_schedule_job import get_mood_data, summary_moods


async def test_get_mood_data():
    """测试 get_mood_data 函数"""
    print("=" * 50)
    print("测试 get_mood_data 函数")
    print("=" * 50)

    # 使用今天的日期
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')

    start_time = f"{today} 04:00:00"
    end_time = f"{tomorrow} 04:00:00"

    print(f"查询时间范围: {start_time} ~ {end_time}")

    mood_data = get_mood_data(start_time, end_time)
    print(f"\n获取到的心情数据:\n{mood_data}")

    return mood_data


async def test_summary_moods(mood_data: str):
    """测试 summary_moods 函数"""
    print("\n" + "=" * 50)
    print("测试 summary_moods 函数")
    print("=" * 50)

    summary = await summary_moods(mood_data)
    print(f"\n心情总结结果:\n{summary}")

    return summary


async def main():
    """主测试函数"""
    try:
        # 测试 get_mood_data
        mood_data = await test_get_mood_data()

        # 测试 summary_moods
        if mood_data and "无心情记录" not in mood_data:
            await test_summary_moods(mood_data)
        else:
            print("\n没有心情数据，跳过总结测试")

        print("\n" + "=" * 50)
        print("测试完成")
        print("=" * 50)

    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
