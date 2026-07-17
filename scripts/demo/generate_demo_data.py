#!/usr/bin/env python3
"""
Web-Demo 演示数据生成脚本（CLI 入口）

自 2026-07-10 起，演示数据生成已集成到 web-demo 的 lifespan 中自动执行。
本脚本保留作为手动 CLI 入口，供独立测试/调试使用。

核心逻辑位于 lifeprism/server/demo/demo_data_generator.py。

用法：
    python scripts/demo/generate_demo_data.py [--data-path PATH] [--days 7]
"""

import argparse
import random
import sys
from datetime import datetime
from pathlib import Path

# 将项目根目录加入 Python path
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Web-Demo 演示数据生成脚本")
    parser.add_argument("--data-path", default="localData", help="数据目录路径（默认: localData）")
    parser.add_argument("--days", type=int, default=7, help="生成多少天的数据（默认: 7）")
    args = parser.parse_args()

    data_path = Path(args.data_path).resolve()
    if not data_path.exists():
        print(f"[ERROR] 数据目录不存在: {data_path}")
        sys.exit(1)

    from lifeprism.config.settings_manager import settings  # noqa: F401
    from scripts.demo.demo_data_generator import DemoDataGenerator

    random.seed(datetime.now().strftime("%Y%m%d"))

    generator = DemoDataGenerator(data_path, args.days)
    generator.run()


if __name__ == "__main__":
    main()
