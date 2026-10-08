"""微信只收发统一输入输出，不识别命令或等待 Agent。"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from lifeprism.llm.bus import MessageQueue, OutboundMessage
from lifeprism.llm.channel.wechat.channel import WechatChannel
from lifeprism.llm.channel.wechat.config import WechatConfig
from lifeprism.llm.providers import LLMResponse

pytestmark = pytest.mark.core


def raw_message(text="/new", *, message_id="message-1", token="fresh"):
    return {
        "from_user_id": "alice",
        "message_id": message_id,
        "context_token": token,
        "item_list": [{"type": 1, "text_item": {"text": text}}],
    }


def test_command_is_forwarded_unchanged_and_credentials_are_separate():
    """渠道不处理 /new，且只向凭据接口写 context_token。"""

    async def scenario():
        receive = AsyncMock()
        replies = SimpleNamespace(remember=Mock(), get_token=Mock(return_value="fresh"))
        channel = WechatChannel(
            WechatConfig(), MessageQueue(), on_message=receive, reply_store=replies
        )
        channel.media = SimpleNamespace(download_media=AsyncMock())
        await channel._handle_wechat_message(raw_message())
        incoming = receive.call_args.args[0]
        assert incoming.text == "/new"
        assert incoming.input_id == "message-1"
        assert incoming.route.recipient_id == "alice"
        replies.remember.assert_called_once_with("alice", "fresh")
        assert not hasattr(channel, "_handle_session_command")
        assert not hasattr(channel, "_user_data")

    asyncio.run(scenario())


def test_business_admission_precedes_credentials_and_media():
    """白名单/本地归属由注入业务判断，拒绝后不处理媒体或提交。"""

    async def scenario():
        receive = AsyncMock()
        replies = SimpleNamespace(remember=Mock())
        channel = WechatChannel(
            WechatConfig(),
            MessageQueue(),
            on_message=receive,
            reply_store=replies,
            allow_input=lambda route: False,
        )
        channel.media = SimpleNamespace(download_media=AsyncMock())
        await channel._handle_wechat_message(raw_message())
        receive.assert_not_awaited()
        replies.remember.assert_not_called()
        channel.media.download_media.assert_not_awaited()

    asyncio.run(scenario())


def test_sending_uses_latest_reply_token_and_unavailable_transport_fails():
    """发送凭据由transport现取，失效收发层不能静默假装成功。"""

    async def scenario():
        from lifeprism.llm.channel.wechat.exceptions import WechatAPIError

        replies = SimpleNamespace(get_token=Mock(return_value="latest"))
        channel = WechatChannel(WechatConfig(), MessageQueue(), reply_store=replies)
        message = OutboundMessage(
            response=LLMResponse(content="question"), extra={"wechat_user_id": "alice"}
        )
        with pytest.raises(WechatAPIError):
            await channel.send(message)
        channel._running = True
        channel.client = SimpleNamespace(api_post=AsyncMock())
        await channel.send(message)
        body = channel.client.api_post.call_args.args[1]
        assert body["msg"]["context_token"] == "latest"

    asyncio.run(scenario())


def test_stop_cleans_business_and_http_after_failed_poll():
    """轮询协程已经失败，也必须释放自有业务任务和 HTTP 客户端。"""

    async def scenario():
        stop_business = AsyncMock()
        channel = WechatChannel(WechatConfig(), MessageQueue(), on_stop=stop_business)
        http = SimpleNamespace(__aexit__=AsyncMock())
        channel.client = http

        async def broken_poll():
            raise RuntimeError("unexpected polling failure")

        channel._poll_task = asyncio.create_task(broken_poll())
        await asyncio.gather(channel._poll_task, return_exceptions=True)
        try:
            await channel.stop()
        except RuntimeError:
            pass
        stop_business.assert_awaited_once()
        http.__aexit__.assert_awaited_once()
        assert channel.client is None and channel._poll_task is None

    asyncio.run(scenario())


def test_partial_business_start_failure_is_cleaned(monkeypatch):
    """启动业务入口中途失败时也调用关闭入口。"""

    async def scenario():
        from lifeprism.llm.channel.wechat import channel as module

        http = SimpleNamespace(__aenter__=AsyncMock(), __aexit__=AsyncMock())
        monkeypatch.setattr(module, "WechatClient", lambda base: http)
        monkeypatch.setattr(
            module,
            "WechatAuth",
            lambda *args: SimpleNamespace(load_state=lambda: {"token": "fake"}),
        )
        start_business = AsyncMock(side_effect=RuntimeError("partial start"))
        stop_business = AsyncMock()
        channel = WechatChannel(
            WechatConfig(),
            MessageQueue(),
            on_message=AsyncMock(),
            on_start=start_business,
            on_stop=stop_business,
            reply_store=SimpleNamespace(migrate_legacy=Mock()),
        )
        with pytest.raises(RuntimeError, match="partial start"):
            await channel.start()
        stop_business.assert_awaited_once()
        http.__aexit__.assert_awaited_once()
        assert channel.client is None and not channel._running

    asyncio.run(scenario())


def test_media_failure_is_normalized_for_poll_isolation():
    """媒体自定义异常与网络异常使用相同的单条输入隔离入口。"""

    async def scenario():
        from lifeprism.llm.channel.wechat.exceptions import WechatMediaError, WechatMessageError

        channel = WechatChannel(
            WechatConfig(),
            MessageQueue(),
            on_message=AsyncMock(),
            reply_store=SimpleNamespace(remember=Mock()),
        )
        channel.media = SimpleNamespace(
            download_media=AsyncMock(side_effect=WechatMediaError("invalid image"))
        )
        raw = raw_message()
        raw["item_list"] = [{"type": 2, "image_item": {}}]
        with pytest.raises(WechatMessageError, match="媒体"):
            await channel._handle_wechat_message(raw)
        channel.on_message.assert_not_awaited()

    asyncio.run(scenario())


def test_bad_business_input_does_not_stop_next_message():
    """业务入口的非协议异常只隔离本条输入，下一条仍能接收。"""

    async def scenario():
        count = 0
        channel = WechatChannel(
            WechatConfig(), MessageQueue(), reply_store=SimpleNamespace(remember=Mock())
        )

        async def receive(incoming):
            nonlocal count
            count += 1
            if count == 1:
                raise OSError("state temporarily unavailable")
            channel._running = False

        channel.on_message = receive
        channel._running = True
        channel.client = SimpleNamespace(
            api_post=AsyncMock(
                return_value={
                    "msgs": [raw_message(message_id="bad"), raw_message(message_id="good")]
                }
            )
        )
        await channel._poll_loop()
        assert count == 2

    asyncio.run(scenario())
