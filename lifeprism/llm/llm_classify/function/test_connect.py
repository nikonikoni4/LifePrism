from lifeprism.llm.llm_classify.utils import create_ChatTongyiModel
import logging

logger = logging.getLogger(__name__)


async def test_connect() -> dict:
    """
    测试 LLM 连接是否正常
    
    发送一个简单的测试请求到 LLM，验证 API Key 和模型配置是否正确。
    
    Returns:
        dict: 测试结果
            - success: bool, 是否连接成功
            - message: str, 结果信息
            - model_response: str, 模型的回复内容（成功时）
    """
    try:
        # 创建 LLM 模型
        llm = create_ChatTongyiModel(temperature=0.1)
        
        # 发送简单的测试请求
        test_prompt = "请回复'连接成功'这四个字。"
        
        # 使用异步调用 LLM
        output = await llm.ainvoke(input=test_prompt)
        
        # 获取回复内容
        response_content = output.content if hasattr(output, 'content') else str(output)
        
        logger.info(f"LLM 连接测试成功: {response_content}")
        
        return {
            "success": True,
            "message": "LLM 连接测试成功",
            "model_response": response_content
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"LLM 连接测试失败: {error_msg}")
        
        return {
            "success": False,
            "message": f"连接失败: {error_msg}",
            "model_response": None
        }
