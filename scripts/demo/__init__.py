"""
Web-Demo 演示数据生成包

每次 web-demo 启动时自动全量重建演示数据。
"""

from scripts.demo.demo_data_generator import DemoDataGenerator, generate_demo_data

__all__ = ["DemoDataGenerator", "generate_demo_data"]
