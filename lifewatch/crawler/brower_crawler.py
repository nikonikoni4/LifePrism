from lifewatch.llm.ollama_client import OllamaClient
from DrissionPage import Chromium
from lifewatch import config 
from lifewatch.crawler.app_description_processor  import AppDescriptionProcessor
LOCAL_MAX_CHARS = 2000
class BaseBrowerCrawler:
    def __init__(self):
        self.browser = Chromium()
        self.tab = self.browser.latest_tab
    def get_target_content(self,selector):
        """
        获取页面中指定选择器的元素文本内容,返回第一个
        
        Args:
            selector: CSS选择器
        
        Returns:
            str: 获取到的文本内容，未找到则返回None
        """
        try:
            target_div = self.tab.ele(f"@class:{selector}", timeout=config.SELECTOR_TIME_OUT)
            if target_div:
                text_content = target_div.text
                return text_content
            else:
                print(f"未找到选择器 '{selector}' 对应的元素")
                return None
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    def get_target_contents(self,selector):
        """
        获取页面中指定选择器的元素文本内容,返回所有
        
        Args:
            selector: CSS选择器
        
        Returns:
            str: 获取到的文本内容，未找到则返回None
        """
        try:
            target_divs = self.tab.eles(f"@class:{selector}", timeout=config.SELECTOR_TIME_OUT)
            if target_divs:
                text_contents = ";".join([target_div.text for target_div in target_divs])
                return text_contents
            else:
                print(f"未找到选择器 '{selector}' 对应的元素")
                return None
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    def get_query(self,search_keyword):
        querys=[f"{search_keyword}是什么软件",search_keyword,f"{search_keyword}.exe是什么程序"]
        return querys
    def quit(self):
        self.browser.quit()

class BaiDuBrowerCrawler(BaseBrowerCrawler):
    def __init__(self):
        super().__init__()
        if config.BROWER_CRAWLER_BAIDU_SEARCH_TYPE == config.BAIDU_MULTI_RESULT:
            self.processor = AppDescriptionProcessor(OllamaClient(config.OLLAMA_BASE_URL, config.OLLAMA_MODEL))
    
    def jump_to_citiao(self,keyword):
        """
        在百度百科中搜索指定关键词的词条
        
        Args:
            keyword: 要搜索的关键词
        """
        self.tab.get(config.BAIDU_BAIKE_URL)
        search_input = self.tab.ele(f"@class:{config.BAIDU_BAIKE_BOX_SELECTOR}")
        if search_input:
            search_input.input(keyword)
            search_input.input("\n")
            return True
        else:
            print(f"未找到搜索框选择器 '{config.BAIDU_BAIKE_BOX_SELECTOR}'")
            return False
    def jump_to_baidu_engine(self,keyword):
        """
        在百度搜索引擎中搜索指定关键词
        
        Args:
            keyword: 要搜索的关键词
        """
        self.tab.get(config.BAIDU_SEARCH_URL)
        search_box = self.tab.ele(config.BAIDU_SEARCH_BOX_SELECTOR, timeout=2)
        if search_box:
            search_box.input(keyword)
            search_box.input("\n")
            return True
        else:
            print(f"未找到搜索框选择器 '{config.BAIDU_SEARCH_BOX_SELECTOR}'")
            return False
    def baidu_baike_search(self):
        """
        在百度百科中搜索指定关键词的词条
        
        Args:
            keyword: 要搜索的关键词
        """
        text_content = self.get_target_content(config.LEMMA_DESCRIPTION_SELECTOR)
        if text_content:
            print(f"成功获取百度百科词条文本内容: {text_content[:50]}{'...' if len(text_content) > 50 else ''}")
            return text_content
        else:
            return None
    def baidu_engine_search_by_text(self,keyword):
        """
        获取百度搜索引擎结果总结中包含指定关键词的文本内容
        
        Args:
            keyword: 要搜索的关键词
        
        Returns:
            str: 包含关键词的文本内容，未找到则返回None
        """
        try:
            target_em = self.tab.eles(f"tag:em@@text():{keyword}是")
            if target_em:
                # 过滤掉无意义的内容：关键词+短句、重复内容、过短文本、问句、问答内容
                filtered_texts = []
                seen_texts = set()
                for em in target_em:
                    text = em.text.strip()
                    # 排除短句、重复内容、无关键词的文本、问句、引导性内容
                    if (len(text) > 5 and  # 长度大于5字符
                        text not in seen_texts and  # 不重复
                        f"{keyword}" in text and  # 包含关键词
                        not (text.startswith(f"{keyword}是") and len(text) < 20) and  # 排除"关键词是..."短句
                        "是什么" not in text and  # 排除包含"是什么"的问句
                        "?" not in text and "？" not in text and  # 排除问句
                        not any(guide_word in text for guide_word in ["先打开", "首先", "然后", "接着", "第一步", "第二步"])):  # 排除引导性操作文本
                        seen_texts.add(text)
                        filtered_texts.append(text)
                
                text_content = ";".join(filtered_texts)
                print(f"成功获取文本内容: {text_content[:50]}{'...' if len(text_content) > 50 else ''}")
                return text_content
            else:
                print(f"未找到选择器 'tag:em@@text():{keyword}是' 对应的元素")
                return None
            
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    def baidu_engine_search_by_ai_conclution(self):
        try:
            text_content = self.get_target_content(config.BAIDU_SEARCH_AI_CONCLUTION_SELECTOR)
            if text_content:
                print(f"成功获取百度AI总结文本内容: {text_content[:50]}{'...' if len(text_content) > 50 else ''}")
                return text_content
            else:
                print(f"未找到选择器 '{config.BAIDU_SEARCH_AI_CONCLUTION_SELECTOR}' 对应的元素")
                return None
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    def baidu_engine_search_by_summary_seletor(self,keyword):
        """
        获取百度搜索引擎结果总结中包含指定关键词的文本内容,仅返回一个符合要求的结果
        
        Args:
            keyword: 要搜索的关键词
        
        Returns:
            str: 包含关键词的文本内容，未找到则返回None
        """
        keyword = keyword.lower()
        try:
            summary_contents = self.tab.eles(f"@class:{config.BAIDU_SEARCH_SUMMARY_SELECTOR}")
            for summary_content in summary_contents :
                summary_content = summary_content.text.strip().lower()
                if keyword in summary_content and "如何" not in summary_content and "什么" not in summary_content:
                    text_content = summary_content
                    print(f"成功获取文本内容: {text_content[:50]}{'...' if len(text_content) > 50 else ''}")
                    return text_content
            else:
                print(f"未找到包含关键词 '{keyword}' 的文本内容")
                return None
            
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    
    def baidu_engine_search_by_title_seletor(self):
        """
        获取百度搜索引擎结果标题中包含指定关键词的文本内容
        该方法是为了避免程序名称和软件名称有差别而直接选择百度词条的推荐
        作为最后的搜索手段
        
        Args:
            keyword: 要搜索的关键词
        
        Returns:
            str: 包含关键词的文本内容，未找到则返回None
        """
        try:
            title_contents = self.tab.eles(f"@class:{config.BAIDU_SEARCH_RESULT_TITLE_SELECTOR}")
            for title_content in title_contents:
                title_text  = title_content.text.strip().lower()
                # 获取与搜索最接近的百度百科词条
                if "百度百科" in title_text:
                    # 向上搜索是否包含跳转
                    a = title_content.parent("@tag()=a")
                    # 获取链接
                    href = a.attr("href")
                    # 跳转
                    self.tab.get(href)
                    # 搜索百度词条
                    return self.baidu_baike_search()
            else:
                print(f"未找到选择器 '@class:{config.BAIDU_SEARCH_RESULT_TITLE_SELECTOR}' 对应的元素")
                print(f"开始查找链接属性")
                title_content = self.tab.ele(f"tag:a@@text():百度百科")
                if title_content:
                    # 获取链接
                    href = title_content.attr("href")
                    # 跳转
                    self.tab.get(href)
                    # 搜索百度词条
                    return self.baidu_baike_search()
                else:
                    print(f"未找到选择器 'tag:a@@text():百度百科' 对应的元素")
                    return None
            
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    
    def baidu_search_return_single_text(self,keyword):
        """
        在百度搜索引擎中搜索指定关键词，返回单个文本内容
        搜索顺序：
        1. AI总结
        2. 搜索summary
        3. 标题百度百科标题跳转
        
        Args:
            keyword: 要搜索的关键词
        """
        content = None
        self.tab.wait(config.BROWER_CRAWLER_INTERVAL)
        
        # 1. 先尝试百度搜索引擎
        querys = self.get_query(keyword) # 获取搜索关键词的查询字符串
        for query in querys:
            if not content:
                self.tab.wait(config.BROWER_CRAWLER_INTERVAL) # 等待1秒，防止反爬虫
                
                if self.jump_to_baidu_engine(query):
                    self.tab.wait.ele_displayed(f"@class:{config.BAIDU_SEARCH_AI_CONCLUTION_SELECTOR}") # 等待AI总结元素出现
                    self.tab.wait(2)
                    print("1. 获取百度引擎的AI总结词条")
                    content = self.baidu_engine_search_by_ai_conclution() # 获取AI总结文本内容
            # if not content:
            #     # 放弃文本匹配
            #     # 如果AI总结不存在，尝试获取搜索结果总结
            #     print("2. 通过页面文本匹配搜索关键词")
            #     content = self.baidu_engine_search_by_text(keyword)
            if not content:
                print("2. 通过页面的总结选择器获取搜索关键词")
                content = self.baidu_engine_search_by_summary_seletor(keyword)
            if not content:
                print("3. 标题选择器获取搜索关键词")
                content = self.baidu_engine_search_by_title_seletor()
            if content:
                break
        
        # 2. 如果百度搜索引擎没有找到内容，最后尝试百度词条
        if not content:
            self.tab.wait(config.BROWER_CRAWLER_INTERVAL)
            if self.jump_to_citiao(keyword):
                print("4. 通过百度词条搜索关键词")
                self.tab.wait(config.BROWER_CRAWLER_INTERVAL)
                content = self.baidu_baike_search()
        
        return content
    

    def baidu_engine_search_by_summary_seletor_return_all(self,keyword):
        """
        获取百度搜索引擎结果总结中包含指定关键词的文本内容,返回所有符合要求的结果
        
        Args:
            keyword: 要搜索的关键词
        """
        try:
            summary_contents = self.tab.eles(f"@class:{config.BAIDU_SEARCH_SUMMARY_SELECTOR}")
            for summary_content in summary_contents :
                summary_content = summary_content.text.strip().lower()
                if keyword in summary_content and "如何" not in summary_content and "什么" not in summary_content:
                    text_content = summary_content
                    print(f"成功获取文本内容: {text_content[:50]}{'...' if len(text_content) > 50 else ''}")
                    return text_content
            else:
                print(f"未找到包含关键词 '{keyword}' 的文本内容")
                return None
            
        except Exception as e:
            print(f"获取元素文本内容时出错: {e}")
            return None
    def baidu_search_return_all_text(self, keyword):
        """
        在百度搜索引擎中搜索指定关键词，
        返回所有querys的搜索结果：
        1. AI总结
        2. 页面的summary
        
        Args:
            keyword: 要搜索的关键词
        
        Returns:
            str: 拼接后的搜索结果，未找到内容则返回None
        """
        content_parts = []  # 使用列表收集内容，提高字符串拼接效率
        self.tab.wait(config.BROWER_CRAWLER_INTERVAL)
        querys = self.get_query(keyword) # 获取搜索关键词的查询字符串
        
        for query in querys:
            try:
                if self.jump_to_baidu_engine(query):
                    self.tab.wait(config.BROWER_CRAWLER_INTERVAL) # 等待1秒，防止反爬虫
                    self.tab.wait.ele_displayed(f"@class:{config.BAIDU_SEARCH_AI_CONCLUTION_SELECTOR}") # 等待AI总结元素出现
                    
                    print("1. 获取百度引擎的AI总结词条")
                    temp = self.baidu_engine_search_by_ai_conclution() # 获取AI总结文本内容
                    if temp:
                        content_parts.append(temp)
                    
                    print("2. 网页summary")
                    temp = self.get_target_contents(config.BAIDU_SEARCH_SUMMARY_SELECTOR)
                    if temp:
                        content_parts.append(temp)
                    
                    # 检查是否超过最大字符数限制
                    current_content = ";".join(content_parts)
                    if len(current_content) > LOCAL_MAX_CHARS:
                        # 截断到最大字符数
                        content_parts = [current_content[:LOCAL_MAX_CHARS]]
                        break
            except Exception as e:
                print(f"搜索查询 '{query}' 时出错: {e}")
                continue

        # 返回拼接后的内容，如果没有内容则返回None
        return ";".join(content_parts) if content_parts else None
    def baidu_search_test(self,keyword,test):
        """
        在百度搜索引擎中搜索指定关键词
        
        Args:
            keyword: 要搜索的关键词
        """
        content = None
        if test == 1:
            if self.jump_to_citiao(keyword):
                print("1. 通过百度词条搜索关键词")
                content = self.baidu_baike_search()
        else:
            querys = self.get_query(keyword)
            for query in querys:
                self.tab.wait(config.BROWER_CRAWLER_INTERVAL) # 等待1秒，防止反爬虫
                if self.jump_to_baidu_engine(query):
                    if test == 2:
                        # 如果词条不存在，在百度搜索中搜索
                        # 2. 搜索页面的ai总结
                        self.tab.wait.ele_displayed(f"@class:{config.BAIDU_SEARCH_AI_CONCLUTION_SELECTOR}") # 等待AI总结元素出现
                        print("2. 获取百度引擎的AI总结词条")
                        content = self.baidu_engine_search_by_ai_conclution() # 获取AI总结文本内容
                    if test == 3:
                        # 放弃文本匹配
                        # # 如果AI总结不存在，尝试获取搜索结果总结
                        # print("3. 通过页面文本匹配搜索关键词")
                        # content = self.baidu_engine_search_by_text(keyword)
                        print("3. 总结选择器获取搜索关键词")
                        content = self.baidu_engine_search_by_summary_seletor(keyword)
                    if test == 4:
                        print("4. 标题选择器获取搜索关键词")
                        content = self.baidu_engine_search_by_title_seletor()
                    if content:
                        break
        return content
    
    
    def fetch_app_description(self,keyword):
        if config.BROWER_CRAWLER_BAIDU_SEARCH_TYPE == config.BAIDU_MULTI_RESULT:
            print("获取所有搜索结果文本")
            result = self.baidu_search_return_all_text(keyword)
            print(result)
            if  result:
                result = self.processor.get_app_description_abbr(keyword,result)
                print(f"{keyword}的描述是：{result}")
                return result
            else:
                return None
        else:
            print("获取单个搜索结果文本")
            return self.baidu_search(keyword)



def test_baidu_search():
    keyword = "ActivityWatch"
    apps = ["msedge","trae cn","upc"]
    test = 4
    crawler = BaiDuBrowerCrawler()
    # for keyword in apps:
    #     content = crawler.baidu_search_test(keyword,test)
    #     if not content:
    #         print("未找到相关内容")
    for keyword in apps:
        
        print(keyword)
        content = crawler.baidu_search(keyword)
        if not content:
            print("未找到相关内容")
def test_baidu_search_return_all_text():
    keyword = "ActivityWatch"
    apps = ["msedge","trae cn","upc"]
    crawler = BaiDuBrowerCrawler()
    for keyword in apps:
        print(keyword)
        content = crawler.baidu_search_return_all_text(keyword)
        if not content:
            print("未找到相关内容")
        else:
            print(content)
def test():
    crawler = BaiDuBrowerCrawler()
    print(f"BAIDU_SEARCH_TYPE:{config.BROWER_CRAWLER_BAIDU_SEARCH_TYPE}")
    print(crawler.fetch_app_description("ActivityWatch"))
    # crawler.quit()

if __name__ == "__main__":
    print(test())
