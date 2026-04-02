import asyncio
import pytest
from unittest.mock import MagicMock, patch
from lifeprism.llm.bus import InboundMessage, OutboundMessage, MessageQueue
from lifeprism.llm.providers.base import LLMResponse

@pytest.mark.asyncio
async def test_channel_token_usage_saving():
    # 1. Mock dependencies
    mock_bus = MagicMock(spec=MessageQueue)

    # Mock the singleton provider
    with patch("lifeprism.llm.providers.llm_usage_db_provider.llm_usage_db_provider") as mock_db:
        from lifeprism.llm.channel.manager import Channel
        channel = Channel(mock_bus)

        # Prepare test data
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        llm_res = LLMResponse(content="hi", usage=usage)

        # We need to capture the ID generated inside send or mock msg creation
        with patch("lifeprism.llm.channel.manager.InboundMessage") as mock_inbound_cls:
            test_msg_id = "test-123"
            mock_inbound_msg = MagicMock(spec=InboundMessage)
            mock_inbound_msg.id = test_msg_id
            mock_inbound_msg.session_id = "session-abc"
            mock_inbound_msg.type = "chat"
            mock_inbound_cls.return_value = mock_inbound_msg

            # Mock the bus flow
            out_msg = OutboundMessage(id=test_msg_id, response=llm_res)

            # 关键：我们不能让 send() 真的去执行 wait_for(self._pending[msg.id])，因为 self._pending 里的 future 没被填充成功或被并发问题干扰
            # 我们直接在 send() 内部逻辑 mock 掉异步等待过程

            async def mock_publish(msg):
                # 模拟接收循环填充结果
                if msg.id in channel._pending:
                    channel._pending[msg.id].set_result(out_msg)

            mock_bus.publish_inbound = mock_publish

            # 2. Execute send
            with patch.object(channel, "_ensure_receive_task"), \
                 patch.object(channel, "_wait_for_rate_limit"):

                # 调用 send，因为 mock_publish 立即设置了 future，所以不会超时
                result = await channel.send("hello", session_id="session-abc")

                # 3. Verify
                assert result == "hi"

                # 等待后台统计任务完成
                await asyncio.sleep(0.2)

                # 检查是否调用了数据库保存逻辑
                mock_db.save_usage.assert_called_once_with(
                    session_id="session-abc",
                    usage=usage,
                    mode="chat"
                )

if __name__ == "__main__":
    pytest.main([__file__])
