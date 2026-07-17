"""Flow 文档函数位置同步脚本

功能：
1. 防抖（10分钟间隔）
2. 运行 AST 扫描器
3. 扫描 flow MD 文件，补充函数行号

用法：
    python scripts/docs_update/sync_flow.py
"""

import io
import json
import re
import subprocess
import sys
import time
from pathlib import Path

# 设置 stdout 为 UTF-8 编码（解决 Windows 控制台问题）
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# 配置
MIN_INTERVAL = 600  # 10 分钟（秒）
STATE_FILE = Path(__file__).parent / ".last_sync_time"
AST_SCANNER = Path(__file__).parent.parent / "code_search" / "ast_scanner_tree.py"
AST_JSON = Path(__file__).parent.parent / "code_search" / "ast_scan_result.json"
FLOWS_DIR = Path(__file__).parent.parent.parent / "docs" / "flows"
SPECS_DIR = Path(__file__).parent.parent.parent / "docs" / "specs"


def should_run() -> bool:
    """防抖检查：是否应该执行"""
    if not STATE_FILE.exists():
        return True
    try:
        last = float(STATE_FILE.read_text().strip())
        return time.time() - last > MIN_INTERVAL
    except (ValueError, OSError):
        return True


def mark_done():
    """记录执行时间"""
    STATE_FILE.write_text(str(time.time()))


def run_ast_scanner():
    """运行 AST 扫描器"""
    print("运行 AST 扫描器...")
    result = subprocess.run(
        [sys.executable, str(AST_SCANNER)],
        capture_output=True,
        text=True,
        cwd=str(AST_SCANNER.parent.parent.parent),
    )
    if result.returncode != 0:
        print(f"AST 扫描失败: {result.stderr}")
        return False
    print(result.stdout)
    return True


def load_definitions() -> dict:
    """加载 AST 扫描结果"""
    if not AST_JSON.exists():
        print(f"AST 结果文件不存在: {AST_JSON}")
        return {}
    with open(AST_JSON, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("definitions", {})


def module_to_path(module: str) -> str:
    """将 module 名转换为文件路径

    api.services.group_chat_service → agents_hub/api/services/group_chat_service.py
    """
    return "lifeprism/" + module.replace(".", "/") + ".py"


def find_definition(func_name: str, definitions: dict) -> dict | None:
    """查找函数定义，支持模糊匹配

    返回 {"key": str, "module": str, "line": int} 或 None
    """
    # 精确匹配
    if func_name in definitions:
        d = definitions[func_name]
        return {"key": func_name, "module": d["module"], "line": d["line"]}

    # 后缀匹配
    suffix_matches = []
    for key in definitions:
        if key.endswith(f".{func_name}") or key == func_name:
            suffix_matches.append(key)

    if len(suffix_matches) == 1:
        key = suffix_matches[0]
        d = definitions[key]
        return {"key": key, "module": d["module"], "line": d["line"]}
    elif len(suffix_matches) > 1:
        print(f"  警告: 多个匹配 - {func_name}: {suffix_matches}")

    return None


def sync_flow_file(md_path: Path, definitions: dict) -> bool:
    """同步单个 flow MD 文件

    格式：
    <key_function>
    - path/to/file.py
      - Class.method:line
    </key_function>

    返回是否修改了文件
    """
    content = md_path.read_text(encoding="utf-8")

    # 匹配 <key_function> 标签
    pattern = r"(<key_function[^>]*>)(.*?)(</key_function>)"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return False

    tag_open = match.group(1)
    tag_content = match.group(2)
    tag_close = match.group(3)

    # 解析内容
    lines = tag_content.strip().split("\n")
    new_lines = []
    modified = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 文件路径行：`- agents_hub/xxx.py`
        if re.match(r"^- [\w/]+\.py$", stripped):
            new_lines.append(line)
            continue

        # 函数行：`  - Class.method:line` 或 `  - Class.method`
        func_match = re.match(r"^(\s+)- (.+?)(?::(\d+))?$", line)
        if func_match:
            indent = func_match.group(1)
            func_name = func_match.group(2).strip()
            existing_line = func_match.group(3)

            # 查找行号
            result = find_definition(func_name, definitions)
            if result is not None:
                actual_line = result["line"]
                new_entry = f"{indent}- {func_name}:{actual_line}"
                if existing_line != str(actual_line):
                    modified = True
                new_lines.append(new_entry)
            else:
                new_lines.append(line)
                print(f"  警告: 函数未找到 - {func_name}")
            continue

        # 其他行保留
        new_lines.append(line)

    if not new_lines:
        return False

    new_content = "\n".join(new_lines)
    new_block = f"{tag_open}\n{new_content}\n{tag_close}"

    if modified or new_block != match.group(0):
        content = content[: match.start()] + new_block + content[match.end() :]
        md_path.write_text(content, encoding="utf-8")
        return True

    return False


def main():
    print("=" * 50)
    print("Flow 文档函数位置同步")
    print("=" * 50)

    # 1. 防抖检查
    if not should_run():
        print(f"距上次执行不足 {MIN_INTERVAL // 60} 分钟，跳过")
        return

    # 2. 运行 AST 扫描
    if not run_ast_scanner():
        print("AST 扫描失败，终止")
        return

    # 3. 加载定义
    definitions = load_definitions()
    if not definitions:
        print("无函数定义，终止")
        return
    print(f"加载 {len(definitions)} 个函数定义")

    # 4. 扫描 flow 和 spec 文件
    modified_files = []
    total_scanned = 0

    for docs_dir in [FLOWS_DIR, SPECS_DIR]:
        if not docs_dir.exists():
            print(f"目录不存在: {docs_dir}")
            continue

        dir_label = "flows" if docs_dir == FLOWS_DIR else "specs"
        scanned = 0
        for md_file in docs_dir.glob("*.md"):
            scanned += 1
            if sync_flow_file(md_file, definitions):
                modified_files.append(f"{dir_label}/{md_file.name}")
        total_scanned += scanned

    # 5. 记录完成时间
    mark_done()

    # 6. 输出结果
    print("\n同步完成:")
    print(f"  扫描文件数: {total_scanned}")
    print(f"  修改文件数: {len(modified_files)}")
    if modified_files:
        for f in modified_files:
            print(f"    - {f}")


if __name__ == "__main__":
    main()
