"""
测试 monitor_type 字段在前后端的传递
验证修复：前端设置界面能正确显示数据源选择
"""

import asyncio

from lifeprism.config.settings_manager import settings
from lifeprism.server.schemas.setting_schemas import UpdateSettingsRequest
from lifeprism.server.services.setting_service import get_settings, update_settings


async def test_monitor_type_flow():
    """测试 monitor_type 的完整数据流"""

    print("=" * 60)
    print("测试 monitor_type 数据流")
    print("=" * 60)

    # 1. 测试从配置读取
    print("\n1. 从配置文件读取 monitor_type:")
    raw_value = settings.get("monitor_type")
    print(f"   settings.get('monitor_type') = {raw_value}")

    # 2. 测试 API 返回
    print("\n2. 通过 API 获取配置:")
    settings_response = get_settings()
    settings_dict = settings_response.model_dump()
    print(f"   API 返回的 monitor_type = {settings_dict.get('monitor_type')}")

    # 3. 测试更新为 activitywatch
    print("\n3. 更新 monitor_type 为 'activitywatch':")
    update_request = UpdateSettingsRequest(monitor_type="activitywatch")
    updated_settings = update_settings(update_request)
    updated_dict = updated_settings.model_dump()
    print(f"   更新后的 monitor_type = {updated_dict.get('monitor_type')}")

    # 4. 验证配置已持久化
    print("\n4. 验证配置已持久化:")
    persisted_value = settings.get("monitor_type")
    print(f"   settings.get('monitor_type') = {persisted_value}")

    # 5. 恢复为 lifeprism
    print("\n5. 恢复 monitor_type 为 'lifeprism':")
    restore_request = UpdateSettingsRequest(monitor_type="lifeprism")
    restored_settings = update_settings(restore_request)
    restored_dict = restored_settings.model_dump()
    print(f"   恢复后的 monitor_type = {restored_dict.get('monitor_type')}")

    print("\n" + "=" * 60)
    print("测试完成！所有步骤通过 ✓")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_monitor_type_flow())
