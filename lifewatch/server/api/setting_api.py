"""
Settings API - 配置管理接口

提供配置的读取和修改功能
"""
from fastapi import APIRouter, HTTPException

from lifewatch.server.schemas.setting_schemas import (
    SettingsResponse,
    UpdateSettingsRequest,
    UpdateApiKeyRequest,
    UpdateApiKeyResponse,
)
from lifewatch.server.services.setting_service import setting_service

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
    """
    settings_data = setting_service.update_settings(request)
    return SettingsResponse(settings=settings_data, message="配置已更新")


@router.put("/api-key", response_model=UpdateApiKeyResponse)
async def update_api_key(request: UpdateApiKeyRequest):
    """
    更新 API Key
    
    API Key 会安全存储到系统密钥管理器 (Keyring)，不保存在配置文件中。
    """
    try:
        setting_service.update_api_key(request.api_key)
        return UpdateApiKeyResponse(success=True, message="API Key 已安全保存")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存 API Key 失败: {str(e)}")


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
    from lifewatch.llm.llm_classify.function.test_connect import test_connect
    
    try:
        result = await test_connect()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"连接测试失败: {str(e)}")
