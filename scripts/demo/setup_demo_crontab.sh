#!/bin/bash
# ============================================================
# Web-Demo 每日数据刷新 crontab 安装脚本
#
# 用法：
#   bash scripts/demo/setup_demo_crontab.sh
#
# 功能：
#   1. 检测当前 Python 路径
#   2. 配置 crontab 每天 12:00 执行 refresh_daily_data.py
#   3. 提供验证命令
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
REFRESH_SCRIPT="$SCRIPT_DIR/refresh_daily_data.py"
CRON_MARKER="# LifeWatch-AI demo daily refresh"

echo "=== LifeWatch-AI Web-Demo 定时刷新配置 ==="
echo ""
echo "项目目录: $PROJECT_DIR"
echo "刷新脚本: $REFRESH_SCRIPT"

# 查找 Python
if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
elif command -v python &>/dev/null; then
    PYTHON=$(command -v python)
else
    echo "[ERROR] 未找到 Python，请确认 Python 已安装"
    exit 1
fi
echo "Python:    $PYTHON"

# 验证脚本存在
if [ ! -f "$REFRESH_SCRIPT" ]; then
    echo "[ERROR] 刷新脚本不存在: $REFRESH_SCRIPT"
    exit 1
fi

# 构建 cron 命令
CRON_CMD="0 12 * * * cd $PROJECT_DIR && $PYTHON $REFRESH_SCRIPT >> $PROJECT_DIR/localData/debug_logs/demo_refresh.log 2>&1 $CRON_MARKER"

echo ""
echo "即将添加的 crontab 条目："
echo "  $CRON_CMD"
echo ""

read -rp "确认添加？[y/N] " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
    echo "已取消"
    exit 0
fi

# 确保日志目录存在
mkdir -p "$PROJECT_DIR/localData/debug_logs"

# 移除旧的同名条目（如果存在）
(crontab -l 2>/dev/null | grep -v "$CRON_MARKER"; echo "$CRON_CMD") | crontab -

echo ""
echo "[OK] crontab 已配置"
echo ""
echo "验证："
echo "  crontab -l"
echo ""
echo "手动触发一次刷新："
echo "  cd $PROJECT_DIR && $PYTHON $REFRESH_SCRIPT"
echo ""
echo "查看日志："
echo "  tail -f $PROJECT_DIR/localData/debug_logs/demo_refresh.log"
