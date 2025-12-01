# 测试网页抓取
from lifewatch.crawler.brower_crawler import BaseBrowerCrawler
from lifewatch import config
if __name__ == "__main__":
    crawler = BaseBrowerCrawler()

    crawler.tab.get("https://www.baidu.com/s?wd=%E8%B1%86%E5%8C%85%E6%98%AF%E4%BB%80%E4%B9%88%E8%BD%AF%E4%BB%B6&pn=0&oq=%E8%B1%86%E5%8C%85%E6%98%AF%E4%BB%80%E4%B9%88%E8%BD%AF%E4%BB%B6&ie=utf-8&usm=5&fenlei=256&rsv_idx=1&rsv_pq=dd8dcc220001e068&rsv_t=941bJBZj0duaTaQ0GSWVMVfjfm9SbWAPrpFa%2B20CtJqJa8CKsOkzLWliA24&bs=%E8%B1%86%E5%8C%85%E6%98%AF%E4%BB%80%E4%B9%88%E8%BD%AF%E4%BB%B6")
    summarys = crawler.tab.eles("@class:{config.BAIDU_SEARCH_SUMMARY_SELECTOR}")
    for summary in summarys:
        print(summary.text)