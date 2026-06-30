#!/usr/bin/env python3
"""LLM Call Log Viewer — 可视化查看 LLM 调用日志

用法:
    python scripts/llm_call_viewer.py                          # 直接打开 HTML（手动选择文件）
    python scripts/llm_call_viewer.py --date 2026-06-30        # 加载指定日期的日志
    python scripts/llm_call_viewer.py --file path/to/file.json # 加载指定文件
    python scripts/llm_call_viewer.py --latest                 # 加载最新的日志文件
    python scripts/llm_call_viewer.py --serve                  # 启动本地服务器（支持图片显示）

选项:
    --date YYYY-MM-DD      加载指定日期的日志文件
    --file PATH            加载指定路径的 JSON 文件
    --latest               加载 logs 目录中最新的日志文件
    --serve                启动 HTTP 服务器（支持 IMAGE 显示！）
    --port PORT            服务器端口（默认 8899，仅 --serve 模式）
    --open                 打开浏览器（默认行为）
    --no-open              仅保存 HTML，不打开浏览器
    --output PATH          输出 HTML 路径（默认临时文件）
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import webbrowser
from pathlib import Path
from datetime import datetime


# ─── 路径配置 ────────────────────────────────────────────────
# 项目根目录（scripts 位于项目根目录下）
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent  # scripts -> 项目根
LOG_DIR = PROJECT_ROOT / "localData" / "debug_logs" / "llm_logs"
HTML_FILE = SCRIPT_DIR / "llm_call_viewer.html"


def find_log_file(date_str: str) -> Path:
    """按日期查找日志文件"""
    if not LOG_DIR.exists():
        raise FileNotFoundError(f"日志目录不存在: {LOG_DIR}")
    files = sorted(LOG_DIR.glob(f"llm_calls_{date_str}.json"))
    if not files:
        raise FileNotFoundError(f"未找到日期 {date_str} 的日志文件")
    return files[-1]


def find_latest_log() -> Path:
    """查找最新的日志文件"""
    if not LOG_DIR.exists():
        raise FileNotFoundError(f"日志目录不存在: {LOG_DIR}")
    files = sorted(LOG_DIR.glob("llm_calls_*.json"))
    if not files:
        raise FileNotFoundError("日志目录中没有找到日志文件")
    return files[-1]


def read_json(file_path: Path) -> dict:
    """读取 JSON 日志文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def embed_data_into_html(html_path: Path, data: dict, image_dir: Path | None = None) -> str:
    """将 JSON 数据嵌入 HTML，返回嵌入后的 HTML 字符串

    如果提供了 image_dir，会尝试将图片转为 base64 嵌入（谨慎：大图可能使 HTML 膨胀）
    """
    html = html_path.read_text(encoding="utf-8")

    # 构建嵌入脚本
    json_str = json.dumps(data, ensure_ascii=False)

    # 尝试嵌入图片（如果图片目录存在且图片文件名匹配）
    embedded_images = {}
    if image_dir and image_dir.exists():
        calls = data.get("calls", [])
        for record in calls:
            images = record.get("input", {}).get("images", [])
            for img_name in images:
                if img_name in embedded_images:
                    continue
                img_path = image_dir / img_name
                if img_path.exists():
                    import base64
                    ext = img_path.suffix.lower()
                    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext.lstrip("."), "png")
                    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
                    embedded_images[img_name] = f"data:image/{mime};base64,{b64}"

    # 在 </body> 前注入数据脚本
    embed_script = f"<script>window.__embeddedData = {json_str};"
    if embedded_images:
        embed_script += f"\nwindow.__embeddedImages = {json.dumps(embedded_images)};"
    embed_script += "\n</script>"

    html = html.replace("</body>", embed_script + "\n</body>")

    # 记录嵌入信息
    img_count = len(embedded_images)
    if img_count > 0:
        print(f"  [信息] 已嵌入 {img_count} 张图片 (base64)")

    return html


def save_html(html_content: str, output_path: str | None = None) -> Path:
    """保存 HTML 到文件"""
    if output_path:
        out = Path(output_path).resolve()
    else:
        fd, tmp_path = tempfile.mkstemp(suffix=".html", prefix="llm_viewer_")
        os.close(fd)
        out = Path(tmp_path)
    out.write_text(html_content, encoding="utf-8")
    return out


def open_in_browser(path: Path):
    """在默认浏览器中打开 HTML 文件"""
    url = path.resolve().as_uri()
    print(f"  [打开] {url}")
    webbrowser.open(url)


def start_server(port: int):
    """启动一个简单的 HTTP 服务器来服务日志目录和 HTML"""
    import http.server
    import socketserver

    # 切换到项目根目录，这样 HTML 可以通过相对路径访问到日志目录
    os.chdir(PROJECT_ROOT)

    html_relative = HTML_FILE.relative_to(PROJECT_ROOT)
    log_relative = LOG_DIR.relative_to(PROJECT_ROOT)

    print(f"  [服务器] http://localhost:{port}/{html_relative.as_posix()}")
    print(f"  [日志]   可通过 ?file= 参数加载，例如：")
    print(f"           ?file={log_relative.as_posix()}/llm_calls_2026-06-30.json")
    print(f"  [提示]   按 Ctrl+C 停止服务器")
    print()

    # 自定义处理程序，添加 CORS 头
    class CORSHandler(http.server.SimpleHTTPRequestHandler):
        def end_headers(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            super().end_headers()

        def log_message(self, format, *args):
            sys.stderr.write(f"  [HTTP] {args[0]} {args[1]} {args[2]}\n")

    with socketserver.TCPServer(("", port), CORSHandler) as httpd:
        print(f"  Serving at http://localhost:{port}")
        print(f"  Open http://localhost:{port}/{html_relative.as_posix()}")
        httpd.serve_forever()


def main():
    parser = argparse.ArgumentParser(
        description="LLM Call Log Viewer — 可视化查看 LLM 调用日志",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--date", help="加载指定日期的日志 (YYYY-MM-DD)")
    group.add_argument("--file", help="加载指定路径的 JSON 文件")
    group.add_argument("--latest", action="store_true", help="加载最新的日志文件")
    group.add_argument("--serve", action="store_true", help="启动本地 HTTP 服务器")

    parser.add_argument("--port", type=int, default=8899, help="服务器端口 (默认 8899)")
    parser.add_argument("--open", action="store_true", default=True, help="打开浏览器 (默认)")
    parser.add_argument("--no-open", action="store_true", help="不打开浏览器，仅保存 HTML")
    parser.add_argument("--output", help="输出 HTML 路径 (默认临时文件)")

    args = parser.parse_args()

    # 检查 HTML 是否存在
    if not HTML_FILE.exists():
        print(f"[错误] HTML 文件不存在: {HTML_FILE}")
        sys.exit(1)

    # ─── Serve 模式 ──────────────────────────────────────
    if args.serve:
        start_server(args.port)
        return

    # ─── 查找日志文件 ─────────────────────────────────────
    try:
        if args.date:
            log_file = find_log_file(args.date)
            print(f"[加载] 日期: {args.date}")
        elif args.file:
            log_file = Path(args.file).resolve()
            if not log_file.exists():
                raise FileNotFoundError(f"文件不存在: {args.file}")
            print(f"[加载] 文件: {log_file}")
        elif args.latest:
            log_file = find_latest_log()
            print(f"[加载] 最新: {log_file.name}")
        else:
            # 无参数：直接打开 HTML（手动选择文件）
            will_open = not args.no_open
            if will_open:
                open_in_browser(HTML_FILE)
            else:
                print(HTML_FILE)
            return
    except FileNotFoundError as e:
        print(f"[错误] {e}")
        sys.exit(1)

    # ─── 读取并嵌入数据 ─────────────────────────────────
    print(f"[读取] {log_file}")
    data = read_json(log_file)
    calls = data.get("calls", [])
    print(f"[数据] 共 {len(calls)} 条记录")

    # 生成嵌入后的 HTML
    html_content = embed_data_into_html(HTML_FILE, data, image_dir=LOG_DIR / "images")

    # 保存
    output_path = args.output
    out_file = save_html(html_content, output_path)
    size_kb = len(html_content) / 1024
    print(f"[输出] {out_file} ({size_kb:.0f} KB)")

    # 打开浏览器
    will_open = not args.no_open
    if will_open:
        open_in_browser(out_file)
    else:
        print(f"[路径] {out_file}")


if __name__ == "__main__":
    main()
