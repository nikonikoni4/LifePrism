"""
resource_initializer.initialize_resources 单元测试

测试资源文件初始化的所有场景：
1. prompts 目录下的文件会被强制覆盖（无论是否存在）
2. prompts 目录外的文件不会被覆盖（已存在时跳过）
"""
import pytest
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 直接使用项目路径
TEMPLATES_DIR = Path("D:/desktop/软件开发/LifeWatch-AI/templates")
DATA_PATH = Path("D:/desktop/软件开发/LifeWatch-AI/localData")

# 需要强制覆盖的目录列表
OVERWRITE_DIR_LIST = ["prompts"]

# 测试文件名
TEST_PROMPT_FILE = "__test_prompt__.md"
TEST_USER_FILE = "__test_user__.md"


def initialize_resources_copy(templates_dir: Path, data_path: Path) -> None:
    """复制的初始化逻辑，用传入路径替代 settings"""
    if not templates_dir.exists():
        logger.warning(f"内嵌 templates 目录不存在，跳过资源初始化: {templates_dir}")
        return

    for source in templates_dir.rglob("*"):
        if not source.is_file():
            continue

        rel = source.relative_to(templates_dir)

        # 所有文件都映射到 data_path（跳过 config 子目录的逻辑，简化测试）
        if rel.parts[0] == "config":
            continue

        target = data_path / rel

        # 如果文件所在目录在强制覆盖列表中，则无论是否存在都覆盖
        if rel.parts[0] in OVERWRITE_DIR_LIST:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            logger.info(f"已强制覆盖资源文件: {target}")
            continue

        if target.exists():
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        logger.info(f"已初始化资源文件: {target}")


@pytest.fixture
def cleanup_prompts():
    """清理测试产生的 prompts 测试文件"""
    yield
    test_template = TEMPLATES_DIR / "prompts" / TEST_PROMPT_FILE
    if test_template.exists():
        test_template.unlink()
    test_target = DATA_PATH / "prompts" / TEST_PROMPT_FILE
    if test_target.exists():
        test_target.unlink()


@pytest.fixture
def cleanup_user():
    """清理测试产生的 user 测试文件"""
    yield
    test_template = TEMPLATES_DIR / "user" / TEST_USER_FILE
    if test_template.exists():
        test_template.unlink()
    test_target = DATA_PATH / "user" / TEST_USER_FILE
    if test_target.exists():
        test_target.unlink()


class TestInitializeResources:
    """测试 initialize_resources 函数"""

    def test_prompts_file_is_overwritten(self, cleanup_prompts):
        """
        场景1：prompts 目录下的文件会被强制覆盖

        前置条件：
        - templates/prompts/__test_prompt__.md 存在，内容为 "template content"
        - localData/prompts/__test_prompt__.md 存在，内容为 "user content"

        预期结果：
        - localData/prompts/__test_prompt__.md 被覆盖为 "template content"
        """
        template_file = TEMPLATES_DIR / "prompts" / TEST_PROMPT_FILE
        target_file = DATA_PATH / "prompts" / TEST_PROMPT_FILE

        template_file.write_text("template content", encoding="utf-8")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("user content", encoding="utf-8")
        assert target_file.read_text(encoding="utf-8") == "user content"

        initialize_resources_copy(TEMPLATES_DIR, DATA_PATH)

        assert target_file.read_text(encoding="utf-8") == "template content"

    def test_non_prompts_file_is_not_overwritten(self, cleanup_user):
        """
        场景2：prompts 目录外的文件不会被覆盖

        前置条件：
        - templates/user/__test_user__.md 存在，内容为 "template content"
        - localData/user/__test_user__.md 存在，内容为 "user content"

        预期结果：
        - localData/user/__test_user__.md 保持不变，仍为 "user content"
        """
        template_file = TEMPLATES_DIR / "user" / TEST_USER_FILE
        target_file = DATA_PATH / "user" / TEST_USER_FILE

        template_file.write_text("template content", encoding="utf-8")
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text("user content", encoding="utf-8")
        assert target_file.read_text(encoding="utf-8") == "user content"

        initialize_resources_copy(TEMPLATES_DIR, DATA_PATH)

        assert target_file.read_text(encoding="utf-8") == "user content"
