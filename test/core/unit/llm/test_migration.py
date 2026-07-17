"""
测试 providers.yaml 迁移脚本
验证 xiaomi_mimo provider 是否通过迁移脚本正确添加
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from lifeprism.config import provider_manager


def test_migration():
    """测试迁移脚本是否正确执行"""
    print("=" * 60)
    print("测试 providers.yaml 迁移脚本")
    print("=" * 60)

    # 1. 检查配置文件路径
    config_path = provider_manager.get_config_path()
    print(f"\n[1] 配置文件路径: {config_path}")
    print(f"    文件存在: {config_path.exists()}")

    # 2. 检查 allowed_providers
    allowed_providers = provider_manager.get_allowed_providers()
    print(f"\n[2] allowed_providers 列表:")
    for i, provider in enumerate(allowed_providers, 1):
        marker = "[X]" if provider == "xiaomi_mimo" else "[ ]"
        print(f"    {marker} {i}. {provider}")

    if "xiaomi_mimo" in allowed_providers:
        print("\n    [OK] xiaomi_mimo 已添加到 allowed_providers")
    else:
        print("\n    [FAIL] xiaomi_mimo 未在 allowed_providers 中")
        return False

    # 3. 检查 providers 配置
    raw_specs = provider_manager.get_raw_specs()
    xiaomi_spec = None
    for spec in raw_specs:
        if spec.get("name") == "xiaomi_mimo":
            xiaomi_spec = spec
            break

    if xiaomi_spec:
        print(f"\n[3] xiaomi_mimo provider 配置:")
        print(f"    [OK] name: {xiaomi_spec.get('name')}")
        print(f"    [OK] display_name: {xiaomi_spec.get('display_name')}")
        print(f"    [OK] env_key: {xiaomi_spec.get('env_key')}")
        print(f"    [OK] default_api_base: {xiaomi_spec.get('default_api_base')}")
        print(f"    [OK] default_model: {xiaomi_spec.get('default_model')}")
        print(f"    [OK] is_direct: {xiaomi_spec.get('is_direct')}")
        print(f"    [OK] keywords: {xiaomi_spec.get('keywords')}")
    else:
        print(f"\n[3] [FAIL] xiaomi_mimo provider 配置未找到")
        return False

    # 4. 检查 config_version
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    config_version = data.get("config_version", 0)
    print(f"\n[4] config_version: {config_version}")
    if config_version >= 2:
        print("    [OK] 迁移已应用 (version >= 2)")
    else:
        print("    [FAIL] 迁移未应用 (version < 2)")
        return False

    # 5. 测试 API Key 读写
    print(f"\n[5] 测试 API Key 读写:")
    test_key = "test-api-key-12345"

    # 写入测试
    try:
        provider_manager.set_api_key("xiaomi_mimo", test_key)
        print(f"    [OK] 写入测试 API Key 成功")
    except Exception as e:
        print(f"    [FAIL] 写入失败: {e}")
        return False

    # 读取测试
    try:
        retrieved_key = provider_manager.get_api_key("xiaomi_mimo")
        if retrieved_key == test_key:
            print(f"    [OK] 读取测试 API Key 成功")
        else:
            print(f"    [FAIL] 读取的 Key 不匹配: {retrieved_key}")
            return False
    except Exception as e:
        print(f"    [FAIL] 读取失败: {e}")
        return False

    # 清理测试 Key
    try:
        provider_manager.delete_api_key("xiaomi_mimo")
        print(f"    [OK] 清理测试 API Key 成功")
    except Exception as e:
        print(f"    [WARN] 清理失败: {e}")

    print("\n" + "=" * 60)
    print("[SUCCESS] 迁移脚本测试通过！")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = test_migration()
    sys.exit(0 if success else 1)
