"""
爬虫模块
"""
from .brower_crawler import BaseBrowerCrawler
from .api_crawler import DDGSAPICrawler, AppDescriptionProcessor
from .app_description_fetching import AppDescriptionFetcher
__all__ = [
    "BaseBrowerCrawler",
    "DDGSAPICrawler",
    "AppDescriptionProcessor",
]