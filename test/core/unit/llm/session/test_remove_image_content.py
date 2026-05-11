"""
测试 SessionManager._remove_image_content 方法
"""
import pytest
from lifeprism.llm.session.manager import SessionManager


@pytest.mark.core
class TestRemoveImageContent:
    """测试移除图片内容功能"""

    def test_remove_image_type_content(self):
        """测试移除 type='image' 的 content block"""
        msg = {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': '这是一段文本'},
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='
                    }
                },
                {'type': 'text', 'text': '这是另一段文本'}
            ]
        }

        result = SessionManager._remove_image_content(msg)

        # 验证图片 block 被移除
        assert len(result['content']) == 2
        assert result['content'][0]['type'] == 'text'
        assert result['content'][0]['text'] == '这是一段文本'
        assert result['content'][1]['type'] == 'text'
        assert result['content'][1]['text'] == '这是另一段文本'

    def test_remove_image_url_type_content(self):
        """测试移除 type='image_url' 的 content block"""
        msg = {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': '请看这张图片'},
                {
                    'type': 'image_url',
                    'image_url': {
                        'url': 'data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAA8A/9k='
                    }
                }
            ]
        }

        result = SessionManager._remove_image_content(msg)

        # 验证图片 block 被移除
        assert len(result['content']) == 1
        assert result['content'][0]['type'] == 'text'
        assert result['content'][0]['text'] == '请看这张图片'

    def test_keep_non_user_message_unchanged(self):
        """测试非 user 角色的消息保持不变"""
        msg = {
            'role': 'assistant',
            'content': [
                {'type': 'text', 'text': '我看到了图片'},
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': 'base64_data_here'
                    }
                }
            ]
        }

        result = SessionManager._remove_image_content(msg)

        # 验证 assistant 消息不被处理
        assert len(result['content']) == 2
        assert result['content'][1]['type'] == 'image'

    def test_keep_string_content_unchanged(self):
        """测试字符串类型的 content 保持不变"""
        msg = {
            'role': 'user',
            'content': '这是一段纯文本消息'
        }

        result = SessionManager._remove_image_content(msg)

        # 验证字符串内容不变
        assert result['content'] == '这是一段纯文本消息'

    def test_deep_copy_original_message(self):
        """测试不修改原始消息（深拷贝）"""
        original_msg = {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': '文本'},
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': 'base64_data'
                    }
                }
            ]
        }

        result = SessionManager._remove_image_content(original_msg)

        # 验证原始消息未被修改
        assert len(original_msg['content']) == 2
        assert original_msg['content'][1]['type'] == 'image'
        # 验证返回的消息已过滤
        assert len(result['content']) == 1
        assert result['content'][0]['type'] == 'text'

    def test_empty_content_list(self):
        """测试空 content 列表"""
        msg = {
            'role': 'user',
            'content': []
        }

        result = SessionManager._remove_image_content(msg)

        # 验证返回空列表
        assert result['content'] == []

    def test_only_image_content(self):
        """测试只包含图片的消息"""
        msg = {
            'role': 'user',
            'content': [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/jpeg',
                        'data': 'base64_data'
                    }
                }
            ]
        }

        result = SessionManager._remove_image_content(msg)

        # 验证返回空列表
        assert result['content'] == []

    def test_mixed_content_types(self):
        """测试混合多种 content 类型"""
        msg = {
            'role': 'user',
            'content': [
                {'type': 'text', 'text': '第一段文本'},
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': 'image/png',
                        'data': 'png_base64_data'
                    }
                },
                {'type': 'text', 'text': '第二段文本'},
                {
                    'type': 'image_url',
                    'image_url': {
                        'url': 'data:image/jpeg;base64,jpeg_data'
                    }
                },
                {'type': 'text', 'text': '第三段文本'}
            ]
        }

        result = SessionManager._remove_image_content(msg)

        # 验证只保留文本类型
        assert len(result['content']) == 3
        assert all(block['type'] == 'text' for block in result['content'])
        assert result['content'][0]['text'] == '第一段文本'
        assert result['content'][1]['text'] == '第二段文本'
        assert result['content'][2]['text'] == '第三段文本'
