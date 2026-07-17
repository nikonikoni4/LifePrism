"""Loop 组件截图脚本

使用方法：
    python scripts/webapp-test/loop/screenshot.py

输出位置：
    scripts/webapp-test/截图/loop/
"""

import os
import sys

# 添加父目录到路径，以便导入 config 和 utils
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import BASE_URL, HEADLESS, ROUTES, VIEWPORT
from playwright.sync_api import sync_playwright
from utils import screenshot_page, wait_for_page


def run():
    """执行截图"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page(viewport=VIEWPORT)

        # 导航到首页
        print("导航到首页...")
        page.goto(BASE_URL + ROUTES["home"])
        wait_for_page(page)
        page.wait_for_timeout(3000)  # 等待数据加载

        # 选择一个群聊（点击第一个群聊）
        print("选择一个群聊...")
        session_groups = page.locator(".session-groups").first
        if session_groups.is_visible():
            first_chat = session_groups.locator("div").first
            if first_chat.is_visible():
                first_chat.click()
                page.wait_for_timeout(3000)
                print("已选择群聊")

                # 检查是否成功选择了群聊
                chat_area = page.locator('[class*="chatArea"]').first
                if chat_area.is_visible():
                    chat_text = chat_area.text_content()
                    if "选择一个群聊开始对话" in chat_text:
                        print("警告：未成功选择群聊，尝试点击其他元素...")
                        session_items = page.locator('[class*="session-item"]').all()
                        if session_items:
                            session_items[0].click()
                            page.wait_for_timeout(2000)
                            print("已点击第一个session-item")
                    else:
                        print("已成功选择群聊")
                else:
                    print("警告：未找到聊天区域")
            else:
                print("警告：未找到群聊项")
        else:
            print("警告：未找到群聊列表")

        # 截图 1: LoopStatusPanel 缩略图
        print("\n截图 1: LoopStatusPanel 缩略图")
        loop_panel = page.locator('[class*="loopPanel"]').first
        if loop_panel.is_visible():
            loop_panel.screenshot(
                path=os.path.join("scripts/webapp-test/截图/loop", "loop_status_panel.png")
            )
            print(f"  已保存: scripts/webapp-test/截图/loop/loop_status_panel.png")
        else:
            print("  警告：未找到 LoopStatusPanel，尝试全页面截图...")
            screenshot_page(page, module="loop", name="loop_status_panel_full")

        # 截图 2: LoopDetailModal 扩展图
        print("\n截图 2: LoopDetailModal 扩展图")
        loop_node_list = page.locator('[class*="loopNodeList"]').first
        if loop_node_list.is_visible():
            loop_node_list.click()
            page.wait_for_timeout(500)  # 等待模态框动画

            modal = page.locator('[class*="modal"]').first
            if modal.is_visible():
                modal.screenshot(
                    path=os.path.join("scripts/webapp-test/截图/loop", "loop_detail_modal.png")
                )
                print(f"  已保存: scripts/webapp-test/截图/loop/loop_detail_modal.png")
            else:
                print("  警告：未找到模态框，尝试全页面截图...")
                screenshot_page(page, module="loop", name="loop_detail_modal_full")
        else:
            print("  警告：未找到节点列表，跳过模态框截图")

        browser.close()


if __name__ == "__main__":
    run()
