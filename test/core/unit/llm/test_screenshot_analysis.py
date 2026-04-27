"""测试 screenshot_analysis 模块的辅助函数"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from lifeprism.llm.function.screenshot_analysis import (
    encode_image_to_base64,
    _get_screenshot_category_info,
    _is_image_screenshot,
    _clean_llm_response,
)


@pytest.mark.core
class TestEncodeImageToBase64:
    """测试 encode_image_to_base64 函数"""

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    @patch('builtins.open', create=True)
    @patch('os.path.join')
    def test_encode_valid_image(self, mock_join, mock_open, mock_settings):
        """测试编码有效图片"""
        # Mock 设置
        mock_settings.lifeprism_data_path = "/fake/data/path"
        mock_join.return_value = "/fake/data/path/test.png"

        # Mock 文件读取
        mock_file = MagicMock()
        mock_file.read.return_value = b'\x89PNG\r\n\x1a\n'  # PNG 文件头
        mock_open.return_value.__enter__.return_value = mock_file

        result = encode_image_to_base64("test.png")

        # 验证返回格式
        assert result is not None
        assert result.startswith("data:image/png;base64,")
        assert len(result) > 30  # 应该包含 base64 数据

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    @patch('builtins.open', side_effect=FileNotFoundError)
    @patch('os.path.join')
    def test_encode_nonexistent_file(self, mock_join, mock_open, mock_settings):
        """测试编码不存在的文件"""
        mock_settings.lifeprism_data_path = "/fake/data/path"
        mock_join.return_value = "/fake/data/path/nonexistent.png"

        result = encode_image_to_base64("nonexistent.png")

        # 应该返回 None
        assert result is None

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    @patch('builtins.open', create=True)
    @patch('os.path.join')
    def test_encode_different_image_types(self, mock_join, mock_open, mock_settings):
        """测试不同类型的图片"""
        mock_settings.lifeprism_data_path = "/fake/data/path"

        # 测试 JPEG
        mock_join.return_value = "/fake/data/path/test.jpg"
        mock_file = MagicMock()
        mock_file.read.return_value = b'\xff\xd8\xff'  # JPEG 文件头
        mock_open.return_value.__enter__.return_value = mock_file

        result = encode_image_to_base64("test.jpg")
        assert result is not None
        assert "data:image/jpeg;base64," in result


@pytest.mark.core
class TestIsImageScreenshot:
    """测试 _is_image_screenshot 函数"""

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_all_images_exist(self, mock_join, mock_exists, mock_settings):
        """测试所有图片都存在"""
        mock_settings.lifeprism_data_path = "/fake/data/path"
        mock_join.side_effect = lambda base, path: f"{base}/{path}"
        mock_exists.return_value = True

        image_paths = ["img1.png", "img2.png", "img3.png"]
        result = _is_image_screenshot(image_paths)

        assert result is True

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_no_images_exist(self, mock_join, mock_exists, mock_settings):
        """测试所有图片都不存在"""
        mock_settings.lifeprism_data_path = "/fake/data/path"
        mock_join.side_effect = lambda base, path: f"{base}/{path}"
        mock_exists.return_value = False

        image_paths = ["img1.png", "img2.png", "img3.png"]
        result = _is_image_screenshot(image_paths)

        assert result is False

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    @patch('os.path.exists')
    @patch('os.path.join')
    def test_some_images_exist(self, mock_join, mock_exists, mock_settings):
        """测试部分图片存在"""
        mock_settings.lifeprism_data_path = "/fake/data/path"
        mock_join.side_effect = lambda base, path: f"{base}/{path}"

        # 第一个不存在，第二个存在
        mock_exists.side_effect = [False, True]

        image_paths = ["img1.png", "img2.png"]
        result = _is_image_screenshot(image_paths)

        # 只要有一个存在就返回 True
        assert result is True

    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    def test_empty_list(self, mock_settings):
        """测试空列表"""
        mock_settings.lifeprism_data_path = "/fake/data/path"

        result = _is_image_screenshot([])

        assert result is False


@pytest.mark.core
class TestGetScreenshotCategoryInfo:
    """测试 _get_screenshot_category_info 函数"""

    @patch('lifeprism.llm.function.screenshot_analysis.category_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.map_cache_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    def test_multi_purpose_app_ignored(self, mock_settings, mock_map_cache, mock_category):
        """测试多用途应用被忽略的情况"""
        # Mock 设置
        mock_settings.is_multi_purpose_app.return_value = True
        mock_settings.get.return_value = ["cat-123"]  # 忽略列表

        # Mock map_cache 查询
        mock_map_cache.query_multi_purpose_map_cache.return_value = (
            [{"category_id": "cat-123", "app_description": "浏览器应用"}],
            1
        )

        # Mock category 查询
        mock_category.get_category_by_id.return_value = {
            "id": "cat-123",
            "name": "娱乐",
            "description": "娱乐类应用"
        }

        result = _get_screenshot_category_info("Chrome", "YouTube - 视频")

        # 验证结果
        assert result["category_id"] == "cat-123"
        assert result["category_name"] == "娱乐"
        assert result["app_description"] == "浏览器应用"
        assert result["is_ignored"] is True

        # 验证调用
        mock_settings.is_multi_purpose_app.assert_called_once_with("Chrome")
        mock_map_cache.query_multi_purpose_map_cache.assert_called_once()

    @patch('lifeprism.llm.function.screenshot_analysis.category_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.map_cache_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    def test_single_purpose_app_not_ignored(self, mock_settings, mock_map_cache, mock_category):
        """测试单用途应用不被忽略的情况"""
        # Mock 设置
        mock_settings.is_multi_purpose_app.return_value = False
        mock_settings.get.return_value = ["cat-999"]  # 忽略列表（不包含当前分类）

        # Mock map_cache 查询
        mock_map_cache.query_single_purpose_map_cache.return_value = (
            [{"category_id": "cat-456", "app_description": "代码编辑器"}],
            1
        )

        result = _get_screenshot_category_info("VSCode", "main.py")

        # 验证结果
        assert result["category_id"] == "cat-456"
        assert result["category_name"] is None  # 不被忽略时不查询名称
        assert result["app_description"] == "代码编辑器"
        assert result["is_ignored"] is False

        # 验证没有调用 category 查询（延迟加载优化）
        mock_category.get_category_by_id.assert_not_called()

    @patch('lifeprism.llm.function.screenshot_analysis.category_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.map_cache_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    def test_no_category_found(self, mock_settings, mock_map_cache, mock_category):
        """测试未找到分类的情况"""
        # Mock 设置
        mock_settings.is_multi_purpose_app.return_value = False
        mock_settings.get.return_value = []

        # Mock map_cache 查询返回空
        mock_map_cache.query_single_purpose_map_cache.return_value = ([], 0)

        result = _get_screenshot_category_info("UnknownApp", "")

        # 验证结果
        assert result["category_id"] is None
        assert result["category_name"] is None
        assert result["app_description"] == ""
        assert result["is_ignored"] is False

    @patch('lifeprism.llm.function.screenshot_analysis.category_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.map_cache_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    def test_exception_handling(self, mock_settings, mock_map_cache, mock_category):
        """测试异常处理"""
        # Mock 设置抛出异常
        mock_settings.is_multi_purpose_app.side_effect = Exception("Database error")

        result = _get_screenshot_category_info("Chrome", "Test")

        # 应该返回默认值
        assert result["category_id"] is None
        assert result["category_name"] is None
        assert result["app_description"] == ""
        assert result["is_ignored"] is False

    @patch('lifeprism.llm.function.screenshot_analysis.category_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.map_cache_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.settings')
    def test_ignored_with_missing_category_name(self, mock_settings, mock_map_cache, mock_category):
        """测试被忽略但分类名称查询失败的情况"""
        # Mock 设置
        mock_settings.is_multi_purpose_app.return_value = True
        mock_settings.get.return_value = ["cat-123"]

        # Mock map_cache 查询
        mock_map_cache.query_multi_purpose_map_cache.return_value = (
            [{"category_id": "cat-123", "app_description": "测试应用"}],
            1
        )

        # Mock category 查询返回 None
        mock_category.get_category_by_id.return_value = None

        result = _get_screenshot_category_info("TestApp", "Test")

        # 验证结果
        assert result["category_id"] == "cat-123"
        assert result["category_name"] == "未分类"  # 应该有默认值
        assert result["is_ignored"] is True


@pytest.mark.core
class TestCleanLlmResponse:
    """测试 _clean_llm_response 函数"""

    def test_clean_valid_response(self):
        """测试清理有效的响应"""
        response = """1. 查看 React 官方文档的 Hooks 章节
2. 编辑 user_service.py 中的登录验证逻辑
3. 观看 YouTube 上的 Python 教程视频"""

        result = _clean_llm_response(response)

        assert result == response  # 应该保持不变

    def test_clean_response_with_markdown_headers(self):
        """测试清理包含 Markdown 标题的响应"""
        response = """### 基础统计
1. 查看文档
2. 编辑代码
### 总结
这是总结"""

        result = _clean_llm_response(response)

        expected = """1. 查看文档
2. 编辑代码"""
        assert result == expected

    def test_clean_response_with_tables(self):
        """测试清理包含表格的响应"""
        response = """| 应用 | 时长 | 用途 |
|------|------|------|
| Chrome | 10分钟 | 浏览 |
1. 查看文档
2. 编辑代码"""

        result = _clean_llm_response(response)

        expected = """1. 查看文档
2. 编辑代码"""
        assert result == expected

    def test_clean_response_with_bold_and_italic(self):
        """测试清理包含加粗和斜体的响应"""
        response = """1. 查看 **React** 官方文档
2. 编辑 *user_service.py* 文件
3. 观看 `Python` 教程"""

        result = _clean_llm_response(response)

        expected = """1. 查看 React 官方文档
2. 编辑 user_service.py 文件
3. 观看 Python 教程"""
        assert result == expected

    def test_clean_response_with_separators(self):
        """测试清理包含分隔线的响应"""
        response = """---
1. 查看文档
---
2. 编辑代码
==="""

        result = _clean_llm_response(response)

        expected = """1. 查看文档
2. 编辑代码"""
        assert result == expected

    def test_clean_response_with_code_blocks(self):
        """测试清理包含代码块的响应"""
        response = """```python
def test():
    pass
```
1. 查看文档
2. 编辑代码"""

        result = _clean_llm_response(response)

        expected = """1. 查看文档
2. 编辑代码"""
        assert result == expected

    def test_clean_response_none(self):
        """测试清理 None 响应"""
        response = "None"
        result = _clean_llm_response(response)
        assert result == "None"

    def test_clean_response_empty(self):
        """测试清理空响应"""
        response = ""
        result = _clean_llm_response(response)
        assert result == ""

    def test_clean_response_only_markdown(self):
        """测试只包含 Markdown 格式没有有效内容的响应"""
        response = """### 标题
| 表格 | 内容 |
|------|------|
---
**加粗文本**"""

        result = _clean_llm_response(response)

        # 应该返回 None（没有有效的行为列表）
        assert result == "None"

    def test_clean_complex_response(self):
        """测试清理复杂的混合格式响应（实际案例）"""
        response = """这是你2026年4月20日凌晨的**AI辅助开发工作活动记录**，整理梳理如下：

---
### 基础统计（总时长约14分钟，全部为开发工作）
| 应用                | 累计使用时长 | 用途                    |
|---------------------|--------------|--------------------------|
| WindowsTerminal(Claude Code) | ~9分钟      | AI辅助开发交互终端       |
| Antigravity代码编辑器 | ~5分钟       | 开发编写代码/配置文件    |

---
### 完整开发工作流
你正在开发`feat_monitor`功能的配置模块，工作轨迹为：
1. 先在Claude Code终端梳理开发需求/代码逻辑
2. 打开编辑器编写配置接口文件setting_api.py
3. 切回终端继续和AI确认开发细节
4. 再次返回编辑器，迭代开发配置模块全栈代码
5. 最后切回终端，准备继续后续开发

属于典型的AI辅助全栈开发流程。"""

        result = _clean_llm_response(response)

        expected = """1. 先在Claude Code终端梳理开发需求/代码逻辑
2. 打开编辑器编写配置接口文件setting_api.py
3. 切回终端继续和AI确认开发细节
4. 再次返回编辑器，迭代开发配置模块全栈代码
5. 最后切回终端，准备继续后续开发"""
        assert result == expected


@pytest.mark.core
class TestAnalyzeChunkScreenshotsFirstScreenshotLogic:
    """测试 analyze_chunk_screenshots 中的首张截图保留逻辑"""

    @pytest.mark.asyncio
    @patch('lifeprism.llm.function.screenshot_analysis.channel_manager')
    @patch('lifeprism.llm.function.screenshot_analysis.raw_behavior_analysis_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.encode_image_to_base64')
    @patch('lifeprism.llm.function.screenshot_analysis._get_screenshot_category_info')
    @patch('lifeprism.llm.function.screenshot_analysis._is_image_screenshot')
    async def test_first_screenshot_preserved_for_ignored_category(
        self, mock_is_image, mock_get_category, mock_encode, mock_repo, mock_channel
    ):
        """测试被忽略分类的第一张截图被保留"""
        from lifeprism.llm.function.screenshot_analysis import analyze_chunk_screenshots

        # Mock 数据
        chunk = {"start": "2026-04-27T10:00:00", "end": "2026-04-27T10:15:00"}
        screenshots = [
            {"file_path": "img1.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:00:00"},
            {"file_path": "img2.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:05:00"},
            {"file_path": "img3.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:10:00"},
        ]

        # Mock 返回值
        mock_is_image.return_value = True
        mock_get_category.return_value = {
            "category_id": "cat-game",
            "category_name": "娱乐",
            "app_description": "游戏应用",
            "is_ignored": True
        }
        mock_encode.return_value = "data:image/png;base64,fake_data"
        mock_channel.send.return_value = "1. 玩游戏"

        await analyze_chunk_screenshots(chunk, screenshots)

        # 验证：第一张截图应该被编码（保留），后续截图不应该被编码
        assert mock_encode.call_count == 1
        mock_encode.assert_called_once_with("img1.png")

        # 验证发送给 LLM 的内容
        call_args = mock_channel.send.call_args
        content = call_args[1]['content']

        # 第一张截图：应该有图片
        assert any(part.get('type') == 'image_url' for part in content)

        # 后续截图：应该是文字描述
        text_parts = [part['text'] for part in content if part.get('type') == 'text']
        assert any('[无截图]' in text and 'Game.exe' in text for text in text_parts)

    @pytest.mark.asyncio
    @patch('lifeprism.llm.function.screenshot_analysis.channel_manager')
    @patch('lifeprism.llm.function.screenshot_analysis.raw_behavior_analysis_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.encode_image_to_base64')
    @patch('lifeprism.llm.function.screenshot_analysis._get_screenshot_category_info')
    @patch('lifeprism.llm.function.screenshot_analysis._is_image_screenshot')
    async def test_multiple_apps_first_screenshots_preserved(
        self, mock_is_image, mock_get_category, mock_encode, mock_repo, mock_channel
    ):
        """测试多个不同 app 的第一张截图都被保留"""
        from lifeprism.llm.function.screenshot_analysis import analyze_chunk_screenshots

        chunk = {"start": "2026-04-27T10:00:00", "end": "2026-04-27T10:15:00"}
        screenshots = [
            {"file_path": "img1.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:00:00"},
            {"file_path": "img2.png", "window_app": "Video.exe", "window_title": "视频", "captured_at": "2026-04-27 10:05:00"},
            {"file_path": "img3.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:10:00"},
        ]

        mock_is_image.return_value = True
        mock_get_category.return_value = {
            "category_id": "cat-entertainment",
            "category_name": "娱乐",
            "app_description": "娱乐应用",
            "is_ignored": True
        }
        mock_encode.return_value = "data:image/png;base64,fake_data"
        mock_channel.send.return_value = "1. 娱乐活动"

        await analyze_chunk_screenshots(chunk, screenshots)

        # 验证：两个不同 app 的第一张截图都应该被编码
        assert mock_encode.call_count == 2
        assert mock_encode.call_args_list[0][0][0] == "img1.png"
        assert mock_encode.call_args_list[1][0][0] == "img2.png"

    @pytest.mark.asyncio
    @patch('lifeprism.llm.function.screenshot_analysis.channel_manager')
    @patch('lifeprism.llm.function.screenshot_analysis.raw_behavior_analysis_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.encode_image_to_base64')
    @patch('lifeprism.llm.function.screenshot_analysis._get_screenshot_category_info')
    @patch('lifeprism.llm.function.screenshot_analysis._is_image_screenshot')
    async def test_not_ignored_screenshots_all_preserved(
        self, mock_is_image, mock_get_category, mock_encode, mock_repo, mock_channel
    ):
        """测试不在忽略列表的截图全部保留"""
        from lifeprism.llm.function.screenshot_analysis import analyze_chunk_screenshots

        chunk = {"start": "2026-04-27T10:00:00", "end": "2026-04-27T10:15:00"}
        screenshots = [
            {"file_path": "img1.png", "window_app": "VSCode.exe", "window_title": "代码", "captured_at": "2026-04-27 10:00:00"},
            {"file_path": "img2.png", "window_app": "VSCode.exe", "window_title": "代码", "captured_at": "2026-04-27 10:05:00"},
        ]

        mock_is_image.return_value = True
        mock_get_category.return_value = {
            "category_id": "cat-work",
            "category_name": "工作",
            "app_description": "代码编辑器",
            "is_ignored": False
        }
        mock_encode.return_value = "data:image/png;base64,fake_data"
        mock_channel.send.return_value = "1. 编写代码"

        await analyze_chunk_screenshots(chunk, screenshots)

        # 验证：所有截图都应该被编码
        assert mock_encode.call_count == 2

    @pytest.mark.asyncio
    @patch('lifeprism.llm.function.screenshot_analysis.channel_manager')
    @patch('lifeprism.llm.function.screenshot_analysis.raw_behavior_analysis_repository')
    @patch('lifeprism.llm.function.screenshot_analysis.encode_image_to_base64')
    @patch('lifeprism.llm.function.screenshot_analysis._get_screenshot_category_info')
    @patch('lifeprism.llm.function.screenshot_analysis._is_image_screenshot')
    async def test_mixed_ignored_and_not_ignored(
        self, mock_is_image, mock_get_category, mock_encode, mock_repo, mock_channel
    ):
        """测试混合场景：部分忽略、部分不忽略"""
        from lifeprism.llm.function.screenshot_analysis import analyze_chunk_screenshots

        chunk = {"start": "2026-04-27T10:00:00", "end": "2026-04-27T10:15:00"}
        screenshots = [
            {"file_path": "img1.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:00:00"},
            {"file_path": "img2.png", "window_app": "VSCode.exe", "window_title": "代码", "captured_at": "2026-04-27 10:05:00"},
            {"file_path": "img3.png", "window_app": "Game.exe", "window_title": "游戏", "captured_at": "2026-04-27 10:10:00"},
        ]

        mock_is_image.return_value = True

        def get_category_side_effect(app, title):
            if app == "Game.exe":
                return {"category_id": "cat-game", "category_name": "娱乐", "app_description": "游戏", "is_ignored": True}
            else:
                return {"category_id": "cat-work", "category_name": "工作", "app_description": "编辑器", "is_ignored": False}

        mock_get_category.side_effect = get_category_side_effect
        mock_encode.return_value = "data:image/png;base64,fake_data"
        mock_channel.send.return_value = "1. 工作和娱乐"

        await analyze_chunk_screenshots(chunk, screenshots)

        # 验证：Game.exe 第一张 + VSCode.exe = 2 张图片被编码
        assert mock_encode.call_count == 2
        encoded_files = [call[0][0] for call in mock_encode.call_args_list]
        assert "img1.png" in encoded_files  # Game.exe 第一张
        assert "img2.png" in encoded_files  # VSCode.exe
        assert "img3.png" not in encoded_files  # Game.exe 第二张被过滤
