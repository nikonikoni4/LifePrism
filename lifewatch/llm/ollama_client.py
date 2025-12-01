import requests

class OllamaClient:
    def __init__(self, base_url,model = "qwen3:0.6B"):
        """
        初始化 Ollama 客户端
        
        Args:
            base_url (str): Ollama 服务的基础 URL
        """
        self.base_url = base_url
        self.model_list = self.get_available_models()
        self.model = None
        if not self.select_model(model) and self.model_list:
            self.model = self.model_list[0]
            print(f"使用模型: {self.model}")
    
    def get_model(self):
        """获取当前使用的模型"""
        return self.model
    
    def select_model(self, model):
        """
        选择模型
        
        Args:
            model (str): 模型名称
        """
        if model.lower() not in [m.lower() for m in self.model_list]:
            print(f"模型 {model} 不可用")
            return False
        self.model = model
        print(f"使用模型: {self.model}")
        return True
    
    def get_available_models(self):
        """
        获取可用的模型列表
        
        Returns:
            list: 可用的模型名称列表
        """
        url = f"{self.base_url}/api/tags"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            # 从返回的 JSON 中提取模型名称
            models = [model['name'] for model in data.get('models', [])]
            return models
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return []
        

    def generate(self, prompt, options=None, temperature=0.1, return_raw=False):
        """
        生成文本响应
        
        Args:
            prompt (str): 输入提示词
            options (dict, optional): 生成选项
            temperature (float): 温度系数，控制输出的随机性，值越低结果越稳定（默认0.1）
            return_raw (bool): 是否返回原始响应，默认 False 返回字符串内容
            
        Returns:
            str or dict: 默认返回生成的文本内容(str)，return_raw=True 时返回完整响应(dict)
        """
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if options:
            # 如果options中也包含temperature，则options中的值会覆盖默认值
            payload["options"].update(options)
            
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # 根据 return_raw 参数决定返回格式
            if return_raw:
                return result
            else:
                return result.get('response', '')
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return None if return_raw else ""
    
    def chat(self, messages, options=None, temperature=0.2, return_raw=False):
        """
        对话模式
        
        Args:
            messages (list): 消息列表
            options (dict, optional): 生成选项
            temperature (float): 温度系数，控制输出的随机性，值越低结果越稳定（默认0.2）
            return_raw (bool): 是否返回原始响应，默认 False 返回字符串内容
            
        Returns:
            str or dict: 默认返回消息内容(str)，return_raw=True 时返回完整响应(dict)
        """
        url = f"{self.base_url}/api/chat"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        if options:
            # 如果options中也包含temperature，则options中的值会覆盖默认值
            payload["options"].update(options)
            
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            # 根据 return_raw 参数决定返回格式
            if return_raw:
                return result
            else:
                return result.get('message', {}).get('content', '')
        except requests.exceptions.RequestException as e:
            print(f"请求错误: {e}")
            return None if return_raw else ""

if __name__ == "__main__":
    client = OllamaClient("http://localhost:11434")
    print(f"可用模型: {client.get_available_models()}")
    client.select_model("qwen3:0.6B")
    print(f"当前模型: {client.get_model()}")
    
    # 测试 generate 方法 - 默认返回字符串
    print("\n=== 测试 generate (返回字符串) ===")
    response = client.generate("Hello, how are you?")
    print(response)
    
    # 测试 chat 方法 - 默认返回字符串
    print("\n=== 测试 chat (返回字符串) ===")
    response = client.chat([{"role": "user", "content": "Hello, how are you?"}])
    print(response)
    
    # 测试返回原始数据
    print("\n=== 测试 generate (返回原始数据) ===")
    response = client.generate("Hello!", return_raw=True)
    print(f"原始响应类型: {type(response)}")
    print(f"响应内容: {response.get('response', '')[:50]}...")