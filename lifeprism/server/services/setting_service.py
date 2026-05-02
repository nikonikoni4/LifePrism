"""
Settings 服务层 - 配置管理业务逻辑

纯函数模块，封装 SettingsManager 的操作，提供给 API 层使用
"""
import os
import sys
import shutil
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from lifeprism.config.settings_manager import settings
from lifeprism.config.provider_manager import provider_manager
from lifeprism.utils.common_utils import is_dev_environment
from lifeprism.server.schemas.setting_schemas import (
    SettingItems,
    UpdateSettingsRequest,
    ValidatePathResponse,
    MigrateDataPathResponse,
)
from lifeprism.utils import get_logger
from lifeprism.llm.channel.wechat.client import WechatClient

logger = get_logger(__name__)


def get_settings() -> SettingItems:
    """
    获取所有配置 (API Key 脱敏显示)

    Returns:
        SettingItems: 完整配置，API Key 已脱敏
    """
    config = settings.get_for_display()
    # 添加 provider_list (来自 provider_manager)
    config['provider_list'] = provider_manager.provider_list
    # 添加 provider_id_map (名称到 ID 的映射)
    config['provider_id_map'] = provider_manager.name_to_id_map
    # 添加 model_history
    config['model_history'] = settings.model_history
    config['config_base_path'] = settings.config_base_path
    return SettingItems(**config)


def update_settings(request: UpdateSettingsRequest) -> SettingItems:
    """
    批量更新配置 (不包含 api_key)

    只更新请求中非 None 的字段

    Args:
        request: 更新配置请求

    Returns:
        SettingItems: 更新后的完整配置

    Raises:
        ValueError: 当 screenshot_monitor=True 但 is_vlm[provider/model] 不存在或为 false 时
    """
    updates = request.model_dump(exclude_none=True)
    if updates:
        logger.info(f"更新配置: {list(updates.keys())}")

        # 检查 screenshot_monitor 开启时的 is_vlm 校验
        if updates.get('screenshot_monitor') is True:
            provider_name = updates.get('provider') or settings.provider
            provider_id = provider_manager.get_provider_id(provider_name) if provider_name else ""
            model = updates.get('model') or settings.model
            if provider_id and model:
                key = f"{provider_id}/{model}"
                is_vlm_cache = settings.get('is_vlm', {})
                vlm_status = is_vlm_cache.get(key)
                if vlm_status is not True:
                    # is_vlm 不存在或为 false，拒绝开启截图监控
                    raise ValueError(
                        f"当前模型 ({provider_id}/{model}) 不具备图片理解能力，"
                        f"请先调用 POST /settings/test-vlm 进行验证。current_vlm_status={vlm_status}"
                    )

        provider_name = updates.get('provider') or settings.provider
        provider_id = provider_manager.get_provider_id(provider_name) if provider_name else ""
        api_base = updates.get('api_base')
        model = updates.get('model')

        if provider_id and api_base is not None:
            settings.set_provider_api_base(provider_id, api_base)
            logger.info(f"已更新 {provider_id} 的 API Base 历史")

        if provider_id and model:
            settings.add_model_to_history(provider_id, model, api_base)
            logger.info(f"已将模型 {model} 添加到 {provider_id} 的历史记录")

        settings.update(updates)
    return get_settings()


def update_api_key(api_key: str, provider_id: Optional[str] = None) -> bool:
    """
    更新 API Key (安全存储到 keyring)

    Args:
        api_key: 新的 API Key
        provider_id: 服务商 ID 或显示名称，如 "aliyun", "火山引擎 (VolcEngine)" 等。
                     如果为 None，则保存到通用位置（向后兼容）

    Returns:
        bool: 是否成功
    """
    if provider_id:
        # 将显示名称转换为 provider_id（如果传入的是显示名称）
        actual_provider_id = provider_manager.get_provider_id(provider_id)
        logger.info(f"正在更新 {actual_provider_id} 的 API Key...")
        settings.set_api_key(api_key, actual_provider_id)
        logger.info(f"{actual_provider_id} 的 API Key 已安全保存到系统密钥管理器")
    else:
        logger.info("正在更新 API Key...")
        settings.set('api_key', api_key)
        logger.info("API Key 已安全保存到系统密钥管理器")
    return True


def validate_api_key(provider_id: Optional[str] = None) -> bool:
    """
    检查 API Key 是否已配置

    Args:
        provider_id: 服务商 ID，如果为 None 则检查通用 API Key

    Returns:
        bool: API Key 是否存在
    """
    if provider_id:
        return settings.get_api_key(provider_id) is not None
    return settings.api_key is not None


def get_model_history(provider_id: str) -> List[str]:
    """
    获取指定服务商的模型历史

    Args:
        provider_id: 服务商 ID

    Returns:
        模型名称列表
    """
    return settings.get_model_history_for_provider(provider_id)


def remove_model_from_history(provider_id: str, model: str) -> bool:
    """
    从历史记录中删除模型

    Args:
        provider_id: 服务商 ID
        model: 模型名称/ID

    Returns:
        是否删除成功
    """
    result = settings.remove_model_from_history(provider_id, model)
    if result:
        logger.info(f"已从 {provider_id} 的历史记录中删除模型 {model}")
    return result


def validate_data_path(path: str, path_type: str) -> ValidatePathResponse:
    """
    验证数据路径是否有效

    Args:
        path: 要验证的路径
        path_type: 路径类型 (lifeprism_data | aw_db)

    Returns:
        ValidatePathResponse: 验证结果
    """
    if not path or not path.strip():
        return ValidatePathResponse(valid=False, message="路径不能为空")

    target = Path(path)

    if path_type == 'lifeprism_data':
        # 检测数据路径不能和安装路径相同
        if getattr(sys, 'frozen', False):
            install_dir = Path(sys.executable).parent.parent.parent
            try:
                if target.resolve() == install_dir.resolve():
                    return ValidatePathResponse(
                        valid=False,
                        message="数据路径不能与安装路径相同"
                    )
                # 检查是否是安装路径的子目录
                target.resolve().relative_to(install_dir.resolve())
                return ValidatePathResponse(
                    valid=False,
                    message="数据路径不能位于安装目录内"
                )
            except ValueError:
                pass  # 不是子目录，正常

        # 检查父目录是否存在或可创建
        if target.exists() and not target.is_dir():
            return ValidatePathResponse(valid=False, message="路径已存在但不是目录")

        return ValidatePathResponse(valid=True, message="路径有效")

    elif path_type == 'aw_db':
        # AW 数据库路径验证
        expanded = Path(os.path.expanduser(path))
        if not expanded.exists():
            return ValidatePathResponse(valid=False, message="文件不存在")
        if not expanded.is_file():
            return ValidatePathResponse(valid=False, message="路径不是文件")
        if not expanded.suffix == '.db':
            return ValidatePathResponse(valid=False, message="文件不是 .db 数据库文件")
        return ValidatePathResponse(valid=True, message="路径有效")

    return ValidatePathResponse(valid=False, message=f"未知的路径类型: {path_type}")


# 迁移时排除的子目录黑名单（配置文件固定在默认路径，不参与迁移）
_EXCLUDED_SUBDIRS = [
    "config",
]


def _get_subdirs_to_migrate(current_path: Path) -> list[str]:
    """获取需要迁移的子目录列表（黑名单过滤）"""
    if not current_path.exists():
        return []
    return [
        d.name for d in current_path.iterdir()
        if d.is_dir() and d.name not in _EXCLUDED_SUBDIRS
    ]


def migrate_data_path(target_base_path: str, migrate_data: bool = True) -> MigrateDataPathResponse:
    """
    迁移数据到新路径，或仅切换路径不迁移数据

    配置文件（config/）固定在默认路径，不参与迁移。
    除 config/ 外的数据子目录都会被迁移。

    流程: 开发模式检查 → 计算新路径 → 验证 → [关闭DB连接 → 复制数据] → 更新配置

    Args:
        target_base_path: 用户选择的目标基础路径（不含 lifeprismData）
        migrate_data: 是否迁移数据，False 则仅切换路径并创建空目录结构

    Returns:
        MigrateDataPathResponse: 迁移结果
    """
    # 1. 开发模式禁用
    if is_dev_environment():
        return MigrateDataPathResponse(
            success=False,
            message="开发模式下不支持数据路径迁移"
        )

    # 2. 计算新路径（末尾已是 lifeprismData 则不再追加）
    if not target_base_path or not target_base_path.strip():
        return MigrateDataPathResponse(success=False, message="目标路径不能为空")

    target = Path(target_base_path)
    if target.name == "lifeprismData":
        new_path = target
    else:
        new_path = target / "lifeprismData"
    current_path = Path(settings.lifeprism_data_path)

    # 3. 验证
    try:
        if new_path.resolve() == current_path.resolve():
            return MigrateDataPathResponse(
                success=False,
                message="新路径与当前路径相同"
            )
    except Exception:
        pass

    # 检查不能在安装路径内
    if getattr(sys, 'frozen', False):
        install_dir = Path(sys.executable).parent.parent.parent
        try:
            new_path.resolve().relative_to(install_dir.resolve())
            return MigrateDataPathResponse(
                success=False,
                message="数据路径不能位于安装目录内"
            )
        except ValueError:
            pass

    # 检查目标父目录是否存在
    if not Path(target_base_path).exists():
        return MigrateDataPathResponse(
            success=False,
            message=f"目标目录不存在: {target_base_path}"
        )

    if migrate_data:
        # 4. 关闭数据库连接池

        from lifeprism.repository import lw_db_manager

        logger.info("迁移数据：关闭数据库连接池...")
        try:
            lw_db_manager._close_connection_pool()
        except Exception as e:
            logger.error(f"关闭连接池失败: {e}")
            return MigrateDataPathResponse(
                success=False,
                message=f"关闭数据库连接失败: {e}"
            )

        # 5. 复制数据
        try:
            new_path.mkdir(parents=True, exist_ok=True)
            for subdir in _get_subdirs_to_migrate(current_path):
                src = current_path / subdir
                dst = new_path / subdir
                if src.exists() and src.is_dir():
                    shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
                    logger.info(f"已复制: {src} -> {dst}")
                else:
                    dst.mkdir(parents=True, exist_ok=True)
                    logger.info(f"源目录不存在，已创建空目录: {dst}")
        except Exception as e:
            logger.error(f"复制数据失败: {e}")
            return MigrateDataPathResponse(
                success=False,
                message=f"复制数据失败: {e}"
            )
    else:
        # 仅切换路径：创建目录结构，不复制数据
        try:
            new_path.mkdir(parents=True, exist_ok=True)
            for subdir in _get_subdirs_to_migrate(current_path):
                (new_path / subdir).mkdir(parents=True, exist_ok=True)
            logger.info(f"仅切换路径，已创建空目录结构: {new_path}")
        except Exception as e:
            logger.error(f"创建目录结构失败: {e}")
            return MigrateDataPathResponse(
                success=False,
                message=f"创建目录结构失败: {e}"
            )

    # 6. 更新配置（写入旧路径的 config.yaml，重启后后端会从中读取新路径）
    try:
        settings.update({"lifeprism_data_path": str(new_path)})
        logger.info(f"数据迁移完成: {current_path} -> {new_path}")
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        return MigrateDataPathResponse(
            success=False,
            message=f"数据已复制但更新配置失败: {e}"
        )

    return MigrateDataPathResponse(
        success=True,
        message="数据迁移成功，请重启程序",
        new_path=str(new_path)
    )


async def test_vlm_capability() -> dict:
    """
    测试当前模型的 VLM 能力

    流程:
    1. 调用 test_connect() 验证 LLM 连接
    2. 连接失败 → 返回错误
    3. 连接成功 → 调用 test_vlm() 测试图像理解
    4. 写入 is_vlm[provider_id/model] = result.success

    Returns:
        dict: 包含 success, message, is_vlm, model_response
    """
    from lifeprism.llm.function.test_connect import test_connect
    from lifeprism.llm.function.test_vlm import test_vlm

    # 1. 先测试连接
    connect_result = await test_connect()
    if not connect_result.get('success', False):
        return {
            'success': False,
            'message': f"连接失败: {connect_result.get('message', '未知错误')}",
            'is_vlm': False,
            'model_response': None
        }

    # 2. 连接成功，测试 VLM
    vlm_result = await test_vlm()

    # 3. 获取 provider_id 和 model 构建 key
    provider_name = settings.provider
    provider_id = provider_manager.get_provider_id(provider_name) if provider_name else ""
    model = settings.model
    cache_updated = False
    if provider_id and model:
        key = f"{provider_id}/{model}"
        is_vlm = vlm_result.get('success', False)
        # 更新 is_vlm 缓存
        is_vlm_cache = settings.get('is_vlm', {})
        is_vlm_cache[key] = is_vlm
        settings.set('is_vlm', is_vlm_cache)
        logger.info(f"VLM 能力测试完成: {key} = {is_vlm}")
        cache_updated = True

    return {
        'success': vlm_result.get('success', False),
        'message': vlm_result.get('message', '测试完成'),
        'is_vlm': vlm_result.get('success', False),
        'model_response': vlm_result.get('model_response'),
        'cache_updated': cache_updated
    }


async def get_qrcode(channel: str) -> dict:
    """获取指定通道的 QR 码

    Args:
        channel: 通道类型（当前仅支持 wechat）

    Returns:
        包含 qr_string 和 qrcode_id 的字典

    Raises:
        ValueError: 不支持的通道类型
    """
    if channel != "wechat":
        raise ValueError(f"不支持的通道类型: {channel}")

    from lifeprism.llm.channel.wechat.config import WechatConfig

    config = WechatConfig()
    base_url = config.base_url

    logger.info(f"正在获取 {channel} 通道的 QR 码")
    async with WechatClient(base_url) as client:
        try:
            data = await client.api_get("ilink/bot/get_bot_qrcode", params={"bot_type": "3"}, auth=False)
        except Exception as e:
            logger.error(f"获取 QR 码失败: {e}", exc_info=True)
            raise ValueError(f"获取 QR 码失败: {str(e)}")

        qrcode_id = data.get("qrcode", "")
        qrcode_img = data.get("qrcode_img_content", qrcode_id)

        if not qrcode_id:
            logger.error(f"获取 QR 码失败，返回数据: {data}")
            raise ValueError("获取 QR 码失败")

        logger.info(f"成功获取 QR 码，ID: {qrcode_id[:20]}...")
        return {
            "qr_string": qrcode_img,
            "qrcode_id": qrcode_id
        }


async def get_qrcode_status(channel: str, qrcode_id: str) -> dict:
    """查询 QR 码扫描状态

    Args:
        channel: 通道类型（wechat）
        qrcode_id: QR 码 ID

    Returns:
        包含 status 和 message 的字典
    """
    if channel != "wechat":
        raise ValueError(f"不支持的通道类型: {channel}")

    from lifeprism.llm.channel.wechat.config import WechatConfig

    config = WechatConfig()
    base_url = config.base_url

    logger.info(f"正在查询 QR 码状态: {qrcode_id[:20]}...")
    async with WechatClient(base_url) as client:
        try:
            data = await client.api_get("ilink/bot/get_qrcode_status", params={"qrcode": qrcode_id}, auth=False)
        except Exception as e:
            logger.error(f"查询 QR 码状态失败: {e}", exc_info=True)
            raise ValueError(f"查询 QR 码状态失败: {str(e)}")

        raw_status = data.get("status", "")

        # 状态映射
        status_map = {
            "": "waiting",
            "waiting": "waiting",
            "scanning": "scanning",
            "confirmed": "confirmed",
            "expired": "expired"
        }
        mapped_status = status_map.get(raw_status, "waiting")

        logger.info(f"QR 码状态: {raw_status} -> {mapped_status}")

        # 如果状态为 confirmed，保存 token
        if mapped_status == "confirmed":
            bot_token = data.get("bot_token", "")
            if bot_token:
                # 使用 WechatAuth 静态方法保存 token 到 keyring
                from lifeprism.llm.channel.wechat.auth import WechatAuth

                account_dir = Path(settings.channel_path) / "wechat"
                account_dir.mkdir(parents=True, exist_ok=True)
                account_file = account_dir / "account.json"

                # 保存 token 到 keyring（使用静态方法）
                if WechatAuth._save_token_to_keyring(bot_token):
                    # 保存 context_tokens 到文件（token 已在 keyring 中）
                    account_data = {"context_tokens": {}}
                    with open(account_file, "w", encoding="utf-8") as f:
                        json.dump(account_data, f, ensure_ascii=False, indent=2)
                    logger.info(f"已保存 bot_token 到 keyring 和 context_tokens 到 {account_file}")
                    
                else:
                    # keyring 不可用，fallback 到文件存储
                    logger.warning("Keyring 不可用，使用文件存储 token")
                    account_data = {"token": bot_token, "context_tokens": {}}
                    with open(account_file, "w", encoding="utf-8") as f:
                        json.dump(account_data, f, ensure_ascii=False, indent=2)

                    logger.info(f"已保存 bot_token 到 {account_file}（文件模式）")
                    

                # 启动微信channel
                from lifeprism.llm.channel import wechat_channel
                await wechat_channel.start() # 有_runing确认启动保护，避免重复启动
                return {"status": mapped_status, "message": "登录成功，token 已保存"}
                
            else:
                logger.warning("状态为 confirmed 但未获取到 bot_token")
                return {"status": mapped_status, "message": "登录成功但未获取到 token"}

        # 其他状态
        message_map = {
            "waiting": "等待扫码",
            "scanning": "已扫码，等待确认",
            "expired": "二维码已过期"
        }
        return {"status": mapped_status, "message": message_map.get(mapped_status, "未知状态")}
