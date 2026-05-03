"""
测试小米 Mimo provider 连接
通过 build_llm_client 创建 client 并测试基本对话功能
"""
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lifeprism.llm.providers.llm_providers.build_llm_client import create_llm_client
from lifeprism.config import settings, provider_manager


async def test_xiaomi_mimo_connection():
    """测试小米 Mimo 连接"""
    print("=" * 60)
    print("小米 Mimo Provider 连接测试")
    print("=" * 60)

    # 1. 显示当前配置
    print("\n[1] 当前配置信息:")
    print(f"  Provider: {settings.provider}")
    print(f"  Model: {settings.model}")
    print(f"  API Base: {settings.api_base}")

    # 2. 检查 API Key
    api_key = provider_manager.get_api_key("xiaomi_mimo")
    if not api_key or api_key == "no-key":
        print("\n[FAIL] 错误: 未设置小米 Mimo API Key")
        print("\n请先设置 API Key:")
        print("  方法1: 在前端设置页面配置")
        print("  方法2: 使用 keyring 命令行设置:")
        print('    python -c "import keyring; keyring.set_password(\'lifeprism\', \'api_key_xiaomi_mimo\', \'your-api-key\')"')
        return False

    print(f"  API Key: {api_key[:10]}...{api_key[-4:] if len(api_key) > 14 else ''}")

    # 3. 创建 LLM client
    print("\n[2] 创建 LLM Client...")
    try:
        llm_client = create_llm_client()
        print(f"  [OK] Client 类型: {type(llm_client).__name__}")
        print(f"  [OK] 默认模型: {llm_client.get_default_model()}")
    except Exception as e:
        print(f"  [FAIL] 创建 Client 失败: {e}")
        return False

    # 4. 测试基本对话
    print("\n[3] 测试基本对话...")
    test_messages = [
        {
            "role": "system",
            "content": "You are MiMo, an AI assistant developed by Xiaomi."
        },
        {
            "role": "user",
            "content": "请用一句话介绍你自己"
        }
    ]

    try:
        response = await llm_client.chat(
            messages=test_messages,
            max_tokens=200,
            temperature=0.7
        )

        print(f"  [OK] 响应状态: {response.finish_reason}")
        print(f"  [OK] 响应内容: {response.content}")

        if response.usage:
            print(f"\n  Token 使用情况:")
            print(f"    - Prompt tokens: {response.usage.get('prompt_tokens', 0)}")
            print(f"    - Completion tokens: {response.usage.get('completion_tokens', 0)}")
            print(f"    - Total tokens: {response.usage.get('total_tokens', 0)}")

    except Exception as e:
        print(f"  [FAIL] 对话测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

    # 5. 测试多轮对话
    print("\n[4] 测试多轮对话...")
    multi_turn_messages = [
        {"role": "user", "content": "1+1等于几？"},
    ]

    try:
        response = await llm_client.chat(
            messages=multi_turn_messages,
            max_tokens=100,
            temperature=0.7
        )
        print(f"  [OK] 第一轮响应: {response.content}")

        # 添加第二轮
        multi_turn_messages.append({"role": "assistant", "content": response.content})
        multi_turn_messages.append({"role": "user", "content": "那2+2呢？"})

        response = await llm_client.chat(
            messages=multi_turn_messages,
            max_tokens=100,
            temperature=0.7
        )
        print(f"  [OK] 第二轮响应: {response.content}")

    except Exception as e:
        print(f"  [FAIL] 多轮对话测试失败: {e}")
        return False

    # 6. 测试不同模型（如果配置了多个）
    print("\n[5] 测试其他可用模型...")
    other_models = ["mimo-v2.5-pro", "mimo-v2-flash"]

    for model in other_models:
        try:
            print(f"\n  测试模型: {model}")
            response = await llm_client.chat(
                messages=[{"role": "user", "content": "你好"}],
                model=model,
                max_tokens=50,
                temperature=0.7
            )
            print(f"    [OK] {model} 响应: {response.content[:50]}...")
        except Exception as e:
            print(f"    [WARN] {model} 测试失败: {e}")

    print("\n" + "=" * 60)
    print("[SUCCESS] 小米 Mimo Provider 测试完成！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_xiaomi_mimo_connection())
    sys.exit(0 if success else 1)
