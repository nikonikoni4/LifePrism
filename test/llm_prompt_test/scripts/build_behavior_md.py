"""
构建 behavior.md 脚本
从 test/llm_prompt_test/results 中的最新测试结果组装 behavior.md
用于测试 templates/prompts/schedule_prompts.md 中的 update_memory prompt
"""

import json
from pathlib import Path
from collections import defaultdict

# 项目根目录
ROOT = Path(__file__).resolve().parent.parent.parent.parent
RESULTS_DIR = ROOT / "test" / "llm_prompt_test" / "results"
OUTPUT_DIR = ROOT / "test" / "llm_prompt_test" / "dataset" / "update_memory"
OUTPUT_FILE = OUTPUT_DIR / "behavior.md"

# 数据源配置 (文件夹名 -> 最新版本的JSON文件)
DATA_SOURCES = {
    "activity_summary": "v1/r2-t0.7.json",
    "mood_summary": "v1/r2-t0.7.json",
    "extract_chat": "v1/r8-t0.7.json",
    "create_diary_summary": "v4/r6-t0.7.json",
}

# behavior.md 各部分对应的标题
SECTION_TITLES = {
    "activity_summary": "行为总结",
    "mood_summary": "心情总结",
    "extract_chat": "聊天总结",
    "create_diary_summary": "日记总结",
}


def load_json_data(source_name: str, file_path: str) -> list[dict]:
    """加载指定的JSON文件"""
    full_path = RESULTS_DIR / source_name / file_path
    if not full_path.exists():
        print(f"警告: 文件不存在 {full_path}")
        return []
    with open(full_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"已加载 {source_name}/{file_path}: {len(data)} 条记录")
    return data


def aggregate_by_date(all_data: dict[str, list[dict]]) -> dict[str, dict[str, str]]:
    """
    按 input_data_date 聚合所有数据
    返回格式: {date: {source_name: result_text, ...}}
    """
    aggregated = defaultdict(dict)

    for source_name, records in all_data.items():
        for record in records:
            date = record.get("input_data_date", "")
            if not date:
                continue
            result = record.get("result", "").strip()
            if not result:
                continue
            # 同一来源同一天可能有多条记录，追加合并
            if source_name in aggregated[date]:
                aggregated[date][source_name] += "\n\n" + result
            else:
                aggregated[date][source_name] = result

    return dict(aggregated)


def build_behavior_md(aggregated: dict[str, dict[str, str]]) -> str:
    """组装 behavior.md 内容"""
    lines = []
    lines.append("# behavior.md")
    lines.append("")
    lines.append("本文档由 build_behavior_md.py 脚本自动生成，用于测试 update_memory prompt。")
    lines.append("")

    # 按日期排序
    sorted_dates = sorted(aggregated.keys())

    for date in sorted_dates:
        sections = aggregated[date]
        lines.append(f"## {date}")

        for source_name, section_title in SECTION_TITLES.items():
            lines.append(f"### {section_title}")
            content = sections.get(source_name, "")
            if content:
                lines.append(content)
            else:
                lines.append("暂无数据")
            lines.append("")

    return "\n".join(lines)


def main():
    # 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 加载所有数据源
    all_data = {}
    for source_name, file_path in DATA_SOURCES.items():
        data = load_json_data(source_name, file_path)
        all_data[source_name] = data

    # 按日期聚合
    aggregated = aggregate_by_date(all_data)

    # 组装 behavior.md
    content = build_behavior_md(aggregated)

    # 写入文件
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n已生成 behavior.md: {OUTPUT_FILE}")
    print(f"包含 {len(aggregated)} 个日期的数据")
    print(f"日期范围: {min(aggregated.keys())} ~ {max(aggregated.keys())}")


if __name__ == "__main__":
    main()
