@echo off
REM 微信会话管理增强功能 - 自动化测试运行脚本 (Windows)

echo ==========================================
echo 微信会话管理增强功能 - 自动化测试
echo ==========================================
echo.

setlocal enabledelayedexpansion
set TOTAL=0
set PASSED=0
set FAILED=0

REM 1. 工具测试
echo ----------------------------------------
echo 运行: 工具测试 (QuerySessionListTool ^& QuerySessionHistoryTool)
echo ----------------------------------------
python -m pytest test/core/unit/llm/test_session_query_tool.py -v --tb=short
if !errorlevel! equ 0 (
    echo ✅ 工具测试 通过
    set /a PASSED+=1
) else (
    echo ❌ 工具测试 失败
    set /a FAILED+=1
)
set /a TOTAL+=1
echo.

REM 2. 命令测试
echo ----------------------------------------
echo 运行: 命令测试 (/continue ^& /new)
echo ----------------------------------------
python -m pytest test/core/integration/llm/agent/test_loop_cmd.py -v --tb=short
if !errorlevel! equ 0 (
    echo ✅ 命令测试 通过
    set /a PASSED+=1
) else (
    echo ❌ 命令测试 失败
    set /a FAILED+=1
)
set /a TOTAL+=1
echo.

REM 3. ChatHistoryManager 测试
echo ----------------------------------------
echo 运行: ChatHistoryManager session_id 功能测试
echo ----------------------------------------
python -m pytest test/core/unit/llm/chat_history/test_chat_history_session_id.py -v --tb=short
if !errorlevel! equ 0 (
    echo ✅ ChatHistoryManager 测试 通过
    set /a PASSED+=1
) else (
    echo ❌ ChatHistoryManager 测试 失败
    set /a FAILED+=1
)
set /a TOTAL+=1
echo.

REM 总结
echo ==========================================
echo 测试总结
echo ==========================================
echo 总计: !TOTAL!
echo 通过: !PASSED! ✅
echo 失败: !FAILED! ❌
echo.

if !FAILED! equ 0 (
    echo 🎉 所有测试通过！
    echo.
    echo 下一步：
    echo 1. 执行端到端测试（参考 end-to-end-test-plan.md）
    echo 2. 验证 AI 行为是否符合预期
    exit /b 0
) else (
    echo ⚠️  有测试失败，请检查并修复
    exit /b 1
)
