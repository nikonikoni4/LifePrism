"""
完整的LLM分类流程测试示例

这个示例演示如何使用 classify_with_web_search 函数进行完整的两步分类流程
"""

import pandas as pd
from lifewatch.llm.ollama_client import OllamaClient
from lifewatch.llm.llm_classify import classify_with_web_search
from lifewatch import config

# 1. 创建测试数据
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
        None,  # Chrome 是常见应用，无需描述也能分类
        '微信是一款即时通讯软件',  # WeChat 有描述
        None,  # Doubao 可能需要网络搜索
        None,  # UnknownApp 可能需要网络搜索
        None   # PyCharm 是常见应用
    ]
}

df = pd.DataFrame(test_data)

# 2. 初始化 Ollama 客户端
client = OllamaClient(config.OLLAMA_BASE_URL, "qwen3:8B")

# 3. 定义分类选项
category = "工作/学习,娱乐,其他"
sub_category = "写笔记,编程,学习AI相关内容,查资料,聊天,其他"

# 4. 执行完整的分类流程
print("开始执行完整的分类流程...")
print("=" * 80)
print("\n原始数据:")
print(df.to_string())
print("\n" + "=" * 80)

result_df = classify_with_web_search(
    df=df,
    client=client,
    category=category,
    sub_category=sub_category,
    crawler_select="BaiDuBrowerCrawler",  # 或者 "DDGSAPICrawler"
    max_chars=2000,
    max_items=15
)

# 5. 查看分类结果
print("\n" + "=" * 80)
print("分类结果:")
print(result_df[['app', 'title', 'category', 'sub_category']].to_string())
print("=" * 80)

# 6. 保存结果（可选）
# result_df.to_csv('classification_results.csv', index=False, encoding='utf-8-sig')
# print("\n结果已保存到 classification_results.csv")
