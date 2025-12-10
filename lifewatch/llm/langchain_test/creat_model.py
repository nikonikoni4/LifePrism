from langchain.agents import create_agent
from langchain_community.chat_models import ChatTongyi

def create_ChatTongyiModel( model_name="qwen-flash",
                            temperature=0.7,
                            dashscope_api_key="sk-b6f3052f6c4f46a9a658bfc020d90c3f",
                            enable_search=True,
                            enable_thinking=False):
    return ChatTongyi(
        model=model_name,  # 指定使用 qwen-plus 模型，也可以改为 'qwen-max' 或 'qwen-turbo'
        temperature=temperature,
        dashscope_api_key=dashscope_api_key,
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
