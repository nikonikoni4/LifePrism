from langchain_community.chat_models import ChatTongyi
import langchain_community.llms.tongyi as llms_tongyi_module
import langchain_community.chat_models.tongyi as chat_tongyi_module
import logging
from lifeprism.config import settings
api_key = settings.api_key
logger = logging.getLogger(__name__)

# Monkey patch check_response 来修复 langchain-community 的 bug
# 原始函数在抛出 HTTPError 时传入了 DashScope Response 对象,导致 KeyError: 'request'

def _patched_check_response(resp):
    """修复后的 check_response,在抛出异常前打印真实错误信息
    
    注意: resp 可能是两种类型:
    - 对象类型 (有 status_code 属性): 成功的响应或某些错误响应
    - dict 类型: 流式响应的 chunk 或某些 API 返回格式
    """
    # 根据 resp 类型获取 status_code
    if isinstance(resp, dict):
        status_code = resp.get('status_code', 200)  # dict 没有 status_code 时默认为成功
        get_value = lambda key, default='unknown': resp.get(key, default)
    else:
        status_code = getattr(resp, 'status_code', 200)
        get_value = lambda key, default='unknown': getattr(resp, key, resp.get(key, default) if hasattr(resp, 'get') else default)
    
    if status_code != 200:
        # 打印真实的 API 错误信息
        error_info = (
            f"\n{'='*60}\n"
            f"通义千问 API 调用失败!\n"
            f"  status_code: {get_value('status_code')}\n"
            f"  code: {get_value('code')}\n"
            f"  message: {get_value('message')}\n"
            f"{'='*60}\n"
        )
        logger.error(error_info)
        print(error_info)  # 确保在终端显示
        
        # 抛出一个自定义异常,避免 HTTPError 的 bug
        raise RuntimeError(
            f"通义千问 API 错误: status_code={get_value('status_code')}, "
            f"code={get_value('code')}, message={get_value('message')}"
        )
    return resp

# 应用 monkey patch 到两个模块
llms_tongyi_module.check_response = _patched_check_response
chat_tongyi_module.check_response = _patched_check_response

def create_ChatTongyiModel(
                            temperature=0.2,
                            enable_search=True,
                            enable_thinking=False,
                            enable_streaming = False):
    return ChatTongyi(
        model=settings.model,  # 指定使用 qwen-plus 模型，也可以改为 'qwen-max' 或 'qwen-turbo'
        temperature=temperature,
        dashscope_api_key=settings.api_key,
        streaming=enable_streaming,
        model_kwargs={
            "enable_search": enable_search,
            "enable_thinking": enable_thinking
        }
        # streaming=True # 如果需要流式输出，可以开启此选项
    )
if __name__ == "__main__":
    model = create_ChatTongyiModel()
    message = [
        {"role": "system", "content": "你是一个翻译专家"},
        {"role": "user", "content": "today is a good day"}
    ]
    result = model.invoke(message)
    print(result)
