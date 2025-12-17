from openai import OpenAI
import os
import time
from lifewatch.config import SELECT_MODEL,MODEL_KEY
class LLMClient:
    def __init__(self,api_key,base_url):
        self.client = OpenAI(
            # 如果没有配置环境变量，请用阿里云百炼API Key替换：api_key="sk-xxx"
            api_key=api_key,
            base_url=base_url,
        )
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.api_call_count = 0
        
    def sent_message(self,messages,model="qwen-plus",enable_thinking=True,enable_search=True):
        self.api_call_count += 1
        extra_body = {"enable_thinking": enable_thinking,"enable_search":enable_search}
        
        start_time = time.time()
        completion = self.client.chat.completions.create(
            model=model,  # 您可以按需更换为其它深度思考模型
            messages=messages,
            extra_body=extra_body,
            stream=True
        )
        
        return completion, start_time
    
    def sent_message_no_stream(self,messages,model="qwen-plus",enable_thinking=False,enable_search=True):
        """非流式调用，获取完整token统计"""
        self.api_call_count += 1
        extra_body = {"enable_thinking": enable_thinking,"enable_search":enable_search}
        
        start_time = time.time()
        response = self.client.chat.completions.create(
            model=model,  # 您可以按需更换为其它深度思考模型
            messages=messages,
            extra_body=extra_body,
            stream=False  # 非流式
        )
        
        # 直接从response获取usage统计
        if hasattr(response, 'usage') and response.usage:
            usage = response.usage
            self.total_tokens += usage.total_tokens
            self.total_prompt_tokens += usage.prompt_tokens
            self.total_completion_tokens += usage.completion_tokens
            
            # 尝试获取思考过程
            reasoning_content = None
            if (hasattr(response.choices[0].message, 'reasoning_content') and 
                response.choices[0].message.reasoning_content):
                reasoning_content = response.choices[0].message.reasoning_content
            
            result = {
                'content': response.choices[0].message.content,
                'prompt_tokens': usage.prompt_tokens,
                'completion_tokens': usage.completion_tokens,
                'total_tokens': usage.total_tokens,
                'start_time': start_time
            }
            
            # 如果有思考过程，添加到结果中
            if reasoning_content:
                result['reasoning_content'] = reasoning_content
            
            return result
        
        return None
    
    def estimate_tokens_from_text(self, text):
        """改进的token估算（用于流式响应）"""
        if not text:
            return 0
        
        # 分离中英文字符
        chinese_chars = 0
        other_chars = 0
        
        for char in text:
            if '\u4e00' <= char <= '\u9fff':  # 中文字符范围
                chinese_chars += 1
            else:
                other_chars += 1
        
        # 中文：1个字符约1.6个token（基于实际测试调整）
        chinese_tokens = int(chinese_chars * 1.6)
        
        # 英文和其他字符：约4个字符=1个token
        other_tokens = max(1, other_chars // 4)
        
        return chinese_tokens + other_tokens
    
    def estimate_prompt_tokens(self, messages):
        """估算prompt的token数量"""
        total_text = ""
        for msg in messages:
            if isinstance(msg, dict) and 'content' in msg:
                total_text += msg['content']
        
        # 加上消息格式的开销（role标签等），约增加20%
        base_tokens = self.estimate_tokens_from_text(total_text)
        return int(base_tokens * 1.2)
    

    
    def print_result_non_stream(self, result, show_usage=True):
        """打印非流式调用的结果和统计信息"""
        if not result:
            print("❌ API调用失败，无法获取结果")
            return
        
        # 检查是否包含思考过程
        content = result.get('content', '')
        reasoning_content = result.get('reasoning_content', '')
        
        if reasoning_content:
            # 如果有思考过程，先打印思考过程
            print("\n" + "=" * 20 + "思考过程" + "=" * 20)
            print(reasoning_content)
        
        # 打印AI最终回复内容
        print("\n" + "=" * 20 + ("完整回复" if reasoning_content else "AI回复") + "=" * 20)
        print(content)
        
        end_time = time.time()
        
        if show_usage:
            # 打印本次调用统计
            print(f"\n{'='*20} API调用统计 {'='*20}")
            print(f"本次调用 - 输入tokens: {result['prompt_tokens']:,}")
            print(f"本次调用 - 输出tokens: {result['completion_tokens']:,}")
            print(f"本次调用 - 总tokens: {result['total_tokens']:,}")
            
            if 'start_time' in result:
                print(f"响应时间: {end_time - result['start_time']:.2f}秒")
            
            # 打印累计统计
            print(f"\n{'='*20} 累计统计 {'='*20}")
            stats = self.get_total_stats()
            print(f"API调用次数: {stats['api_call_count']}")
            print(f"累计输入tokens: {stats['total_prompt_tokens']:,}")
            print(f"累计输出tokens: {stats['total_completion_tokens']:,}")
            print(f"累计总tokens: {stats['total_tokens']:,}")
    
    def print_result(self, completion, start_time=None, show_usage=True, messages=None):
        """打印流式调用的结果和统计信息
        
        Args:
            completion: 流式响应对象
            start_time: 开始时间
            show_usage: 是否显示token统计
            messages: 原始消息列表，用于估算prompt tokens
        """
        is_answering = False  # 是否进入回复阶段
        print("\n" + "=" * 20 + "思考过程" + "=" * 20)
        
        # 收集所有chunks以获取完整的content和reasoning_content
        full_content = ""
        reasoning_content = ""
        
        for chunk in completion:
            # 正确的流式响应处理方式
            try:
                if hasattr(chunk, 'choices') and chunk.choices:
                    delta = chunk.choices[0].delta
                    if delta:
                        # 处理reasoning_content
                        if hasattr(delta, "reasoning_content") and delta.reasoning_content is not None:
                            reasoning_content += delta.reasoning_content
                            if not is_answering:
                                print(delta.reasoning_content, end="", flush=True)
                        # 处理content
                        if hasattr(delta, "content") and delta.content:
                            if not is_answering:
                                print("\n" + "=" * 20 + "完整回复" + "=" * 20)
                                is_answering = True
                            full_content += delta.content
                            print(delta.content, end="", flush=True)
                # 兼容其他流式响应格式
                elif hasattr(chunk, 'content') and chunk.content:
                    if not is_answering:
                        print("\n" + "=" * 20 + "完整回复" + "=" * 20)
                        is_answering = True
                    full_content += chunk.content
                    print(chunk.content, end="", flush=True)
            except (AttributeError, IndexError) as e:
                print(f"\n警告：无法处理流式响应块: {e}")
                continue
        
        end_time = time.time()
        
        if show_usage:
            # 使用已收集的内容估算tokens
            completion_tokens = self.estimate_tokens_from_text(full_content + reasoning_content)
            prompt_tokens = self.estimate_prompt_tokens(messages) if messages else 0
            total_tokens = prompt_tokens + completion_tokens
            
            # 更新累计统计
            self.total_prompt_tokens += prompt_tokens
            self.total_completion_tokens += completion_tokens
            self.total_tokens += total_tokens
            
            # 打印本次调用统计
            print(f"\n{'='*20} API调用统计 {'='*20}")
            if messages:
                print(f"本次调用 - 输入tokens: {prompt_tokens:,} (估算)")
            else:
                print(f"本次调用 - 输入tokens: 未提供消息")
            print(f"本次调用 - 输出tokens: {completion_tokens:,} (估算)")
            print(f"本次调用 - 总tokens: {total_tokens:,} (估算)")
            print("注：流式响应中的估算值，实际值可能有±20%的误差")
            
            if start_time:
                print(f"响应时间: {end_time - start_time:.2f}秒")
            
            # 打印累计统计
            print(f"\n{'='*20} 累计统计 {'='*20}")
            stats = self.get_total_stats()
            print(f"API调用次数: {stats['api_call_count']}")
            print(f"累计输入tokens: {stats['total_prompt_tokens']:,}")
            print(f"累计输出tokens: {stats['total_completion_tokens']:,}")
            print(f"累计总tokens: {stats['total_tokens']:,}")
    
    def get_total_stats(self):
        """获取累计统计信息"""
        return {
            'api_call_count': self.api_call_count,
            'total_tokens': self.total_tokens,
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens
        }
    
    def reset_stats(self):
        """重置统计信息"""
        self.total_tokens = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.api_call_count = 0

if __name__ == "__main__":
    llm_client = LLMClient(api_key=MODEL_KEY[SELECT_MODEL]["api_key"],base_url=MODEL_KEY[SELECT_MODEL]["base_url"])
    
    # print("="*60)
    # print("测试1: 流式响应（带token估算）")
    # print("="*60)
    # messages = [{"role": "user", "content": "你是谁"}]
    # completion, start_time = llm_client.sent_message(messages)
    # llm_client.print_result(completion, start_time, messages=messages)
    
    print("\n" + "="*60)
    print("测试2: 非流式响应（获取真实token统计）")
    print("="*60)
    messages2 = [{"role": "user", "content": "现在沈阳和平区的温度是多少"}]
    result = llm_client.sent_message_no_stream(messages2)
    llm_client.print_result_non_stream(result)