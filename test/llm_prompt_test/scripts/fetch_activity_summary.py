"""获取每日活动数据脚本

从 LifePrism 系统中获取指定日期范围内的每日活动数据，
包含 high_usage_segments, computer_overview, user_behavior_notes, ai_behavior_notes, todolist。

时间范围为每天 04:00:00 到次日 04:00:00。

输出格式：每个日期生成一个 YYYY-MM-DD.md 文件
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 添加项目根目录到 Python 路径 (4 levels up from this file)
project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from lifeprism.llm.agent.tools.lifeprismsystem import query_user_activity_summary


# 常量定义
DAILY_START_HOUR = "04:00:00"
# 输出到 test/llm_prompt_test/dataset/activity_summary 目录
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "dataset" / "activity_summary"
QUERY_OPTIONS = {"high_usage_segments", "computer_overview", "user_behavior_notes", "ai_behavior_notes", "todolist"}

# 日期范围：从5月开始
START_DATE = "2026-05-01"
END_DATE = "2026-05-22"


def generate_date_range(start_date: str, end_date: str) -> list[str]:
    """生成日期范围列表

    Args:
        start_date: 开始日期 YYYY-MM-DD
        end_date: 结束日期 YYYY-MM-DD

    Returns:
        list[str]: 日期列表
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return dates


def fetch_activity_for_date(date: str) -> str:
    """获取指定日期的活动数据

    Args:
        date: 日期 YYYY-MM-DD

    Returns:
        str: 格式化的活动数据
    """
    next_date = (datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
    start_time = f"{date} {DAILY_START_HOUR}"
    end_time = f"{next_date} {DAILY_START_HOUR}"

    print(f"获取数据: {start_time} ~ {end_time}")

    try:
        result = query_user_activity_summary(QUERY_OPTIONS, start_time, end_time)
        return result
    except Exception as e:
        return f"获取数据失败: {str(e)}"


def save_to_md(date: str, content: str) -> None:
    """将内容保存到 md 文件

    Args:
        date: 日期 YYYY-MM-DD
        content: 文件内容
    """
    file_path = OUTPUT_DIR / f"{date}.md"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(f"# {date} 活动数据\n\n")
        f.write(f"时间范围: {date} 04:00:00 ~ {(datetime.strptime(date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')} 04:00:00\n\n")
        f.write(content)

    print(f"已保存: {file_path}")


def main():
    """主函数"""
    print(f"开始获取活动数据")
    print(f"日期范围: {START_DATE} ~ {END_DATE}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("-" * 50)

    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dates = generate_date_range(START_DATE, END_DATE)
    total = len(dates)

    for idx, date in enumerate(dates, 1):
        print(f"[{idx}/{total}] 处理日期: {date}")

        # 获取数据
        content = fetch_activity_for_date(date)

        # 保存到文件
        save_to_md(date, content)

    print("-" * 50)
    print(f"完成! 共处理 {total} 天的数据")


if __name__ == "__main__":
    main()
