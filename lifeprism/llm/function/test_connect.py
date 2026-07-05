from lifeprism.llm.providers import create_llm_client
from lifeprism.config.settings_manager import settings
import logging
import json
import re

logger = logging.getLogger(__name__)


async def test_connect() -> dict:
    """
    测试 LLM 连接是否正常

    使用用户选择的服务商和模型发送测试请求，验证 API Key 和模型配置是否正确。

    Returns:
        dict: 测试结果
            - success: bool, 是否连接成功
            - message: str, 结果信息
            - model_response: str, 模型的回复内容（成功时）
            - provider: str, 使用的服务商
            - model: str, 使用的模型
    """
    try:
        # 使用用户配置的服务商和模型创建 LLM
        llm = create_llm_client()
        
        # 发送简单的测试请求
        message = [
            {
                "role": "user",
                "content": [{"type": "text", "text": "请回复'连接成功'这四个字"}],
            }
        ]
        # 使用异步调用 LLM
        output = await llm.chat(messages=message)
        
        # 获取回复内容
        response_content = output.content if hasattr(output, 'content') else str(output)

        # 严格成功判定：2个失败条件 + 1个成功条件，默认失败

        # 失败条件1: 包含错误信息
        if "error" in response_content.lower():
            error_message = _parse_error_message(response_content)
            logger.error("LLM 连接测试失败: 模型返回错误 (provider=%s, model=%s): %s", settings.provider, settings.model, response_content[:200])
            return {
                "success": False,
                "message": f"连接失败: {error_message}",
                "model_response": response_content,
                "provider": settings.provider,
                "model": settings.model
            }

        # 成功条件: 包含"连接成功"
        if "连接成功" in response_content:
            logger.info("LLM 连接测试成功 (provider=%s, model=%s): %s", settings.provider, settings.model, response_content)
            return {
                "success": True,
                "message": "LLM 连接测试成功",
                "model_response": response_content,
                "provider": settings.provider,
                "model": settings.model
            }

        # 失败条件2 (默认): 未返回预期内容
        logger.error("LLM 连接测试失败: 模型未返回预期内容 (provider=%s, model=%s): %s", settings.provider, settings.model, response_content[:100])
        return {
            "success": False,
            "message": "连接失败: 模型未返回预期内容",
            "model_response": response_content,
            "provider": settings.provider,
            "model": settings.model
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error("LLM 连接测试失败 (provider=%s, model=%s): %s", settings.provider, settings.model, error_msg)

        return {
            "success": False,
            "message": f"连接失败: {error_msg}",
            "model_response": None,
            "provider": settings.provider,
            "model": settings.model
        }


def _parse_error_message(response_content: str) -> str:
    """
    解析错误响应，提取友好的错误提示

    Args:
        response_content: 原始响应内容

    Returns:
        str: 友好的错误提示信息
    """
    try:
        # 尝试提取 JSON 部分（可能包含 "Error: {...}" 格式）
        json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
        if json_match:
            error_data = json.loads(json_match.group())

            # 提取 error 字段
            if "error" in error_data:
                error_info = error_data["error"]
                code = error_info.get("code", "")
                message = error_info.get("message", "")

                # 根据错误码和消息返回友好提示
                if code == "401" or "Invalid API Key" in message:
                    return "API Key 无效，请检查配置中的 API Key 是否正确；检查API url 是否正确"
                elif code == "400" and "Not supported model" in message:
                    return f"模型不支持，请检查模型名称是否正确（当前模型: {settings.model}）"
                elif message:
                    return f"模型返回错误: {message}"

    except (json.JSONDecodeError, KeyError, AttributeError):
        pass

    # 如果解析失败，返回截断的原始内容
    return f"模型返回错误: {response_content[:200]}"


if __name__ == "__main__":
    import asyncio
    # ---------- 测试 test_connect ----------
    print("\n[2] 测试 test_connect（LLM 连接）")
    print("  正在测试 LLM 连接...")
    result = asyncio.run(test_connect())

    print(f"  success: {result['success']}")
    print(f"  message: {result['message']}")
    print(f"  provider: {result['provider']}")
    print(f"  model: {result['model']}")
    if result["model_response"]:
        print(f"  model_response: {result['model_response'][:200]}")

    if result["success"]:
        print("\n  LLM 连接测试通过 ✅")
    else:
        print("\n  LLM 连接测试失败 ❌")

    print("\n" + "=" * 60)
    print("测试完成")
