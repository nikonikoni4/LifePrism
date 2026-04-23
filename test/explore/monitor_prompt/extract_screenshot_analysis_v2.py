import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List


@dataclass
class SingalBucketAnalysis:
    start_time: str  # YYYY-MM-DD HH-MM-SS
    end_time: str
    behavior: str
    screen_count: int


BLOCK_HEADER_RE = re.compile(r"^\[\d+/\d+\]\s+(.+?)\s+->\s+(.+?)\s*$")
SCREEN_COUNT_RE = re.compile(r"单数过滤后:\s*(\d+)\s*张")
BEHAVIOR_LINE_RE = re.compile(r"^\d+\.\s*(.+?)\s*$")


def parse_analysis_blocks(text: str) -> List[SingalBucketAnalysis]:
    lines = text.splitlines()
    results: List[SingalBucketAnalysis] = []
    i = 0

    while i < len(lines):
        header_match = BLOCK_HEADER_RE.match(lines[i].strip())
        if not header_match:
            i += 1
            continue

        start_time = header_match.group(1).strip()
        end_time = header_match.group(2).strip()

        i += 1
        screen_count = 0
        behaviors: List[str] = []
        in_behavior_section = False

        while i < len(lines):
            current = lines[i].strip()

            if BLOCK_HEADER_RE.match(current):
                break

            screen_match = SCREEN_COUNT_RE.search(current)
            if screen_match:
                screen_count = int(screen_match.group(1))

            if current == "用户行为：":
                in_behavior_section = True
                i += 1
                continue

            if current == "总结：":
                in_behavior_section = False

            if in_behavior_section:
                behavior_match = BEHAVIOR_LINE_RE.match(current)
                if behavior_match:
                    behaviors.append(behavior_match.group(1))

            i += 1

        results.append(
            SingalBucketAnalysis(
                start_time=start_time,
                end_time=end_time,
                behavior="\n".join(behaviors),
                screen_count=screen_count,
            )
        )

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="提取 screenshot_analysis_v2_result.txt 为结构化数据。"
    )
    parser.add_argument(
        "--input",
        default="test/explore/monitor_prompt/screenshot_analysis_v2_result.txt",
        help="输入文本文件路径。",
    )
    parser.add_argument(
        "--output",
        default="test/explore/monitor_prompt/screenshot_analysis_v2_result.json",
        help="输出 JSON 文件路径。",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    text = input_path.read_text(encoding="utf-8")
    parsed = parse_analysis_blocks(text)
    payload = [asdict(item) for item in parsed]

    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
