"""测试微信 channel keyring 迁移功能"""

import json
import keyring
from pathlib import Path
from lifeprism.llm.channel.wechat.auth import WechatAuth, KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME
from lifeprism.llm.channel.wechat.client import WechatClient


def cleanup():
    """清理测试环境"""
    # 清理 keyring
    try:
        keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME)
        print("[OK] 清理 keyring 成功")
    except Exception:
        print("[OK] Keyring 中无数据")

    # 清理测试文件
    test_file = Path("test_account.json")
    if test_file.exists():
        test_file.unlink()
        print("[OK] 清理测试文件成功")


def test_save_and_load_keyring():
    """测试保存和加载 token 到 keyring"""
    print("\n=== 测试 1: 保存和加载 token 到 keyring ===")

    client = WechatClient("https://test.com")
    auth = WechatAuth(client, Path("test_account.json"))

    # 保存状态
    test_token = "test_token_12345"
    test_context_tokens = {"user1": "ctx1", "user2": "ctx2"}
    state = {
        "token": test_token,
        "context_tokens": test_context_tokens
    }

    auth.save_state(state)
    print("[OK] 保存状态完成")

    # 验证 keyring
    saved_token = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME)
    assert saved_token == test_token, f"Keyring token 不匹配: {saved_token}"
    print(f"[OK] Keyring 中的 token 正确: {saved_token}")

    # 验证文件
    file_data = json.loads(Path("test_account.json").read_text())
    assert "token" not in file_data, "文件中不应包含 token"
    assert file_data["context_tokens"] == test_context_tokens, "Context tokens 不匹配"
    print(f"[OK] 文件中仅包含 context_tokens: {file_data}")

    # 加载状态
    loaded_state = auth.load_state()
    assert loaded_state["token"] == test_token, "加载的 token 不匹配"
    assert loaded_state["context_tokens"] == test_context_tokens, "加载的 context_tokens 不匹配"
    print(f"[OK] 加载状态成功: token={loaded_state['token']}, context_tokens={loaded_state['context_tokens']}")


def test_migration_from_file():
    """测试从文件自动迁移到 keyring"""
    print("\n=== 测试 2: 从文件自动迁移到 keyring ===")

    # 准备旧格式文件
    test_token = "old_token_67890"
    test_context_tokens = {"user3": "ctx3"}
    old_state = {
        "token": test_token,
        "context_tokens": test_context_tokens
    }

    test_file = Path("test_account.json")
    test_file.write_text(json.dumps(old_state, ensure_ascii=False, indent=2))
    print(f"[OK] 创建旧格式文件: {old_state}")

    # 加载状态（应触发迁移）
    client = WechatClient("https://test.com")
    auth = WechatAuth(client, test_file)
    loaded_state = auth.load_state()

    # 验证迁移结果
    assert loaded_state["token"] == test_token, "迁移后 token 不匹配"
    assert loaded_state["context_tokens"] == test_context_tokens, "迁移后 context_tokens 不匹配"
    print(f"[OK] 迁移后加载成功: {loaded_state}")

    # 验证 keyring
    keyring_token = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_WECHAT_TOKEN_USERNAME)
    assert keyring_token == test_token, "Keyring 中的 token 不匹配"
    print(f"[OK] Token 已迁移到 keyring: {keyring_token}")

    # 验证文件中 token 已移除
    file_data = json.loads(test_file.read_text())
    assert "token" not in file_data, "文件中仍包含 token"
    assert file_data["context_tokens"] == test_context_tokens, "文件中 context_tokens 不匹配"
    print(f"[OK] 文件中 token 已移除: {file_data}")


def test_empty_state():
    """测试空状态（无文件无 keyring）"""
    print("\n=== 测试 3: 空状态 ===")

    client = WechatClient("https://test.com")
    auth = WechatAuth(client, Path("test_account.json"))

    loaded_state = auth.load_state()
    assert loaded_state["token"] == "", "空状态 token 应为空字符串"
    assert loaded_state["context_tokens"] == {}, "空状态 context_tokens 应为空字典"
    print(f"[OK] 空状态加载正确: {loaded_state}")


if __name__ == "__main__":
    try:
        print("开始测试微信 channel keyring 功能\n")

        # 测试 1: 保存和加载
        cleanup()
        test_save_and_load_keyring()

        # 测试 2: 迁移
        cleanup()
        test_migration_from_file()

        # 测试 3: 空状态
        cleanup()
        test_empty_state()

        # 清理
        cleanup()

        print("\n" + "="*50)
        print("[SUCCESS] 所有测试通过！")
        print("="*50)

    except AssertionError as e:
        print(f"\n[FAIL] 测试失败: {e}")
        cleanup()
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] 测试出错: {e}")
        import traceback
        traceback.print_exc()
        cleanup()
        exit(1)
