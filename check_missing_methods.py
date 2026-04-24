#!/usr/bin/env python3
"""检查 Aggregator 中缺失的方法"""

import re
import os
from pathlib import Path

# 定义需要检查的 store 和对应的 aggregator 文件
stores = {
    'goal_store': 'lifeprism/storage/aggregators/goal_aggregator.py',
    'habit_store': 'lifeprism/storage/aggregators/habit_aggregator.py',
    'mood_store': 'lifeprism/storage/aggregators/mood_aggregator.py',
    'habit_chain_store': 'lifeprism/storage/aggregators/habit_chain_aggregator.py',
    'map_cache_store': 'lifeprism/storage/aggregators/map_cache_aggregator.py',
    'category_store': 'lifeprism/storage/aggregators/category_aggregator.py',
}

def get_aggregator_methods(file_path):
    """获取 aggregator 中定义的所有方法"""
    methods = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 匹配 def method_name(self, ...)
            pattern = r'def (\w+)\(self'
            for match in re.finditer(pattern, content):
                method_name = match.group(1)
                if not method_name.startswith('_'):  # 排除私有方法
                    methods.add(method_name)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return methods

def get_service_calls(store_name):
    """获取 service 层中调用的所有 store 方法"""
    calls = set()
    services_dir = 'lifeprism/server/services'

    # 匹配 store.method_name( 或 self.store.method_name(
    pattern = rf'(?:self\.)?{store_name}\.(\w+)\('

    for root, dirs, files in os.walk(services_dir):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for match in re.finditer(pattern, content):
                            method_name = match.group(1)
                            calls.add(method_name)
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

    return calls

def main():
    print("=" * 80)
    print("检查 Aggregator 缺失的方法")
    print("=" * 80)
    print()

    all_missing = {}

    for store_name, aggregator_file in stores.items():
        print(f"\n{'=' * 60}")
        print(f"检查 {store_name} ({aggregator_file})")
        print(f"{'=' * 60}")

        # 获取 aggregator 中已有的方法
        existing_methods = get_aggregator_methods(aggregator_file)
        print(f"已有方法数量: {len(existing_methods)}")

        # 获取 service 层调用的方法
        called_methods = get_service_calls(store_name)
        print(f"Service 层调用的方法数量: {len(called_methods)}")

        # 找出缺失的方法
        missing_methods = called_methods - existing_methods

        if missing_methods:
            print(f"\n缺失的方法 ({len(missing_methods)} 个):")
            for method in sorted(missing_methods):
                print(f"  - {method}")
            all_missing[store_name] = sorted(missing_methods)
        else:
            print("\n[OK] 没有缺失的方法")

    # 总结
    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)

    if all_missing:
        print(f"\n发现 {len(all_missing)} 个 store 有缺失的方法:")
        for store_name, methods in all_missing.items():
            print(f"\n{store_name}:")
            for method in methods:
                print(f"  - {method}")
    else:
        print("\n[OK] 所有 store 都没有缺失的方法！")

if __name__ == '__main__':
    main()
