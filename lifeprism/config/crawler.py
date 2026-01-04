"""
爬虫配置模块
"""
# 百度百科首页URL
BAIDU_BAIKE_URL = 'https://baike.baidu.com/'

# 百度百科首页搜索框选择器
BAIDU_BAIKE_BOX_SELECTOR = 'searchInput'

# 有词条内容页面的词条描述文本选择器
LEMMA_DESCRIPTION_SELECTOR = 'lemmaDescText_gU5Fz'

# 无词条内容页面的第一个推荐词条容器选择器
FIRST_RECOMMEND_CONTAINER_SELECTOR = 'listWrap_Yn22D'

# 无词条内容页面的推荐词条条目选择器
RECOMMEND_ITEM_SELECTOR = 'container_OT5ZI'

# 无词条内容页面的推荐词条标题链接选择器
RECOMMEND_TITLE_LINK_SELECTOR = 'title_aWWAv'

# 百度搜素主页URL
BAIDU_SEARCH_URL = 'https://www.baidu.com/'
# 百度搜索主页搜索框选择器
BAIDU_SEARCH_BOX_SELECTOR = 'chat-input-container'
# 选择器重复次数
SELECTOR_TIME_OUT= 2

# 百度搜索引擎的AI总结
BAIDU_SEARCH_AI_CONCLUTION_SELECTOR = "marklang-paragraph"

# 百度搜索引擎结果总结
BAIDU_SEARCH_SUMMARY_SELECTOR = "summary-text_560AW"
                                        
# 百度搜索引擎结果标题选择器
BAIDU_SEARCH_RESULT_TITLE_SELECTOR = "_no-spacing_10ku5_31"

# 浏览器爬虫间隔时间
BROWER_CRAWLER_INTERVAL = 1

# 浏览器爬虫百度爬虫搜索类型 1：单个结果，不用llm总结 2：多个结果，用llm总结
BAIDU_SINGLE_RESULT = "single"
BAIDU_MULTI_RESULT = "multi"
BROWER_CRAWLER_BAIDU_SEARCH_TYPE = BAIDU_MULTI_RESULT