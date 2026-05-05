"""
add_on_service 单元测试
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from lifeprism.server.services import add_on_service
from lifeprism.server.schemas.add_on_schemas import CreateExpandDirRequest, UpdateExpandDirRequest, ExpandDirItem


@pytest.fixture
def temp_data_dir(tmp_path):
    """创建临时数据目录"""
    expand_dir = tmp_path / "expand_dir"
    expand_dir.mkdir()
    return tmp_path


@pytest.fixture
def mock_settings(temp_data_dir):
    """Mock settings.lifeprism_data_path"""
    with patch('lifeprism.server.services.add_on_service.settings') as mock:
        mock.lifeprism_data_path = str(temp_data_dir)
        yield mock


def test_get_all_expand_dirs_empty(mock_settings):
    """测试获取空列表"""
    result = add_on_service.get_all_expand_dirs()
    assert result == []


def test_create_expand_dir_success(mock_settings, tmp_path):
    """测试创建扩展文件夹成功"""
    # 创建一个真实的测试目录
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()

    data = CreateExpandDirRequest(
        name="测试文件夹",
        path=str(test_dir),
        description="测试描述",
        ai_index=True
    )

    result = add_on_service.create_expand_dir(data)

    assert result.id == "1"
    assert result.name == "测试文件夹"
    assert result.path == str(test_dir)
    assert result.description == "测试描述"
    assert result.ai_index is True
    assert result.created_at is not None


def test_create_expand_dir_invalid_path(mock_settings):
    """测试创建时路径无效"""
    data = CreateExpandDirRequest(
        name="测试",
        path="/invalid/path/does/not/exist",
        description="",
        ai_index=False
    )

    with pytest.raises(ValueError, match="路径不存在或无法访问"):
        add_on_service.create_expand_dir(data)


def test_create_expand_dir_duplicate_path(mock_settings, tmp_path):
    """测试创建时路径重复"""
    test_dir = tmp_path / "test_folder"
    test_dir.mkdir()

    data = CreateExpandDirRequest(
        name="文件夹1",
        path=str(test_dir),
        description="",
        ai_index=False
    )

    # 第一次创建成功
    add_on_service.create_expand_dir(data)

    # 第二次创建相同路径应该失败
    data2 = CreateExpandDirRequest(
        name="文件夹2",
        path=str(test_dir),
        description="",
        ai_index=False
    )

    with pytest.raises(ValueError, match="该路径已被添加"):
        add_on_service.create_expand_dir(data2)


def test_update_expand_dir_success(mock_settings, tmp_path):
    """测试更新扩展文件夹成功"""
    # 创建初始数据
    test_dir1 = tmp_path / "folder1"
    test_dir1.mkdir()

    create_data = CreateExpandDirRequest(
        name="原名称",
        path=str(test_dir1),
        description="原描述",
        ai_index=False
    )
    created = add_on_service.create_expand_dir(create_data)

    # 更新数据
    test_dir2 = tmp_path / "folder2"
    test_dir2.mkdir()

    update_data = UpdateExpandDirRequest(
        name="新名称",
        path=str(test_dir2),
        description="新描述",
        ai_index=True
    )

    result = add_on_service.update_expand_dir(created.id, update_data)

    assert result.id == created.id
    assert result.name == "新名称"
    assert result.path == str(test_dir2)
    assert result.description == "新描述"
    assert result.ai_index is True


def test_update_expand_dir_not_found(mock_settings, tmp_path):
    """测试更新不存在的 ID"""
    test_dir = tmp_path / "folder"
    test_dir.mkdir()

    update_data = UpdateExpandDirRequest(
        name="名称",
        path=str(test_dir),
        description="",
        ai_index=False
    )

    with pytest.raises(ValueError, match="扩展文件夹不存在"):
        add_on_service.update_expand_dir("999", update_data)


def test_delete_expand_dir_success(mock_settings, tmp_path):
    """测试删除扩展文件夹成功"""
    # 创建数据
    test_dir = tmp_path / "folder"
    test_dir.mkdir()

    create_data = CreateExpandDirRequest(
        name="测试",
        path=str(test_dir),
        description="",
        ai_index=False
    )
    created = add_on_service.create_expand_dir(create_data)

    # 删除
    add_on_service.delete_expand_dir(created.id)

    # 验证已删除
    result = add_on_service.get_all_expand_dirs()
    assert len(result) == 0


def test_delete_expand_dir_not_found(mock_settings):
    """测试删除不存在的 ID"""
    with pytest.raises(ValueError, match="扩展文件夹不存在"):
        add_on_service.delete_expand_dir("999")


def test_id_generation_sequence(mock_settings, tmp_path):
    """测试 ID 自增序列"""
    # 创建多个文件夹
    for i in range(1, 4):
        test_dir = tmp_path / f"folder{i}"
        test_dir.mkdir()

        data = CreateExpandDirRequest(
            name=f"文件夹{i}",
            path=str(test_dir),
            description="",
            ai_index=False
        )
        result = add_on_service.create_expand_dir(data)
        assert result.id == str(i)

    # 删除中间的
    add_on_service.delete_expand_dir("2")

    # 创建新的，ID 应该是 4
    test_dir4 = tmp_path / "folder4"
    test_dir4.mkdir()

    data4 = CreateExpandDirRequest(
        name="文件夹4",
        path=str(test_dir4),
        description="",
        ai_index=False
    )
    result4 = add_on_service.create_expand_dir(data4)
    assert result4.id == "4"
