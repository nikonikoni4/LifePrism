"""基于 grep 的通用函数搜索工具"""

import re
import subprocess
import sys
from pathlib import Path


def search_func(name, root=".", ext="py", ignore_comments=True):
    """搜索函数定义和调用

    name 支持格式:
      - func_name: 搜索所有同名函数
      - ClassName.method_name: 搜索指定类的方法
      - module.ClassName.method_name: 搜索指定模块的类方法
    """
    root = Path(root)

    # 解析名称
    parts = name.rsplit(".", 1)
    if len(parts) == 2 and parts[1][0].isupper() == False:
        # 可能是 ClassName.method 或 module.method
        target_func = parts[1]
        scope = parts[0]
    else:
        target_func = parts[-1]
        scope = None

    print(f"# 函数搜索: {name}")
    print(f"# 范围: {root} (.{ext})")
    if scope:
        print(f"# 限定: {scope}")
    print()

    # 1. 搜索定义 (函数或类)
    print("## 定义")
    def_pattern = rf"(?:(?:async\s+)?def\s+|class\s+){re.escape(target_func)}\s*[\(:]"
    def_results = collect_grep(def_pattern, root, ext, "定义", ignore_comments)

    if def_results:
        # 如果指定了 scope，过滤匹配的结果
        if scope:
            def_results = [r for r in def_results if is_in_scope(r, scope, root)]

        for r in def_results:
            full_name = build_full_name(r, target_func, root)
            print(f"名称: {full_name}")
            print(f"文件: {r['file']}")
            print(f"行号: {r['line']}")
            print(f"代码: {r['content']}")
            print()
    else:
        print("(未找到定义)")
        print()

    # 2. 搜索被调用
    print("## called by")
    call_pattern = rf"(?:await\s+)?(?:\w+\.)*{re.escape(target_func)}\s*\("
    call_results = collect_grep(call_pattern, root, ext, "调用", ignore_comments)

    if call_results:
        # 按文件分组
        by_file = {}
        for r in call_results:
            by_file.setdefault(r["file"], []).append(r)

        for file, items in by_file.items():
            print(f"文件: {file}")
            for item in items:
                func = item.get("enclosing_func")
                if func:
                    func_full = build_enclosing_full_name(file, func, root)
                    print(f"  called by: {func_full} (line {func['line']})")
                else:
                    print(f"  called by: <module>")
                print(f"  {item['content']} (line {item['line']})")
            print()
    else:
        print("(未找到调用)")


def find_enclosing_func(file_path, target_line):
    """找到 target_line 所在的函数/方法"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, PermissionError):
        return None

    # 向上搜索最近的 def
    for i in range(target_line - 1, -1, -1):
        line = lines[i].strip()
        match = re.match(r"^(?:async\s+)?def\s+(\w+)\s*\(", line)
        if match:
            return {"name": match.group(1), "line": i + 1}
        # 遇到 class 也记录
        match = re.match(r"^class\s+(\w+)", line)
        if match:
            return {"name": f"<class {match.group(1)}>", "line": i + 1}
    return None


def collect_grep(pattern, root, ext, label, ignore_comments):
    """执行 grep 搜索，返回结果列表"""
    results = []

    try:
        cmd = [
            "rg",
            "--no-heading",
            "--line-number",
            "--color=never",
            "-g",
            f"*.{ext}",
            pattern,
            str(root),
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")
            for line in lines:
                if not line:
                    continue

                parts = line.split(":", 2)
                if len(parts) < 3:
                    continue

                file_path = parts[0]
                line_no = int(parts[1])
                content = parts[2].strip()

                if ignore_comments and is_comment(content, ext):
                    continue

                if label == "调用" and re.match(r"^\s*(?:async\s+)?def\s+", content):
                    continue

                try:
                    rel_path = str(Path(file_path).relative_to(root))
                except ValueError:
                    rel_path = file_path

                entry = {
                    "file": rel_path,
                    "line": line_no,
                    "content": content,
                }

                if label == "调用":
                    entry["enclosing_func"] = find_enclosing_func(file_path, line_no)

                results.append(entry)

        else:
            pass  # rg 失败，fallback 到 python

    except (FileNotFoundError, subprocess.TimeoutExpired):
        results = collect_grep_python(pattern, root, ext, label, ignore_comments)

    return results


def collect_grep_python(pattern, root, ext, label, ignore_comments):
    """Python 实现的 grep，返回结果列表"""
    regex = re.compile(pattern)
    results = []

    for file in root.rglob(f"*.{ext}"):
        if any(skip in str(file) for skip in [".venv", "__pycache__", ".claude", "node_modules"]):
            continue

        try:
            with open(file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if regex.search(line):
                        content = line.strip()

                        if ignore_comments and is_comment(content, ext):
                            continue

                        if label == "调用" and re.match(r"^\s*(?:async\s+)?def\s+", content):
                            continue

                        try:
                            rel_path = str(file.relative_to(root))
                        except ValueError:
                            rel_path = str(file)

                        entry = {
                            "file": rel_path,
                            "line": line_no,
                            "content": content,
                        }

                        if label == "调用":
                            entry["enclosing_func"] = find_enclosing_func(str(file), line_no)

                        results.append(entry)
        except (UnicodeDecodeError, PermissionError):
            continue

    return results


def grep_python(pattern, root, ext, label, ignore_comments):
    """Python 实现的 grep"""
    regex = re.compile(pattern)
    count = 0

    for file in root.rglob(f"*.{ext}"):
        # 跳过特定目录
        if any(skip in str(file) for skip in [".venv", "__pycache__", ".claude", "node_modules"]):
            continue

        try:
            with open(file, "r", encoding="utf-8") as f:
                for line_no, line in enumerate(f, 1):
                    if regex.search(line):
                        content = line.strip()

                        # 忽略注释
                        if ignore_comments and is_comment(content, ext):
                            continue

                        # 忽略定义本身（当搜索调用时）
                        if label == "调用" and re.match(r"^\s*(?:async\s+)?def\s+", content):
                            continue

                        try:
                            rel_path = file.relative_to(root)
                        except ValueError:
                            rel_path = file

                        print(f"  {rel_path}:{line_no}")
                        print(f"    {content}")

                        # 找所在函数
                        func = find_enclosing_func(str(file), line_no)
                        if func:
                            print(f"    ^ 所在函数: {func['name']} (line {func['line']})")

                        count += 1
        except (UnicodeDecodeError, PermissionError):
            continue

    if count == 0:
        print(f"  (未找到{label})")
    else:
        print(f"\n  共 {count} 处{label}")


def is_comment(line, ext):
    """判断是否是注释"""
    stripped = line.strip()
    if ext == "py":
        return stripped.startswith("#")
    elif ext in ("js", "ts", "jsx", "tsx"):
        return stripped.startswith("//") or stripped.startswith("/*") or stripped.startswith("*")
    return False


def file_to_module(file_path):
    """文件路径转模块名"""
    # agents_hub/executors/claude.py -> agents_hub.executors.claude
    parts = Path(file_path).with_suffix("").parts
    return ".".join(parts)


def is_in_scope(result, scope, root="."):
    """检查结果是否在指定范围内"""
    module = file_to_module(result["file"])

    # scope 可以是类名、模块前缀或两者的组合
    # 1. 模块路径匹配
    if scope in module or module.endswith(scope):
        return True

    # 2. 类名匹配 - 检查该行是否在指定类内
    full_path = Path(root) / result["file"]
    enclosing_class = find_enclosing_class(str(full_path), result["line"])
    if enclosing_class and (enclosing_class == scope or scope.endswith(enclosing_class)):
        return True

    # 3. 组合匹配: module.ClassName
    if "." in scope:
        scope_parts = scope.rsplit(".", 1)
        if len(scope_parts) == 2:
            scope_module, scope_class = scope_parts
            if scope_module in module and (
                enclosing_class == scope_class or scope_class == enclosing_class
            ):
                return True

    return False


def build_full_name(result, func_name, root="."):
    """构建完整名称: 模块.类名.方法名"""
    module = file_to_module(result["file"])
    content = result["content"].strip()

    # 检查是否是类方法
    full_path = Path(root) / result["file"]
    enclosing = find_enclosing_class(str(full_path), result["line"])
    if enclosing:
        return f"{module}.{enclosing}.{func_name}"
    else:
        return f"{module}.{func_name}"


def find_enclosing_class(file_path, target_line):
    """找到 target_line 所在的类"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (UnicodeDecodeError, PermissionError):
        return None

    for i in range(target_line - 1, -1, -1):
        line = lines[i].strip()
        match = re.match(r"^class\s+(\w+)", line)
        if match:
            return match.group(1)
    return None


def build_enclosing_full_name(file_path, func_info, root="."):
    """构建调用方的完整名称"""
    module = file_to_module(file_path)
    func_name = func_info["name"]

    # 如果是类方法（名字带点或首字母大写）
    if func_name.startswith("<"):
        return f"{module}.{func_name}"

    # 检查是否在类内
    full_path = Path(root) / file_path
    enclosing_class = find_enclosing_class(str(full_path), func_info["line"])
    if enclosing_class:
        return f"{module}.{enclosing_class}.{func_name}"
    else:
        return f"{module}.{func_name}"


def main():
    if len(sys.argv) < 2:
        print("用法: python func_search.py <名称> [目录] [后缀]")
        print()
        print("参数:")
        print("  名称    函数/方法名，支持以下格式:")
        print("          func_name              搜索所有同名函数")
        print("          Class.method           搜索指定类的方法")
        print("          module.Class.method    完整路径匹配")
        print("  目录    搜索范围，默认当前目录")
        print("  后缀    文件类型，默认 py")
        print()
        print("示例:")
        print("  python func_search.py execute")
        print("  python func_search.py ClaudeExecutor.execute agents_hub py")
        print("  python func_search.py handleSubmit src tsx")
        return

    name = sys.argv[1]
    root = sys.argv[2] if len(sys.argv) > 2 else "."
    ext = sys.argv[3] if len(sys.argv) > 3 else "py"

    search_func(name, root, ext)


if __name__ == "__main__":
    main()
