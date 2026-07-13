"""
LifePrism Linux Agent Only 启动入口 + 云端 CLI 管理

运行形态：Agent Loop + WeChat Channel + 轻量 FastAPI（仅同步 API，无 Monitor，无 ScheduleService）

适用场景：仅需 AI 助手对话能力 + 云端数据同步，不需要完整 Web 界面。
Agent 通过微信渠道接收/回复消息，直接读写数据库。
FastAPI 仅提供同步 API（端口 8102），供本地客户端拉取/推送数据。

与 Web Demo 模式（端口 8101）的区别：
- 使用独立端口 8102（便于同时启动 web-demo 和 agent-only 进行测试）
- 仅启动轻量 FastAPI（仅同步 API，不含业务 API）
- 不启动 Monitor 模块
- 不启动 ScheduleService
- 资源占用更低

CLI 命令：
    python -m lifeprism.server.main_agent_only [start]         # 启动 Agent Loop + FastAPI 同步服务（默认）
    python -m lifeprism.server.main_agent_only reinit-config   # 重新初始化配置
    python -m lifeprism.server.main_agent_only show-config     # 查看当前配置（脱敏）
    python -m lifeprism.server.main_agent_only test-llm        # 测试 LLM 连接

环境变量：
    LIFEPRISM_DATA_PATH — 数据目录路径（可选，默认 localData/）

参考:
- Issue #10: .scratch/linux-deployment-discussion/issues-p2/10-cloud-cli-management.md
- PRD: .scratch/linux-deployment-discussion/linux-deployment-prd.md (云端 CLI 管理)
"""

import argparse
import asyncio
import contextlib
import signal

import uvicorn
from fastapi import Request
from fastapi.responses import JSONResponse

# 配置初始化（必须在所有 lifeprism 模块之前）
from lifeprism.config.cloud_initializer import CloudInitializer
from lifeprism.config.provider_manager import provider_manager
from lifeprism.config.settings_manager import settings  # noqa: F401
from lifeprism.llm.providers.llm_providers.build_llm_client import create_llm_client
from lifeprism.server.bootstrap import (
    init_database_full,
    start_agent_and_channel,
    stop_agent_and_channel,
)
from lifeprism.server.errors import to_http_exception
from lifeprism.utils import get_logger
from lifeprism.utils.exceptions import LWBaseError

settings.set_runtime_config("run_mode", "agent_only")

logger = get_logger(__name__)


# ==================== 全局异常处理器 ====================


async def _lw_base_error_handler(request: Request, exc: LWBaseError):
    """统一处理所有 LWBaseError 子类异常（与 main.py 保持一致）。

    映射关系（由 _fallback_code + ERROR_CODE_TO_STATUS 决定）：
    - NotFoundError       → 404
    - ConflictError       → 409
    - ValidationError     → 422
    - DataAccessError     → 500
    - ExternalServiceError → 503
    """
    http_exc = to_http_exception(exc)
    if http_exc.status_code < 500:
        logger.warning(
            "%s: %s (code=%s, path=%s)",
            type(exc).__name__,
            exc.message,
            exc.code,
            request.url.path,
        )
    else:
        logger.error(
            "%s: %s (code=%s, path=%s)",
            type(exc).__name__,
            exc.message,
            exc.code,
            request.url.path,
            exc_info=True,
        )
    return JSONResponse(
        status_code=http_exc.status_code,
        content=http_exc.detail,
    )


async def _global_exception_handler(request: Request, exc: Exception):
    """全局兜底异常处理器 → 500（与 main.py 保持一致）。捕获所有非 LWBaseError 的未知异常。"""
    logger.error(
        "未处理的异常: type=%s, error=%s, path=%s",
        type(exc).__name__,
        str(exc),
        request.url.path,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_ERROR",
            "message": "服务器内部错误",
            "details": {},
        },
    )


# test-llm 命令发送的测试消息
_LLM_TEST_MESSAGE = "Hello, please reply 'OK' if you receive this."


# ==================== 工具函数 ====================


def mask_api_key(api_key: str | None) -> str:
    """
    脱敏 API Key，只显示后 8 位。

    格式:
    - 未设置（None / 空串）→ "(未设置)"
    - 长度 <= 8 → "***"（完全隐藏，避免泄露）
    - 长度 > 8 → "***...{后8位}"

    Args:
        api_key: 原始 API Key

    Returns:
        脱敏后的字符串
    """
    if not api_key:
        return "(未设置)"
    if len(api_key) <= 8:
        return "***"
    return f"***...{api_key[-8:]}"


# ==================== 命令实现 ====================


def _prepare_start() -> None:
    """
    start 命令的前置准备：检测 cloud_init.yaml 并初始化，校验 monitor_type。

    流程:
        1. 检测 {data_path}/cloud_init.yaml 是否存在
        2. 存在则执行 CloudInitializer.initialize() 写入配置
        3. 校验 monitor_type 必须为 none（云端不支持 monitor）
    """
    initializer = CloudInitializer(settings.lifeprism_data_path)
    if initializer.should_initialize():
        logger.info("检测到 cloud_init.yaml，开始云端配置初始化...")
        initializer.initialize()
    initializer.validate_monitor_type()


def cmd_start(args: argparse.Namespace) -> None:
    """
    start 命令：启动 Agent Loop。

    先执行云端配置初始化检测（_prepare_start），再启动 Agent Loop 主循环。

    Args:
        args: argparse 解析后的参数（start 命令无额外参数）
    """
    _prepare_start()
    asyncio.run(_run_agent_loop())


def cmd_reinit_config(args: argparse.Namespace) -> None:
    """
    reinit-config 命令：重新初始化配置。

    调用 CloudInitializer.initialize() 从 cloud_init.yaml 读取并覆盖
    config.yaml 和 providers.yaml，完成后提示用户手动重启服务。

    重要：不自动重启服务。云端环境下自动重启可能导致配置未完全落盘，
    且 systemd 管理的服务应通过 systemctl 显式重启。

    Args:
        args: argparse 解析后的参数（reinit-config 命令无额外参数）
    """
    print("正在重新初始化配置...")
    initializer = CloudInitializer(settings.lifeprism_data_path)
    initializer.initialize()
    print("配置初始化完成。")
    print()
    print("请手动重启服务以使配置生效：")
    print("    systemctl restart lifeprism-agent")


def cmd_show_config(args: argparse.Namespace) -> None:
    """
    show-config 命令：脱敏显示当前配置。

    显示字段:
    - Provider、Model、API Base
    - API Key（只显示后 8 位，格式 ***...后8位）
    - Monitor Type、Run Mode
    - Timezone（用户时区，影响 AI 工具时间显示）

    Args:
        args: argparse 解析后的参数（show-config 命令无额外参数）
    """
    provider = settings.provider
    model = settings.model
    api_base = settings.api_base
    monitor_type = settings.monitor_type
    run_mode = settings.run_mode
    timezone = settings.timezone

    # API Key 脱敏：通过 provider_manager 读取（云端 keyring 不可用时 fallback 到 providers.yaml）
    provider_id = provider_manager.get_provider_id(provider) if provider else ""
    api_key = provider_manager.get_api_key(provider_id) if provider_id else None
    masked_key = mask_api_key(api_key)

    print("=" * 50)
    print("LifePrism 当前配置")
    print("=" * 50)
    print(f"Provider:      {provider or '(未设置)'}")
    print(f"Model:         {model or '(未设置)'}")
    print(f"API Base:      {api_base or '(默认)'}")
    print(f"API Key:       {masked_key}")
    print(f"Monitor Type:  {monitor_type}")
    print(f"Run Mode:      {run_mode}")
    print(f"Timezone:      {timezone}")
    print("=" * 50)


def cmd_test_llm(args: argparse.Namespace) -> None:
    """
    test-llm 命令：测试 LLM 连接。

    发送测试消息 "Hello, please reply 'OK' if you receive this."，
    根据响应判断连接状态（成功/失败）并显示回复内容或错误信息。

    异常处理：LLM 调用异常不向上抛出，统一显示为连接失败。

    Args:
        args: argparse 解析后的参数（test-llm 命令无额外参数）
    """
    print("正在测试 LLM 连接...")
    try:
        client = create_llm_client()
        messages = [{"role": "user", "content": [{"type": "text", "text": _LLM_TEST_MESSAGE}]}]
        response = asyncio.run(client.chat(messages=messages))
    except Exception as e:
        print(f"连接失败: {e}")
        return

    if response.finish_reason == "error" or not response.content:
        print("连接失败")
        if response.content:
            print(f"错误信息: {response.content}")
    else:
        print("连接成功")
        print(f"LLM 回复: {response.content}")


# ==================== Agent Loop + FastAPI 主循环 ====================


async def _run_agent_and_api() -> None:
    """Agent Only 主循环 + FastAPI 同步服务。

    启动流程：
        1. 创建 FastAPI 实例（仅注册 sync_cloud_router）
        2. 启动 uvicorn 服务（后台任务，端口 8101）
        3. 数据库初始化（建表 + 迁移 + 默认数据 + 资源文件）
        4. 启动 Agent Loop + WeChat Channel
        5. 等待终止信号或 Agent Loop 异常退出
        6. 优雅关闭 FastAPI 和 Agent Loop
    """
    from fastapi import FastAPI

    from lifeprism.server.api import sync_cloud_router

    logger.info("=== LifePrism Agent Only 模式启动 ===")

    # 1. 创建 FastAPI 实例（仅同步 API）
    app = FastAPI(
        title="LifePrism Agent Only - Sync API",
        description="云端同步 API 服务（仅数据同步，不包含业务 API）",
        version="1.0.0",
        openapi_url=None,
        docs_url=None,
        redoc_url=None,
    )
    app.include_router(sync_cloud_router)

    # 注册全局异常处理器（与 main.py 保持一致）
    # 确保 verify_sync_api_key 抛出的 ValidationError 等返回 422 而非默认 500
    app.add_exception_handler(LWBaseError, _lw_base_error_handler)
    app.add_exception_handler(Exception, _global_exception_handler)
    logger.info("[AGENT-ONLY] 全局异常处理器已注册（LWBaseError + Exception）")

    logger.info("[AGENT-ONLY] FastAPI 实例创建完成（仅同步 API）")

    # 2. 启动 FastAPI（后台任务）
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8102,
        log_level="info",
    )
    server = uvicorn.Server(config)
    api_task = asyncio.create_task(server.serve())
    logger.info("[AGENT-ONLY] FastAPI 启动: host=0.0.0.0, port=8102")

    # 3. 数据库初始化
    logger.info("正在初始化数据库...")
    init_database_full()

    # 4. 启动 Agent + Channel
    logger.info("正在启动 Agent Loop 和 WeChat Channel...")
    loop_task, wechat_channel = await start_agent_and_channel()
    logger.info("[AGENT-ONLY] Agent Loop + WeChat Channel 启动完成")

    # 5. 注册信号处理（优雅关闭）
    stop_event = asyncio.Event()

    def _signal_handler(sig_name: str) -> None:
        logger.info("收到信号 %s，准备关闭...", sig_name)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda s=sig: _signal_handler(s.name))
        except NotImplementedError:
            # Windows 不支持 add_signal_handler，回退到 signal.signal
            signal.signal(sig, lambda *_, _sig=sig: _signal_handler(_sig.name))

    # 6. 等待终止信号或 Agent Loop 异常退出
    stop_wait_task = asyncio.create_task(stop_event.wait())
    done, pending = await asyncio.wait(
        {loop_task, stop_wait_task},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if loop_task in done:
        # Agent Loop 先结束（异常或正常退出）
        exc = loop_task.exception()
        if exc:
            logger.error("Agent Loop 异常退出: error=%s", exc, exc_info=exc)
        else:
            logger.info("Agent Loop 正常退出")

    # 7. 停止 FastAPI 服务
    logger.info("[AGENT-ONLY] 正在停止 FastAPI 服务...")
    server.should_exit = True
    try:
        await api_task
    except asyncio.CancelledError:
        logger.info("[AGENT-ONLY] FastAPI 任务已取消")

    # 取消未完成的 stop_wait_task
    if not stop_wait_task.done():
        stop_wait_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await stop_wait_task

    # 8. 优雅关闭 Agent 和 Channel
    logger.info("正在关闭 Agent 和 Channel...")
    await stop_agent_and_channel(loop_task, wechat_channel)
    logger.info("=== LifePrism Agent Only 已关闭 ===")


async def _run_agent_loop() -> None:
    """Agent Only 主循环（委托给 _run_agent_and_api）。

    保留此函数以兼容 test_cloud_cli.py 的 noop_agent_loop fixture。
    """
    await _run_agent_and_api()


# ==================== CLI 入口 ====================


def _build_parser() -> argparse.ArgumentParser:
    """
    构建 argparse 解析器。

    支持 4 个子命令：
    - start（默认）
    - reinit-config
    - show-config
    - test-llm
    """
    parser = argparse.ArgumentParser(
        prog="main_agent_only",
        description="LifePrism Agent Only 模式启动入口 + 云端 CLI 管理",
    )
    subparsers = parser.add_subparsers(dest="command")

    # start（默认）
    p_start = subparsers.add_parser("start", help="启动 Agent Loop（默认命令）")
    p_start.set_defaults(func=cmd_start)

    # reinit-config
    p_reinit = subparsers.add_parser(
        "reinit-config", help="重新初始化配置（从 cloud_init.yaml 读取并覆盖）"
    )
    p_reinit.set_defaults(func=cmd_reinit_config)

    # show-config
    p_show = subparsers.add_parser(
        "show-config", help="查看当前配置（脱敏显示，API Key 只显示后 8 位）"
    )
    p_show.set_defaults(func=cmd_show_config)

    # test-llm
    p_test = subparsers.add_parser("test-llm", help="测试 LLM 连接（发送测试消息并显示连接状态）")
    p_test.set_defaults(func=cmd_test_llm)

    return parser


def main(argv: list[str] | None = None) -> None:
    """
    CLI 入口函数。

    解析命令行参数并分发到对应子命令。无子命令时默认执行 start。

    支持通过模块方式调用：
        python -m lifeprism.server.main_agent_only <command>

    Args:
        argv: 命令行参数列表。None 时读取 sys.argv[1:]。
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    command = args.command or "start"

    if command == "start":
        cmd_start(args)
    elif command == "reinit-config":
        cmd_reinit_config(args)
    elif command == "show-config":
        cmd_show_config(args)
    elif command == "test-llm":
        cmd_test_llm(args)
    else:
        # argparse 已对未知子命令报错退出，此处为防御性兜底
        parser.print_help()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
