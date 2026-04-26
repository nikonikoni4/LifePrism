"""
测试 plandoc_sync_service.insert_todo_to_md 函数

目的：验证插入任务到 MD 文件的各种场景
- 文件不存在时自动创建
- 插入到第一个 todoblock
- 插入到父任务下
- 多个 todoblock 的情况
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
from lifeprism.server.services.plandoc_sync_service import (
    insert_todo_to_md,
    _read_plan_doc_content,
    _get_plan_doc_path,
)


@pytest.fixture
def temp_plan_dir():
    """创建临时计划书目录"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_settings(temp_plan_dir):
    """Mock settings.lifeprism_data_path"""
    with patch('lifeprism.config.settings_manager.settings') as mock:
        mock.lifeprism_data_path = str(temp_plan_dir)
        yield mock


@pytest.mark.core
class TestInsertTodoToMd:
    """测试 insert_todo_to_md 函数的各种场景"""

    def test_create_file_when_not_exists(self, mock_settings, temp_plan_dir):
        """
        场景1：文件不存在时自动创建

        前置条件：MD 文件不存在
        预期结果：
        1. 自动创建文件
        2. 文件包含初始结构（标题 + todoblock）
        3. 成功插入任务
        4. 返回锚点 ID
        """
        plan_doc_id = "test-plan"
        content = "测试任务"

        # 执行插入
        anchor_id = insert_todo_to_md(plan_doc_id, content)

        # 验证：返回了锚点 ID
        assert anchor_id is not None
        assert anchor_id.startswith("t-")
        assert len(anchor_id) == 10  # t- + 8位uuid

        # 验证：文件已创建
        file_path = temp_plan_dir / "plan" / f"{plan_doc_id}.md"
        assert file_path.exists()

        # 验证：文件内容正确
        md_content = file_path.read_text(encoding='utf-8')
        assert f"# {plan_doc_id}" in md_content
        assert "<!-- lp:todoblock -->" in md_content
        assert "<!-- /lp:todoblock -->" in md_content
        assert f"- [ ] {content} <!-- lp:{anchor_id} -->" in md_content

    def test_insert_to_existing_file(self, mock_settings, temp_plan_dir):
        """
        场景2：插入到已存在的文件

        前置条件：MD 文件已存在，包含 todoblock
        预期结果：
        1. 成功插入任务
        2. 任务添加到 todoblock 末尾
        3. 返回锚点 ID
        """
        plan_doc_id = "existing-plan"
        plan_dir = temp_plan_dir / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)

        # 创建已存在的文件
        existing_content = """# existing-plan

## 任务列表
<!-- lp:todoblock -->
- [ ] 已存在的任务 <!-- lp:t-12345678 -->
<!-- /lp:todoblock -->
"""
        file_path = plan_dir / f"{plan_doc_id}.md"
        file_path.write_text(existing_content, encoding='utf-8')

        # 执行插入
        new_content = "新任务"
        anchor_id = insert_todo_to_md(plan_doc_id, new_content)

        # 验证：返回了锚点 ID
        assert anchor_id is not None
        assert anchor_id.startswith("t-")

        # 验证：文件内容包含新任务
        md_content = file_path.read_text(encoding='utf-8')
        assert "已存在的任务" in md_content
        assert f"- [ ] {new_content} <!-- lp:{anchor_id} -->" in md_content

    def test_insert_with_parent(self, mock_settings, temp_plan_dir):
        """
        场景3：插入子任务到父任务下

        前置条件：MD 文件包含父任务
        预期结果：
        1. 子任务插入到父任务下
        2. 子任务缩进正确（父任务缩进 + 1）
        3. 返回锚点 ID
        """
        plan_doc_id = "parent-plan"
        plan_dir = temp_plan_dir / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)

        # 创建包含父任务的文件
        parent_anchor = "t-parent01"
        existing_content = f"""# parent-plan

## 任务列表
<!-- lp:todoblock -->
- [ ] 父任务 <!-- lp:{parent_anchor} -->
<!-- /lp:todoblock -->
"""
        file_path = plan_dir / f"{plan_doc_id}.md"
        file_path.write_text(existing_content, encoding='utf-8')

        # 执行插入子任务
        child_content = "子任务"
        child_anchor = insert_todo_to_md(plan_doc_id, child_content, parent_anchor)

        # 验证：返回了锚点 ID
        assert child_anchor is not None
        assert child_anchor.startswith("t-")

        # 验证：子任务缩进正确
        md_content = file_path.read_text(encoding='utf-8')
        assert f"- [ ] 父任务 <!-- lp:{parent_anchor} -->" in md_content
        assert f"\t- [ ] {child_content} <!-- lp:{child_anchor} -->" in md_content

    def test_insert_multiple_children(self, mock_settings, temp_plan_dir):
        """
        场景4：插入多个子任务

        前置条件：MD 文件包含父任务和一个子任务
        预期结果：
        1. 新子任务插入到已有子任务之后
        2. 缩进正确
        3. 返回锚点 ID
        """
        plan_doc_id = "multi-child-plan"
        plan_dir = temp_plan_dir / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)

        # 创建包含父任务和子任务的文件
        parent_anchor = "t-parent02"
        child1_anchor = "t-child001"
        existing_content = f"""# multi-child-plan

## 任务列表
<!-- lp:todoblock -->
- [ ] 父任务 <!-- lp:{parent_anchor} -->
\t- [ ] 子任务1 <!-- lp:{child1_anchor} -->
<!-- /lp:todoblock -->
"""
        file_path = plan_dir / f"{plan_doc_id}.md"
        file_path.write_text(existing_content, encoding='utf-8')

        # 执行插入第二个子任务
        child2_content = "子任务2"
        child2_anchor = insert_todo_to_md(plan_doc_id, child2_content, parent_anchor)

        # 验证：返回了锚点 ID
        assert child2_anchor is not None

        # 验证：新子任务在子任务1之后
        md_content = file_path.read_text(encoding='utf-8')
        lines = md_content.split('\n')

        child1_line_index = None
        child2_line_index = None
        for i, line in enumerate(lines):
            if child1_anchor in line:
                child1_line_index = i
            if child2_anchor in line:
                child2_line_index = i

        assert child1_line_index is not None
        assert child2_line_index is not None
        assert child2_line_index > child1_line_index

    def test_insert_to_multiple_todoblocks(self, mock_settings, temp_plan_dir):
        """
        场景5：多个 todoblock 的情况

        前置条件：MD 文件包含多个 todoblock
        预期结果：
        1. 无父任务时插入到第一个 block
        2. 有父任务时插入到父任务所在的 block
        """
        plan_doc_id = "multi-block-plan"
        plan_dir = temp_plan_dir / "plan"
        plan_dir.mkdir(parents=True, exist_ok=True)

        # 创建包含多个 todoblock 的文件
        parent_anchor = "t-parent03"
        existing_content = f"""# multi-block-plan

## 第一个任务列表
<!-- lp:todoblock -->
- [ ] 第一个block的任务 <!-- lp:t-block001 -->
<!-- /lp:todoblock -->

## 第二个任务列表
<!-- lp:todoblock -->
- [ ] 第二个block的父任务 <!-- lp:{parent_anchor} -->
<!-- /lp:todoblock -->
"""
        file_path = plan_dir / f"{plan_doc_id}.md"
        file_path.write_text(existing_content, encoding='utf-8')

        # 测试1：无父任务，应插入到第一个 block
        task1_content = "插入到第一个block"
        anchor1 = insert_todo_to_md(plan_doc_id, task1_content)
        assert anchor1 is not None

        md_content = file_path.read_text(encoding='utf-8')
        blocks = md_content.split("<!-- lp:todoblock -->")
        assert task1_content in blocks[1]  # 第一个 block

        # 测试2：有父任务，应插入到父任务所在的 block（第二个）
        task2_content = "插入到第二个block"
        anchor2 = insert_todo_to_md(plan_doc_id, task2_content, parent_anchor)
        assert anchor2 is not None

        md_content = file_path.read_text(encoding='utf-8')
        blocks = md_content.split("<!-- lp:todoblock -->")
        assert task2_content in blocks[2]  # 第二个 block

    def test_create_directory_if_not_exists(self, mock_settings, temp_plan_dir):
        """
        场景6：plan 目录不存在时自动创建

        前置条件：plan 目录不存在
        预期结果：
        1. 自动创建 plan 目录
        2. 成功创建文件并插入任务
        """
        plan_doc_id = "new-dir-plan"
        content = "测试任务"

        # 确保 plan 目录不存在
        plan_dir = temp_plan_dir / "plan"
        assert not plan_dir.exists()

        # 执行插入
        anchor_id = insert_todo_to_md(plan_doc_id, content)

        # 验证：返回了锚点 ID
        assert anchor_id is not None

        # 验证：目录和文件都已创建
        assert plan_dir.exists()
        file_path = plan_dir / f"{plan_doc_id}.md"
        assert file_path.exists()

    def test_insert_with_chinese_content(self, mock_settings, temp_plan_dir):
        """
        场景7：插入中文内容

        前置条件：任务内容包含中文
        预期结果：
        1. 成功插入中文任务
        2. 文件编码正确（UTF-8）
        """
        plan_doc_id = "中文计划"
        content = "这是一个中文任务 🎯"

        # 执行插入
        anchor_id = insert_todo_to_md(plan_doc_id, content)

        # 验证：返回了锚点 ID
        assert anchor_id is not None

        # 验证：文件内容正确
        file_path = temp_plan_dir / "plan" / f"{plan_doc_id}.md"
        md_content = file_path.read_text(encoding='utf-8')
        assert content in md_content
        assert f"<!-- lp:{anchor_id} -->" in md_content
