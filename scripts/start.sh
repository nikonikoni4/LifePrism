#!/bin/bash
#
# LifePrism 统一启动脚本 — 支持三种运行形态
#
# 用法：
#   ./start.sh <mode> <action>
#
#   mode:
#     desktop     Windows 桌面完整版（FastAPI + Agent + Monitor）
#     web-demo    Linux Web Demo（FastAPI + Agent，无 Monitor）
#     agent-only  Linux Agent Only（仅 Agent Loop + WeChat Channel）
#
#   action:
#     start       启动（后台）
#     stop        停止
#     status      查看状态
#     restart     重启
#     foreground  前台启动（调试用，Ctrl+C 退出）
#
# 示例：
#   ./start.sh web-demo start        # 后台启动 Web Demo
#   ./start.sh agent-only start      # 后台启动 Agent Only
#   ./start.sh desktop foreground    # 前台启动桌面版（调试）
#   ./start.sh web-demo status       # 查看 Web Demo 状态
#   ./start.sh agent-only restart    # 重启 Agent Only
#
# 环境变量：
#   LIFEPRISM_DATA_PATH  — 数据目录路径（可选）
#   LIFEPRISM_HOST       — Web 服务监听地址（web-demo/desktop 模式，默认 0.0.0.0）
#   LIFEPRISM_PORT       — Web 服务监听端口（web-demo 默认 8101，desktop 默认 8000）
#

set -euo pipefail

# ==================== 模式配置 ====================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 每种模式的元数据
declare -A MODE_LABEL=(
    ["desktop"]="Windows 桌面完整版"
    ["web-demo"]="Linux Web Demo"
    ["agent-only"]="Linux Agent Only"
)

declare -A MODE_APP_NAME=(
    ["desktop"]="lifeprism-desktop"
    ["web-demo"]="lifeprism-web-demo"
    ["agent-only"]="lifeprism-agent-only"
)

declare -A MODE_DEFAULT_PORT=(
    ["desktop"]="8000"
    ["web-demo"]="8101"
    ["agent-only"]=""
)

declare -A MODE_DEFAULT_HOST=(
    ["desktop"]="127.0.0.1"
    ["web-demo"]="0.0.0.0"
    ["agent-only"]=""
)

# ==================== 参数解析 ====================

MODE="${1:-}"
ACTION="${2:-}"

usage() {
    echo "LifePrism 统一启动脚本"
    echo ""
    echo "用法: $0 <mode> <action>"
    echo ""
    echo "mode:"
    echo "  desktop      ${MODE_LABEL[desktop]}"
    echo "  web-demo     ${MODE_LABEL[web-demo]}"
    echo "  agent-only   ${MODE_LABEL[agent-only]}"
    echo ""
    echo "action:"
    echo "  start        后台启动"
    echo "  stop         停止"
    echo "  status       查看状态"
    echo "  restart      重启"
    echo "  foreground   前台启动（调试用）"
    echo ""
    echo "示例:"
    echo "  $0 web-demo start"
    echo "  $0 agent-only foreground"
    echo "  $0 desktop foreground"
    exit 1
}

if [[ -z "$MODE" ]] || [[ -z "${MODE_LABEL[$MODE]:-}" ]]; then
    echo "错误: 请指定有效的 mode（desktop / web-demo / agent-only）"
    echo ""
    usage
fi

if [[ -z "$ACTION" ]]; then
    echo "错误: 请指定 action（start / stop / status / restart / foreground）"
    echo ""
    usage
fi

case "$ACTION" in
    start|stop|status|restart|foreground) ;;
    *) echo "错误: 无效的 action '$ACTION'"; echo ""; usage ;;
esac

# ==================== 模式参数 ====================

APP_NAME="${MODE_APP_NAME[$MODE]}"
APP_LABEL="${MODE_LABEL[$MODE]}"
PID_FILE="$PROJECT_ROOT/localData/.${APP_NAME}.pid"
LOG_FILE="$PROJECT_ROOT/localData/${APP_NAME}.log"
HOST="${LIFEPRISM_HOST:-${MODE_DEFAULT_HOST[$MODE]}}"
PORT="${LIFEPRISM_PORT:-${MODE_DEFAULT_PORT[$MODE]}}"

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

print_banner() {
    echo "============================================"
    echo "  LifePrism — $APP_LABEL"
    echo "============================================"
}

# ==================== 启动逻辑 ====================

start_desktop() {
    local foreground="${1:-false}"

    if [[ "$foreground" != "true" ]]; then
        ensure_dirs

        local pid
        pid="$(get_pid)"
        if is_running "$pid"; then
            echo "[$APP_NAME] 已在运行 (PID: $pid)"
            exit 0
        fi
        rm -f "$PID_FILE"

        echo "[$APP_NAME] 正在启动..."
        echo "[$APP_NAME]   模式: $APP_LABEL"
        echo "[$APP_NAME]   Host: $HOST"
        echo "[$APP_NAME]   Port: $PORT"
        echo "[$APP_NAME]   Data: ${LIFEPRISM_DATA_PATH:-localData/}"
        echo "[$APP_NAME]   Log:  $LOG_FILE"

        cd "$PROJECT_ROOT"
        nohup python -m uvicorn lifeprism.server.main:app \
            --host "$HOST" \
            --port "$PORT" \
            --log-level info \
            > "$LOG_FILE" 2>&1 &

        local new_pid=$!
        echo "$new_pid" > "$PID_FILE"

        sleep 2
        if is_running "$new_pid"; then
            echo "[$APP_NAME] 启动成功 (PID: $new_pid)"
            echo "[$APP_NAME] API 文档: http://$HOST:$PORT/docs"
        else
            echo "[$APP_NAME] 启动失败，请查看日志: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
    else
        print_banner
        echo "  模式: $APP_LABEL"
        echo "  Host: $HOST"
        echo "  Port: $PORT"
        echo "  按 Ctrl+C 退出"
        echo "============================================"
        cd "$PROJECT_ROOT"
        exec python -m uvicorn lifeprism.server.main:app \
            --host "$HOST" \
            --port "$PORT" \
            --log-level info
    fi
}

start_web_demo() {
    local foreground="${1:-false}"

    if [[ "$foreground" != "true" ]]; then
        ensure_dirs

        local pid
        pid="$(get_pid)"
        if is_running "$pid"; then
            echo "[$APP_NAME] 已在运行 (PID: $pid)"
            exit 0
        fi
        rm -f "$PID_FILE"

        echo "[$APP_NAME] 正在启动..."
        echo "[$APP_NAME]   模式: $APP_LABEL"
        echo "[$APP_NAME]   Host: $HOST"
        echo "[$APP_NAME]   Port: $PORT"
        echo "[$APP_NAME]   Data: ${LIFEPRISM_DATA_PATH:-localData/}"
        echo "[$APP_NAME]   Log:  $LOG_FILE"

        cd "$PROJECT_ROOT"
        nohup python -m uvicorn lifeprism.server.main_web_demo:app \
            --host "$HOST" \
            --port "$PORT" \
            --log-level info \
            > "$LOG_FILE" 2>&1 &

        local new_pid=$!
        echo "$new_pid" > "$PID_FILE"

        sleep 2
        if is_running "$new_pid"; then
            echo "[$APP_NAME] 启动成功 (PID: $new_pid)"
            echo "[$APP_NAME] API 文档: http://$HOST:$PORT/docs"
        else
            echo "[$APP_NAME] 启动失败，请查看日志: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
    else
        print_banner
        echo "  模式: $APP_LABEL"
        echo "  Host: $HOST"
        echo "  Port: $PORT"
        echo "  按 Ctrl+C 退出"
        echo "============================================"
        cd "$PROJECT_ROOT"
        exec python -m uvicorn lifeprism.server.main_web_demo:app \
            --host "$HOST" \
            --port "$PORT" \
            --log-level info
    fi
}

start_agent_only() {
    local foreground="${1:-false}"

    if [[ "$foreground" != "true" ]]; then
        ensure_dirs

        local pid
        pid="$(get_pid)"
        if is_running "$pid"; then
            echo "[$APP_NAME] 已在运行 (PID: $pid)"
            exit 0
        fi
        rm -f "$PID_FILE"

        echo "[$APP_NAME] 正在启动..."
        echo "[$APP_NAME]   模式: $APP_LABEL"
        echo "[$APP_NAME]   Data: ${LIFEPRISM_DATA_PATH:-localData/}"
        echo "[$APP_NAME]   Log:  $LOG_FILE"

        cd "$PROJECT_ROOT"
        nohup python -m lifeprism.server.main_agent_only \
            > "$LOG_FILE" 2>&1 &

        local new_pid=$!
        echo "$new_pid" > "$PID_FILE"

        sleep 2
        if is_running "$new_pid"; then
            echo "[$APP_NAME] 启动成功 (PID: $new_pid)"
        else
            echo "[$APP_NAME] 启动失败，请查看日志: $LOG_FILE"
            rm -f "$PID_FILE"
            exit 1
        fi
    else
        print_banner
        echo "  模式: $APP_LABEL"
        echo "  按 Ctrl+C 退出"
        echo "============================================"
        cd "$PROJECT_ROOT"
        exec python -m lifeprism.server.main_agent_only
    fi
}

# ==================== 命令实现 ====================

cmd_start() {
    case "$MODE" in
        desktop)    start_desktop false ;;
        web-demo)   start_web_demo false ;;
        agent-only) start_agent_only false ;;
    esac
}

cmd_foreground() {
    case "$MODE" in
        desktop)    start_desktop true ;;
        web-demo)   start_web_demo true ;;
        agent-only) start_agent_only true ;;
    esac
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

    local count=0
    while is_running "$pid" && [[ $count -lt 10 ]]; do
        sleep 1
        count=$((count + 1))
    done

    if is_running "$pid"; then
        echo "[$APP_NAME] 强制终止..."
        kill -9 "$pid" 2>/dev/null || true
        sleep 1
    fi

    rm -f "$PID_FILE"
    echo "[$APP_NAME] 已停止"
}

cmd_status() {
    local pid
    pid="$(get_pid)"
    if is_running "$pid"; then
        echo "[$APP_NAME] 运行中"
        echo "  PID:    $pid"
        echo "  模式:   $APP_LABEL"
        if [[ "$MODE" != "agent-only" ]]; then
            echo "  Host:   $HOST"
            echo "  Port:   $PORT"
        fi
        echo "  Log:    $LOG_FILE"
        echo "  Data:   ${LIFEPRISM_DATA_PATH:-localData/}"
        exit 0
    else
        echo "[$APP_NAME] 未运行"
        rm -f "$PID_FILE"
        exit 1
    fi
}

cmd_restart() {
    echo "[$APP_NAME] 正在重启..."
    cmd_stop
    sleep 1
    cmd_start
}

# ==================== 主入口 ====================

case "$ACTION" in
    start)      cmd_start ;;
    stop)       cmd_stop ;;
    status)     cmd_status ;;
    restart)    cmd_restart ;;
    foreground) cmd_foreground ;;
esac
