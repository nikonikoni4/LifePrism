from email.policy import default
from zoneinfo import available_timezones
from lifeprism.llm.providers import litellm_provider
from lifeprism.llm.providers.litellm_provider import LiteLLMProvider
from lifeprism.llm.providers.base import LLMResponse
from lifeprism.config import provider_manager
from lifeprism.llm.providers.registry import find_by_name
import asyncio
# allowed_providers:
#   - custom
#   - volcengine
#   - dashscope
#   - deepseek
#   - zhipu
#   - moonshot
#   - minimax
#   - openai

## 通过测试的provider
tested_providers = ["volcengine","dashscope","minimax","deepseek","zhipu","moonshot"]
tested_providers = []
## 测试provider
async def test_providers():
    ## 测试api_key是否存在
    available_providers = []
    for provider in provider_manager._allowed_providers:

        api_key = provider_manager.get_api_key(provider)
        if api_key:
            print(f"{provider}'s api is {api_key}")
            available_providers.append(provider)
    # else:
    #     print(f"{provider}'s api is not exist")

    messages = [{"role":"user","content":"你是谁"}]

    for provider in available_providers:
        if provider not in tested_providers:
            api_key = provider_manager.get_api_key(provider)
            spec = find_by_name(provider)
            api_base = spec.default_api_base
            default_model = spec.default_model
            client = LiteLLMProvider(api_base=api_base,api_key=api_key,default_model=default_model, provider_name = provider)
            response:LLMResponse=  await client.chat(messages=messages)
            print(response)
    
if __name__ == "__main__":
    asyncio.run(test_providers())