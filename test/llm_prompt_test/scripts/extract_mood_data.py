"""
提取 mood_entries 表数据到 JSON 文件

从 localData/dataset/lifewatch_ai.db 中读取 mood_entries 表的所有记录，
每条记录输出为一个 JSON 对象，整体输出为一个 JSON 数组文件 mood.json
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到 Python 路径
# 脚本位于 test/llm_prompt_test/scripts/，需要回到项目根目录
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent.parent.parent
sys.path.insert(0, str(project_root))

from lifeprism.repository import mood_repository


def extract_mood_entries() -> List[Dict[str, Any]]:
    """
    从数据库中提取 mood_entries 表的所有数据

    Returns:
        List[Dict[str, Any]]: 心情记录列表
    """
    # 使用 mood_repository 获取所有心情记录
    mood_entries = mood_repository.get_mood_entries()

    # 处理 factors 字段：从 JSON 字符串解析为数组
    for entry in mood_entries:
        if 'factors' in entry and isinstance(entry['factors'], str):
            try:
                entry['factors'] = json.loads(entry['factors'])
            except (json.JSONDecodeError, TypeError):
                entry['factors'] = []

    return mood_entries


def save_to_json(data: List[Dict[str, Any]], output_path: Path) -> None:
    """
    保存数据到 JSON 文件

    Args:
        data: 要保存的数据
        output_path: 输出文件路径
    """
    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def main():
    """主函数"""
    # 输出文件路径 - 输出到 test/llm_prompt_test/dataset/mood 目录
    script_dir = Path(__file__).resolve().parent
    output_dir = script_dir.parent / "dataset" / "mood"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "mood.json"

    print(f"正在从数据库提取 mood_entries 数据...")
    mood_entries = extract_mood_entries()

    print(f"共提取 {len(mood_entries)} 条记录")

    print(f"正在保存到 {output_path}...")
    save_to_json(mood_entries, output_path)

    print(f"[SUCCESS] 数据已成功保存到: {output_path}")
    print(f"\n前 3 条记录预览:")
    for i, entry in enumerate(mood_entries[:3], 1):
        print(f"\n记录 {i}:")
        print(json.dumps(entry, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
