"""
云端 CLI 管理单元测试

验证 main_agent_only.py 的命令行参数支持，覆盖 4 个子命令：
1. start        — 检测 cloud_init.yaml 并初始化，再启动 Agent Loop
2. reinit-config — 调用 CloudInitializer.initialize()，提示手动重启（不自动重启）
3. show-config  — 脱敏显示当前配置（API Key 只显示后 8 位）
4. test-llm     — 发送测试消息并显示连接状态

参考:
- Issue #10: .scratch/linux-deployment-discussion/issues-p2/10-cloud-cli-management.md
- PRD: .scratch/linux-deployment-discussion/linux-deployment-prd.md (云端 CLI 管理)
"""

import argparse
import subprocess
from unittest.mock import AsyncMock, MagicMock

import pytest

from lifeprism.server import main_agent_only

pytestmark = pytest.mark.core


# ==================== Fixtures ====================


@pytest.fixture
def mock_cloud_initializer(monkeypatch):
    """Mock CloudInitializer 类，返回受控实例。

    用法:
        mock = mock_cloud_initializer()
        mock["instance"].should_initialize.return_value = True
        ... # 调用被测函数
        mock["instance"].initialize.assert_called_once()
    """
    mock_instance = MagicMock()
    mock_class = MagicMock(return_value=mock_instance)
    monkeypatch.setattr(main_agent_only, "CloudInitializer", mock_class)
    return {"class": mock_class, "instance": mock_instance}


@pytest.fixture
def noop_agent_loop(monkeypatch):
    """将 _run_agent_loop 替换为空操作 async 函数，避免真实启动"""

    async def _noop():
        return None

    monkeypatch.setattr(main_agent_only, "_run_agent_loop", _noop)
    return _noop


@pytest.fixture
def mock_settings_config(monkeypatch):
    """Mock settings.get，使 settings.provider/model/api_base/monitor_type/timezone 返回受控值。

    settings 的 provider 等属性内部调用 self.get(key)，因此 patch get 即可控制。
    """
    config_map = {
        "provider": "anthropic",
        "model": "claude-opus-4",
        "api_base": "https://api.anthropic.com",
        "monitor_type": "none",
        "run_mode": "agent_only",
        "timezone": "Asia/Shanghai",
    }
    monkeypatch.setattr(
        main_agent_only.settings,
        "get",
        lambda key, default=None: config_map.get(key, default),
    )
    return config_map


# ==================== Slice 1: start 命令 ====================


class TestStartCommand:
    """测试 start 命令：检测 cloud_init.yaml 并初始化，再启动 Agent Loop"""

    def test_start_calls_should_initialize(self, mock_cloud_initializer, noop_agent_loop):
        """start 命令调用 CloudInitializer.should_initialize()"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False

        main_agent_only.main(["start"])

        mock_init.should_initialize.assert_called_once()

    def test_start_calls_initialize_when_cloud_init_present(
        self, mock_cloud_initializer, noop_agent_loop
    ):
        """cloud_init.yaml 存在时，start 命令调用 initialize()"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = True

        main_agent_only.main(["start"])

        mock_init.initialize.assert_called_once()

    def test_start_skips_initialize_when_cloud_init_absent(
        self, mock_cloud_initializer, noop_agent_loop
    ):
        """cloud_init.yaml 不存在时，start 命令不调用 initialize()"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False

        main_agent_only.main(["start"])

        mock_init.initialize.assert_not_called()

    def test_start_calls_validate_monitor_type(self, mock_cloud_initializer, noop_agent_loop):
        """start 命令调用 validate_monitor_type()（无论 cloud_init 是否存在）"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False

        main_agent_only.main(["start"])

        mock_init.validate_monitor_type.assert_called_once()

    def test_start_runs_agent_loop(self, mock_cloud_initializer, monkeypatch):
        """start 命令最终启动 Agent Loop（调用 _run_agent_loop）"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False

        called = {"flag": False}

        async def _spy():
            called["flag"] = True

        monkeypatch.setattr(main_agent_only, "_run_agent_loop", _spy)

        main_agent_only.main(["start"])

        assert called["flag"] is True

    def test_start_default_command_when_no_args(self, mock_cloud_initializer, noop_agent_loop):
        """无子命令时默认执行 start"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False

        main_agent_only.main([])

        mock_init.should_initialize.assert_called_once()
        mock_init.validate_monitor_type.assert_called_once()


# ==================== Slice 2: reinit-config 命令 ====================


class TestReinitConfigCommand:
    """测试 reinit-config 命令：重新初始化配置，提示手动重启，不自动重启"""

    def test_reinit_config_calls_initialize(self, mock_cloud_initializer, capsys):
        """reinit-config 命令调用 CloudInitializer.initialize()"""
        mock_init = mock_cloud_initializer["instance"]

        main_agent_only.main(["reinit-config"])

        mock_init.initialize.assert_called_once()

    def test_reinit_config_prints_restart_hint(self, mock_cloud_initializer, capsys):
        """reinit-config 命令输出包含手动重启提示（systemctl restart）"""
        main_agent_only.main(["reinit-config"])

        out = capsys.readouterr().out
        assert "systemctl restart" in out
        assert "lifeprism-agent" in out

    def test_reinit_config_calls_initialize_directly(self, mock_cloud_initializer, capsys):
        """reinit-config 直接调用 initialize()（initialize 内部自检 should_initialize）"""
        mock_init = mock_cloud_initializer["instance"]

        main_agent_only.main(["reinit-config"])

        mock_init.initialize.assert_called_once()

    def test_reinit_config_does_not_auto_restart(self, mock_cloud_initializer, monkeypatch, capsys):
        """reinit-config 不自动重启服务（不调用 subprocess/systemctl restart）"""
        mock_run = MagicMock()
        mock_call = MagicMock()
        mock_popen = MagicMock()
        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(subprocess, "call", mock_call)
        monkeypatch.setattr(subprocess, "Popen", mock_popen)

        main_agent_only.main(["reinit-config"])

        mock_run.assert_not_called()
        mock_call.assert_not_called()
        mock_popen.assert_not_called()

    def test_reinit_config_prints_success_message(self, mock_cloud_initializer, capsys):
        """reinit-config 成功后输出完成提示"""
        main_agent_only.main(["reinit-config"])

        out = capsys.readouterr().out
        assert "完成" in out or "成功" in out

    def test_reinit_config_does_not_run_agent_loop(self, mock_cloud_initializer, monkeypatch):
        """reinit-config 不启动 Agent Loop"""
        called = {"flag": False}

        async def _spy():
            called["flag"] = True

        monkeypatch.setattr(main_agent_only, "_run_agent_loop", _spy)

        main_agent_only.main(["reinit-config"])

        assert called["flag"] is False


# ==================== Slice 3: show-config 命令 ====================


class TestShowConfigCommand:
    """测试 show-config 命令：脱敏显示当前配置"""

    def test_show_config_displays_provider(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 显示 provider"""
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "anthropic" in out

    def test_show_config_displays_model(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 显示 model"""
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "claude-opus-4" in out

    def test_show_config_displays_api_base(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 显示 API Base"""
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "https://api.anthropic.com" in out

    def test_show_config_masks_api_key(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 的 API Key 只显示后 8 位（***...后8位）"""
        fake_key = "sk-ant-api03-abcdefghijklmnop1234567890"
        monkeypatch.setattr(
            main_agent_only.provider_manager, "get_api_key", lambda *a, **k: fake_key
        )

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        # 后 8 位应出现
        assert fake_key[-8:] in out
        # 完整 key 不应出现
        assert fake_key not in out
        # 脱敏标记应出现
        assert "***" in out

    def test_show_config_masks_short_api_key(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """API Key 长度 <= 8 时完全隐藏为 ***"""
        short_key = "abc123"
        monkeypatch.setattr(
            main_agent_only.provider_manager, "get_api_key", lambda *a, **k: short_key
        )

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert short_key not in out
        assert "***" in out

    def test_show_config_no_api_key(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """API Key 未设置时显示未设置提示"""
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "未设置" in out

    def test_show_config_displays_monitor_type(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 显示 monitor_type"""
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "none" in out

    def test_show_config_displays_timezone(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 显示 timezone"""
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "Asia/Shanghai" in out

    def test_show_config_displays_timezone_custom_value(
        self, mock_cloud_initializer, mock_settings_config, monkeypatch, capsys
    ):
        """show-config 显示自定义 timezone 值（如 America/New_York）"""
        # 修改 timezone 返回值
        original_get = main_agent_only.settings.get

        def mock_get(key, default=None):
            if key == "timezone":
                return "America/New_York"
            return original_get(key, default)

        monkeypatch.setattr(main_agent_only.settings, "get", mock_get)
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        main_agent_only.main(["show-config"])

        out = capsys.readouterr().out
        assert "America/New_York" in out


# ==================== Slice 4: test-llm 命令 ====================


class TestTestLlmCommand:
    """测试 test-llm 命令：发送测试消息并显示连接状态"""

    @pytest.fixture
    def mock_llm_client(self, monkeypatch):
        """Mock create_llm_client，返回受控 client"""
        client = MagicMock()
        client.chat = AsyncMock()
        monkeypatch.setattr(main_agent_only, "create_llm_client", lambda: client)
        return client

    def test_test_llm_sends_test_message(self, mock_cloud_initializer, mock_llm_client):
        """test-llm 命令发送测试消息"""
        from lifeprism.llm.providers.llm_providers.base import LLMResponse

        mock_llm_client.chat.return_value = LLMResponse(content="OK", finish_reason="stop")

        main_agent_only.main(["test-llm"])

        mock_llm_client.chat.assert_awaited_once()
        # 验证发送的消息包含测试文本
        call_args = mock_llm_client.chat.call_args
        messages = call_args.kwargs.get("messages") or call_args.args[0]
        assert isinstance(messages, list)
        assert len(messages) >= 1
        # 测试消息文本应出现在 content 中
        text_parts = []
        for msg in messages:
            content = msg.get("content")
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
        full_text = " ".join(text_parts)
        assert "OK" in full_text or "reply" in full_text.lower()

    def test_test_llm_shows_success(self, mock_cloud_initializer, mock_llm_client, capsys):
        """LLM 返回正常响应时显示连接成功"""
        from lifeprism.llm.providers.llm_providers.base import LLMResponse

        mock_llm_client.chat.return_value = LLMResponse(content="OK", finish_reason="stop")

        main_agent_only.main(["test-llm"])

        out = capsys.readouterr().out
        assert "成功" in out

    def test_test_llm_shows_failure_on_error_response(
        self, mock_cloud_initializer, mock_llm_client, capsys
    ):
        """LLM 返回 error 时显示连接失败"""
        from lifeprism.llm.providers.llm_providers.base import LLMResponse

        mock_llm_client.chat.return_value = LLMResponse(
            content="Error: timeout", finish_reason="error"
        )

        main_agent_only.main(["test-llm"])

        out = capsys.readouterr().out
        assert "失败" in out

    def test_test_llm_shows_failure_on_empty_content(
        self, mock_cloud_initializer, mock_llm_client, capsys
    ):
        """LLM 返回空内容时显示连接失败"""
        from lifeprism.llm.providers.llm_providers.base import LLMResponse

        mock_llm_client.chat.return_value = LLMResponse(content=None, finish_reason="stop")

        main_agent_only.main(["test-llm"])

        out = capsys.readouterr().out
        assert "失败" in out

    def test_test_llm_handles_exception(self, mock_cloud_initializer, mock_llm_client, capsys):
        """LLM 调用抛出异常时显示连接失败（不向上抛出）"""
        mock_llm_client.chat.side_effect = RuntimeError("connection refused")

        # 不应抛出异常
        main_agent_only.main(["test-llm"])

        out = capsys.readouterr().out
        assert "失败" in out

    def test_test_llm_displays_reply_content(self, mock_cloud_initializer, mock_llm_client, capsys):
        """连接成功时显示 LLM 回复内容"""
        from lifeprism.llm.providers.llm_providers.base import LLMResponse

        mock_llm_client.chat.return_value = LLMResponse(content="Hello, OK", finish_reason="stop")

        main_agent_only.main(["test-llm"])

        out = capsys.readouterr().out
        assert "Hello, OK" in out


# ==================== Slice 5: CLI 入口与参数解析 ====================


class TestCliDispatch:
    """测试 CLI 入口 main() 的参数解析与命令分发"""

    def test_main_accepts_argv_none(self, mock_cloud_initializer, noop_agent_loop, monkeypatch):
        """main(None) 读取 sys.argv，无参数时默认 start"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False
        # 模拟无命令行参数的启动场景
        monkeypatch.setattr("sys.argv", ["main_agent_only"])

        main_agent_only.main(None)

        mock_init.should_initialize.assert_called_once()

    def test_main_unknown_command_raises_system_exit(self, mock_cloud_initializer):
        """未知命令时 argparse 报错并退出（SystemExit）"""
        with pytest.raises(SystemExit):
            main_agent_only.main(["nonexistent-command"])

    def test_main_help_flag_exits(self, mock_cloud_initializer):
        """--help 触发 SystemExit（argparse 行为）"""
        with pytest.raises(SystemExit):
            main_agent_only.main(["--help"])

    def test_cmd_start_is_callable_directly(self, mock_cloud_initializer, noop_agent_loop):
        """cmd_start 可独立调用（不通过 main）"""
        mock_init = mock_cloud_initializer["instance"]
        mock_init.should_initialize.return_value = False

        args = argparse.Namespace()
        main_agent_only.cmd_start(args)

        mock_init.validate_monitor_type.assert_called_once()

    def test_cmd_show_config_is_callable_directly(
        self, mock_cloud_initializer, monkeypatch, capsys
    ):
        """cmd_show_config 可独立调用（不通过 main）"""
        config_map = {
            "provider": "anthropic",
            "model": "claude-opus-4",
            "api_base": "https://api.anthropic.com",
            "monitor_type": "none",
            "run_mode": "agent_only",
            "timezone": "Asia/Shanghai",
        }
        monkeypatch.setattr(
            main_agent_only.settings,
            "get",
            lambda key, default=None: config_map.get(key, default),
        )
        monkeypatch.setattr(main_agent_only.provider_manager, "get_api_key", lambda *a, **k: None)

        args = argparse.Namespace()
        main_agent_only.cmd_show_config(args)

        out = capsys.readouterr().out
        assert "anthropic" in out
