"""
LifePrism Linux Agent Only 启动入口 + 云端 CLI 管理

运行形态：Agent Loop + WeChat Channel（无 FastAPI，无 Monitor，无 ScheduleService）

适用场景：仅需 AI 助手对话能力，不需要 Web 界面。
Agent 通过微信渠道接收/回复消息，直接读写数据库。

与 Web Demo 模式的区别：
- 不启动 FastAPI 服务（无 HTTP API）
- 不启动 Monitor 模块
- 不启动 ScheduleService
- 资源占用更低

CLI 命令：
    python -m lifeprism.server.main_agent_only [start]         # 启动 Agent Loop（默认）
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
import signal

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
from lifeprism.utils import get_logger

logger = get_logger(__name__)


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

    Args:
        args: argparse 解析后的参数（show-config 命令无额外参数）
    """
    provider = settings.provider
    model = settings.model
    api_base = settings.api_base
    monitor_type = settings.monitor_type
    run_mode = settings.run_mode

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


# ==================== Agent Loop 主循环（原有逻辑）====================


async def _run_agent_loop() -> None:
    """
    Agent Only 主循环。

    启动流程：
        1. 数据库初始化（建表 + 迁移 + 默认数据 + 资源文件）
        2. 启动 WeChat Channel（接收/发送消息）
        3. 启动 Agent Loop（处理消息、调用工具）
        4. 等待 Agent Loop 运行（直到收到终止信号）
        5. 优雅关闭
    """
    logger.info("=== LifePrism Agent Only 模式启动 ===")

    # 1. 数据库初始化
    logger.info("正在初始化数据库...")
    init_database_full()

    # 2. 启动 Agent + Channel
    logger.info("正在启动 Agent Loop 和 WeChat Channel...")
    loop_task, wechat_channel = await start_agent_and_channel()

    # 3. 注册信号处理（优雅关闭）
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

    # 4. 等待终止信号或 Agent Loop 异常退出
    done, pending = await asyncio.wait(
        {loop_task, asyncio.create_task(stop_event.wait())},
        return_when=asyncio.FIRST_COMPLETED,
    )

    if loop_task in done:
        # Agent Loop 先结束（异常或正常退出）
        exc = loop_task.exception()
        if exc:
            logger.error("Agent Loop 异常退出: error=%s", exc, exc_info=exc)
        else:
            logger.info("Agent Loop 正常退出")

    # 5. 优雅关闭
    logger.info("正在关闭 Agent 和 Channel...")
    await stop_agent_and_channel(loop_task, wechat_channel)
    logger.info("=== LifePrism Agent Only 已关闭 ===")


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
