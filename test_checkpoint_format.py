"""测试 checkpointer.aget() 返回的数据格式"""
import asyncio
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from lifewatch.config.settings_manager import settings


async def inspect_checkpoint():
    async with AsyncSqliteSaver.from_conn_string(str(settings.chat_db_path)) as checkpointer:
        config = {"configurable": {"thread_id": "session-7f38c6a5"}}
        
        # 方式1: aget_tuple() - 返回完整的 CheckpointTuple
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        
        if checkpoint_tuple is None:
            print("未找到 checkpoint")
            return
        
        print("=" * 60)
        print("CheckpointTuple 结构")
        print("=" * 60)
        print(f"类型: {type(checkpoint_tuple).__name__}")
        print(f"可用属性: {[a for a in dir(checkpoint_tuple) if not a.startswith('_')]}")
        print()
        
        # CheckpointTuple 的主要属性
        print("--- checkpoint_tuple.config ---")
        print(checkpoint_tuple.config)
        print()
        
        print("--- checkpoint_tuple.checkpoint ---")
        checkpoint = checkpoint_tuple.checkpoint
        print(f"类型: {type(checkpoint)}")
        if isinstance(checkpoint, dict):
            print(f"键: {list(checkpoint.keys())}")
        print()
        
        # channel_values 包含实际的状态数据
        if "channel_values" in checkpoint:
            print("--- checkpoint['channel_values'] ---")
            cv = checkpoint["channel_values"]
            print(f"类型: {type(cv)}")
            print(f"键: {list(cv.keys())}")
            print()
            
            # messages 是聊天记录
            if "messages" in cv:
                print("--- messages 列表 ---")
                messages = cv["messages"]
                print(f"消息数量: {len(messages)}")
                print()
                
                for i, msg in enumerate(messages):
                    print(f"[{i}] {type(msg).__name__}")
                    print(f"    .content = {repr(msg.content[:100])}..." if len(msg.content) > 100 else f"    .content = {repr(msg.content)}")
                    if hasattr(msg, "response_metadata"):
                        print(f"    .response_metadata = {msg.response_metadata}")
                    print()


if __name__ == "__main__":
    asyncio.run(inspect_checkpoint())
