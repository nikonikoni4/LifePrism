#!/bin/bash
#
# LifePrism Agent Only 启动脚本
#
# 用法：
#   ./start_agent_only.sh start    — 启动 Agent Only（后台）
#   ./start_agent_only.sh stop     — 停止
#   ./start_agent_only.sh status   — 查看状态
#   ./start_agent_only.sh restart  — 重启
#
# 环境变量：
#   LIFEPRISM_DATA_PATH  — 数据目录路径（可选，默认 localData/）
#

set -euo pipefail

# ==================== 配置 ====================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
APP_NAME="lifeprism-agent-only"
PID_FILE="$PROJECT_ROOT/localData/.${APP_NAME}.pid"
LOG_FILE="$PROJECT_ROOT/localData/${APP_NAME}.log"

# ==================== 工具函数 ====================

ensure_dirs() {
    mkdir -p "$PROJECT_ROOT/localData"
}

get_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE" 2>/dev/null || echo ""
    else
        echo ""
    fi
}

is_running() {
    local pid="$1"
    if [[ -z "$pid" ]]; then
        return 1
    fi
    if kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# ==================== 命令 ====================

cmd_start() {
    ensure_dirs

    local pid
    pid="$(get_pid)"
    if is_running "$pid"; then
        echo "[$APP_NAME] 已在运行 (PID: $pid)"
        exit 0
    fi

    # 清理过期 PID 文件
    rm -f "$PID_FILE"

    echo "[$APP_NAME] 正在启动..."
    echo "[$APP_NAME]   Data: ${LIFEPRISM_DATA_PATH:-localData/}"
    echo "[$APP_NAME]   Log:  $LOG_FILE"

    cd "$PROJECT_ROOT"

    # 设置部署模式为 Agent Only
    export LIFEPRISM_RUN_MODE=agent_only

    # 使用 nohup 后台启动
    nohup python -m lifeprism.server.main_agent_only \
        > "$LOG_FILE" 2>&1 &

    local new_pid=$!
    echo "$new_pid" > "$PID_FILE"

    # 等待启动
    sleep 2
    if is_running "$new_pid"; then
        echo "[$APP_NAME] 启动成功 (PID: $new_pid)"
    else
        echo "[$APP_NAME] 启动失败，请查看日志: $LOG_FILE"
        rm -f "$PID_FILE"
        exit 1
    fi
}

cmd_stop() {
    local pid
    pid="$(get_pid)"
    if ! is_running "$pid"; then
        echo "[$APP_NAME] 未运行"
        rm -f "$PID_FILE"
        exit 0
    fi

    echo "[$APP_NAME] 正在停止 (PID: $pid)..."
    kill "$pid" 2>/dev/null || true

    # 等待进程退出（最多 10 秒）
    local count=0
    while is_running "$pid" && [[ $count -lt 10 ]]; do
        sleep 1
        count=$((count + 1))
    done

    # 如果还没退出，强制终止
    if is_running "$pid"; then
        echo "[$APP_NAME] 强制终止..."
        kill -9 "$pid" 2>/dev/null || true
    fi

    rm -f "$PID_FILE"
    echo "[$APP_NAME] 已停止"
}

cmd_status() {
    local pid
    pid="$(get_pid)"
    if is_running "$pid"; then
        echo "[$APP_NAME] 运行中 (PID: $pid)"
        echo "[$APP_NAME]   Log:  $LOG_FILE"
        exit 0
    else
        echo "[$APP_NAME] 未运行"
        rm -f "$PID_FILE"
        exit 1
    fi
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

# ==================== 主入口 ====================

case "${1:-}" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    status)  cmd_status ;;
    restart) cmd_restart ;;
    *)
        echo "用法: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
