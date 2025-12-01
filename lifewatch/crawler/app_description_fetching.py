
from lifewatch.crawler.api_crawler import DDGSAPICrawler
from lifewatch.crawler.brower_crawler import BaiDuBrowerCrawler
class AppDescriptionFetcher:
    def __init__(self,crawler_select = "BaiDuBrowerCrawler"):
        """
        初始化爬虫选择器
        Args:
            crawler_select: 爬虫选择器，可选值为 ["DDGSAPICrawler","BaiDuBrowerCrawler"]
        """
        self.crawler = None
        self.init_crawlers(crawler_select)
    def init_crawlers(self,crawler):
        
        if crawler == "DDGSAPICrawler":
            self.crawler = DDGSAPICrawler()
        elif crawler == "BaiDuBrowerCrawler":
            self.crawler = BaiDuBrowerCrawler()
        else:
            print(f"未找到爬虫选择器 '{crawler}'")
            self.crawler = BaiDuBrowerCrawler()
            print("使用BaiDuBrowerCrawler")
    def fetch_app_description(self,keyword):
        if self.crawler:
            return self.crawler.fetch_app_description(keyword)
        else:
            print("未找到爬虫")
            return None
    def fetch_batch_app_descriptions(self,keywords):
        results = {}
        for keyword in keywords: 
            results[keyword] = {}
            results[keyword]= self.fetch_app_description(keyword)
        return results
        