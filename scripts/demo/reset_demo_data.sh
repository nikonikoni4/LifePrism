#!/bin/bash
# ==============================================================================
# Web-Demo 数据重置脚本
# ==============================================================================
#
# 功能：
#   1. 停止 LifePrism 后端服务
#   2. 删除 localData 目录（清除所有旧数据）
#   3. 重新生成演示数据（过去 7 天）
#   4. 重启 LifePrism 后端服务
#
# 用法：
#   bash scripts/demo/reset_demo_data.sh
#
# 配置（Crontab）：
#   每天凌晨 4 点自动重置：
#   0 4 * * * cd /path/to/LifeWatch-AI && bash scripts/demo/reset_demo_data.sh >> /var/log/lifeprism-demo-reset.log 2>&1
#
# ==============================================================================

set -e  # 遇到错误立即退出

# ==================== 配置 ====================

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DATA_DIR="$PROJECT_ROOT/localData"
BACKEND_PID_FILE="/tmp/lifeprism-backend.pid"
BACKEND_START_CMD="cd $PROJECT_ROOT && source venv/bin/activate && python -m lifeprism.server.main"
DEMO_SCRIPT="$PROJECT_ROOT/scripts/demo/generate_demo_data.py"

# ==================== 日志函数 ====================

log_info() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] $*"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] $*" >&2
}

# ==================== 步骤 1: 停止后端服务 ====================

log_info "正在停止 LifePrism 后端服务..."

if [ -f "$BACKEND_PID_FILE" ]; then
    BACKEND_PID=$(cat "$BACKEND_PID_FILE")
    if kill -0 "$BACKEND_PID" 2>/dev/null; then
        log_info "找到后端进程 (PID: $BACKEND_PID)，正在终止..."
        kill "$BACKEND_PID" || true
        sleep 3
        # 如果进程还在，强制杀死
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            log_info "进程未退出，强制杀死..."
            kill -9 "$BACKEND_PID" || true
        fi
        rm -f "$BACKEND_PID_FILE"
        log_info "后端服务已停止"
    else
        log_info "PID 文件存在但进程不存在，清理 PID 文件"
        rm -f "$BACKEND_PID_FILE"
    fi
else
    log_info "未找到 PID 文件，尝试通过进程名查找..."
    # 查找 Python 进程运行 lifeprism.server.main
    PIDS=$(pgrep -f "lifeprism.server.main" || true)
    if [ -n "$PIDS" ]; then
        log_info "找到进程: $PIDS，正在终止..."
        echo "$PIDS" | xargs kill || true
        sleep 3
    else
        log_info "未找到运行中的后端服务"
    fi
fi

# ==================== 步骤 2: 删除旧数据 ====================

log_info "正在删除旧数据目录: $DATA_DIR"

if [ -d "$DATA_DIR" ]; then
    rm -rf "$DATA_DIR"
    log_info "旧数据已删除"
else
    log_info "数据目录不存在，跳过删除"
fi

# ==================== 步骤 3: 生成演示数据 ====================

log_info "正在生成新的演示数据（过去 7 天）..."

cd "$PROJECT_ROOT"
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    log_error "未找到虚拟环境 venv，请先创建虚拟环境"
    exit 1
fi

python "$DEMO_SCRIPT" --data-path "$DATA_DIR" --days 7 --force

if [ $? -eq 0 ]; then
    log_info "演示数据生成成功"
else
    log_error "演示数据生成失败"
    exit 1
fi

# ==================== 步骤 4: 重启后端服务 ====================

log_info "正在启动 LifePrism 后端服务..."

# 使用 nohup 在后台启动，并将 PID 写入文件
nohup bash -c "$BACKEND_START_CMD" > /var/log/lifeprism-backend.log 2>&1 &
BACKEND_PID=$!
echo "$BACKEND_PID" > "$BACKEND_PID_FILE"

log_info "后端服务已启动 (PID: $BACKEND_PID)"

# 等待 5 秒检查服务是否正常启动
sleep 5
if kill -0 "$BACKEND_PID" 2>/dev/null; then
    log_info "后端服务运行正常"
else
    log_error "后端服务启动失败，请检查日志: /var/log/lifeprism-backend.log"
    exit 1
fi

# ==================== 完成 ====================

log_info "===================================================="
log_info "Demo 数据重置完成！"
log_info "===================================================="
log_info "数据目录: $DATA_DIR"
log_info "后端 PID: $BACKEND_PID"
log_info "后端日志: /var/log/lifeprism-backend.log"
log_info "===================================================="
