"""测试 lifeprism.llm.agent.context 模块的 _read_file 参数注入功能"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from lifeprism.llm.agent.context import Context


@pytest.mark.core
class TestReadFile:
    """测试 _read_file 方法"""

    def test_file_not_exists(self):
        """测试文件不存在时返回 None"""
        result = Context._read_file("/nonexistent/path/file.md")
        assert result is None

    def test_read_file_without_params(self):
        """测试无参数时正常读取文件内容"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# 测试文档\n这是测试内容")
            temp_path = f.name

        try:
            result = Context._read_file(temp_path)
            assert result == "# 测试文档\n这是测试内容"
        finally:
            Path(temp_path).unlink()

    def test_read_file_with_params_injection(self):
        """测试参数注入功能"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# {title}\n作者: {author}\n时间: {time}")
            temp_path = f.name

        try:
            result = Context._read_file(
                temp_path, title="测试标题", author="LifePrism", time="2026-05-22"
            )
            assert result == "# 测试标题\n作者: LifePrism\n时间: 2026-05-22"
        finally:
            Path(temp_path).unlink()

    def test_read_file_with_partial_params(self):
        """测试部分参数注入（缺失参数保持原样）"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("你好 {name}，当前时间 {time}")
            temp_path = f.name

        try:
            result = Context._read_file(temp_path, name="LifePrism")
            assert result == "你好 LifePrism，当前时间 {time}"
        finally:
            Path(temp_path).unlink()

    def test_read_file_with_no_placeholders(self):
        """测试文档中无占位符时的参数注入（kwargs 被忽略）"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("# 固定内容\n没有参数占位符")
            temp_path = f.name

        try:
            result = Context._read_file(temp_path, name="LifePrism")
            assert result == "# 固定内容\n没有参数占位符"
        finally:
            Path(temp_path).unlink()

    @patch("lifeprism.llm.agent.context.logger")
    def test_missing_params_warning(self, mock_logger):
        """测试缺失参数时输出 warning 日志"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("用户: {name}\n邮箱: {email}\n手机: {phone}")
            temp_path = f.name

        try:
            result = Context._read_file(temp_path, name="LifePrism")
            # 验证 warning 日志被调用
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "未注入的参数" in warning_msg
            assert "email" in warning_msg
            assert "phone" in warning_msg
            # 验证内容正确（未注入的参数保持原样）
            assert result == "用户: LifePrism\n邮箱: {email}\n手机: {phone}"
        finally:
            Path(temp_path).unlink()

    def test_params_extraction(self):
        """测试参数提取功能（验证能正确识别所有 {key} 参数）"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("{greeting} {name}！\n今天是 {date}，天气 {weather}。")
            temp_path = f.name

        try:
            # 使用 regex 手动验证参数提取
            import re

            content = Path(temp_path).read_text(encoding="utf-8")
            placeholders = set(re.findall(r"\{(\w+)\}", content))
            assert placeholders == {"greeting", "name", "date", "weather"}
        finally:
            Path(temp_path).unlink()

    def test_params_injection_with_special_chars(self):
        """测试包含特殊字符的参数注入"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("内容: {content}\n链接: {url}")
            temp_path = f.name

        try:
            result = Context._read_file(
                temp_path,
                content="这是一段包含特殊字符的内容：!@#$%^&*()",
                url="https://example.com/path?param=value&other=123",
            )
            assert "这是一段包含特殊字符的内容：!@#$%^&*()" in result
            assert "https://example.com/path?param=value&other=123" in result
        finally:
            Path(temp_path).unlink()

    def test_params_injection_with_empty_string(self):
        """测试空字符串参数注入"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("名称: {name}\n描述: {desc}")
            temp_path = f.name

        try:
            result = Context._read_file(temp_path, name="LifePrism", desc="")
            assert result == "名称: LifePrism\n描述: "
        finally:
            Path(temp_path).unlink()

    def test_params_injection_with_numeric_values(self):
        """测试数值类型参数注入"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".md", delete=False, encoding="utf-8"
        ) as f:
            f.write("数量: {count}\n价格: {price}")
            temp_path = f.name

        try:
            result = Context._read_file(temp_path, count=42, price=99.99)
            assert result == "数量: 42\n价格: 99.99"
        finally:
            Path(temp_path).unlink()


@pytest.mark.core
class TestBuildExpandDir:
    """测试 _build_expand_dir 方法"""

    @patch("lifeprism.llm.agent.context.settings")
    def test_expand_dir_not_exists(self, mock_settings):
        """测试 expand_meta_data.json 不存在时返回 '无'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings.lifeprism_data_path = Path(tmpdir)
            result = Context._build_expand_dir()
            assert result == "无"

    @patch("lifeprism.llm.agent.context.settings")
    def test_expand_dir_empty_list(self, mock_settings):
        """测试 expand_meta_data.json 为空列表时返回 '无'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings.lifeprism_data_path = Path(tmpdir)
            expand_dir = Path(tmpdir) / "localData/expand_dir"
            expand_dir.mkdir(parents=True)
            meta_file = expand_dir / "expand_meta_data.json"
            meta_file.write_text("[]", encoding="utf-8")
            result = Context._build_expand_dir()
            assert result == "无"

    @patch("lifeprism.llm.agent.context.settings")
    def test_expand_dir_with_data(self, mock_settings):
        """测试 expand_meta_data.json 有数据时正确格式化"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings.lifeprism_data_path = Path(tmpdir)
            expand_dir = Path(tmpdir) / "localData/expand_dir"
            expand_dir.mkdir(parents=True)
            meta_file = expand_dir / "expand_meta_data.json"
            test_data = [
                {
                    "path": "/data/projects",
                    "path_name": "项目目录",
                    "description": "存放所有项目文件",
                },
                {"path": "/data/backup", "path_name": "备份目录", "description": "数据备份位置"},
            ]
            meta_file.write_text(json.dumps(test_data, ensure_ascii=False), encoding="utf-8")
            result = Context._build_expand_dir()
            assert "- /data/projects (项目目录): 存放所有项目文件" in result
            assert "- /data/backup (备份目录): 数据备份位置" in result

    @patch("lifeprism.llm.agent.context.settings")
    def test_expand_dir_invalid_json(self, mock_settings):
        """测试 expand_meta_data.json 格式错误时返回 '无'"""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_settings.lifeprism_data_path = Path(tmpdir)
            expand_dir = Path(tmpdir) / "localData/expand_dir"
            expand_dir.mkdir(parents=True)
            meta_file = expand_dir / "expand_meta_data.json"
            meta_file.write_text("invalid json", encoding="utf-8")
            result = Context._build_expand_dir()
            assert result == "无"


@pytest.mark.core
class TestBuildBootstrap:
    """测试 _build_bootstrap 方法的参数注入"""

    @patch("lifeprism.llm.agent.context.settings")
    def test_agent_md_params_injection(self, mock_settings):
        """测试 agent.md 参数注入"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            mock_settings.lifeprism_data_path = tmpdir_path

            # 创建 agent/chat 目录和 agent.md
            agent_chat_dir = tmpdir_path / "agent/chat"
            agent_chat_dir.mkdir(parents=True)
            agent_md = agent_chat_dir / "agent.md"
            agent_md.write_text(
                "Agent路径: {agent_path}\n用户路径: {user_path}\n日记路径: {diary_path}\n扩展目录:\n{expand_dir}",
                encoding="utf-8",
            )

            # 创建 user 目录
            (tmpdir_path / "user").mkdir()

            result = Context._build_bootstrap()
            assert f"Agent路径: {tmpdir_path / 'agent'}" in result
            assert f"用户路径: {tmpdir_path / 'user'}" in result
            assert f"日记路径: {tmpdir_path / 'diary'}" in result

    @patch("lifeprism.llm.agent.context.settings")
    def test_agent_md_with_expand_dir(self, mock_settings):
        """测试 agent.md 包含 expand_dir 参数"""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            mock_settings.lifeprism_data_path = tmpdir_path

            # 创建 agent/chat 目录和 agent.md
            agent_chat_dir = tmpdir_path / "agent/chat"
            agent_chat_dir.mkdir(parents=True)
            agent_md = agent_chat_dir / "agent.md"
            agent_md.write_text("扩展目录:\n{expand_dir}", encoding="utf-8")

            # 创建 expand_meta_data.json
            expand_dir = tmpdir_path / "localData/expand_dir"
            expand_dir.mkdir(parents=True)
            meta_file = expand_dir / "expand_meta_data.json"
            test_data = [
                {
                    "path": "/data/projects",
                    "path_name": "项目目录",
                    "description": "存放所有项目文件",
                }
            ]
            meta_file.write_text(json.dumps(test_data, ensure_ascii=False), encoding="utf-8")

            # 创建 user 目录
            (tmpdir_path / "user").mkdir()

            result = Context._build_bootstrap()
            assert "- /data/projects (项目目录): 存放所有项目文件" in result
