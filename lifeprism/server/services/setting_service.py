"""
Settings 服务层 - 配置管理业务逻辑

纯函数模块，封装 SettingsManager 的操作，提供给 API 层使用
"""
import os
import sys
import shutil
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
    """
    updates = request.model_dump(exclude_none=True)
    if updates:
        logger.info(f"更新配置: {list(updates.keys())}")

        # 如果同时更新了 provider 和 model，将模型添加到历史
        provider = updates.get('provider')
        model = updates.get('model')
        if provider and model:
            # 将显示名称转换为 provider_id
            provider_id = provider_manager.get_provider_id(provider)
            settings.add_model_to_history(provider_id, model)
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


# 迁移时需要复制的子目录列表（不含 config，配置文件固定在默认路径）
_DATA_SUBDIRS = ["dataset", "plan", "debug_logs", "workflow", "external_files", "docs", "diary"]


def migrate_data_path(target_base_path: str, migrate_data: bool = True) -> MigrateDataPathResponse:
    """
    迁移数据到新路径，或仅切换路径不迁移数据

    配置文件（config/）固定在默认路径，不参与迁移。
    只迁移数据目录：dataset/、plan/、debug_logs/、workflow/、external_files/

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
        from lifeprism.storage import lw_db_manager, chat_history_db_manager
        logger.info("迁移数据：关闭数据库连接池...")
        try:
            lw_db_manager._close_connection_pool()
            chat_history_db_manager._close_connection_pool()
        except Exception as e:
            logger.error(f"关闭连接池失败: {e}")
            return MigrateDataPathResponse(
                success=False,
                message=f"关闭数据库连接失败: {e}"
            )

        # 5. 复制数据
        try:
            new_path.mkdir(parents=True, exist_ok=True)
            for subdir in _DATA_SUBDIRS:
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
            for subdir in _DATA_SUBDIRS:
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
