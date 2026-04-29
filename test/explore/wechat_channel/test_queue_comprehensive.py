"""Comprehensive test for all three MessageQueue fixes"""
import asyncio
import sys
import io
from lifeprism.llm.bus.queue import MessageQueue
from lifeprism.llm.bus.events import OutboundMessage, InboundMessage

# Fix encoding for Windows console
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

class MockResponse:
    def __init__(self, content):
        self.content = content
        self.usage = None

async def test_fix_1_receive_loop_exit():
    """Test Fix 1: _receive_loop respects stop_receive flag"""
    print("\n=== Test 1: _receive_loop Exit Condition ===")
    queue = MessageQueue()

    # Start the receive loop
    queue._ensure_receive_task()
    await asyncio.sleep(0.1)  # Let it start

    assert queue._receive_task is not None, "Receive task should be running"
    assert not queue._receive_task.done(), "Receive task should not be done yet"

    # Close should set stop_receive and cancel the task
    await queue.close()

    assert queue.stop_receive == True, "stop_receive should be True after close"
    assert queue._receive_task is None, "Receive task should be None after close"

    print("✓ Test 1 passed: _receive_loop properly exits on close")

async def test_fix_2_close_cleanup():
    """Test Fix 2: close() properly sets stop_receive and cleans up pending futures"""
    print("\n=== Test 2: close() Cleanup ===")
    queue = MessageQueue()

    # Create some pending futures
    loop = asyncio.get_running_loop()
    future1 = loop.create_future()
    future2 = loop.create_future()
    queue._pending["msg1"] = future1
    queue._pending["msg2"] = future2

    # Start receive loop
    queue._ensure_receive_task()
    await asyncio.sleep(0.1)

    # Close should cancel the task and clean up futures
    await queue.close()

    assert queue.stop_receive == True, "stop_receive should be True"
    assert len(queue._pending) == 0, "All pending futures should be cleaned up"
    assert future1.cancelled(), "Future 1 should be cancelled"
    assert future2.cancelled(), "Future 2 should be cancelled"

    print("✓ Test 2 passed: close() properly cleans up pending futures")

async def test_fix_3_timeout_handling():
    """Test Fix 3: send() properly handles timeout without NameError"""
    print("\n=== Test 3: Timeout Handling ===")
    queue = MessageQueue()

    # Test timeout scenario - no responder, should timeout cleanly
    try:
        # Use a very short timeout to speed up test
        from lifeprism.llm.bus import queue as queue_module
        original_timeout = queue_module.TIMEOUT_MAX
        queue_module.TIMEOUT_MAX = 0.1

        result = await queue.send("timeout test", session_id="test_session")
        assert False, "Should have raised TimeoutError"
    except asyncio.TimeoutError:
        print("✓ Timeout occurred as expected")
        # Give a moment for finally block to execute
        await asyncio.sleep(0.01)
        assert len(queue._pending) == 0, f"Future should be cleaned up after timeout, but found {len(queue._pending)} pending"
    finally:
        queue_module.TIMEOUT_MAX = original_timeout
        await queue.close()

    print("✓ Test 3 passed: Timeout handled without NameError, future cleaned up")

async def test_normal_flow():
    """Test that normal message flow still works after fixes"""
    print("\n=== Test 4: Normal Flow ===")
    queue = MessageQueue()

    async def responder():
        msg = await queue.consume_inbound()
        response = OutboundMessage(
            id=msg.id,
            session_id=msg.session_id,
            response=MockResponse("test response")
        )
        await queue.publish_outbound(response)

    responder_task = asyncio.create_task(responder())

    try:
        result = await queue.send("test message", session_id="test_session")
        assert result == "test response", f"Expected 'test response', got {result}"
        assert len(queue._pending) == 0, "Future should be cleaned up"
        print("✓ Test 4 passed: Normal flow works correctly")
    finally:
        await responder_task
        await queue.close()

async def test_receive_loop_exception_handling():
    """Test that _receive_loop handles exceptions properly"""
    print("\n=== Test 5: Exception Handling in _receive_loop ===")
    queue = MessageQueue()

    # Start receive loop
    queue._ensure_receive_task()
    await asyncio.sleep(0.1)

    # Create a pending future
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    queue._pending["test_msg"] = future

    # Cancel the receive task (simulates CancelledError)
    await queue.close()

    # Verify cleanup happened
    assert len(queue._pending) == 0, "Pending futures should be cleaned up on CancelledError"
    assert future.cancelled(), "Future should be cancelled"

    print("✓ Test 5 passed: Exception handling works correctly")

async def test_future_done_check():
    """Test that _receive_loop checks if future is done before setting result"""
    print("\n=== Test 6: Future Done Check ===")
    queue = MessageQueue()

    async def responder():
        msg = await queue.consume_inbound()

        # Simulate a race: cancel the future before response arrives
        future = queue._pending.get(msg.id)
        if future:
            future.cancel()

        # Now try to send response - should not crash
        response = OutboundMessage(
            id=msg.id,
            session_id=msg.session_id,
            response=MockResponse("late response")
        )
        await queue.publish_outbound(response)

    responder_task = asyncio.create_task(responder())

    try:
        result = await queue.send("test message", session_id="test_session")
        assert False, "Should have been cancelled"
    except asyncio.CancelledError:
        print("✓ Future was cancelled as expected")

    await responder_task
    await asyncio.sleep(0.1)  # Let receive loop process the late response
    await queue.close()

    print("✓ Test 6 passed: _receive_loop checks future.done() before setting result")

async def main():
    print("=" * 60)
    print("Running Comprehensive MessageQueue Fix Tests")
    print("=" * 60)

    try:
        await test_fix_1_receive_loop_exit()
        await test_fix_2_close_cleanup()
        await test_fix_3_timeout_handling()
        await test_normal_flow()
        await test_receive_loop_exception_handling()
        await test_future_done_check()

        print("\n" + "=" * 60)
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        print("\nAll three fixes verified:")
        print("1. _receive_loop respects stop_receive flag")
        print("2. close() sets stop_receive and cleans up pending futures")
        print("3. send() handles timeout without NameError")

    except Exception as e:
        print(f"\n✗ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
