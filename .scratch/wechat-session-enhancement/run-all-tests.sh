#!/bin/bash
# 微信会话管理增强功能 - 自动化测试运行脚本

echo "=========================================="
echo "微信会话管理增强功能 - 自动化测试"
echo "=========================================="
echo ""

# 计数器
TOTAL=0
PASSED=0
FAILED=0

# 函数：运行测试并统计结果
run_test() {
    local test_name=$1
    local test_path=$2

    echo "----------------------------------------"
    echo "运行: $test_name"
    echo "----------------------------------------"

    python -m pytest "$test_path" -v --tb=short

    if [ $? -eq 0 ]; then
        echo "✅ $test_name 通过"
        PASSED=$((PASSED + 1))
    else
        echo "❌ $test_name 失败"
        FAILED=$((FAILED + 1))
    fi

    TOTAL=$((TOTAL + 1))
    echo ""
}

# 1. 工具测试
run_test "工具测试 (QuerySessionListTool & QuerySessionHistoryTool)" \
    "test/core/unit/llm/test_session_query_tool.py"

# 2. 命令测试
run_test "命令测试 (/continue & /new)" \
    "test/core/integration/llm/agent/test_loop_cmd.py"

# 3. ChatHistoryManager 测试
run_test "ChatHistoryManager session_id 功能测试" \
    "test/core/unit/llm/chat_history/test_chat_history_session_id.py"

# 总结
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo "总计: $TOTAL"
echo "通过: $PASSED ✅"
echo "失败: $FAILED ❌"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 所有测试通过！"
    echo ""
    echo "下一步："
    echo "1. 执行端到端测试（参考 end-to-end-test-plan.md）"
    echo "2. 验证 AI 行为是否符合预期"
    exit 0
else
    echo "⚠️  有测试失败，请检查并修复"
    exit 1
fi
