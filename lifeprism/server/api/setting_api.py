"""
Settings API - 配置管理接口

提供配置的读取和修改功能
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from lifeprism.server.schemas.setting_schemas import (
    SettingsResponse,
    UpdateSettingsRequest,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
    ProviderListResponse,
    ProviderInfo,
    ValidatePathRequest,
    ValidatePathResponse,
    MigrateDataPathRequest,
    MigrateDataPathResponse,
    TestVlmResponse,
    QRCodeResponse,
    QRCodeStatusResponse,
)
from lifeprism.server.services import setting_service
from lifeprism.config.provider_manager import provider_manager
from lifeprism.utils.exceptions import LWBaseError
from lifeprism.utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings - 配置管理"])


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """
    获取当前配置
    
    API Key 会以脱敏形式返回 (如: sk-ab...xy)
    """
    settings_data = setting_service.get_settings()
    return SettingsResponse(settings=settings_data)


@router.patch("", response_model=SettingsResponse)
async def update_settings(request: UpdateSettingsRequest):
    """
    更新配置 (部分更新)

    只需要传入需要修改的字段，未传入的字段保持不变。

    **注意**: 此接口不支持更新 API Key，请使用 PUT /settings/api-key

    **截图监控校验**:
    当 screenshot_monitor=true 时，后端会检查 is_vlm[provider_id/model] 是否为 true。
    如果不是，返回 require_vlm_test=true，前端需要调用 POST /settings/test-vlm 进行测试。
    """
    try:
        settings_data = setting_service.update_settings(request)
        return SettingsResponse(settings=settings_data, message="配置已更新")
    except ValueError as e:
        # is_vlm 校验失败，需要前端先调用 test-vlm
        settings_data = setting_service.get_settings()
        return SettingsResponse(
            settings=settings_data,
            message=str(e),
            require_vlm_test=True
        )


@router.put("/api-key", response_model=UpdateApiKeyResponse)
async def update_api_key(request: UpdateApiKeyRequest):
    """
    更新 API Key

    API Key 会安全存储到系统密钥管理器 (Keyring)，不保存在配置文件中。

    Args:
        request.api_key: 新的 API Key
        request.provider_id: 服务商 ID（可选），如 aliyun, openai 等
    """
    try:
        setting_service.update_api_key(request.api_key, request.provider_id)
        provider_msg = f" ({request.provider_id})" if request.provider_id else ""
        return UpdateApiKeyResponse(success=True, message=f"API Key{provider_msg} 已安全保存")
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("保存 API Key 失败: provider_id=%s, error=%s", request.provider_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/api-key/status")
async def check_api_key_status():
    """
    检查 API Key 配置状态
    
    返回 API Key 是否已配置，不返回实际的 Key 值。
    """
    is_configured = setting_service.validate_api_key()
    return {
        "configured": is_configured,
        "message": "API Key 已配置" if is_configured else "API Key 未配置"
    }


@router.post("/test-connection")
async def test_llm_connection():
    """
    测试 LLM 连接

    发送一个简单的测试请求到 LLM，验证 API Key 和模型配置是否正确。

    Returns:
        - success: bool, 是否连接成功
        - message: str, 结果信息
        - model_response: str, 模型的回复内容（成功时）
    """
    from lifeprism.llm.function.test_connect import test_connect

    try:
        result = await test_connect()
        return result
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("LLM 连接测试失败: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post("/test-vlm", response_model=TestVlmResponse, summary="测试 VLM 图像理解能力")
async def test_vlm_capability():
    """
    测试当前模型的图片理解能力

    流程:
    1. 先调用 test_connect() 验证 LLM 连接
    2. 连接失败 → 返回错误
    3. 连接成功 → 调用 test_vlm() 测试图像理解
    4. 根据测试结果更新 is_vlm 缓存

    Returns:
        TestVlmResponse: 测试结果
    """
    try:
        result = await setting_service.test_vlm_capability()
        return TestVlmResponse(**result)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("VLM 测试失败: error=%s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/providers", response_model=ProviderListResponse, summary="获取所有支持的服务商列表")
async def get_providers():
    """
    获取所有支持的 LLM 服务商列表

    返回每个服务商的 ID、显示名称、默认模型和 API Base
    """
    providers_data = provider_manager.get_all_providers(allowed_only=True)
    providers = [ProviderInfo(**p) for p in providers_data]
    return ProviderListResponse(providers=providers)


@router.delete("/model-history", summary="删除模型历史记录")
async def delete_model_history(
    provider_id: str = Query(..., description="服务商 ID，如 aliyun, volcengine 等"),
    model: str = Query(..., description="要删除的模型名称/ID")
):
    """
    从指定服务商的历史记录中删除模型

    Args:
        provider_id: 服务商 ID
        model: 模型名称/ID

    Returns:
        删除结果
    """
    success = setting_service.remove_model_from_history(provider_id, model)
    if success:
        return {"success": True, "message": f"已删除模型 {model}"}
    else:
        return {"success": False, "message": "模型不存在于历史记录中"}


@router.post("/validate-path", response_model=ValidatePathResponse, summary="验证路径有效性")
async def validate_path(request: ValidatePathRequest):
    """
    验证数据路径是否有效

    检查路径是否存在、是否可写、是否与安装路径冲突等

    Args:
        request.path: 要验证的路径
        request.path_type: 路径类型 (lifeprism_data | aw_db)
    """
    return setting_service.validate_data_path(request.path, request.path_type)


@router.post("/migrate-data-path", response_model=MigrateDataPathResponse, summary="迁移数据路径")
async def migrate_data_path(request: MigrateDataPathRequest):
    """
    迁移数据到新路径

    将当前 lifeprismData 目录下的所有数据复制到新路径。
    新路径会自动追加 lifeprismData 子文件夹。
    迁移成功后需要重启程序。

    注意：开发模式下此接口不可用。
    """
    result = setting_service.migrate_data_path(request.target_base_path, request.migrate_data)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)
    return result


@router.get("/qrcode", response_model=QRCodeResponse, summary="获取通道 QR 码")
async def get_qrcode(channel: str = Query(..., description="通道类型，如 wechat")):
    """
    获取指定通道的 QR 码

    Args:
        channel: 通道类型（当前仅支持 wechat）

    Returns:
        QR 码字符串和 ID
    """
    try:
        result = await setting_service.get_qrcode(channel)
        return QRCodeResponse(**result)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("获取 QR 码失败: channel=%s, error=%s", channel, e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.get("/qrcode/status", response_model=QRCodeStatusResponse, summary="查询 QR 码状态")
async def get_qrcode_status(
    channel: str = Query(..., description="通道类型"),
    qrcode_id: str = Query(..., description="QR 码 ID")
):
    """
    查询 QR 码扫描状态

    Args:
        channel: 通道类型（wechat）
        qrcode_id: QR 码 ID

    Returns:
        扫描状态和消息
    """
    try:
        result = await setting_service.get_qrcode_status(channel, qrcode_id)
        return QRCodeStatusResponse(**result)
    except LWBaseError:
        raise
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("查询 QR 码状态失败: channel=%s, qrcode_id=%s, error=%s", channel, qrcode_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")
