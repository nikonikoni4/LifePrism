"""
LLM分类器使用示例（重构后）

展示如何使用新的分类器架构：
- Ollama本地：两步流程（判断 → 搜索 → 分类）
- 云端API：一步流程（模型自带搜索）
"""

import pandas as pd
from lifewatch import config

# ==================== 示例1: Ollama两步流程 ====================

def example_ollama_two_step():
    """使用Ollama本地模型进行两步分类（启用网络搜索）"""
    from lifewatch.llm.ollama_client import OllamaClient
    from lifewatch.llm.ollama_classifier import OllamaClassifier
    
    print("\n" + "=" * 80)
    print("示例1: Ollama两步分类流程（启用网络搜索）")
    print("=" * 80)
    
    # 创建测试数据
    test_data = {
        'app': ['Chrome', 'WeChat', 'Doubao', 'UnknownApp', 'PyCharm'],
        'title': [
            'Google - 搜索Python教程',
            None,
            None,
            '文档编辑器',
            'main.py - PyCharm'
        ],
        'is_multipurpose_app': [True, False, False, False, True],
        'app_description': [
            None,
            '微信是一款即时通讯软件',
            None,
            None,
            None
        ]
    }
    df = pd.DataFrame(test_data)
    
    # 初始化Ollama分类器
    client = OllamaClient(config.OLLAMA_BASE_URL, "qwen3:8B")
    classifier = OllamaClassifier(
        client=client,
        category="工作/学习,娱乐,其他",
        sub_category="写笔记,编程,学习AI相关内容,查资料,聊天,其他"
    )
    
    # 执行两步分类（启用网络搜索）
    result_df = classifier.classify(
        df=df,
        enable_web_search=True,  # 启用两步流程
        crawler_select="BaiDuBrowerCrawler"
    )
    
    # 查看结果
    print("\n分类结果:")
    print(result_df[['app', 'title', 'category', 'sub_category']].to_string())


# ==================== 示例2: Ollama一步流程 ====================

def example_ollama_one_step():
    """使用Ollama本地模型进行一步分类（不启用网络搜索）"""
    from lifewatch.llm.ollama_client import OllamaClient
    from lifewatch.llm.ollama_classifier import OllamaClassifier
    
    print("\n" + "=" * 80)
    print("示例2: Ollama一步分类流程（不启用网络搜索）")
    print("=" * 80)
    
    # 创建测试数据（信息充分的应用）
    test_data = {
        'app': ['Chrome', 'WeChat', 'PyCharm'],
        'title': [
            'GitHub - 浏览代码',
            '与朋友聊天',
            'main.py - PyCharm'
        ],
        'is_multipurpose_app': [True, False, True],
        'app_description': [
            None,
            '微信是一款即时通讯软件',
            'PyCharm是Python IDE'
        ]
    }
    df = pd.DataFrame(test_data)
    
    # 初始化Ollama分类器
    client = OllamaClient(config.OLLAMA_BASE_URL, "qwen3:8B")
    classifier = OllamaClassifier(
        client=client,
        category="工作/学习,娱乐,其他",
        sub_category="写笔记,编程,查资料,聊天,其他"
    )
    
    # 执行一步分类（不启用网络搜索）
    result_df = classifier.classify(
        df=df,
        enable_web_search=False  # 禁用网络搜索，直接分类
    )
    
    # 查看结果
    print("\n分类结果:")
    print(result_df[['app', 'title', 'category', 'sub_category']].to_string())


# ==================== 示例3: 通义千问一步流程 ====================

def example_qwen_classifier():
    """使用通义千问API进行一步分类"""
    from lifewatch.llm.cloud_classifier import QwenAPIClassifier
    
    print("\n" + "=" * 80)
    print("示例3: 通义千问一步分类流程")
    print("=" * 80)
    
    # 创建测试数据
    test_data = {
        'app': ['钉钉', '抖音', 'WPS', 'Doubao'],
        'title': [
            '团队会议',
            None,
            '年度报告.docx',
            None
        ],
        'is_multipurpose_app': [False, False, True, False],
        'app_description': [
            '钉钉是企业协作平台',
            '抖音是短视频平台',
            None,
            None
        ]
    }
    df = pd.DataFrame(test_data)
    
    # 初始化通义千问分类器
    classifier = QwenAPIClassifier(
        api_key=config.MODEL_KEY[config.SELECT_MODEL]["api_key"],
        base_url=config.MODEL_KEY[config.SELECT_MODEL]["base_url"],
        category="工作/学习,娱乐,其他",
        sub_category="写笔记,编程,视频娱乐,办公,学习AI相关内容,其他",
        model=config.SELECT_MODEL
    )
    
    # 执行一步分类
    result_df = classifier.classify(df=df)
    
    # 查看结果
    print("\n分类结果:")
    print(result_df[['app', 'title', 'category', 'sub_category']].to_string())
    
    # 打印累计token统计
    print("\n" + "=" * 60)
    print("累计Token消耗统计")
    print("=" * 60)
    stats = classifier.client.get_total_stats()
    print(f"API调用次数: {stats['api_call_count']}")
    print(f"累计输入tokens: {stats['total_prompt_tokens']:,}")
    print(f"累计输出tokens: {stats['total_completion_tokens']:,}")
    print(f"累计总tokens: {stats['total_tokens']:,}")
    print("=" * 60)


if __name__ == "__main__":
    # 运行示例1: Ollama两步流程（启用网络搜索）
    # example_ollama_two_step()
    
    # 运行示例2: Ollama一步流程（不启用网络搜索）
    # example_ollama_one_step()
    
    # 运行示例3: 通义千问一步流程
    example_qwen_classifier()