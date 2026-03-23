"""
创建llm client的统一接口，支持litellmProvider + CustomProvider（OpenAI SDK），
通过providers.yaml 中 is_direct 进行路由
True -> CustomProvider
False -> litellmProvider 
"""
from lifeprism.llm.providers.litellm_provider import LiteLLMProvider
from lifeprism.llm.providers.custom_provider import CustomProvider


