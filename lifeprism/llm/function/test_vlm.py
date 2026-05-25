import asyncio
import base64
from pathlib import Path

from lifeprism.llm.providers import create_llm_client
from lifeprism.config.settings_manager import settings
import logging

logger = logging.getLogger(__name__)


def _load_image_as_base64(image_path: str) -> str:
    """Load image file and return base64 encoded string with data URL prefix."""
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")

    mime_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")

    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


async def test_vlm() -> dict:
    """
    测试 LLM 是否具备图像理解能力 (VLM = Vision Language Model)

    使用用户选择的服务商和模型发送一张测试图片，验证模型是否能正确识别图片内容。

    Args:
        image_path: 图片路径，默认为 assets/test-vlm.png

    Returns:
        dict: 测试结果
            - success: bool, 是否识别成功
            - message: str, 结果信息
            - model_response: str, 模型的回复内容（成功时）
            - provider: str, 使用的服务商
            - model: str, 使用的模型
            - image_path: str, 测试图片路径
    """
    # 默认测试图片路径

    default_image = settings.lifeprism_data_path / "assets" / "test-vlm.png"
    image_path = str(default_image)

    try:
        # 将图片转为 base64 data URL
        image_data_url = _load_image_as_base64(image_path)

        # 构建多模态消息：文字提问 + 图片
        messages = [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "请描述这张图片的内容，用一句话即可。如果没有收到任何图片，请直接回复：未收到图片"
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": image_data_url
                    }
                }
            ]
        }]

        # 使用用户配置的 LLM 创建 client
        llm = create_llm_client()

        # 发送多模态请求
        output = await llm.chat(messages=messages)
        print(output.usage)
        # 获取回复内容
        response_content = output.content if hasattr(output, 'content') else str(output)

        # 严格成功判定：3个失败条件 + 1个成功条件，默认失败

        # 失败条件1: 包含错误信息
        if "error" in response_content.lower():
            logger.error(f"VLM 测试失败: 模型返回错误 (provider={settings.provider}, model={settings.model}): {response_content[:200]}")
            return {
                "success": False,
                "message": f"VLM 测试失败: 模型返回错误",
                "model_response": response_content,
                "provider": settings.provider,
                "model": settings.model,
                "image_path": image_path
            }

        # 失败条件2: 未收到图片
        if "未收到图片" in response_content:
            logger.error(f"VLM 测试失败: 模型未收到图片 (provider={settings.provider}, model={settings.model})")
            return {
                "success": False,
                "message": "VLM 测试失败: 模型未收到图片",
                "model_response": response_content,
                "provider": settings.provider,
                "model": settings.model,
                "image_path": image_path
            }

        # 成功条件: 识别出猫
        if "猫" in response_content or "cat" in response_content.lower():
            logger.info(
                f"VLM 测试成功 (provider={settings.provider}, model={settings.model}): "
                f"{response_content[:100] if response_content else 'None'}..."
            )
            return {
                "success": True,
                "message": "VLM 图像理解测试成功",
                "model_response": response_content,
                "provider": settings.provider,
                "model": settings.model,
                "image_path": image_path
            }

        # 失败条件3 (默认): 未识别出猫
        logger.error(f"VLM 测试失败: 模型未识别出猫 (provider={settings.provider}, model={settings.model}): {response_content[:100]}...")
        return {
            "success": False,
            "message": "VLM 测试失败",
            "model_response": response_content,
            "provider": settings.provider,
            "model": settings.model,
            "image_path": image_path
        }

    except FileNotFoundError as e:
        error_msg = str(e)
        logger.error(f"VLM 测试失败: 图片文件不存在 - {error_msg}")
        return {
            "success": False,
            "message": f"测试失败: 图片文件不存在 - {error_msg}",
            "model_response": None,
            "provider": settings.provider,
            "model": settings.model,
            "image_path": image_path
        }

    except Exception as e:
        error_msg = str(e)
        logger.error(
            f"VLM 测试失败 (provider={settings.provider}, model={settings.model}): "
            f"{error_msg}"
        )

        return {
            "success": False,
            "message": f"VLM 测试失败: {error_msg}",
            "model_response": None,
            "provider": settings.provider,
            "model": settings.model,
            "image_path": image_path
        }


if __name__ == "__main__":
    result = asyncio.run(test_vlm())
    print(f"Success: {result['success']}")
    print(f"Message: {result['message']}")
    if result["success"]:
        print(f"Model Response: {result['model_response']}")
    print(f"Provider: {result['provider']}, Model: {result['model']}")
