#!/usr/bin/env python3
"""Pre-commit hook：检查 flow 文档是否需要更新

安装方法：
    # 创建软链接（推荐，方便更新）
    ln -s ../../scripts/docs_update/pre-commit-check-flow.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

    # 或者复制文件
    cp scripts/docs_update/pre-commit-check-flow.py .git/hooks/pre-commit
    chmod +x .git/hooks/pre-commit

功能：
    在 git commit 前检查暂存区的函数变化是否影响 flow 文档
    如果有影响，给出警告提示，但不阻塞提交
    检查结果会记录到日志文件：scripts/docs_update/flow-check.log
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_repo_root() -> Path | None:
    """获取主仓库根目录（支持 git worktree）

    在 worktree 中，通过 --git-common-dir 找到主仓库的 .git 目录
    """
    # 获取 git 公共目录（worktree 中指向主仓库 .git）
    result = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None

    # 转换为绝对路径（可能返回 ".git" 相对路径）
    git_common_dir = Path(result.stdout.strip()).resolve()

    # 主仓库：.git 是目录，父目录就是仓库根
    # Worktree：--git-common-dir 返回主仓库的 .git 绝对路径
    if git_common_dir.name == ".git":
        return git_common_dir.parent

    # 如果返回的不是 .git 目录（异常情况），回退到 --show-toplevel
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())

    return None


def write_log(repo_root: Path, output: str, returncode: int):
    """记录检查结果到日志文件"""
    log_file = repo_root / "scripts" / "docs_update" / "flow-check.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    status = "✅ 无需更新" if "没有文档需要更新" in output else "⚠️  需要更新"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 60}\n")
        f.write(f"[{timestamp}] Pre-commit 检查 - {status}\n")
        f.write(f"{'=' * 60}\n")
        f.write(output)
        f.write(f"\n{'=' * 60}\n")


def main():
    # 1. 获取仓库根目录（支持 worktree）
    repo_root = get_repo_root()
    if not repo_root:
        print("错误：无法获取仓库根目录")
        sys.exit(0)  # 不阻塞提交

    # 2. 构造检查脚本路径
    check_script = repo_root / "scripts" / "docs_update" / "check_flow_outdated.py"
    if not check_script.exists():
        print(f"错误：找不到检查脚本 {check_script}")
        sys.exit(0)  # 不阻塞提交

    # 3. 运行检查（捕获输出）
    print("\n🔍 检查文档（flows + specs）是否需要更新...\n")
    result = subprocess.run(
        [sys.executable, str(check_script), "--staged"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(repo_root),
    )

    # 4. 打印输出
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    # 5. 记录日志
    try:
        output = result.stdout if result.stdout else result.stderr
        write_log(repo_root, output, result.returncode)
    except Exception as e:
        print(f"⚠️  日志记录失败: {e}")

    # 6. 始终允许提交
    print("\n💡 提示：检查结果已记录到 scripts/docs_update/flow-check.log")
    if result.returncode != 0 or "需要更新" in result.stdout:
        print("💡 如果有文档需要更新，请在提交后尽快更新\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
