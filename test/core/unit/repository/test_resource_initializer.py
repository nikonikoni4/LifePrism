"""resource_initializer.initialize_resources 单元测试

测试资源文件初始化的所有场景：
1. OVERWRITE_DIR_LIST 目录下文件强制覆盖（如 prompts/）
2. OVERWRITE_FILE_LIST 文件强制覆盖（如 agent/chat/soul.md）
3. 其余文件遵循"仅复制不覆盖"原则
4. 用户数据不被覆盖（identity.md / classify_preference.md）
5. bootstrap.md 已退休：任何情况下都不生成、不覆盖用户已有文件

测试直接调用生产函数 lifeprism.repository.resource_initializer.initialize_resources()，
仅通过 patch 替换打包环境（sys.frozen / sys._MEIPASS）与 settings，不复制生产逻辑。
测试使用 tmp_path 完全隔离，不污染真实 templates/ 与 localData/ 目录。
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def initialize_resources_copy(templates_dir: Path, data_path: Path) -> None:
    """调用真实生产 initialize_resources()，用临时路径替代打包环境与 settings

    通过 patch 模拟 PyInstaller 打包环境：
    - sys.frozen = True
    - sys._MEIPASS = templates_dir.parent，使生产代码解析出的模板根为
      templates_dir.parent / "templates"（即传入的 templates_dir，要求其目录名为 "templates"）
    - settings.lifeprism_data_path = data_path
    - settings.config_base_path = data_path.parent / "config"

    生产函数在调用时 `from lifeprism.config.settings_manager import settings`，
    因此在 settings_manager 模块命名空间 patch 即可生效。
    """
    from lifeprism.repository import resource_initializer

    fake_settings = SimpleNamespace(
        lifeprism_data_path=data_path,
        config_base_path=data_path.parent / "config",
    )

    with (
        patch.object(sys, "frozen", True, create=True),
        patch.object(sys, "_MEIPASS", str(templates_dir.parent), create=True),
        patch("lifeprism.config.settings_manager.settings", fake_settings),
    ):
        resource_initializer.initialize_resources()


def _write(path: Path, content: str) -> None:
    """辅助函数：写入文件（自动创建父目录）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class TestInitializeResources:
    """测试 initialize_resources 函数"""

    def test_prompts_file_is_overwritten(self, tmp_path):
        """
        场景1：prompts 目录下文件被强制覆盖（OVERWRITE_DIR_LIST 命中）

        前置条件：
        - templates/prompts/prompt.md 存在，内容为 "template content"
        - data/prompts/prompt.md 存在，内容为 "user content"

        预期结果：
        - data/prompts/prompt.md 被覆盖为 "template content"
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "prompts" / "prompt.md", "template content")
        _write(data_path / "prompts" / "prompt.md", "user content")
        assert (data_path / "prompts" / "prompt.md").read_text(encoding="utf-8") == "user content"

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "prompts" / "prompt.md").read_text(encoding="utf-8") == "template content"

    def test_non_overwrite_file_is_not_overwritten(self, tmp_path):
        """
        场景2：不在任何白名单中的文件不被覆盖（"仅复制不覆盖"原则）

        前置条件：
        - templates/user/user.md 存在，内容为 "template content"
        - data/user/user.md 存在，内容为 "user content"

        预期结果：
        - data/user/user.md 保持不变，仍为 "user content"
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "user" / "user.md", "template content")
        _write(data_path / "user" / "user.md", "user content")

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "user" / "user.md").read_text(encoding="utf-8") == "user content"

    def test_agent_system_prompt_is_overwritten(self, tmp_path):
        """
        场景3：agent/chat/ 下系统提示词被强制覆盖（OVERWRITE_FILE_LIST 命中）

        前置条件：
        - templates/agent/chat/soul.md 存在，内容为 "template soul"
        - data/agent/chat/soul.md 存在，内容为 "user soul"

        预期结果：
        - data/agent/chat/soul.md 被覆盖为 "template soul"
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "soul.md", "template soul")
        _write(data_path / "agent" / "chat" / "soul.md", "user soul")

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "agent" / "chat" / "soul.md").read_text(encoding="utf-8") == "template soul"

    def test_bootstrap_md_is_not_overwritten(self, tmp_path):
        """
        场景4（核心回归）：bootstrap.md 不被强制覆盖

        前置条件：
        - templates/agent/chat/bootstrap.md 存在，内容为 "template bootstrap"
        - data/agent/chat/bootstrap.md 不存在（模拟用户已完成引导并删除）

        预期结果：
        - initialize_resources 执行后，data/agent/chat/bootstrap.md 不被创建
        - 即 bootstrap.md 不会反复出现

        回归背景：原 OVERWRITE_DIR_LIST=["prompts","tool","agent"] 导致 agent/ 下
        所有文件被强制覆盖，bootstrap.md 反复出现，干扰用户引导流程。
        现该文件已退休，任何情况下都不再初始化。
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "bootstrap.md", "template bootstrap")
        # 模拟用户已完成引导并删除 bootstrap.md
        _write(data_path / "agent" / "chat" / "other.md", "placeholder")

        initialize_resources_copy(templates_dir, data_path)

        # 关键断言：bootstrap.md 不应被创建
        assert not (data_path / "agent" / "chat" / "bootstrap.md").exists()

    def test_identity_md_is_not_overwritten(self, tmp_path):
        """
        场景5（核心回归）：identity.md 不被强制覆盖

        前置条件：
        - templates/agent/chat/identity.md 存在，内容为 "template identity (name empty)"
        - data/agent/chat/identity.md 存在，内容为 "user set name: Alice"

        预期结果：
        - data/agent/chat/identity.md 保持不变，仍为 "user set name: Alice"

        回归背景：identity.md 是用户在引导流程中编辑的文件（保存 AI 名称），
        原实现被 OVERWRITE_DIR_LIST 中的 "agent" 误伤，导致用户设置的 AI 名称丢失。
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "identity.md", "template identity (name empty)")
        _write(data_path / "agent" / "chat" / "identity.md", "user set name: Alice")

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "agent" / "chat" / "identity.md").read_text(encoding="utf-8") == "user set name: Alice"

    def test_classify_preference_md_is_not_overwritten(self, tmp_path):
        """
        场景6：classify_preference.md 不被强制覆盖（用户偏好数据）

        前置条件：
        - templates/agent/classify/classify_preference.md 存在，内容为 "template"
        - data/agent/classify/classify_preference.md 存在，内容为 "user preference"

        预期结果：
        - data/agent/classify/classify_preference.md 保持不变
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "classify" / "classify_preference.md", "template")
        _write(data_path / "agent" / "classify" / "classify_preference.md", "user preference")

        initialize_resources_copy(templates_dir, data_path)

        assert (
            (data_path / "agent" / "classify" / "classify_preference.md").read_text(encoding="utf-8")
            == "user preference"
        )

    def test_bootstrap_md_not_created_on_first_init(self, tmp_path):
        """
        场景7：首次初始化也不生成 bootstrap.md（已退休文件）

        前置条件：
        - templates/agent/chat/bootstrap.md 存在，内容为 "template bootstrap"
        - data/agent/chat/ 完全不存在（首次启动）

        预期结果：
        - data/agent/chat/bootstrap.md 不被创建
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "bootstrap.md", "template bootstrap")

        initialize_resources_copy(templates_dir, data_path)

        assert not (data_path / "agent" / "chat" / "bootstrap.md").exists()

    def test_existing_user_bootstrap_is_kept(self, tmp_path):
        """
        场景8：用户已存在的 bootstrap.md 不被删除、不被覆盖

        前置条件：
        - templates/agent/chat/bootstrap.md 存在，内容为 "template bootstrap"
        - data/agent/chat/bootstrap.md 存在，内容为 "user bootstrap"（用户自行维护）

        预期结果：
        - data/agent/chat/bootstrap.md 保持不变，内容仍为 "user bootstrap"
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "bootstrap.md", "template bootstrap")
        _write(data_path / "agent" / "chat" / "bootstrap.md", "user bootstrap")

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "agent" / "chat" / "bootstrap.md").read_text(encoding="utf-8") == "user bootstrap"

    def test_non_existent_user_file_is_copied(self, tmp_path):
        """
        场景9：用户数据文件首次启动被复制（不存在目标时复制）

        前置条件：
        - templates/user/user.md 存在，内容为 "template content"
        - data/user/user.md 不存在

        预期结果：
        - data/user/user.md 被创建，内容为 "template content"
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "user" / "user.md", "template content")

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "user" / "user.md").read_text(encoding="utf-8") == "template content"

    def test_overwrite_file_list_priority_over_dir_list(self, tmp_path):
        """
        场景10：OVERWRITE_FILE_LIST 优先级验证（agent/chat/soul.md 命中文件白名单）

        前置条件：
        - templates/agent/chat/soul.md 存在
        - data/agent/chat/soul.md 存在（应被覆盖）

        预期结果：
        - data/agent/chat/soul.md 被覆盖为模板内容
        - 验证 agent 目录虽然不在 OVERWRITE_DIR_LIST，但文件白名单仍能命中
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "soul.md", "new template soul")
        _write(data_path / "agent" / "chat" / "soul.md", "old user soul")

        initialize_resources_copy(templates_dir, data_path)

        assert (data_path / "agent" / "chat" / "soul.md").read_text(encoding="utf-8") == "new template soul"

    def test_bootstrap_md_not_overwritten_even_if_agent_in_dir_list(self, tmp_path):
        """
        场景11（核心回归，防御性测试）：即使 "agent" 被误加入 OVERWRITE_DIR_LIST，
        bootstrap.md 也不应被复制

        前置条件：
        - 模拟历史 bug 场景：patch 生产常量 OVERWRITE_DIR_LIST = ["prompts", "agent"]
        - templates/agent/chat/bootstrap.md 存在，内容为 "template bootstrap"
        - data/agent/chat/bootstrap.md 不存在（模拟用户已完成引导并删除）
        - data/agent/chat/ 目录存在（含其他文件，模拟用户已使用过）

        预期结果：
        - data/agent/chat/bootstrap.md 不被创建
        - 即 "agent" 误入 OVERWRITE_DIR_LIST 时，优先级 0 的 bootstrap.md 保护
          仍能拦截，防止 bug 复发

        回归背景：2026-07-27 修复前，bootstrap.md 跳过逻辑位于优先级 3，
        被 OVERWRITE_DIR_LIST 的整目录覆盖（优先级 2）绕过，导致 bug 复发。
        本次修复将 bootstrap.md 跳过逻辑提前到优先级 0（最高），即使
        OVERWRITE_DIR_LIST 误包含 "agent" 也能拦截。
        """
        templates_dir = tmp_path / "templates"
        data_path = tmp_path / "data"

        _write(templates_dir / "agent" / "chat" / "bootstrap.md", "template bootstrap")
        # 模拟用户已完成引导并删除 bootstrap.md，但 agent/chat 目录已存在
        _write(data_path / "agent" / "chat" / "other.md", "placeholder")

        # patch 生产常量，模拟 "agent" 误入 OVERWRITE_DIR_LIST 的历史 bug 场景
        with patch(
            "lifeprism.repository.resource_initializer.OVERWRITE_DIR_LIST",
            ["prompts", "agent"],
        ):
            initialize_resources_copy(templates_dir, data_path)

        # 关键断言：即使 "agent" 在 OVERWRITE_DIR_LIST 中，bootstrap.md 也不应被创建
        assert not (data_path / "agent" / "chat" / "bootstrap.md").exists()
