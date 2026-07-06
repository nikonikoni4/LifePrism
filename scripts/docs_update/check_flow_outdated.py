"""检查 flow 文档是否需要更新

功能：
1. 从 git diff 中提取函数变化
2. 解析 flow 文档的 key_function 标签
3. 匹配检查：哪些 flow 文档涉及变化的函数
4. 输出提醒报告

用法：
    # 检查暂存区（用于 pre-commit hook）
    python scripts/docs_update/check_flow_outdated.py --staged

    # 检查最近 N 次提交
    python scripts/docs_update/check_flow_outdated.py --commits 3

    # 检查指定提交范围
    python scripts/docs_update/check_flow_outdated.py --range HEAD~3..HEAD
"""

import argparse
import io
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# 设置 stdout 为 UTF-8 编码（解决 Windows 控制台问题）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


FLOWS_DIR = Path(__file__).parent.parent.parent / "docs" / "flows"
SPECS_DIR = Path(__file__).parent.parent.parent / "docs" / "specs"


def run_git_command(cmd: list[str]) -> str:
    """运行 git 命令并返回输出"""
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',  # 忽略编码错误
        cwd=Path(__file__).parent.parent.parent
    )
    if result.returncode != 0:
        print(f"Git 命令失败: {' '.join(cmd)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return ""
    return result.stdout if result.stdout else ""


def get_changed_files(mode: str, value: str = "") -> list[str]:
    """获取变化的 Python 文件列表

    Args:
        mode: "staged", "commits", "range"
        value: commits 的数量或 range 的范围

    Returns:
        ["agents_hub/core/agent/base_agent.py", ...]
    """
    if mode == "staged":
        cmd = ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"]
    elif mode == "commits":
        n = int(value) if value else 1
        cmd = ["git", "diff", f"HEAD~{n}", "HEAD", "--name-only", "--diff-filter=AM"]
    elif mode == "range":
        cmd = ["git", "diff", value, "--name-only", "--diff-filter=AM"]
    else:
        return []

    output = run_git_command(cmd)
    files = [line.strip() for line in output.split("\n") if line.strip()]
    # 只保留 Python 文件
    py_files = [f for f in files if f.endswith(".py")]
    return py_files


def get_changed_functions(file_path: str, mode: str, value: str = "") -> set[str]:
    """获取文件中变化的函数列表

    返回函数名集合，格式：{"Agent.run", "Agent._process_message"}
    """
    if mode == "staged":
        cmd = ["git", "diff", "--cached", "-U0", file_path]
    elif mode == "commits":
        n = int(value) if value else 1
        cmd = ["git", "diff", f"HEAD~{n}", "HEAD", "-U0", file_path]
    elif mode == "range":
        cmd = ["git", "diff", value, "-U0", file_path]
    else:
        return set()

    output = run_git_command(cmd)
    functions = set()

    # 解析 diff 输出，查找函数定义变化
    # 匹配：+    def method_name( 或 -    def method_name( 或 +    async def method_name(
    for line in output.split("\n"):
        # 匹配函数定义（支持 async def）
        match = re.match(r'^[\+\-]\s*(async\s+)?def\s+(\w+)\s*\(', line)
        if match:
            func_name = match.group(2)
            functions.add(func_name)

    return functions


def parse_flow_key_functions() -> dict[str, dict[str, list[str]]]:
    """解析所有 flow 和 spec 文档的 key_function 标签

    返回格式：
    {
        "agent-call-lifecycle.md": {
            "agents_hub/core/agent/base_agent.py": [
                "base_agent.Agent.run",
                "base_agent.Agent._process_message"
            ]
        }
    }
    """
    result = {}

    for docs_dir in [FLOWS_DIR, SPECS_DIR]:
        if not docs_dir.exists():
            continue

        for md_file in docs_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8")

            # 匹配 <key_function> 标签
            pattern = r'<key_function[^>]*>(.*?)</key_function>'
            match = re.search(pattern, content, re.DOTALL)
            if not match:
                continue

            tag_content = match.group(1)
            lines = tag_content.strip().split("\n")

            file_functions = defaultdict(list)
            current_file = None

            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue

                # 文件路径行：`- agents_hub/xxx.py`
                if re.match(r'^- [\w/]+\.py$', stripped):
                    current_file = stripped[2:]  # 去掉 "- "
                    continue

                # 函数行：`  - file.Class.method:line`
                func_match = re.match(r'^\s+- (.+?)(?::(\d+))?$', line)
                if func_match and current_file:
                    func_name = func_match.group(1).strip()
                    file_functions[current_file].append(func_name)

            if file_functions:
                dir_label = "flows" if docs_dir == FLOWS_DIR else "specs"
                result[f"{dir_label}/{md_file.name}"] = dict(file_functions)

    return result


def extract_function_name(full_name: str) -> str:
    """从完整函数签名提取函数名

    Args:
        full_name: "base_agent.Agent.run" or "module.function"

    Returns:
        "run" or "function"
    """
    return full_name.split(".")[-1]


def check_flows_need_update(changed_files: list[str], changed_functions_map: dict[str, set[str]],
                            flow_functions: dict[str, dict[str, list[str]]]) -> list[tuple[str, list[str]]]:
    """检查哪些 flow 文档需要更新

    Returns:
        [(flow_name, [matched_functions]), ...]
    """
    needs_update = []

    for flow_name, file_funcs in flow_functions.items():
        matched_funcs = []

        for changed_file in changed_files:
            if changed_file not in file_funcs:
                continue

            # 获取该文件变化的函数
            changed_funcs = changed_functions_map.get(changed_file, set())
            if not changed_funcs:
                continue

            # 检查 flow 中声明的函数是否有变化
            for full_func_name in file_funcs[changed_file]:
                func_name = extract_function_name(full_func_name)
                if func_name in changed_funcs:
                    matched_funcs.append(f"{changed_file}:{full_func_name}")

        if matched_funcs:
            needs_update.append((flow_name, matched_funcs))

    return needs_update


def main():
    parser = argparse.ArgumentParser(description="检查 flow 文档是否需要更新")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--staged", action="store_true", help="检查暂存区（用于 pre-commit hook）")
    group.add_argument("--commits", type=int, metavar="N", help="检查最近 N 次提交")
    group.add_argument("--range", type=str, metavar="RANGE", help="检查指定提交范围（如 HEAD~3..HEAD）")

    args = parser.parse_args()

    # 确定模式和值
    if args.staged:
        mode, value = "staged", ""
    elif args.commits:
        mode, value = "commits", str(args.commits)
    else:
        mode, value = "range", args.range

    print("=" * 60)
    print("文档更新检查（flows + specs）")
    print("=" * 60)

    # 1. 获取变化的文件
    changed_files = get_changed_files(mode, value)
    if not changed_files:
        print("✅ 没有 Python 文件变化")
        return 0

    print(f"\n变化的文件数：{len(changed_files)}")

    # 2. 获取每个文件变化的函数
    changed_functions_map = {}
    for file_path in changed_files:
        funcs = get_changed_functions(file_path, mode, value)
        if funcs:
            changed_functions_map[file_path] = funcs
            print(f"  {file_path}: {len(funcs)} 个函数")

    if not changed_functions_map:
        print("\n✅ 没有函数定义变化")
        return 0

    # 3. 解析 flow 和 spec 文档
    flow_functions = parse_flow_key_functions()
    print(f"\n扫描文档数：{len(flow_functions)}")

    # 4. 检查匹配
    needs_update = check_flows_need_update(changed_files, changed_functions_map, flow_functions)

    if not needs_update:
        print("\n✅ 没有文档需要更新")
        return 0

    # 5. 输出报告
    print("\n" + "=" * 60)
    print("⚠️  以下文档可能需要更新：")
    print("=" * 60)

    for flow_name, matched_funcs in needs_update:
        print(f"\n📄 {flow_name}")
        for func in matched_funcs:
            print(f"   - {func}")

    print("\n" + "=" * 60)
    print(f"提示：共 {len(needs_update)} 个文档可能需要检查")
    print("=" * 60)

    # 返回非零退出码，表示有 flow 需要更新（但不阻塞提交）
    return 0  # 改为 1 可以阻塞提交


if __name__ == "__main__":
    sys.exit(main())
